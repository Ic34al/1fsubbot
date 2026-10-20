
import logging

from pyrogram import Client, filters
from pyrogram.types import ChatJoinRequest, ChatMemberUpdated
from pyrogram.enums import ChatMemberStatus

from config import FSUB_CHANNELS, FORCE_MSG
from database import database as db
from helper_func import all_channels_satisfied

LOG = logging.getLogger(__name__)


async def try_deliver_pending(client, user_id):
    code = await db.get_pending_file(user_id)
    if not code:
        return

    if not await all_channels_satisfied(client, user_id):
        return

    from plugins.start import deliver_file
    await deliver_file(client, user_id, code)


for channel in FSUB_CHANNELS:
    channel_id = channel["id"]

    @Client.on_chat_join_request(filters.chat(channel_id))
    async def on_join_request(
        client, request: ChatJoinRequest, _channel_id=channel_id
    ):
        user = request.from_user
        if not user:
            return

        await db.set_request(
            user.id, _channel_id, "requested"
        )

        LOG.info(
            "Recorded request from %s for %s",
            user.id, _channel_id
        )

        await try_deliver_pending(client, user.id)

    @Client.on_chat_member_updated(filters.chat(channel_id))
    async def on_member_update(
        client, update: ChatMemberUpdated, _channel_id=channel_id
    ):
        member = update.new_chat_member
        user = member.user if member else None

        if not user or user.is_bot:
            return

        if member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
            ChatMemberStatus.RESTRICTED,
        ):
            await db.set_request(
                user.id, _channel_id, "member"
            )
            await try_deliver_pending(client, user.id)

        elif member.status in (
            ChatMemberStatus.LEFT,
            ChatMemberStatus.BANNED,
        ):
            await db.invalidate_request(
                user.id, _channel_id
            )

            code = await db.get_last_file(user.id)
            if not code:
                return

            await db.set_pending_file(user.id, code)

            try:
                from plugins.start import force_markup

                text = FORCE_MSG.format(
                    first=user.first_name or "",
                    last=user.last_name or "",
                    username=(
                        f"@{user.username}"
                        if user.username else ""
                    ),
                    mention=user.mention,
                    id=user.id,
                )

                await client.send_message(
                    user.id,
                    text,
                    reply_markup=force_markup(client, code),
                    disable_web_page_preview=True,
                )
            except Exception:
                LOG.exception(
                    "Could not send re-subscription prompt to %s",
                    user.id
                )
