from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

from config import MONGO_URI, DATABASE_NAME


_client = AsyncIOMotorClient(
    MONGO_URI,
    serverSelectionTimeoutMS=10000,
    connectTimeoutMS=10000,
    socketTimeoutMS=20000,
    retryWrites=True,
)

_db = _client[DATABASE_NAME]
_users = _db["users"]


async def ping():
    await _client.admin.command("ping")


async def close():
    _client.close()


async def get_user(user_id: int):
    return await _users.find_one({
        "_id": int(user_id)
    })


async def set_pending_file(
    user_id: int,
    file_code: str
):
    now = datetime.now(timezone.utc)

    await _users.update_one(
        {"_id": int(user_id)},
        {
            "$set": {
                "pending_file": file_code,
                "last_file_code": file_code,
                "updated_at": now,
            }
        },
        upsert=True,
    )


async def get_pending_file(user_id: int):
    user = await get_user(user_id)

    return (
        user.get("pending_file")
        if user
        else None
    )


async def get_last_file(user_id: int):
    user = await get_user(user_id)

    return (
        user.get("last_file_code")
        if user
        else None
    )


async def clear_pending_file(user_id: int):
    await _users.update_one(
        {"_id": int(user_id)},
        {
            "$unset": {
                "pending_file": ""
            },
            "$set": {
                "updated_at": datetime.now(timezone.utc)
            },
        },
    )


async def set_request(
    user_id: int,
    channel_id: int,
    status: str = "requested"
):
    now = datetime.now(timezone.utc)

    await _users.update_one(
        {"_id": int(user_id)},
        {
            "$set": {
                f"requests.{int(channel_id)}": {
                    "status": status,
                    "updated_at": now,
                },
                "updated_at": now,
            }
        },
        upsert=True,
    )


async def get_request_status(
    user_id: int,
    channel_id: int
):
    user = await get_user(user_id)

    if not user:
        return None

    request = (
        user.get("requests") or {}
    ).get(str(int(channel_id)))

    if isinstance(request, dict):
        return request.get("status")

    return None


async def invalidate_request(
    user_id: int,
    channel_id: int
):
    now = datetime.now(timezone.utc)

    await _users.update_one(
        {"_id": int(user_id)},
        {
            "$set": {
                f"requests.{int(channel_id)}.status": "left",
                f"requests.{int(channel_id)}.updated_at": now,
            }
        },
    )


async def get_all_user_ids():
    cursor = _users.find(
        {},
        {"_id": 1}
    )

    return [
        doc["_id"]
        async for doc in cursor
    ]


async def count_users():
    return await _users.count_documents({})
