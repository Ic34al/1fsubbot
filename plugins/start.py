import asyncio
import logging

from pyrogram import filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from pyrogram.errors import FloodWait

from bot import Bot
from config import (
    ADMINS,
    START_MSG,
    START_PIC,
    FORCE_MSG,
    FORCE_PIC,
    CUSTOM_CAPTION,
    PROTECT_CONTENT,
    FSUB_CHANNELS,
)
from database import database as db
from helper_func import (
    decode,
    all_channels_satisfied,
    get_messages,
)


LOG = logging.getLogger(__name__)

MAX_BATCH = 1000


def parse_decoded_file_code(client, decoded):
    parts = decoded.split("-")

    if len(parts) not in (2, 3):
        return None

    if parts[0] != "get":
        return None

    try:
        divisor = abs(client.db_channel.id)

        first = int(parts[1]) // divisor

        last = (
            int(parts[2]) // divisor
            if len(parts) == 3
            else first
        )

    except (ValueError, ZeroDivisionError):
        return None

    if first <= 0 or last <= 0:
        return None

    if first > last:
        first, last = last, first

    if last - first >= MAX_BATCH:
        return None

    return list(range(first, last + 1))


def force_markup(client, code):
    rows = []
    links = []

    for channel in FSUB_CHANNELS:
        link = (
            client.invite_links.get(channel["id"])
            or channel["link"]
        )

        links.append((
            channel["number"],
            link
        ))

    for i in range(0, len(links), 2):
        pair = links[i:i + 2]

        rows.append([
            InlineKeyboardButton(
                f"↗ Join Channel {number}",
                url=link
            )
            for number, link in pair
        ])


    rows.append([
        InlineKeyboardButton(
            "🔄 Try Again",
            url=f"https://t.me/{client.username}?start={code}"
        )
    ])

    return InlineKeyboardMarkup(rows)



async def show_fsub(client, message, code):
    user = message.from_user

    caption = (
        f"👋 Welcome, {user.first_name or 'Friend'} To Anime Soul!\n\n"
        "You Need To Join All Channel To Use Me!!"
    )

    markup = force_markup(client, code)

    ANIME_SOUL_PHOTO = (
        "AgACAgUAAxkBAAFWbHFq2BilvD7iKj-CUgaX6zOY2OE-YAACKBFrG4X_wVZN7HUi2pMmtQEAAwIAA3kAAz0E"
    )

    try:
        await message.reply_photo(
            photo=ANIME_SOUL_PHOTO,
            caption=caption,
            reply_markup=markup
        )

    except Exception:
        LOG.exception("ANIME SOUL FSUB banner failed")

        await message.reply_text(
            caption,
            reply_markup=markup,
            disable_web_page_preview=True
        )

async def deliver_file(client, user_id: int, code: str):
    LOG.info("DELIVERY START user=%s", user_id)

    try:
        decoded = await decode(code)
    except Exception:
        LOG.exception("FILE CODE DECODE FAILED user=%s", user_id)
        await client.send_message(user_id, "❌ This file link is invalid.")
        return False

    message_ids = parse_decoded_file_code(client, decoded)

    if not message_ids:
        LOG.warning("INVALID FILE CODE user=%s", user_id)
        await client.send_message(
            user_id,
            "❌ This link is invalid or the batch is too large."
        )
        return False

    try:
        messages = await get_messages(client, message_ids)
    except Exception:
        LOG.exception("SOURCE FETCH FAILED user=%s", user_id)
        await client.send_message(
            user_id,
            "❌ Could not retrieve the files. Please try again later."
        )
        return False

    if not messages:
        LOG.error(
            "NO SOURCE MESSAGES user=%s requested=%s",
            user_id, len(message_ids)
        )
        await client.send_message(
            user_id,
            "❌ No source files were found. The source post may have been deleted."
        )
        return False

    semaphore = asyncio.Semaphore(3)

    async def copy_one(msg):
        async with semaphore:
            for attempt in range(2):
                try:
                    await msg.copy(
                        chat_id=user_id,
                        caption=CUSTOM_CAPTION or None,
                        protect_content=PROTECT_CONTENT,
                    )
                    return True

                except FloodWait as exc:
                    LOG.warning(
                        "TELEGRAM FLOOD WAIT seconds=%s user=%s",
                        exc.value, user_id
                    )
                    if attempt == 0:
                        await asyncio.sleep(exc.value)
                    else:
                        return False

                except Exception:
                    LOG.exception(
                        "FILE COPY FAILED message=%s user=%s",
                        msg.id, user_id
                    )
                    return False

            return False

    results = await asyncio.gather(
        *(copy_one(msg) for msg in messages)
    )

    sent = sum(results)

    LOG.info(
        "DELIVERY FINISHED user=%s sent=%s total=%s",
        user_id, sent, len(messages)
    )

    if sent:
        await db.clear_pending_file(user_id)

        if sent < len(message_ids):
            LOG.warning(
                "PARTIAL DELIVERY user=%s sent=%s requested=%s",
                user_id, sent, len(message_ids)
            )

        return True

    await client.send_message(
        user_id,
        "❌ No files could be delivered. Check the Heroku logs for details."
    )
    return False


async def process_file_request(
    client,
    message,
    code,
    user_id=None
):
    user = message.from_user if message else None
    uid = user_id or (user.id if user else None)

    if not uid:
        return

    await db.set_pending_file(uid, code)

    if (
        uid not in ADMINS
        and not await all_channels_satisfied(client, uid)
    ):
        if message and user:
            await show_fsub(client, message, code)
        return

    await deliver_file(client, uid, code)


@Bot.on_message(
    filters.private
    & filters.command("start")
)
async def start(
    client: Bot,
    message: Message
):
    user = message.from_user

    if not user:
        return

    if len(message.command) == 1:
        text = START_MSG.format(
            first=user.first_name or "",
            last=user.last_name or "",
            username=(
                f"@{user.username}"
                if user.username
                else ""
            ),
            mention=user.mention,
            id=user.id,
        )

        try:
            if START_PIC:
                await message.reply_photo(
                    START_PIC,
                    caption=text
                )
            else:
                await message.reply_text(text)

        except Exception:
            await message.reply_text(text)

        return

    await process_file_request(
        client,
        message,
        message.command[1]
    )



@Bot.on_callback_query(
    filters.regex(r"^check:")
)
async def check_again(
    client: Bot,
    query: CallbackQuery
):
    user = query.from_user
    data = query.data or ""
    code = data.split(":", 1)[1] if ":" in data else ""

    if not code:
        await query.answer(
            "Invalid file link.",
            show_alert=True
        )
        return

    try:
        await db.set_pending_file(user.id, code)

        if (
            user.id not in ADMINS
            and not await all_channels_satisfied(
                client, user.id
            )
        ):
            await query.answer(
                "Please join all required channels first.",
                show_alert=True
            )
            await query.message.edit_reply_markup(
                force_markup(client, code)
            )
            return


        bot_username = getattr(client, "username", None)
        if not bot_username:
            me = await client.get_me()
            bot_username = me.username

        await query.answer("Subscription verified!")

        await client.send_message(
            user.id,
            "✅ Subscription verified!\n\n"
            "Tap the link below and press Start to get your file:\n"
            f"https://t.me/{bot_username}?start={code}"
        )

    except Exception:
        LOG.exception(
            "TRY AGAIN FAILED user=%s",
            user.id
        )
        await query.answer(
            "Verification failed. Please try again.",
            show_alert=True
        )


@Bot.on_message(
    filters.private
    & filters.user(list(ADMINS))
    & filters.command("users")
)
async def users(
    client: Bot,
    message: Message
):
    await message.reply_text(
        f"👥 Total users: {await db.count_users()}"
    )


@Bot.on_message(
    filters.private
    & filters.user(list(ADMINS))
    & filters.command("broadcast")
)
async def broadcast(
    client: Bot,
    message: Message
):
    if not message.reply_to_message:
        return await message.reply_text(
            "Reply to the message you want to "
            "broadcast with /broadcast."
        )

    ids = await db.get_all_user_ids()

    sent = 0
    failed = 0

    status = await message.reply_text(
        "Broadcast started…"
    )

    for uid in ids:
        try:
            await message.reply_to_message.copy(uid)
            sent += 1

        except FloodWait as exc:
            await asyncio.sleep(exc.value)

            try:
                await message.reply_to_message.copy(uid)
                sent += 1
            except Exception:
                failed += 1

        except Exception:
            failed += 1

    await status.edit_text(
        f"✅ Broadcast finished.\n"
        f"Sent: {sent}\n"
        f"Failed: {failed}"
    )
