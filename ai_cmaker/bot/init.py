from dotenv import load_dotenv
from aiogram import Bot, Dispatcher 
import os
from aiogram.fsm.storage.redis import RedisStorage

async def get_bot():

    load_dotenv()
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

    storage = RedisStorage.from_url(os.getenv("REDIS_URL", "redis://redis:6379"))

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=storage)
    
    return bot, dp 
