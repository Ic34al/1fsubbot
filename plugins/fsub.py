
import logging

from pyrogram import Client, filters
from pyrogram.types import ChatJoinRequest, ChatMemberUpdated
from pyrogram.enums import ChatMemberStatus

from config import FSUB_CHANNELS, FORCE_MSG
from database import database as db

LOG = logging.getLogger(__name__)

MEMBER_STATUSES = {
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.OWNER,
    ChatMemberStatus.RESTRICTED,
}


def format_force_message(user):
    return FORCE_MSG.format(
        first=user.first_name or "",
        last=user.last_name or "",
        username=f"@{user.username}" if user.username else "",
        mention=user.mention,
        id=user.id,
    )


async def show_fsub_again(client, user, channel_id):
    await db.invalidate_request(user.id, channel_id)

    code = await db.get_last_file(user.id)
    if not code:
        LOG.info(
            "No previous file link for user %s",
            user.id,
        )
        return

    await db.set_pending_file(user.id, code)

    try:
        from plugins.start import force_markup

        await client.send_message(
            chat_id=user.id,
            text=format_force_message(user),
            reply_markup=force_markup(client, code),
            disable_web_page_preview=True,
        )

        LOG.info(
            "FSUB shown again: user=%s channel=%s",
            user.id,
            channel_id,
        )

    except Exception:
        LOG.exception(
            "Failed to show FSUB to user %s",
            user.id,
        )


for channel in FSUB_CHANNELS:
    channel_id = channel["id"]

    @Client.on_chat_join_request(filters.chat(channel_id))
    async def on_join_request(
        client,
        request: ChatJoinRequest,
        _channel_id=channel_id,
    ):
        user = request.from_user

        if not user or user.is_bot:
            return

        # Save the request immediately. Approval is not required.
        await db.set_request(
            user.id,
            _channel_id,
            "requested",
        )

        LOG.info(
            "FSUB REQUEST SAVED user=%s channel=%s",
            user.id,
            _channel_id,
        )

    @Client.on_chat_member_updated(filters.chat(channel_id))
    async def on_member_update(
        client,
        update: ChatMemberUpdated,
        _channel_id=channel_id,
    ):
        new_member = update.new_chat_member
        old_member = update.old_chat_member

        user = new_member.user if new_member else None

        if not user or user.is_bot or not new_member:
            return

        # Joining or being approved satisfies this channel.
        if new_member.status in MEMBER_STATUSES:
            await db.set_request(
                user.id,
                _channel_id,
                "member",
            )

            LOG.info(
                "FSUB MEMBER SAVED user=%s channel=%s",
                user.id,
                _channel_id,
            )
            return

        # Do not erase a pending request just because it was rejected.
        # Only invalidate when an actual member leaves or gets banned.
        was_member = (
            old_member is not None
            and old_member.status in MEMBER_STATUSES
        )

        is_out = new_member.status in (
            ChatMemberStatus.LEFT,
            ChatMemberStatus.BANNED,
        )

        if was_member and is_out:
            LOG.info(
                "FSUB MEMBER LEFT user=%s channel=%s",
                user.id,
                _channel_id,
            )

            await show_fsub_again(
                client,
                user,
                _channel_id,
            )
