import asyncio
import base64
import logging
import time

from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import Client, filters, idle
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import FloodWait
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from config import (
    API_ID,
    API_HASH,
    BOT_TOKEN,
    MONGO_URI,
    DATABASE_NAME,
    OWNER_ID,
    ADMINS,
    CHANNEL_ID,
    FSUB_CHANNELS,
    START_MSG,
    FORCE_MSG,
    CUSTOM_CAPTION,
    PROTECT_CONTENT,
    START_PIC,
    FORCE_PIC,
    TG_BOT_WORKERS,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = Client(
    "file_share_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=TG_BOT_WORKERS,
)

mongo = AsyncIOMotorClient(MONGO_URI)
database = mongo[DATABASE_NAME]

users = database["users"]
requests = database["join_requests"]
pending_files = database["pending_files"]

JOIN_LINKS = []
user_locks = {}


# ---------------------------------------------------------
# GENERAL HELPERS
# ---------------------------------------------------------

async def save_user(user):
    if not user:
        return

    await users.update_one(
        {"_id": int(user.id)},
        {
            "$set": {
                "first_name": user.first_name or "",
                "username": user.username or "",
                "last_seen": int(time.time()),
            }
        },
        upsert=True,
    )


async def decode_link(value):
    value = value.rstrip("=")
    padding = "=" * (-len(value) % 4)

    return base64.urlsafe_b64decode(
        (value + padding).encode()
    ).decode()


async def encode_link(value):
    return base64.urlsafe_b64encode(
        value.encode()
    ).decode().rstrip("=")


async def get_missing_channels(user_id):
    missing = []

    for index, (channel_id, _) in enumerate(FSUB_CHANNELS):
        record = await requests.find_one({
            "user_id": int(user_id),
            "channel_id": int(channel_id),
        })

        if not record:
            missing.append(index)

    return missing


def make_join_keyboard(missing, start_param=None):
    rows = []

    for index in missing:
        rows.append([
            InlineKeyboardButton(
                f"📢 Request to Join Channel {index + 1}",
                url=JOIN_LINKS[index],
            )
        ])

    if start_param:
        rows.append([
            InlineKeyboardButton(
                "🔄 I Sent All Requests — Retry",
                url=f"https://t.me/{app.username}?start={start_param}",
            )
        ])

    return InlineKeyboardMarkup(rows)


async def show_force_sub(message, start_param=None):
    user = message.from_user
    missing = await get_missing_channels(user.id)

    if not missing:
        return False

    text = (
        FORCE_MSG.format(
            first=user.first_name or "",
            last=user.last_name or "",
            username=f"@{user.username}" if user.username else "",
            mention=user.mention,
            id=user.id,
        )
    )

    keyboard = make_join_keyboard(missing, start_param)

    try:
        if FORCE_PIC:
            await message.reply_photo(
                photo=FORCE_PIC,
                caption=text,
                reply_markup=keyboard,
            )
        else:
            await message.reply_text(
                text,
                reply_markup=keyboard,
            )
    except Exception:
        log.exception("Could not display force-sub message")
        await message.reply_text(
            text,
            reply_markup=keyboard,
        )

    return True


# ---------------------------------------------------------
# FILE LINK DECODING AND DELIVERY
# Preserves the original get-... link format.
# ---------------------------------------------------------

async def send_file_code(client, user_id, file_code):
    try:
        decoded = await decode_link(file_code)
        parts = decoded.split("-")

        if len(parts) < 2 or parts[0] != "get":
            return False

        channel_abs_id = abs(client.db_channel.id)

        if channel_abs_id == 0:
            return False

        if len(parts) == 2:
            first_id = int(parts[1]) // channel_abs_id
            last_id = first_id

        elif len(parts) == 3:
            first_id = int(parts[1]) // channel_abs_id
            last_id = int(parts[2]) // channel_abs_id

        else:
            return False

        if first_id <= 0 or last_id <= 0:
            return False

        if first_id > last_id:
            first_id, last_id = last_id, first_id

        if last_id - first_id > 1000:
            await client.send_message(
                user_id,
                "❌ This batch link contains too many files.",
            )
            return False

    except Exception:
        log.warning("Invalid file link: %s", file_code)
        return False

    sent = 0

    for message_id in range(first_id, last_id + 1):
        try:
            source_message = await client.get_messages(
                chat_id=client.db_channel.id,
                message_ids=message_id,
            )

            if not source_message or source_message.empty:
                continue

            kwargs = {
                "chat_id": user_id,
                "protect_content": PROTECT_CONTENT,
            }

            if CUSTOM_CAPTION:
                kwargs["caption"] = CUSTOM_CAPTION

            await source_message.copy(**kwargs)
            sent += 1

        except FloodWait as exc:
            await asyncio.sleep(exc.value)

            try:
                source_message = await client.get_messages(
                    chat_id=client.db_channel.id,
                    message_ids=message_id,
                )

                if source_message and not source_message.empty:
                    kwargs = {
                        "chat_id": user_id,
                        "protect_content": PROTECT_CONTENT,
                    }

                    if CUSTOM_CAPTION:
                        kwargs["caption"] = CUSTOM_CAPTION

                    await source_message.copy(**kwargs)
                    sent += 1

            except Exception:
                log.exception(
                    "Retry failed for source message %s",
                    message_id,
                )

        except Exception:
            log.exception(
                "Could not send source message %s",
                message_id,
            )

    if sent:
        return True

    await client.send_message(
        user_id,
        "❌ File not found. The source message may have been deleted.",
    )
    return False


async def deliver_pending_file(client, user_id):
    # Prevent two near-simultaneous join requests from sending
    # the same pending file twice.
    lock = user_locks.setdefault(int(user_id), asyncio.Lock())

    async with lock:
        missing = await get_missing_channels(user_id)

        if missing:
            return False

        pending = await pending_files.find_one({
            "_id": int(user_id),
        })

        if not pending:
            return False

        file_code = pending.get("file_code")

        if not file_code:
            return False

        success = await send_file_code(
            client,
            user_id,
            file_code,
        )

        if success:
            await pending_files.delete_one({
                "_id": int(user_id),
            })

            try:
                await client.send_message(
                    user_id,
                    "✅ Your requested file has been sent.",
                )
            except Exception:
                pass

        return success


# ---------------------------------------------------------
# /START
# ---------------------------------------------------------

@app.on_message(filters.private & filters.command("start"))
async def start_handler(client, message):
    user = message.from_user

    if not user:
        return

    await save_user(user)

    start_param = (
        message.command[1]
        if len(message.command) > 1
        else None
    )

    # A file link was opened.
    if start_param:
        if user.id not in ADMINS:
            # Save the file request before displaying the buttons.
            await pending_files.update_one(
                {"_id": int(user.id)},
                {
                    "$set": {
                        "file_code": start_param,
                        "created_at": int(time.time()),
                    }
                },
                upsert=True,
            )

            missing = await get_missing_channels(user.id)

            if missing:
                await show_force_sub(message, start_param)
                return

        success = await send_file_code(
            client,
            user.id,
            start_param,
        )

        if not success:
            await message.reply_text(
                "❌ Unable to send the file. "
                "Check that the link and source file are valid."
            )

        return

    # Normal /start.
    text = START_MSG.format(
        first=user.first_name or "",
        last=user.last_name or "",
        username=f"@{user.username}" if user.username else "",
        mention=user.mention,
        id=user.id,
    )

    try:
        if START_PIC:
            await message.reply_photo(
                photo=START_PIC,
                caption=text,
            )
        else:
            await message.reply_text(text)
    except Exception:
        await message.reply_text(text)


# ---------------------------------------------------------
# JOIN REQUEST HANDLERS
# A request counts immediately. The bot does not approve it.
# ---------------------------------------------------------

async def record_join_request(client, join_request, channel_index):
    user = join_request.from_user

    if not user:
        return

    channel_id = FSUB_CHANNELS[channel_index][0]

    await requests.update_one(
        {
            "user_id": int(user.id),
            "channel_id": int(channel_id),
        },
        {
            "$set": {
                "user_id": int(user.id),
                "channel_id": int(channel_id),
                "first_name": user.first_name or "",
                "username": user.username or "",
                "request_date": str(join_request.date),
            }
        },
        upsert=True,
    )

    log.info(
        "Join request recorded: user=%s channel=%s",
        user.id,
        channel_id,
    )

    await deliver_pending_file(client, user.id)


@app.on_chat_join_request(filters.chat(FSUB_CHANNELS[0][0]))
async def channel_1_request(client, join_request):
    await record_join_request(client, join_request, 0)


@app.on_chat_join_request(filters.chat(FSUB_CHANNELS[1][0]))
async def channel_2_request(client, join_request):
    await record_join_request(client, join_request, 1)


@app.on_chat_join_request(filters.chat(FSUB_CHANNELS[2][0]))
async def channel_3_request(client, join_request):
    await record_join_request(client, join_request, 2)


@app.on_chat_join_request(filters.chat(FSUB_CHANNELS[3][0]))
async def channel_4_request(client, join_request):
    await record_join_request(client, join_request, 3)


# ---------------------------------------------------------
# ADMIN LINK GENERATION
#
# /genlink MESSAGE_ID
# /batch FIRST_MESSAGE_ID LAST_MESSAGE_ID
#
# Message IDs must belong to your database channel.
# ---------------------------------------------------------

@app.on_message(
    filters.private
    & filters.user(ADMINS)
    & filters.command("genlink")
)
async def genlink_handler(client, message):
    if len(message.command) != 2:
        await message.reply_text(
            "Usage:\n"
            "/genlink MESSAGE_ID\n\n"
            "Use the message ID from your database channel."
        )
        return

    try:
        message_id = int(message.command[1])

        source = await client.get_messages(
            client.db_channel.id,
            message_id,
        )

        if not source or source.empty:
            raise ValueError("Source message not found")

        encoded = await encode_link(
            f"get-{message_id * abs(client.db_channel.id)}"
        )

        link = f"https://t.me/{client.username}?start={encoded}"

        await message.reply_text(
            f"✅ **File link created**\n\n`{link}`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📂 Open File", url=link)]
            ]),
        )

    except Exception as exc:
        log.exception("Link generation failed")
        await message.reply_text(
            f"❌ Could not create link: {exc}"
        )


@app.on_message(
    filters.private
    & filters.user(ADMINS)
    & filters.command("batch")
)
async def batch_handler(client, message):
    if len(message.command) != 3:
        await message.reply_text(
            "Usage:\n"
            "/batch FIRST_MESSAGE_ID LAST_MESSAGE_ID\n\n"
            "Both IDs must belong to your database channel."
        )
        return

    try:
        first_id = int(message.command[1])
        last_id = int(message.command[2])

        if first_id <= 0 or last_id <= 0:
            raise ValueError("IDs must be positive.")

        if first_id > last_id:
            first_id, last_id = last_id, first_id

        if last_id - first_id > 1000:
            raise ValueError("Batch limit is 1001 messages.")

        encoded = await encode_link(
            f"get-{first_id * abs(client.db_channel.id)}"
            f"-{last_id * abs(client.db_channel.id)}"
        )

        link = f"https://t.me/{client.username}?start={encoded}"

        await message.reply_text(
            f"✅ **Batch link created**\n\n`{link}`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📂 Open Batch", url=link)]
            ]),
        )

    except Exception as exc:
        await message.reply_text(
            f"❌ Could not create batch link: {exc}"
        )


# ---------------------------------------------------------
# ADMIN BROADCAST
#
# /broadcast Your message
# Or reply to a message/media and send /broadcast
# ---------------------------------------------------------

async def safe_broadcast_send(client, user_id, message, text):
    while True:
        try:
            if message.reply_to_message:
                await client.copy_message(
                    chat_id=user_id,
                    from_chat_id=message.chat.id,
                    message_id=message.reply_to_message.id,
                )
            else:
                await client.send_message(
                    chat_id=user_id,
                    text=text,
                )
            return True

        except FloodWait as exc:
            await asyncio.sleep(exc.value)

        except Exception as exc:
            log.warning(
                "Broadcast failed for %s: %s",
                user_id,
                exc,
            )
            return False


@app.on_message(
    filters.private
    & filters.user(ADMINS)
    & filters.command("broadcast")
)
async def broadcast_handler(client, message):
    parts = message.text.split(maxsplit=1)
    text = parts[1] if len(parts) > 1 else ""

    if not message.reply_to_message and not text:
        await message.reply_text(
            "Send text:\n"
            "/broadcast Hello everyone!\n\n"
            "Or reply to a text/photo/video/document and send:\n"
            "/broadcast"
        )
        return

    status = await message.reply_text(
        "📢 Broadcast started..."
    )

    total = await users.count_documents({})
    sent = 0
    failed = 0

    async for user_doc in users.find({}, {"_id": 1}):
        user_id = user_doc["_id"]

        success = await safe_broadcast_send(
            client,
            user_id,
            message,
            text,
        )

        if success:
            sent += 1
        else:
            failed += 1

        # Keep sending at a conservative rate.
        await asyncio.sleep(0.05)

    await status.edit_text(
        "✅ **Broadcast completed**\n\n"
        f"👥 Total users: {total}\n"
        f"📨 Sent: {sent}\n"
        f"❌ Failed: {failed}"
    )


# ---------------------------------------------------------
# ADMIN STATS AND HELP
# ---------------------------------------------------------

@app.on_message(filters.private & filters.command("stats"))
async def stats_handler(client, message):
    if message.from_user.id not in ADMINS:
        return

    user_count = await users.count_documents({})
    link_requests = await requests.count_documents({})
    pending_count = await pending_files.count_documents({})

    await message.reply_text(
        "📊 **Bot Statistics**\n\n"
        f"👥 Registered users: {user_count}\n"
        f"📝 Recorded channel requests: {link_requests}\n"
        f"📁 Pending file requests: {pending_count}"
    )


@app.on_message(filters.private & filters.command("help"))
async def help_handler(client, message):
    await message.reply_text(
        "📚 **Bot Commands**\n\n"
        "/start — Start the bot or open a file link\n"
        "/help — Show commands\n"
        "/id — Show your Telegram ID\n\n"
        "**Admin commands**\n"
        "/genlink MESSAGE_ID — Create a single-file link\n"
        "/batch FIRST_ID LAST_ID — Create a batch link\n"
        "/broadcast TEXT — Broadcast a text message\n"
        "Reply to media with /broadcast to copy it to users\n"
        "/stats — Show bot statistics"
    )


@app.on_message(filters.private & filters.command("id"))
async def id_handler(client, message):
    await message.reply_text(
        f"Your Telegram ID: `{message.from_user.id}`"
    )


# ---------------------------------------------------------
# STARTUP
# ---------------------------------------------------------

async def initialize():
    await mongo.admin.command("ping")

    app.db_channel = await app.get_chat(CHANNEL_ID)

    me = await app.get_me()
    app.username = me.username

    JOIN_LINKS.clear()

    for index, (channel_id, fallback_link) in enumerate(FSUB_CHANNELS, start=1):
        try:
            # Generate a link that triggers ChatJoinRequest.
            invite = await app.create_chat_invite_link(
                chat_id=channel_id,
                name=f"File Bot FSUB {index}",
                creates_join_request=True,
            )

            JOIN_LINKS.append(invite.invite_link)

            log.info(
                "Join-request link created for channel %s",
                channel_id,
            )

        except Exception:
            log.exception(
                "Could not create a join-request link for channel %s",
                channel_id,
            )

            if fallback_link:
                JOIN_LINKS.append(fallback_link)
                log.warning(
                    "Using configured fallback link for channel %s. "
                    "Ensure it is a join-request link.",
                    channel_id,
                )
            else:
                raise RuntimeError(
                    f"Cannot create a join-request link for channel "
                    f"{channel_id}. Make the bot an admin with "
                    f"invite-user permission, then restart."
                )

    log.info("Bot initialized successfully.")


async def main():
    await app.start()

    try:
        await initialize()
        await idle()
    finally:
        await app.stop()
        mongo.close()


if __name__ == "__main__":
    asyncio.run(main())
