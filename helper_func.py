import base64
import re
import asyncio

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant

from config import ADMINS, FORCE_SUB_CHANNEL, FORCE_SUB_CHANNEL2
from database.join_reqs import JoinReqs
from database.join_reqs2 import JoinReqs2


async def is_subscribed1(filter, client, update):
    if not FORCE_SUB_CHANNEL:
        return True

    if not getattr(update, "from_user", None):
        return False

    user_id = update.from_user.id

    if user_id in ADMINS:
        return True

    try:
        db = JoinReqs()
        user = await db.get_user(user_id)

        if user and user.get("user_id") == user_id:
            return True

        member = await client.get_chat_member(
            chat_id=FORCE_SUB_CHANNEL,
            user_id=user_id
        )

        return member.status in (
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.MEMBER
        )

    except UserNotParticipant:
        return False

    except Exception:
        return False


async def is_subscribed2(filter, client, update):
    if not FORCE_SUB_CHANNEL2:
        return True

    if not getattr(update, "from_user", None):
        return False

    user_id = update.from_user.id

    if user_id in ADMINS:
        return True

    try:
        db = JoinReqs2()
        user = await db.get_user(user_id)

        if user and user.get("user_id") == user_id:
            return True

        member = await client.get_chat_member(
            chat_id=FORCE_SUB_CHANNEL2,
            user_id=user_id
        )

        return member.status in (
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.MEMBER
        )

    except UserNotParticipant:
        return False

    except Exception:
        return False


async def encode(string):
    return base64.urlsafe_b64encode(
        string.encode("utf-8")
    ).decode("utf-8").rstrip("=")


async def decode(base64_string):
    try:
        base64_string = base64_string.rstrip("=")
        padding = "=" * (-len(base64_string) % 4)

        return base64.urlsafe_b64decode(
            (base64_string + padding).encode("utf-8")
        ).decode("utf-8")

    except Exception:
        raise ValueError("Invalid start parameter.")


async def get_messages(client, message_ids):
    messages = []

    for start in range(0, len(message_ids), 200):
        batch_ids = message_ids[start:start + 200]

        try:
            msgs = await client.get_messages(
                chat_id=client.db_channel.id,
                message_ids=batch_ids
            )

            if isinstance(msgs, list):
                messages.extend(
                    msg for msg in msgs
                    if msg is not None
                )
            elif msgs is not None:
                messages.append(msgs)

        except FloodWait as e:
            await asyncio.sleep(e.value)

            msgs = await client.get_messages(
                chat_id=client.db_channel.id,
                message_ids=batch_ids
            )

            if isinstance(msgs, list):
                messages.extend(
                    msg for msg in msgs
                    if msg is not None
                )
            elif msgs is not None:
                messages.append(msgs)

        except Exception:
            continue

    return messages


async def get_message_id(client, message):
    if message.forward_from_chat:
        if message.forward_from_chat.id == client.db_channel.id:
            return message.forward_from_message_id

        return 0

    if message.forward_sender_name:
        return 0

    if not message.text:
        return 0

    pattern = r"^https?://t\.me/(?:c/)?([^/]+)/(\d+)"
    matches = re.match(pattern, message.text.strip())

    if not matches:
        return 0

    channel_id = matches.group(1)
    msg_id = int(matches.group(2))

    if channel_id.isdigit():
        if f"-100{channel_id}" == str(client.db_channel.id):
            return msg_id

    elif client.db_channel.username:
        if channel_id.lstrip("@") == client.db_channel.username:
            return msg_id

    return 0


def get_readable_time(seconds: int) -> str:
    seconds = max(0, int(seconds))

    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    parts = []

    if days:
        parts.append(f"{days}d")
    if hours or parts:
        parts.append(f"{hours}h")
    if minutes or parts:
        parts.append(f"{minutes}m")

    parts.append(f"{seconds}s")

    return " ".join(parts)


def get_exp_time(seconds: int) -> str:
    seconds = max(0, int(seconds))

    periods = (
        ("days", 86400),
        ("hours", 3600),
        ("mins", 60),
        ("secs", 1)
    )

    result = []

    for name, value in periods:
        amount, seconds = divmod(seconds, value)

        if amount:
            result.append(f"{amount}{name}")

    return " ".join(result) if result else "0secs"


subscribed1 = filters.create(is_subscribed1)
subscribed2 = filters.create(is_subscribed2)
