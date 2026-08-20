from pyrogram import Client, filters, enums
from pyrogram.types import ChatJoinRequest

from database.join_reqs2 import JoinReqs2
from config import ADMINS, FORCE_SUB_CHANNEL2


db2 = JoinReqs2()


if FORCE_SUB_CHANNEL2:

    @Client.on_chat_join_request(
        filters.chat(FORCE_SUB_CHANNEL2)
    )
    async def join_reqs2(
        client,
        join_req: ChatJoinRequest
    ):
        if not db2.isActive():
            return

        await db2.add_user(
            user_id=join_req.from_user.id,
            first_name=join_req.from_user.first_name,
            username=join_req.from_user.username,
            date=join_req.date
        )


@Client.on_message(
    filters.command("total2")
    & filters.private
    & filters.user(ADMINS)
)
async def total_requests2(client, message):

    if not db2.isActive():
        return await message.reply_text(
            "❌ Join request database is not configured."
        )

    total = await db2.get_all_users_count()

    await message.reply_text(
        text=f"🗿 Total Requests: {total}",
        parse_mode=enums.ParseMode.MARKDOWN
    )


@Client.on_message(
    filters.command("clear2")
    & filters.private
    & filters.user(ADMINS)
)
async def purge_requests2(client, message):

    if not db2.isActive():
        return await message.reply_text(
            "❌ Join request database is not configured."
        )

    await db2.delete_all_users()

    await message.reply_text(
        text="Cleared All Requests 🧹"
    )
