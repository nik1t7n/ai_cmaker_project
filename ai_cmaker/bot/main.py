import asyncio
from dotenv import load_dotenv
from bot.handlers import start, avatar, script, editing, testing, back, payment, profile
from bot.init import get_bot 


async def main():

    load_dotenv()


    bot, dp = await get_bot()

    # Регистрация роутеров в порядке приоритета
    dp.include_routers(
        start.router,
        avatar.router,
        script.router,
        editing.router,
        testing.router,
        back.router,
        payment.router,
        profile.router,
    )

    # await bot.delete_webhook(drop_pending_updates=True) # из документашки хз зачем
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
