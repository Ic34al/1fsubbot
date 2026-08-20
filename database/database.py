from motor.motor_asyncio import AsyncIOMotorClient

from config import DB_URI, DB_NAME


dbclient = AsyncIOMotorClient(DB_URI)

database = dbclient[DB_NAME]

user_data = database["users"]


async def present_user(user_id: int):
    found = await user_data.find_one(
        {"_id": int(user_id)},
        {"_id": 1}
    )

    return found is not None


async def add_user(user_id: int):
    await user_data.update_one(
        {"_id": int(user_id)},
        {"$setOnInsert": {"_id": int(user_id)}},
        upsert=True
    )


async def full_userbase():
    cursor = user_data.find(
        {},
        {"_id": 1}
    )

    return [
        document["_id"]
        async for document in cursor
    ]


async def del_user(user_id: int):
    await user_data.delete_one(
        {"_id": int(user_id)}
    )
