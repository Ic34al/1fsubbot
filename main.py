import asyncio
from bot import Bot
import pyrogram.utils

# Fix Heroku event loop issue
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

pyrogram.utils.MIN_CHANNEL_ID = -1009147483647

Bot().run()
