from pyrogram import filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from bot import Bot
from config import ADMINS
from helper_func import encode, get_message_id


async def ask_for_db_message(
    client,
    message,
    prompt
):
    while True:
        answer = await client.ask(
            chat_id=message.from_user.id,
            text=prompt,
            filters=(
                filters.forwarded
                | (filters.text & ~filters.forwarded)
            ),
            timeout=120,
        )

        msg_id = await get_message_id(
            client,
            answer
        )

        if msg_id:
            return msg_id

        await answer.reply_text(
            "❌ That message or link is not from "
            "the configured private database channel. "
            "Try again."
        )


def link_markup(link):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔁 Share URL",
                url=(
                    "https://telegram.me/share/url"
                    f"?url={link}"
                ),
            )
        ]
    ])


@Bot.on_message(
    filters.private
    & filters.user(list(ADMINS))
    & filters.command("genlink")
)
async def genlink(
    client: Bot,
    message: Message
):
    try:
        msg_id = await ask_for_db_message(
            client,
            message,
            "Forward a post from your private database "
            "channel, or send its Telegram post link."
        )

        code = await encode(
            f"get-{msg_id * abs(client.db_channel.id)}"
        )

        link = (
            f"https://t.me/{client.username}"
            f"?start={code}"
        )

        await message.reply_text(
            f"<b>File link created:</b>\n{link}",
            reply_markup=link_markup(link),
            disable_web_page_preview=True,
        )

    except TimeoutError:
        await message.reply_text(
            "⌛ Timed out. Send /genlink to try again."
        )

    except Exception as exc:
        await message.reply_text(
            f"❌ Could not create link: {exc}"
        )


@Bot.on_message(
    filters.private
    & filters.user(list(ADMINS))
    & filters.command("batch")
)
async def batch(
    client: Bot,
    message: Message
):
    try:
        first = await ask_for_db_message(
            client,
            message,
            "Forward the FIRST post from your private "
            "database channel, or send its post link."
        )

        last = await ask_for_db_message(
            client,
            message,
            "Now forward the LAST post from your private "
            "database channel, or send its post link."
        )

        code = await encode(
            f"get-{first * abs(client.db_channel.id)}"
            f"-{last * abs(client.db_channel.id)}"
        )

        link = (
            f"https://t.me/{client.username}"
            f"?start={code}"
        )

        await message.reply_text(
            f"<b>Batch link created:</b>\n{link}",
            reply_markup=link_markup(link),
            disable_web_page_preview=True,
        )

    except TimeoutError:
        await message.reply_text(
            "⌛ Timed out. Send /batch to try again."
        )

    except Exception as exc:
        await message.reply_text(
            f"❌ Could not create batch link: {exc}"
        )
