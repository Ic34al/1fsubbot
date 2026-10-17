import os

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
MONGO_URI = os.environ["MONGO_URI"]
DATABASE_NAME = os.getenv("DATABASE_NAME", "FileBot")

OWNER_ID = int(os.environ["OWNER_ID"])

# Configure four channels using environment variables.
FSUB_CHANNELS = [
    (
        int(os.environ["FSUB_CHANNEL_1_ID"]),
        os.environ["FSUB_CHANNEL_1_LINK"],
    ),
    (
        int(os.environ["FSUB_CHANNEL_2_ID"]),
        os.environ["FSUB_CHANNEL_2_LINK"],
    ),
    (
        int(os.environ["FSUB_CHANNEL_3_ID"]),
        os.environ["FSUB_CHANNEL_3_LINK"],
    ),
    (
        int(os.environ["FSUB_CHANNEL_4_ID"]),
        os.environ["FSUB_CHANNEL_4_LINK"],
    ),
]
