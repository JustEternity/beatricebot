import sys
import asyncio
import logging
from aiogram import Bot, Dispatcher
from bot.config import load_config
from bot.handlers import routers
from bot.services.database import Database
from bot.services.encryption import CryptoService
from bot.handlers.algorithm import router as compatibility_router

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ],
    encoding='utf-8'  # параметр кодировки
)
logger = logging.getLogger(__name__)

async def main():
    try:
        config = load_config()
        logger.info("Config loaded")

        # Инициализация сервисов
        db = Database(config)
        await db.connect()
        crypto = CryptoService(config.cryptography_key)

        bot = Bot(token=config.bot_token)
        dp = Dispatcher()

        # Регистрация зависимостей
        dp["db"] = db
        dp["crypto"] = crypto

        # Подключение роутеров
        for router in routers:
            dp.include_router(router)

        logger.info("Bot starting...")
        await dp.start_polling(bot)

    except Exception as e:
        logger.exception("Critical error")
    finally:
        logger.info("Bot stopped")

if __name__ == "__main__":
    asyncio.run(main())