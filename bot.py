import asyncio
import logging
import secrets
import time

from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient

from config import (
    API_ID,
    API_HASH,
    BOT_TOKEN,
    MONGO_URI,
    DATABASE_NAME,
    OWNER_ID,
    FSUB_CHANNELS,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = Client(
    "file_share_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

mongo = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=10000,
)
db = mongo[DATABASE_NAME]
users = db["users"]
files = db["files"]

# Verify the database connection at startup.
mongo.admin.command("ping")


async def check_membership(user_id):
    missing = []

    for channel_id, link in FSUB_CHANNELS:
        try:
            member = await app.get_chat_member(
                channel_id, user_id
            )

            if member.status in (
                ChatMemberStatus.LEFT,
                ChatMemberStatus.BANNED,
            ):
                missing.append((channel_id, link))

        except Exception as exc:
            log.warning(
                "Cannot verify membership for %s: %s",
                channel_id, exc
            )
            return None

    return missing


def join_keyboard(missing):
    rows = []

    for index, (_, link) in enumerate(missing, start=1):
        rows.append([
            InlineKeyboardButton(
                f"📢 Join Channel {index}",
                url=link
            )
        ])

    rows.append([
        InlineKeyboardButton(
            "✅ Check Membership",
            callback_data="check_fsub"
        )
    ])

    return InlineKeyboardMarkup(rows)


async def require_membership(message):
    if not message.from_user:
        return False

    missing = await check_membership(message.from_user.id)

    if missing is None:
        await message.reply_text(
            "⚠️ Membership verification is temporarily "
            "unavailable. Please try again later."
        )
        return False

    if missing:
        await message.reply_text(
            "🔒 Join all required channels to access your file.",
            reply_markup=join_keyboard(missing),
        )
        return False

    return True


async def send_with_retry(send_function, *args, **kwargs):
    while True:
        try:
            return await send_function(*args, **kwargs)
        except FloodWait as exc:
            await asyncio.sleep(exc.value)


@app.on_message(filters.command("start"))
async def start_handler(client, message):
    if not message.from_user:
        return

    user_id = message.from_user.id

    users.update_one(
        {"_id": user_id},
        {"$set": {
            "first_name": message.from_user.first_name,
            "username": message.from_user.username,
            "last_seen": int(time.time()),
        }},
        upsert=True,
    )

    parts = message.text.split(maxsplit=1)

    if len(parts) > 1:
        token = parts[1].strip()

        if not await require_membership(message):
            return

        record = files.find_one({"_id": token})

        if not record:
            await message.reply_text(
                "❌ This file link is invalid or expired."
            )
            return

        try:
            await client.copy_message(
                chat_id=message.chat.id,
                from_chat_id=record["chat_id"],
                message_id=record["message_id"],
            )
        except Exception:
            log.exception("File delivery failed")
            await message.reply_text(
                "❌ Unable to send this file. Please contact the admin."
            )
        return

    await message.reply_text(
        "👋 Welcome to the File Sharing Bot!\n\n"
        "Send /help to see the available commands."
    )


@app.on_message(filters.command("help"))
async def help_handler(client, message):
    await message.reply_text(
        "📚 **Bot Commands**\n\n"
        "/start - Start the bot or open a file link\n"
        "/help - Show help\n"
        "/id - Show your Telegram ID\n\n"
        "Admin commands:\n"
        "/genlink - Reply to a message to create a file link\n"
        "/broadcast - Send a broadcast to registered users\n"
        "/stats - Show bot statistics"
    )


@app.on_message(filters.command("id"))
async def id_handler(client, message):
    await message.reply_text(
        f"Your Telegram ID: `{message.from_user.id}`"
    )


@app.on_callback_query(filters.regex("^check_fsub$"))
async def membership_callback(client, query):
    missing = await check_membership(query.from_user.id)

    if missing is None:
        await query.answer(
            "Verification unavailable. Try again later.",
            show_alert=True,
        )
        return

    if missing:
        await query.answer(
            "Please join all required channels first.",
            show_alert=True,
        )
        if query.message:
            await query.message.edit_reply_markup(
                join_keyboard(missing)
            )
        return

    await query.answer(
        "Membership verified! Open your file link again.",
        show_alert=True,
    )

    if query.message:
        await query.message.delete()


@app.on_message(filters.command("genlink") & filters.user(OWNER_ID))
async def genlink_handler(client, message):
    if not message.reply_to_message:
        await message.reply_text(
            "Reply to a file or message with /genlink."
        )
        return

    token = secrets.token_urlsafe(12)

    files.insert_one({
        "_id": token,
        "chat_id": message.chat.id,
        "message_id": message.reply_to_message.id,
        "created_at": int(time.time()),
    })

    me = await client.get_me()
    link = f"https://t.me/{me.username}?start={token}"

    await message.reply_text(
        f"✅ **File link created**\n\n`{link}`",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Open File", url=link)]
        ]),
    )


@app.on_message(filters.command("stats") & filters.user(OWNER_ID))
async def stats_handler(client, message):
    await message.reply_text(
        f"👥 Registered users: {users.count_documents({})}\n"
        f"📁 Saved links: {files.count_documents({})}"
    )


@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast_handler(client, message):
    replied = message.reply_to_message
    parts = message.text.split(maxsplit=1)

    if replied is None and len(parts) < 2:
        await message.reply_text(
            "Send `/broadcast Your message`\n"
            "Or reply to a message with `/broadcast`."
        )
        return

    status = await message.reply_text(
        "📢 Broadcast started..."
    )

    total = users.count_documents({})
    sent = 0
    failed = 0

    cursor = users.find({}, {"_id": 1})

    try:
        for document in cursor:
            user_id = document["_id"]

            try:
                if replied:
                    await send_with_retry(
                        client.copy_message,
                        chat_id=user_id,
                        from_chat_id=message.chat.id,
                        message_id=replied.id,
                    )
                else:
                    await send_with_retry(
                        client.send_message,
                        chat_id=user_id,
                        text=parts[1],
                    )

                sent += 1

            except Exception as exc:
                failed += 1
                log.warning(
                    "Broadcast failed for %s: %s",
                    user_id, exc
                )

            # Keep the request rate conservative.
            await asyncio.sleep(0.05)

    finally:
        cursor.close()

    await status.edit_text(
        "✅ **Broadcast completed**\n\n"
        f"👥 Total users: {total}\n"
        f"📨 Sent: {sent}\n"
        f"❌ Failed: {failed}"
    )


if __name__ == "__main__":
    app.run()
