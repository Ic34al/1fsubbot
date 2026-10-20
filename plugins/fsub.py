import logging

from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import ChatJoinRequest, ChatMemberUpdated

from config import FSUB_CHANNELS, FORCE_MSG
from database import database as db

LOG = logging.getLogger(__name__)

FSUB_IDS = [int(channel["id"]) for channel in FSUB_CHANNELS]

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
            "FSUB recheck: no previous file for user=%s",
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
            "FSUB buttons shown again user=%s channel=%s",
            user.id,
            channel_id,
        )
    except Exception:
        LOG.exception(
            "Could not send FSUB buttons to user=%s",
            user.id,
        )


@Client.on_chat_join_request(filters.chat(FSUB_IDS))
async def record_join_request(
    client,
    request: ChatJoinRequest,
):
    user = request.from_user
    channel_id = int(request.chat.id)

    if not user or user.is_bot:
        return

    if channel_id not in FSUB_IDS:
        LOG.warning(
            "Ignoring unexpected request channel=%s",
            channel_id,
        )
        return

    try:
        # A submitted request counts immediately, pending approval.
        await db.set_request(
            user.id,
            channel_id,
            "requested",
        )

        LOG.info(
            "FSUB REQUEST SAVED user=%s channel=%s status=requested",
            user.id,
            channel_id,
        )
    except Exception:
        LOG.exception(
            "FAILED TO SAVE FSUB REQUEST user=%s channel=%s",
            user.id,
            channel_id,
        )


@Client.on_chat_member_updated(filters.chat(FSUB_IDS))
async def track_membership(
    client,
    update: ChatMemberUpdated,
):
    channel_id = int(update.chat.id)
    new_member = update.new_chat_member
    old_member = update.old_chat_member
    user = new_member.user if new_member else None

    if not user or user.is_bot or not new_member:
        return

    if channel_id not in FSUB_IDS:
        return

    if new_member.status in MEMBER_STATUSES:
        try:
            await db.set_request(
                user.id,
                channel_id,
                "member",
            )
            LOG.info(
                "FSUB MEMBER SAVED user=%s channel=%s",
                user.id,
                channel_id,
            )
        except Exception:
            LOG.exception(
                "FAILED TO SAVE MEMBERSHIP user=%s channel=%s",
                user.id,
                channel_id,
            )
        return

    # Only invalidate a genuine member leaving; a rejected pending
    # request must not erase the previously saved request.
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
            channel_id,
        )
        await show_fsub_again(client, user, channel_id)
