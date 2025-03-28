import sys
import asyncio
import logging
import signal
from aiogram import Bot, Dispatcher
from bot.config import load_config
from bot.handlers import routers
from bot.services.database import Database
from bot.services.encryption import CryptoService
from bot.middlewares.basic import DependencyInjectionMiddleware
from bot.services.s3storage import S3Service


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ],
    encoding='utf-8'
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
        s3 = S3Service(config)
        logger.info("Services intialized")

        bot = Bot(token=config.bot_token)
        dp = Dispatcher()

        dp.workflow_data.update({
            "config": config,
            "db": db,
            "crypto": crypto,
            "bot": bot,
            "s3": s3
        })

        dp.update.outer_middleware(DependencyInjectionMiddleware(dp))

        # Подключение роутеров
        for router in routers:
            dp.include_router(router)

        logger.info("Bot starting...")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("Bot stopped gracefully")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")