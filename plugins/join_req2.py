from pyrogram import Client, filters, enums
from pyrogram.types import ChatJoinRequest

from database.join_reqs import JoinReqs
from database.join_reqs2 import JoinReqs2

from config import (
    ADMINS,
    FORCE_SUB_CHANNEL2
)

from plugins.join_req import send_pending_file


db = JoinReqs()
db2 = JoinReqs2()


# ============================================================
# CHANNEL 2 JOIN REQUEST
# ============================================================

if FORCE_SUB_CHANNEL2:

    @Client.on_chat_join_request(
        filters.chat(FORCE_SUB_CHANNEL2)
    )
    async def join_reqs2(
        client,
        join_req: ChatJoinRequest
    ):

        user = join_req.from_user

        if not user:
            return

        # Save Channel 2 request
        if db2.isActive():

            await db2.add_user(
                user_id=user.id,
                first_name=user.first_name,
                username=user.username,
                date=join_req.date
            )

        # Both requests are now checked.
        # If Channel 1 + Channel 2 requests exist,
        # the pending file is sent automatically.
        await send_pending_file(
            client,
            user.id
        )


# ============================================================
# ADMIN COMMANDS
# ============================================================

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
