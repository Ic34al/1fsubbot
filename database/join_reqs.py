#(©)Javpostr made by @rohit_1888

import motor
import motor.motor_asyncio
from config import *


class JoinReqs:

    def __init__(self):
        from config import JOIN_REQS_DB

        if JOIN_REQS_DB:
            self.client = motor.motor_asyncio.AsyncIOMotorClient(
                JOIN_REQS_DB
            )
            self.db = self.client["JoinReqs"]
            self.col = self.db[str(FORCE_SUB_CHANNEL)]
        else:
            self.client = None
            self.db = None
            self.col = None

    def isActive(self):
        return self.client is not None

    async def add_user(
        self,
        user_id,
        first_name,
        username,
        date
    ):
        try:
            # UPDATE instead of insert.
            # This is important because the user may already have
            # a pending file saved before sending the join request.
            await self.col.update_one(
                {"_id": int(user_id)},
                {
                    "$set": {
                        "user_id": int(user_id),
                        "first_name": first_name,
                        "username": username,
                        "date": date
                    }
                },
                upsert=True
            )
        except Exception:
            pass

    async def get_user(self, user_id):
        if not self.isActive():
            return None

        try:
            return await self.col.find_one(
                {"user_id": int(user_id)}
            )
        except Exception:
            return None

    # ---------------------------------------------------------
    # PENDING FILE
    # ---------------------------------------------------------

    async def set_pending_file(self, user_id, file_code):
        if not self.isActive():
            return

        try:
            await self.col.update_one(
                {"_id": int(user_id)},
                {
                    "$set": {
                        "user_id": int(user_id),
                        "pending_file": file_code
                    }
                },
                upsert=True
            )
        except Exception:
            pass

    async def get_pending_file(self, user_id):
        if not self.isActive():
            return None

        try:
            user = await self.col.find_one(
                {"_id": int(user_id)}
            )

            if user:
                return user.get("pending_file")

        except Exception:
            pass

        return None

    async def clear_pending_file(self, user_id):
        if not self.isActive():
            return

        try:
            await self.col.update_one(
                {"_id": int(user_id)},
                {
                    "$unset": {
                        "pending_file": ""
                    }
                }
            )
        except Exception:
            pass

    # ---------------------------------------------------------

    async def get_all_users(self):
        return await self.col.find().to_list(None)

    async def delete_user(self, user_id):
        await self.col.delete_one(
            {"user_id": int(user_id)}
        )

    async def delete_all_users(self):
        await self.col.delete_many({})

    async def get_all_users_count(self):
        return await self.col.count_documents({})
