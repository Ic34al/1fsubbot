import base64
import re
import asyncio
import logging
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import FloodWait, UserNotParticipant

from config import ADMINS, FSUB_CHANNELS
from database import database as db
LOG = logging.getLogger(__name__)

MEMBER_STATUSES = {
    ChatMemberStatus.OWNER,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.RESTRICTED,
}


async def encode(value: str) -> str:
    return (
        base64.urlsafe_b64encode(
            value.encode("utf-8")
        )
        .decode("ascii")
        .rstrip("=")
    )


async def decode(value: str) -> str:
    try:
        value = value.strip()

        return base64.urlsafe_b64decode(
            value + "=" * (-len(value) % 4)
        ).decode("utf-8")

    except Exception as exc:
        raise ValueError(
            "Invalid start parameter"
        ) from exc


async def is_member(client, user_id, channel_id):
    try:
        member = await client.get_chat_member(
            channel_id,
            user_id
        )

        return member.status in MEMBER_STATUSES

    except UserNotParticipant:
        return False

    except Exception:
        return False

async def channel_is_satisfied(client, user_id, channel_id):
    if user_id in ADMINS:
        return True

    if await is_member(client, user_id, channel_id):
        await db.set_request(user_id, channel_id, "member")
        return True

    status = await db.get_request_status(user_id, channel_id)
    return status == "requested"





async def all_channels_satisfied(client, user_id):
    for channel in FSUB_CHANNELS:
        channel_id = channel["id"]

        try:
            satisfied = await channel_is_satisfied(
                client, user_id, channel_id
            )
            LOG.info(
                "FSUB CHECK user=%s channel=%s satisfied=%s status=%s",
                user_id,
                channel_id,
                satisfied,
                await db.get_request_status(user_id, channel_id),
            )

            if not satisfied:
                LOG.warning(
                    "FSUB BLOCKED user=%s channel=%s",
                    user_id, channel_id
                )
                return False

        except Exception:
            LOG.exception(
                "FSUB CHECK ERROR user=%s channel=%s",
                user_id, channel_id
            )
            return False

    LOG.info("ALL FOUR FSUB CHANNELS PASSED for user=%s", user_id)
    return True


async def get_message_id(client, message):
    forward_chat = getattr(
        message,
        "forward_from_chat",
        None
    )

    if forward_chat:
        if forward_chat.id == client.db_channel.id:
            return (
                getattr(
                    message,
                    "forward_from_message_id",
                    None
                )
                or 0
            )

        return 0

    if (
        getattr(message, "forward_sender_name", None)
        or not getattr(message, "text", None)
    ):
        return 0

    match = re.match(
        r"^https?://t\.me/(?:c/)?([^/]+)/(\d+)",
        message.text.strip()
    )

    if not match:
        return 0

    channel_name = match.group(1)
    msg_id = int(match.group(2))

    if channel_name.isdigit():
        if f"-100{channel_name}" == str(
            client.db_channel.id
        ):
            return msg_id

    elif (
        client.db_channel.username
        and channel_name.lstrip("@")
        == client.db_channel.username
    ):
        return msg_id

    return 0


async def get_messages(client, message_ids):
    output = []

    for start in range(0, len(message_ids), 100):
        batch = message_ids[start:start + 100]

        try:
            result = await client.get_messages(
                client.db_channel.id,
                batch
            )

        except FloodWait as exc:
            await asyncio.sleep(exc.value)

            result = await client.get_messages(
                client.db_channel.id,
                batch
            )

        if isinstance(result, list):
            output.extend(
                message
                for message in result
                if message
                and not getattr(message, "empty", False)
            )

        elif (
            result
            and not getattr(result, "empty", False)
        ):
            output.append(result)

    return output
