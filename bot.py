from pyromod import listen
import logging
from datetime import datetime, timezone

from aiohttp import web
from pyrogram import Client
from pyrogram.enums import ParseMode

from config import (
    API_HASH,
    APP_ID,
    BOT_TOKEN,
    CHANNEL_ID,
    FSUB_CHANNELS,
    TG_BOT_WORKERS,
    PORT,
)

from database import database as db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | "
           "%(name)s | %(message)s",
)

LOGGER = logging.getLogger("FourChannelFSUB")


class Bot(Client):

    def __init__(self):
        super().__init__(
            name="four_channel_fsub_bot",
            api_id=APP_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workers=TG_BOT_WORKERS,
            plugins={"root": "plugins"},
            sleep_threshold=30,
        )

        self.username = None
        self.invite_links = {}

        self.uptime = datetime.now(timezone.utc)
        self.web_runner = None

    async def start(self):
        await super().start()

        me = await self.get_me()
        self.username = me.username

        self.set_parse_mode(ParseMode.HTML)
        
        self.db_channel = await self.get_chat(CHANNEL_ID)

        for channel in FSUB_CHANNELS:
            channel_id = channel["id"]
            link = channel["link"]

            if not link:
                try:
                    invite = await self.create_chat_invite_link(
                        chat_id=channel_id,
                        creates_join_request=True,
                        name=(
                            "File bot request channel "
                            f"{channel['number']}"
                        ),
                    )

                    link = invite.invite_link

                except Exception as exc:
                    LOGGER.exception(
                        "Cannot create request link for %s",
                        channel_id
                    )

                    await super().stop()

                    raise RuntimeError(
                        f"Check admin permissions for "
                        f"FSUB_CHANNEL_{channel['number']}_ID."
                    ) from exc

            self.invite_links[channel_id] = link

        app = web.Application()

        async def health(_request):
            return web.json_response({
                "status": "ok",
                "bot": self.username
            })

        app.router.add_get("/", health)
        app.router.add_get("/health", health)

        self.web_runner = web.AppRunner(app)

        await self.web_runner.setup()

        await web.TCPSite(
            self.web_runner,
            "0.0.0.0",
            PORT
        ).start()

        await db.ping()

        LOGGER.info(
            "Bot @%s started with four FSUB channels.",
            self.username
        )

    async def stop(self, *args):
        if self.web_runner:
            await self.web_runner.cleanup()
            self.web_runner = None

        await db.close()

        await super().stop()

        LOGGER.info("Bot stopped.")


app = Bot()
