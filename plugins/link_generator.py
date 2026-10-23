
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
        f"<b>File link created:</b>\n"
        f"{name}\n\n"
        f"Here is your link:\n{link}",
        reply_to_message_id=message.id,
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
    user_id = message.from_user.id
    state = pending.get(user_id)

    # Continue an existing /genlink or /batch workflow only
    # for text containing a storage-channel post link.
    if state and message.chat.id == state["chat_id"] and message.text:
        try:
            msg_id = await get_message_id(client, message)
        except Exception:
            LOG.exception("Could not identify database post")
            msg_id = None

        if msg_id:
            state["ids"].append(msg_id)

            if state["mode"] == "batch" and len(state["ids"]) == 1:
                await message.reply_text(
                    "Now forward the LAST database post."
                )
                return

            ids = state["ids"][:]
            pending.pop(user_id, None)

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

        await message.reply_text(
            "❌ Couldn't identify that database post. "
            "Send a valid storage-channel post link, or send a file "
            "to generate a link automatically."
        )
        return

    # Automatically generate an individual link for each file
    # sent directly to the bot.
    media = (
        message.document
        or message.video
        or message.audio
        or message.animation
        or message.photo
        or message.voice
        or message.video_note
    )

    if not media:
        return

    try:
        # Save a copy to the configured storage channel.
        saved = await message.copy(
            chat_id=client.db_channel.id
        )

        file_name = (
            getattr(media, "file_name", None)
            or getattr(message, "caption", None)
            or "Your file"
        )

        # Reply to the original file with its own link and button.
        await finish_link(
            client,
            message,
            [saved.id],
            file_name=file_name
        )

    except Exception:
        LOG.exception(
            "Automatic file link generation failed user=%s",
            user_id
        )

        await message.reply_text(
            "❌ Couldn't save the file or generate its link. "
            "Check Heroku logs and storage-channel permissions."
        )
