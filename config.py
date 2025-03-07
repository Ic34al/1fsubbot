#(©)CodeXBotz




import os
import logging
from logging.handlers import RotatingFileHandler



#Bot token @Botfather
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "7396885670:AAHbg3Pt4IJQjZ34BejVJ0cKy50VsPvtWlE")

#Your API ID from my.telegram.org
APP_ID = int(os.environ.get("APP_ID", "22418774"))

#Your API Hash from my.telegram.org
API_HASH = os.environ.get("API_HASH", "d8c8dab274f9a811814a6a96d044028e")

#Your db channel Id
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1002412358436"))

#OWNER ID
OWNER_ID = int(os.environ.get("OWNER_ID", "6064386294"))

#Port
PORT = os.environ.get("PORT", "8080")

#Database 
DB_URI = os.environ.get("DATABASE_URL", "mongodb+srv://admin:AnimeCrewAdmin76@cluster0.qdfs750.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
DB_NAME = os.environ.get("DATABASE_NAME", "filesharexbot")
JOIN_REQS_DB = os.environ.get("JOIN_REQS_DB", DB_URI)
JOIN_REQS_DB2 = os.environ.get("JOIN_REQS_DB2", DB_URI)

#force sub channel id, if you want enable force sub
FORCE_SUB_CHANNEL = int(os.environ.get("FORCE_SUB_CHANNEL", "-1002276001042"))
FORCE_SUB_CHANNEL2 = int(os.environ.get("FORCESUB_CHANNEL2", "-1002296471833"))

START_PIC = os.environ.get("START_PIC", "https://envs.sh/wH9.jpg")
FORCE_PIC = os.environ.get("FORCE_PIC", "https://envs.sh/wHv.jpg")


TG_BOT_WORKERS = int(os.environ.get("TG_BOT_WORKERS", "4"))

#start message
START_MSG = os.environ.get("START_MESSAGE", "Hello {first}\n\nI can store private files in Specified Channel and other users can access it from special link.")
try:
    ADMINS=[]
    for x in (os.environ.get("ADMINS", "5254177746 7328629001").split()):
        ADMINS.append(int(x))
except ValueError:
        raise Exception("Your Admins list does not contain valid integers.")

#Force sub message 
FORCE_MSG = os.environ.get("FORCE_SUB_MESSAGE", "Hello {first}\n\n<b>You need to join in my Channel/Group to use me\n\nKindly Please join Channel</b>")

#set your Custom Caption here, Keep None for Disable Custom Caption
CUSTOM_CAPTION = os.environ.get("CUSTOM_CAPTION", None)

#set True if you want to prevent users from forwarding files from bot
PROTECT_CONTENT = True if os.environ.get('PROTECT_CONTENT', "False") == "True" else False

#Set true if you want Disable your Channel Posts Share button
DISABLE_CHANNEL_BUTTON = os.environ.get("DISABLE_CHANNEL_BUTTON", None) == 'True'

BOT_STATS_TEXT = "<b>BOT UPTIME</b>\n{uptime}"
USER_REPLY_TEXT = "❌Don't send me messages directly I'm only File Share bot!"

ADMINS.append(OWNER_ID)
ADMINS.append(1250450587)

LOG_FILE_NAME = "filesharingbot.txt"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt='%d-%b-%y %H:%M:%S',
    handlers=[
        RotatingFileHandler(
            LOG_FILE_NAME,
            maxBytes=50000000,
            backupCount=10
        ),
        logging.StreamHandler()
    ]
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)


def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
