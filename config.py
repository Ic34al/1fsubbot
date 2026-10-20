import os

APP_ID = int(os.environ.get("APP_ID", "0"))
BOT_TOKEN = os.environ["BOT_TOKEN"]

MONGO_URI = os.environ["MONGO_URI"]
DATABASE_NAME = os.getenv("DATABASE_NAME", "FileBot")

OWNER_ID = int(os.environ["OWNER_ID"])

# Optional: comma-separated Telegram user IDs.
# Example: ADMINS=123456789,987654321

ADMINS = [
    int(x.strip())
    for x in os.getenv("ADMINS", "").split(",")
    if x.strip().isdigit()
]
if OWNER_ID not in ADMINS:
    ADMINS.append(OWNER_ID)

# Private database channel containing your files.
# Use the numeric channel ID, usually beginning with -100.
CHANNEL_ID = int(
    os.getenv("CHANNEL_ID", os.getenv("DB_CHANNEL_ID", "0"))
)

if CHANNEL_ID == 0:
    raise ValueError(
        "Set CHANNEL_ID to your file/database channel ID."
    )

# Four force-subscribe channels.
# The bot will try to create join-request invite links automatically.
FSUB_CHANNELS = [
    (
        int(os.environ["FSUB_CHANNEL_1_ID"]),
        os.getenv("FSUB_CHANNEL_1_LINK", ""),
    ),
    (
        int(os.environ["FSUB_CHANNEL_2_ID"]),
        os.getenv("FSUB_CHANNEL_2_LINK", ""),
    ),
    (
        int(os.environ["FSUB_CHANNEL_3_ID"]),
        os.getenv("FSUB_CHANNEL_3_LINK", ""),
    ),
    (
        int(os.environ["FSUB_CHANNEL_4_ID"]),
        os.getenv("FSUB_CHANNEL_4_LINK", ""),
    ),
]

START_MSG = os.getenv(
    "START_MSG",
    "👋 Hello {first}!\n\nWelcome to the File Sharing Bot."
)

FORCE_MSG = os.getenv(
    "FORCE_MSG",
    "🔒 Please send a join request to all four channels "
    "below to receive your requested file.\n\n"
    "After sending all four requests, the file will be sent automatically."
)

CUSTOM_CAPTION = os.getenv("CUSTOM_CAPTION", "")
PROTECT_CONTENT = (
    os.getenv("PROTECT_CONTENT", "False").lower()
    in ("true", "1", "yes")
)

START_PIC = os.getenv("START_PIC", "")
FORCE_PIC = os.getenv("FORCE_PIC", "")
DISABLE_CHANNEL_BUTTON = (
    os.getenv("DISABLE_CHANNEL_BUTTON", "False").lower()
    in ("true", "1", "yes")
)

TG_BOT_WORKERS = int(os.getenv("TG_BOT_WORKERS", "8"))
PORT = int(os.getenv("PORT", "8080"))
