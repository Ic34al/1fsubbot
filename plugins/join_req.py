import asyncio

from pyrogram import Client, filters, enums
from pyrogram.types import ChatJoinRequest
from pyrogram.errors import FloodWait

from database.join_reqs import JoinReqs
from database.join_reqs2 import JoinReqs2

from config import (
    ADMINS,
    FORCE_SUB_CHANNEL,
    FORCE_SUB_CHANNEL2,
    CUSTOM_CAPTION,
    PROTECT_CONTENT
)

from helper_func import decode


db = JoinReqs()
db2 = JoinReqs2()


async def send_pending_file(client, user_id):
    """
    Send the file that the user originally requested.

    A pending join request counts as ForceSub completion.
    No channel approval or actual membership is required.
    """

    # Need both request records
    request1 = await db.get_user(user_id)
    request2 = await db2.get_user(user_id)

    if FORCE_SUB_CHANNEL and not request1:
        return False

    if FORCE_SUB_CHANNEL2 and not request2:
        return False

    # Get requested file code
    file_code = await db.get_pending_file(user_id)

    if not file_code:
        return False

    try:
        data = await decode(file_code)
        parts = data.split("-")

        if len(parts) < 2 or parts[0] != "get":
            return False

        channel_id = abs(client.db_channel.id)

        # Single file
        if len(parts) == 2:

            message_ids = [
                int(parts[1]) // channel_id
            ]

        # Batch
        elif len(parts) == 3:

            first_id = int(parts[1]) // channel_id
            last_id = int(parts[2]) // channel_id

            if first_id <= 0 or last_id <= 0:
                return False

            if first_id > last_id:
                first_id, last_id = last_id, first_id

            # Safety limit
            if last_id - first_id > 1000:
                await client.send_message(
                    user_id,
                    "❌ This batch link contains too many files."
                )
                return False

            message_ids = list(
                range(first_id, last_id + 1)
            )

        else:
            return False

    except Exception:
        return False

    sent = 0

    # Send requested files
    for message_id in message_ids:

        try:
            db_message = await client.get_messages(
                client.db_channel.id,
                message_id
            )

            if not db_message or db_message.empty:
                continue

            await db_message.copy(
                chat_id=user_id,
                caption=CUSTOM_CAPTION or None,
                protect_content=PROTECT_CONTENT
            )

            sent += 1

        except FloodWait as e:

            await asyncio.sleep(e.value)

            try:
                db_message = await client.get_messages(
                    client.db_channel.id,
                    message_id
                )

                if db_message and not db_message.empty:

                    await db_message.copy(
                        chat_id=user_id,
                        caption=CUSTOM_CAPTION or None,
                        protect_content=PROTECT_CONTENT
                    )

                    sent += 1

            except Exception:
                continue

        except Exception:
            continue

    # File successfully delivered
    if sent > 0:

        await db.clear_pending_file(user_id)

        try:
            await client.send_message(
                user_id,
                "✅ File sent successfully!"
            )
        except Exception:
            pass

        return True

    return False


# ============================================================
# CHANNEL 1 JOIN REQUEST
# ============================================================

if FORCE_SUB_CHANNEL:

    @Client.on_chat_join_request(
        filters.chat(FORCE_SUB_CHANNEL)
    )
    async def join_reqs(
        client,
        join_req: ChatJoinRequest
    ):

        user = join_req.from_user

        if not user:
            return

        # Save request
        if db.isActive():

            await db.add_user(
                user_id=user.id,
                first_name=user.first_name,
                username=user.username,
                date=join_req.date
            )

        # Check whether both required join requests are now present.
        # The second request, regardless of which channel it is,
        # will trigger the pending file delivery.
        await send_pending_file(
            client,
            user.id
        )


# ============================================================
# ADMIN COMMANDS
# ============================================================

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
