
from datetime import datetime, timezone

from pyrogram import filters

from bot import Bot
from config import ADMINS
from database import database as db


@Bot.on_message(
    filters.private
    & filters.user(list(ADMINS))
    & filters.command("stats")
)
async def stats(client: Bot, message):
    uptime = datetime.now(timezone.utc) - client.uptime
    seconds = int(uptime.total_seconds())

    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    await message.reply_text(
        f"📊 <b>Bot Status</b>\n"
        f"👥 Users: {await db.count_users()}\n"
        f"⏱ Uptime: {days}d {hours}h "
        f"{minutes}m {seconds}s"
    )
