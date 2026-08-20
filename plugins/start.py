import asyncio

from pyrogram import filters
from pyrogram.errors import FloodWait
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message
)

from bot import Bot
from config import (
    ADMINS,
    START_PIC,
    CUSTOM_CAPTION,
    DISABLE_CHANNEL_BUTTON,
    FORCE_MSG,
    FORCE_PIC,
    PROTECT_CONTENT,
    START_MSG
)
from helper_func import (
    decode,
    is_subscribed1,
    is_subscribed2
)
)


async def send_force_message(client, message):
    buttons = []

    if getattr(client, "invitelink", None):
        buttons.append([
            InlineKeyboardButton(
                "ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ 1",
                url=client.invitelink
            )
        ])

    if getattr(client, "invitelink2", None):
        buttons.append([
            InlineKeyboardButton(
                "ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ 2",
                url=client.invitelink2
            )
        ])

    if not buttons:
        return False

    start_param = (
        message.command[1]
        if len(message.command) > 1
        else None
    )

    if start_param and getattr(client, "username", None):
        buttons.append([
            InlineKeyboardButton(
                "🔄 Try Again",
                url=f"https://t.me/{client.username}?start={start_param}"
            )
        ])

    user = message.from_user

    caption = FORCE_MSG.format(
        first=user.first_name or "",
        last=user.last_name or "",
        username=f"@{user.username}" if user.username else "",
        mention=user.mention,
        id=user.id
    )

    markup = InlineKeyboardMarkup(buttons)

    try:
        if FORCE_PIC:
            await message.reply_photo(
                photo=FORCE_PIC,
                caption=caption,
                reply_markup=markup
            )
        else:
            await message.reply_text(
                caption,
                reply_markup=markup
            )
    except Exception:
        await message.reply_text(
            caption,
            reply_markup=markup
        )

    return True


@Bot.on_message(
    filters.command("start")
    & filters.private
)
async def start(client, message: Message):

    user = message.from_user

    if not user:
        return

    # Force subscription checks.
    # Admins can bypass force subscription.
    if user.id not in ADMINS:

        is_subscribed_channel1 = await is_subscribed1(
    None,
    client,
    message
)

        if not is_subscribed_channel1:
            await send_force_message(client, message)
            return

        is_subscribed_channel2 = await is_subscribed2(
    None,
    client,
    message
)

        if not is_subscribed_channel2:
            await send_force_message(client, message)
            return

    # Normal /start
    if len(message.command) == 1:

        try:
            await message.reply_photo(
                photo=START_PIC,
                caption=START_MSG.format(
                    first=user.first_name or "",
                    last=user.last_name or "",
                    username=f"@{user.username}" if user.username else "",
                    mention=user.mention,
                    id=user.id
                )
            )
        except Exception:
            await message.reply_text(
                START_MSG.format(
                    first=user.first_name or "",
                    last=user.last_name or "",
                    username=f"@{user.username}" if user.username else "",
                    mention=user.mention,
                    id=user.id
                )
            )

        return

    # Decode file-sharing link
    try:
        data = await decode(message.command[1])
        parts = data.split("-")

        if len(parts) < 2 or parts[0] != "get":
            raise ValueError("Invalid link")

        channel_id = abs(client.db_channel.id)

        # Single file link
        if len(parts) == 2:
            message_ids = [
                int(parts[1]) // channel_id
            ]

        # Batch link
        elif len(parts) == 3:
            first_id = int(parts[1]) // channel_id
            last_id = int(parts[2]) // channel_id

            if first_id <= 0 or last_id <= 0:
                raise ValueError("Invalid message ID")

            if first_id > last_id:
                first_id, last_id = last_id, first_id

            # Safety limit
            if last_id - first_id > 1000:
                await message.reply_text(
                    "❌ This batch link contains too many files."
                )
                return

            message_ids = list(
                range(first_id, last_id + 1)
            )

        else:
            raise ValueError("Invalid link")

    except Exception:
        await message.reply_text(
            "❌ This link is invalid or has expired."
        )
        return

    sent = 0

    # Send files
    for message_id in message_ids:

        try:
            db_message = await client.get_messages(
                client.db_channel.id,
                message_id
            )

            if not db_message or db_message.empty:
                continue

            await db_message.copy(
                chat_id=message.chat.id,
                caption=CUSTOM_CAPTION or None,
                protect_content=PROTECT_CONTENT
            )

            sent += 1

        except FloodWait as e:
            await asyncio.sleep(e.value)

            try:
                db_message = await client.get_messages(
                    client.db_channel.id,
                    message_id
                )

                if db_message and not db_message.empty:
                    await db_message.copy(
                        chat_id=message.chat.id,
                        caption=CUSTOM_CAPTION or None,
                        protect_content=PROTECT_CONTENT
                    )
                    sent += 1

            except Exception:
                continue

        except Exception:
            continue

    if sent == 0:
        await message.reply_text(
            "❌ File not found. The link may be invalid or the source file was deleted."
        )
