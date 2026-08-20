from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message
)

from bot import Bot
from config import (
    FORCE_SUB_CHANNEL,
    FORCE_SUB_CHANNEL2,
    FORCE_PIC,
    FORCE_MSG
)


@Bot.on_message(
    filters.command("start")
    & filters.private
    & ~filters.user(0)
)
async def not_joined(client: Client, message: Message):

    buttons = []

    if FORCE_SUB_CHANNEL:
        invite_link = getattr(client, "invitelink", None)

        if invite_link:
            buttons.append([
                InlineKeyboardButton(
                    "ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ 1",
                    url=invite_link
                )
            ])

    if FORCE_SUB_CHANNEL2:
        invite_link2 = getattr(client, "invitelink2", None)

        if invite_link2:
            buttons.append([
                InlineKeyboardButton(
                    "ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ 2",
                    url=invite_link2
                )
            ])

    if not buttons:
        await message.reply_text(
            "Hello! The bot is running successfully."
        )
        return

    start_param = (
        message.command[1]
        if len(message.command) > 1
        else None
    )

    if start_param and getattr(client, "username", None):
        buttons.append([
            InlineKeyboardButton(
                "🔄 Try Again",
                url=(
                    f"https://t.me/{client.username}"
                    f"?start={start_param}"
                )
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

    reply_markup = InlineKeyboardMarkup(buttons)

    if FORCE_PIC:
        try:
            await message.reply_photo(
                photo=FORCE_PIC,
                caption=caption,
                reply_markup=reply_markup
            )
            return
        except Exception:
            pass

    await message.reply_text(
        text=caption,
        reply_markup=reply_markup
    )
