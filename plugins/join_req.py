from pyrogram import Client, filters, enums
from pyrogram.types import ChatJoinRequest

from database.join_reqs import JoinReqs
from config import ADMINS, FORCE_SUB_CHANNEL


db = JoinReqs()


if FORCE_SUB_CHANNEL:

    @Client.on_chat_join_request(
        filters.chat(FORCE_SUB_CHANNEL)
    )
    async def join_reqs(
        client,
        join_req: ChatJoinRequest
    ):
        if not db.isActive():
            return

        await db.add_user(
            user_id=join_req.from_user.id,
            first_name=join_req.from_user.first_name,
            username=join_req.from_user.username,
            date=join_req.date
        )


@Client.on_message(
    filters.command("total1")
    & filters.private
    & filters.user(ADMINS)
)
async def total_requests(client, message):

    if not db.isActive():
        return await message.reply_text(
            "❌ Join request database is not configured."
        )

    total = await db.get_all_users_count()

    await message.reply_text(
        text=f"🗿 Total Requests: {total}",
        parse_mode=enums.ParseMode.MARKDOWN
    )


@Client.on_message(
    filters.command("clear1")
    & filters.private
    & filters.user(ADMINS)
)
async def purge_requests(client, message):

    if not db.isActive():
        return await message.reply_text(
            "❌ Join request database is not configured."
        )

    await db.delete_all_users()

    await message.reply_text(
        text="Cleared All Requests 🧹"
    )
