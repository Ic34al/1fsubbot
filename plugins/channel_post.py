import asyncio

from pyrogram import filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from pyrogram.errors import FloodWait

from bot import Bot
from config import (
    ADMINS,
    CHANNEL_ID,
    DISABLE_CHANNEL_BUTTON,
)
from helper_func import encode


def share_markup(link):
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


async def make_link(client, message_id):
    code = await encode(
        f"get-{message_id * abs(client.db_channel.id)}"
    )

    return (
        f"https://t.me/{client.username}"
        f"?start={code}"
    )


@Bot.on_message(
    filters.private
    & filters.user(list(ADMINS))
    & ~filters.command([
        "start",
        "genlink",
        "batch",
        "users",
        "broadcast",
        "stats",
    ])
)
async def save_admin_post(
    client: Bot,
    message: Message
):
    status = await message.reply_text(
        "Saving to the private file database…"
    )

    try:
        saved = await message.copy(
            client.db_channel.id,
            disable_notification=True,
        )

        link = await make_link(
            client,
            saved.id
        )

        await status.edit_text(
            f"<b>File link created:</b>\n{link}",
            reply_markup=share_markup(link),
            disable_web_page_preview=True,
        )

        if not DISABLE_CHANNEL_BUTTON:
            try:
                await saved.edit_reply_markup(
                    share_markup(link)
                )
            except Exception:
                pass

    except FloodWait as exc:
        await asyncio.sleep(exc.value)

        await status.edit_text(
            "Telegram rate limit passed. "
            "Please send the file again."
        )

    except Exception:
        await status.edit_text(
            "❌ Could not save this post. "
            "Check that the bot can post in "
            "the private database channel."
        )


@Bot.on_message(
    filters.channel
    & filters.incoming
    & filters.chat(CHANNEL_ID)
)
async def add_share_button(
    client: Bot,
    message: Message
):
    if DISABLE_CHANNEL_BUTTON:
        return

    link = await make_link(
        client,
        message.id
    )

    try:
        await message.edit_reply_markup(
            share_markup(link)
        )
    except Exception:
        pass
