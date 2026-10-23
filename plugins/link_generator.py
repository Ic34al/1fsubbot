
import asyncio
import logging

from pyrogram import filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from bot import Bot
from config import ADMINS
from helper_func import encode, get_message_id

LOG = logging.getLogger(__name__)

# Temporary admin prompts, without pyromod.
pending = {}


def link_markup(link):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "🔁 Share URL",
            url=f"https://t.me/share/url?url={link}",
        )
    ]])


async def finish_link(client, message, ids, file_name=None):
    divisor = abs(client.db_channel.id)

    encoded = "get-" + "-".join(
        str(msg_id * divisor) for msg_id in ids
    )

    code = await encode(encoded)
    link = f"https://t.me/{client.username}?start={code}"

    name = file_name or "Your file"

    await message.reply_text(
        f"📁 <b>{name}</b>\n\n"
        f"Here is your link:\n\n"
        f"{link}",
        reply_markup=link_markup(link),
        disable_web_page_preview=True,
    )


@Bot.on_message(
    filters.private
    & filters.user(list(ADMINS))
    & filters.command(["genlink", "batch"])
)
async def begin_link(client: Bot, message: Message):
    mode = message.command[0].lower()

    pending[message.from_user.id] = {
        "mode": mode,
        "ids": [],
        "chat_id": message.chat.id,
    }

    prompt = (
        "Forward the FIRST database post, then the LAST post."
        if mode == "batch"
        else "Forward the database post or send its post link."
    )

    await message.reply_text(prompt)


@Bot.on_message(
    filters.private
    & filters.user(list(ADMINS))
    & ~filters.command([
        "start",
        "users",
        "broadcast",
        "stats",
        "genlink",
        "batch",
    ])
)
async def receive_link_input(client: Bot, message: Message):
    state = pending.get(message.from_user.id)

    # Existing manual /genlink and /batch workflow.
    if state and message.chat.id == state["chat_id"]:
        try:
            msg_id = await get_message_id(client, message)
        except Exception:
            LOG.exception("Could not identify database post")
            msg_id = None

        if not msg_id:
            await message.reply_text(
                "❌ Couldn't identify that database post. "
                "Forward the post from your storage channel "
                "or send its post link."
            )
            return

        state["ids"].append(msg_id)

        if state["mode"] == "batch" and len(state["ids"]) == 1:
            await message.reply_text(
                "Now forward the LAST database post."
            )
            return

        ids = state["ids"][:]
        pending.pop(message.from_user.id, None)

        try:
            if len(ids) == 2 and ids[0] > ids[1]:
                ids.reverse()

            await finish_link(client, message, ids)

        except Exception:
            LOG.exception("Link generation failed")
            await message.reply_text(
                "❌ Link generation failed. Check Heroku logs."
            )

        return

    # Automatic link generation for a file sent directly to the bot.
    if not (
        message.document
        or message.video
        or message.audio
        or message.animation
        or message.photo
        or message.voice
        or message.video_note
    ):
        return

    try:
        saved = await message.copy(
            chat_id=client.db_channel.id
        )

        media = (
            message.document
            or message.video
            or message.audio
            or message.animation
            or message.voice
            or message.video_note
            or message.photo
        )

        file_name = (
            getattr(media, "file_name", None)
            or getattr(media, "file_unique_id", None)
            or "Your file"
        )

        await finish_link(
            client,
            message,
            [saved.id],
            file_name=file_name
        )

    except Exception:
        LOG.exception(
            "Automatic file link generation failed user=%s",
            message.from_user.id
        )

        await message.reply_text(
            "❌ Couldn't save the file or generate its link. "
            "Check the bot's Heroku logs and storage-channel permissions."
        )
