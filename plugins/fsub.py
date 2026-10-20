import logging

from pyrogram import Client, filters
from pyrogram.types import ChatJoinRequest, ChatMemberUpdated
from pyrogram.enums import ChatMemberStatus

from config import FSUB_CHANNELS, FORCE_MSG
from database import database as db

LOG = logging.getLogger(__name__)


def format_force_message(user):
    return FORCE_MSG.format(
        first=user.first_name or "",
        last=user.last_name or "",
        username=f"@{user.username}" if user.username else "",
        mention=user.mention,
        id=user.id,
    )


async def show_fsub_again(client, user, channel_id):
    # A user who leaves must no longer count for this channel.
    await db.invalidate_request(user.id, channel_id)

    code = await db.get_last_file(user.id)
    if not code:
        LOG.info(
            "User %s left channel %s; no previous file link found",
            user.id,
            channel_id,
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
            "Re-shown FSUB buttons to user %s after leaving %s",
            user.id,
            channel_id,
        )

    except Exception:
        LOG.exception(
            "Could not re-show FSUB buttons to user %s",
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

        # Pending approval counts as satisfied.
        # Delivery happens only when the user taps Try Again.
        await db.set_request(
            user.id,
            _channel_id,
            "requested",
        )

        LOG.info(
            "Join request recorded: user=%s channel=%s",
            user.id,
            _channel_id,
        )

    @Client.on_chat_member_updated(filters.chat(channel_id))
    async def on_member_update(
        client,
        update: ChatMemberUpdated,
        _channel_id=channel_id,
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
                user.id,
                _channel_id,
                "member",
            )

            LOG.info(
                "Membership recorded: user=%s channel=%s",
                user.id,
                _channel_id,
            )

        elif member.status in (
            ChatMemberStatus.LEFT,
            ChatMemberStatus.BANNED,
        ):
            await show_fsub_again(
                client,
                user,
                _channel_id,
            )
