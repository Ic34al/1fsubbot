import os


def env_int(name, default=None):
    value = os.getenv(name)

    if value is None or value.strip() == "":
        if default is None:
            raise RuntimeError(
                f"Missing required environment variable: {name}"
            )
        return int(default)

    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(
            f"{name} must be an integer"
        ) from exc


APP_ID = env_int("APP_ID")
API_HASH = os.environ["API_HASH"].strip()

BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    os.getenv("TG_BOT_TOKEN", "")
).strip()

if not BOT_TOKEN:
    raise RuntimeError(
        "Set BOT_TOKEN in Heroku Config Vars."
    )

MONGO_URI = os.getenv(
    "MONGO_URI",
    os.getenv("DATABASE_URL", "")
).strip()

if not MONGO_URI:
    raise RuntimeError(
        "Set MONGO_URI in Heroku Config Vars."
    )

DATABASE_NAME = os.getenv(
    "DATABASE_NAME",
    "FileBot"
).strip()

OWNER_ID = env_int("OWNER_ID")

ADMINS = {OWNER_ID}

for item in os.getenv("ADMINS", "").replace(" ", ",").split(","):
    if item.strip().isdigit():
        ADMINS.add(int(item.strip()))

CHANNEL_ID = env_int("CHANNEL_ID")

TG_BOT_WORKERS = env_int("TG_BOT_WORKERS", 16)
PORT = env_int("PORT", 8080)

FSUB_CHANNELS = []

for n in range(1, 5):
    channel_id = env_int(f"FSUB_CHANNEL_{n}_ID")
    link = os.getenv(
        f"FSUB_CHANNEL_{n}_LINK",
        ""
    ).strip()

    FSUB_CHANNELS.append({
        "id": channel_id,
        "link": link,
        "number": n
    })

START_MSG = os.getenv(
    "START_MSG",
    "👋 Hello {first}!\n\n"
    "Welcome to the file-sharing bot."
)

FORCE_MSG = os.getenv(
    "FORCE_MSG",
    "🔒 To receive your file, send a join request "
    "to all four channels below.\n\n"
    "Your request counts while it is waiting for approval. "
    "Tap Try Again after sending all four requests."
)

START_PIC = os.getenv("START_PIC", "").strip()
FORCE_PIC = os.getenv("FORCE_PIC", "").strip()

CUSTOM_CAPTION = os.getenv(
    "CUSTOM_CAPTION",
    ""
).strip()

PROTECT_CONTENT = os.getenv(
    "PROTECT_CONTENT",
    "False"
).lower() in ("1", "true", "yes")

DISABLE_CHANNEL_BUTTON = os.getenv(
    "DISABLE_CHANNEL_BUTTON",
    "False"
).lower() in ("1", "true", "yes")
