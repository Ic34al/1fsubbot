import os
import logging
from logging.handlers import RotatingFileHandler


def get_int_env(name, default=None, required=False):
    value = os.environ.get(name)

    if value is None or value.strip() == "":
        if required:
            raise RuntimeError(f"Missing required environment variable: {name}")
        return default

    try:
        return int(value)
    except ValueError:
        raise RuntimeError(f"{name} must be a valid integer.")


# Telegram
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "").strip()
APP_ID = get_int_env("APP_ID", required=True)
API_HASH = os.environ.get("API_HASH", "").strip()

if not TG_BOT_TOKEN:
    raise RuntimeError("Missing required environment variable: TG_BOT_TOKEN")

if not API_HASH:
    raise RuntimeError("Missing required environment variable: API_HASH")


# Database channel
CHANNEL_ID = get_int_env("CHANNEL_ID", required=True)

# Owner
OWNER_ID = get_int_env("OWNER_ID", required=True)

# Web port
PORT = get_int_env("PORT", default=8080)


# MongoDB
DB_URI = os.environ.get("DATABASE_URL", "").strip()
DB_NAME = os.environ.get("DATABASE_NAME", "filesharexbot").strip()

if not DB_URI:
    raise RuntimeError("Missing required environment variable: DATABASE_URL")

JOIN_REQS_DB = os.environ.get("JOIN_REQS_DB", DB_URI).strip()
JOIN_REQS_DB2 = os.environ.get("JOIN_REQS_DB2", DB_URI).strip()


# Force subscription
FORCE_SUB_CHANNEL = get_int_env("FORCE_SUB_CHANNEL", default=0)
FORCE_SUB_CHANNEL2 = get_int_env("FORCE_SUB_CHANNEL2", default=0)


# Images
START_PIC = os.environ.get(
    "START_PIC",
    "https://envs.sh/wH9.jpg"
).strip()

FORCE_PIC = os.environ.get(
    "FORCE_PIC",
    "https://envs.sh/wgj.jpg"
).strip()


# Workers
TG_BOT_WORKERS = get_int_env("TG_BOT_WORKERS", default=8)


# Messages
START_MSG = os.environ.get(
    "START_MESSAGE",
    "Hello {first}\n\n"
    "I can store private files in the specified channel "
    "and users can access them using a special link."
)

FORCE_MSG = os.environ.get(
    "FORCE_SUB_MESSAGE",
    "Hello {first}\n\n"
    "<b>You need to join the required channel(s) to use this bot.</b>"
)


# Admins
ADMINS = []

admins_env = os.environ.get("ADMINS", "").strip()

if admins_env:
    try:
        ADMINS = [int(x) for x in admins_env.split()]
    except ValueError:
        raise RuntimeError(
            "ADMINS must contain only valid numeric Telegram user IDs."
        )

if OWNER_ID not in ADMINS:
    ADMINS.append(OWNER_ID)


# Custom caption
CUSTOM_CAPTION = os.environ.get("CUSTOM_CAPTION", "").strip()


# Content protection
PROTECT_CONTENT = (
    os.environ.get("PROTECT_CONTENT", "False").strip().lower() == "true"
)


# Channel button setting
DISABLE_CHANNEL_BUTTON = (
    os.environ.get("DISABLE_CHANNEL_BUTTON", "False").strip().lower() == "true"
)


BOT_STATS_TEXT = "<b>BOT UPTIME</b>\n{uptime}"

USER_REPLY_TEXT = (
    "❌ Don't send me messages directly. "
    "I'm only a file-sharing bot!"
)


# Logging
LOG_FILE_NAME = "filesharingbot.txt"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler(
            LOG_FILE_NAME,
            maxBytes=50_000_000,
            backupCount=3
        ),
        logging.StreamHandler()
    ]
)

logging.getLogger("pyrogram").setLevel(logging.WARNING)


def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
