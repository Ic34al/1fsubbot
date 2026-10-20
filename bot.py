import asyncio
import base64
import logging
import time

from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import Client, filters, idle
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import pyrogram.utils as pyrogram_utils


def get_peer_type_fixed(peer_id: int) -> str:
    peer_id = int(peer_id)

    if peer_id > 0:
        return "user"

    if str(peer_id).startswith("-100"):
        return "channel"

    if peer_id < 0:
        return "chat"

    raise ValueError(f"Peer id invalid: {peer_id}")


pyrogram_utils.get_peer_type = get_peer_type_fixed

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

# ---------------------------------------------------------
# LOGGING
# ---------------------------------------------------------

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ---------------------------------------------------------
# BOT AND DATABASE
# ---------------------------------------------------------

app = Client(
    "file_share_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=TG_BOT_WORKERS,
)

mongo = AsyncIOMotorClient(
    MONGO_URI,
    serverSelectionTimeoutMS=10000,
)

database = mongo[DATABASE_NAME]

users = database["users"]
requests = database["join_requests"]
pending_files = database["pending_files"]

JOIN_LINKS = []
user_locks = {}


# ---------------------------------------------------------
# ENCODE / DECODE
# Compatible with the original get-... file links.
# ---------------------------------------------------------

async def encode_link(value):
    return base64.urlsafe_b64encode(
        value.encode("utf-8")
    ).decode("utf-8").rstrip("=")


async def decode_link(value):
    value = value.rstrip("=")
    padding = "=" * (-len(value) % 4)

    return base64.urlsafe_b64decode(
        (value + padding).encode("utf-8")
    ).decode("utf-8")


# ---------------------------------------------------------
# USER DATABASE
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
    
# ---------------------------------------------------------
# FORCE SUBSCRIBE HELPERS
# A join request counts until a member-leave event clears it.
# ---------------------------------------------------------


async def get_missing_channels(user_id):
    missing = []

    for index, (channel_id, _) in enumerate(FSUB_CHANNELS):
        channel_id = int(channel_id)
        user_id = int(user_id)

        record = await requests.find_one({
            "user_id": user_id,
            "channel_id": channel_id,
        })

        if not record:
            missing.append(index)
            continue

        try:
            member = await app.get_chat_member(
                channel_id, user_id
            )
            status = getattr(
                member.status, "value", member.status
            )
            status = str(status).lower().split(".")[-1]

            if status in ("member", "administrator", "owner", "creator"):
                await requests.update_one(
                    {
                        "user_id": user_id,
                        "channel_id": channel_id,
                    },
                    {"$set": {"was_member": True}},
                )
                continue

            if status in ("kicked", "banned"):
                await requests.delete_one({
                    "user_id": user_id,
                    "channel_id": channel_id,
                })
                missing.append(index)
                continue

            # A previously confirmed member who is now left
            # must request to join again.
            if record.get("was_member", False):
                await requests.delete_one({
                    "user_id": user_id,
                    "channel_id": channel_id,
                })
                missing.append(index)
                continue

            # A user who has only requested to join can count
            # while their request is pending.
            if status == "left":
                continue

            missing.append(index)

        except Exception:
            log.exception(
                "Membership verification failed: user=%s channel=%s",
                user_id, channel_id,
            )

            # Fail closed for previously confirmed members.
            # Pending requests remain valid if verification fails.
            if record.get("was_member", False):
                missing.append(index)

    return missing
    
# ---------------------------------------------------------
# FILE DELIVERY
# Supports original single-file and batch links.
# ---------------------------------------------------------

async def send_file_code(client, user_id, file_code):
    try:
        decoded = await decode_link(file_code)
        parts = decoded.split("-")

        if len(parts) < 2 or parts[0] != "get":
            raise ValueError("Invalid file link")

        channel_abs_id = abs(client.db_channel.id)

        if not channel_abs_id:
            raise ValueError("Invalid database channel ID")

        if len(parts) == 2:
            first_id = int(parts[1]) // channel_abs_id
            last_id = first_id

        elif len(parts) == 3:
            first_id = int(parts[1]) // channel_abs_id
            last_id = int(parts[2]) // channel_abs_id

        else:
            raise ValueError("Invalid link format")

        if first_id <= 0 or last_id <= 0:
            raise ValueError("Invalid message IDs")

        if first_id > last_id:
            first_id, last_id = last_id, first_id

        if last_id - first_id > 1000:
            await client.send_message(
                user_id,
                "❌ This batch contains too many files.",
            )
            return False

    except Exception:
        log.warning("Invalid file link: %s", file_code)
        return False

    sent = 0

    for message_id in range(first_id, last_id + 1):
        try:
            source = await client.get_messages(
                chat_id=client.db_channel.id,
                message_ids=message_id,
            )

            if not source or source.empty:
                continue

            kwargs = {
                "chat_id": user_id,
                "protect_content": PROTECT_CONTENT,
            }

            if CUSTOM_CAPTION:
                kwargs["caption"] = CUSTOM_CAPTION

            await source.copy(**kwargs)
            sent += 1

        except FloodWait as exc:
            await asyncio.sleep(exc.value)

            try:
                source = await client.get_messages(
                    chat_id=client.db_channel.id,
                    message_ids=message_id,
                )

                if source and not source.empty:
                    kwargs = {
                        "chat_id": user_id,
                        "protect_content": PROTECT_CONTENT,
                    }

                    if CUSTOM_CAPTION:
                        kwargs["caption"] = CUSTOM_CAPTION

                    await source.copy(**kwargs)
                    sent += 1

            except Exception:
                log.exception("File retry failed: %s", message_id)

        except Exception:
            log.exception("File delivery failed: %s", message_id)

    if sent == 0:
        await client.send_message(
            user_id,
            "❌ File not found. The source message may have been deleted.",
        )
        return False

    return True


# ---------------------------------------------------------
# SEND PENDING FILE AFTER ALL FOUR JOIN REQUESTS
# ---------------------------------------------------------

async def deliver_pending_file(client, user_id):
    lock = user_locks.setdefault(
        int(user_id),
        asyncio.Lock(),
    )

    async with lock:
        missing = await get_missing_channels(user_id)

        if missing:
            return False

        pending = await pending_files.find_one(
            {"_id": int(user_id)}
        )

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
            await pending_files.delete_one(
                {"_id": int(user_id)}
            )

            try:
                await client.send_message(
                    user_id,
                    "✅ Your requested file has been sent.",
                )
            except Exception:
                pass

        return success
        
@app.on_callback_query(filters.regex("^check_requests$"))
async def check_requests_callback(client, query):
    user_id = query.from_user.id

    try:
        missing = await get_missing_channels(user_id)

        if missing:
            await query.answer(
                "Please request to join all four channels first.",
                show_alert=True,
            )
            await query.message.edit_reply_markup(
                reply_markup=make_join_keyboard(missing)
            )
            return

        success = await deliver_pending_file(client, user_id)

        if success:
            await query.answer("Verified! Your file is being sent.")
        else:
            await query.answer(
                "No pending file found. Open your file link again.",
                show_alert=True,
            )

    except Exception:
        log.exception("Try Again verification failed")
        await query.answer(
            "Verification failed. Please try again.",
            show_alert=True,
        )
@app.on_message(filters.private & filters.photo)
async def get_photo_id(client, message):
    if message.from_user and message.from_user.id in ADMINS:
        await message.reply_text(
            f"Photo file_id:\n\n`{message.photo.file_id}`"
        )
# ---------------------------------------------------------
# START COMMAND
# ---------------------------------------------------------

@app.on_message(
    filters.private & filters.command("start")
)
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

    if start_param:
        if user.id not in ADMINS:
            # Save the requested link until all requests arrive.
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

            # Requests are complete. Deliver and clear pending data.
            await deliver_pending_file(client, user.id)
            return

        # Admins bypass force subscription.
        success = await send_file_code(
            client,
            user.id,
            start_param,
        )

        if not success:
            await message.reply_text(
                "❌ Unable to send this file. Check the link and source."
            )

        return

    # Normal /start
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
# JOIN REQUEST HANDLER
# ---------------------------------------------------------

async def record_join_request(client, join_request, index):
    user = join_request.from_user

    if not user:
        return

    channel_id = int(FSUB_CHANNELS[index][0])

    await requests.update_one(
        {
            "user_id": int(user.id),
            "channel_id": channel_id,
        },
        {
            "$set": {
                "user_id": int(user.id),
                "channel_id": channel_id,
                "first_name": user.first_name or "",
                "username": user.username or "",
                "request_date": str(join_request.date),
                "was_member": False,
            }
        },
        upsert=True,
    )

    log.info(
        "Recorded join request from %s for channel %s",
        user.id,
        channel_id,
    )

    await deliver_pending_file(client, user.id)

# ---------------------------------------------------------
# CLEAR SAVED REQUEST WHEN A MEMBER LEAVES
# ---------------------------------------------------------

@app.on_chat_member_updated()
async def membership_updates(client, update):
    try:
        chat = getattr(update, "chat", None)
        member = getattr(update, "new_chat_member", None)
        user = getattr(member, "user", None) if member else None

        if not chat or not member or not user:
            return

        channel_id = int(chat.id)
        configured_ids = {
            int(cid) for cid, _ in FSUB_CHANNELS
        }

        status = getattr(
            member.status, "value", member.status
        )
        status = str(status).lower().split(".")[-1]

        log.info(
            "MEMBERSHIP UPDATE: channel=%s user=%s status=%s",
            channel_id, user.id, status,
        )

        if channel_id not in configured_ids:
            return

        await clear_request_if_left(
            user.id, channel_id, member
        )

        if status in (
            "member", "administrator", "owner", "creator"
        ):
            await deliver_pending_file(client, user.id)

    except Exception:
        log.exception("Membership update handler failed")

# AUTO-GENERATE LINKS FOR ADMIN FILES

@app.on_message(filters.private & filters.media)
async def auto_generate_link(client, message):
    user = message.from_user

    if not user or user.id not in ADMINS:
        return

    try:
        stored = await client.copy_message(
            chat_id=client.db_channel.id,
            from_chat_id=message.chat.id,
            message_id=message.id,
        )

        if not stored:
            await message.reply_text("❌ Could not save the file.")
            return

        encoded = await encode_link(
            f"get-{stored.id * abs(client.db_channel.id)}"
        )

        link = f"https://t.me/{client.username}?start={encoded}"

        await message.reply_text(
            f"✅ Here is your link!\n\n{link}",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "📲 Share URL",
                        url="https://t.me/share/url?url=" + link,
                    )
                ]
            ]),
        )

    except Exception:
        log.exception("Automatic link generation failed")
        await message.reply_text(
            "❌ Link generation failed. Check the Heroku logs."
        )

# ---------------------------------------------------------
# ADMIN: GENERATE BATCH LINK
# Usage: /batch FIRST_MESSAGE_ID LAST_MESSAGE_ID
# ---------------------------------------------------------

@app.on_message(
    filters.private
    & filters.user(ADMINS)
    & filters.command("batch")
)
async def batch_handler(client, message):
    if len(message.command) != 3:
        await message.reply_text(
            "Usage:\n/batch FIRST_MESSAGE_ID LAST_MESSAGE_ID"
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

        channel_abs_id = abs(client.db_channel.id)

        encoded = await encode_link(
            f"get-{first_id * channel_abs_id}"
            f"-{last_id * channel_abs_id}"
        )

        link = f"https://t.me/{client.username}?start={encoded}"

        await message.reply_text(
            f"✅ Batch link created:\n\n{link}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📂 Open Batch", url=link)]
            ]),
        )

    except Exception as exc:
        await message.reply_text(
            f"❌ Could not create batch link: {exc}"
        )


# ---------------------------------------------------------
# ADMIN: BROADCAST TEXT OR COPIED MEDIA
#
# /broadcast Hello everyone!
# Or reply to media with /broadcast
# ---------------------------------------------------------

async def send_broadcast_message(client, user_id, message, text):
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
            "Text broadcast:\n"
            "/broadcast Hello everyone!\n\n"
            "Media broadcast:\n"
            "Reply to a message or media and send /broadcast"
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

        success = await send_broadcast_message(
            client,
            user_id,
            message,
            text,
        )

        if success:
            sent += 1
        else:
            failed += 1

        await asyncio.sleep(0.05)

    await status.edit_text(
        "✅ Broadcast completed\n\n"
        f"👥 Total users: {total}\n"
        f"📨 Sent: {sent}\n"
        f"❌ Failed: {failed}"
    )


# ---------------------------------------------------------
# ADMIN: STATS
# ---------------------------------------------------------

@app.on_message(
    filters.private
    & filters.command("stats")
)
async def stats_handler(client, message):
    if message.from_user.id not in ADMINS:
        return

    user_count = await users.count_documents({})
    request_count = await requests.count_documents({})
    pending_count = await pending_files.count_documents({})

    await message.reply_text(
        "📊 Bot Statistics\n\n"
        f"👥 Registered users: {user_count}\n"
        f"📝 Recorded join requests: {request_count}\n"
        f"📁 Pending file requests: {pending_count}"
    )


# ---------------------------------------------------------
# ADMIN AND USER HELP
# ---------------------------------------------------------

@app.on_message(
    filters.private & filters.command("help")
)
async def help_handler(client, message):
    await message.reply_text(
        "📚 Bot Commands\n\n"
        "/start - Start bot or open a file link\n"
        "/help - Show help\n"
        "/id - Show your Telegram ID\n\n"
        "Admin commands:\n"
        "/genlink MESSAGE_ID - Create a file link\n"
        "/batch FIRST_ID LAST_ID - Create a batch link\n"
        "/broadcast TEXT - Broadcast a text message\n"
        "Reply to media with /broadcast to copy it\n"
        "/stats - Show bot statistics"
    )


@app.on_message(
    filters.private & filters.command("id")
)
async def id_handler(client, message):
    if message.from_user:
        await message.reply_text(
            f"Your Telegram ID: `{message.from_user.id}`"
        )


# ---------------------------------------------------------
# INITIALIZE BOT
# ---------------------------------------------------------

async def initialize():
    # Confirm database connectivity.
    await mongo.admin.command("ping")

    # Load the channel containing the source files.
    app.db_channel = await app.get_chat(CHANNEL_ID)

    me = await app.get_me()
    app.username = me.username

    JOIN_LINKS.clear()

    # Create one join-request invite link per channel.
    for index, (channel_id, fallback_link) in enumerate(
        FSUB_CHANNELS,
        start=1,
    ):
        try:
            invite = await app.create_chat_invite_link(
                chat_id=channel_id,
                name=f"File Bot FSUB {index}",
                creates_join_request=True,
            )

            JOIN_LINKS.append(invite.invite_link)

            log.info(
                "Created join-request link for channel %s",
                channel_id,
            )

        except Exception:
            log.exception(
                "Could not create invite link for channel %s",
                channel_id,
            )

            if fallback_link:
                JOIN_LINKS.append(fallback_link)
                log.warning(
                    "Using fallback invite link for channel %s",
                    channel_id,
                )
            else:
                raise RuntimeError(
                    f"Cannot create join-request link for channel "
                    f"{channel_id}. Add the bot as a channel admin "
                    f"with invite-user permission."
                )

    log.info("Bot initialization complete.")


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------


async def main():
    try:
        async with app:
            await initialize()
            log.info("Bot is running.")
            await idle()
    finally:
        mongo.close()


if __name__ == "__main__":
    app.run(main())
