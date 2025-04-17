import sys
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter
from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp import ClientTimeout
from bot.config import load_config
from bot.handlers import routers
from bot.services.database import Database
from bot.services.encryption import CryptoService
from bot.middlewares.basic import DependencyInjectionMiddleware
from bot.services.s3storage import S3Service

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ],
    encoding='utf-8'
)
logger = logging.getLogger(__name__)

async def on_startup(bot: Bot, **kwargs):
    logger.info("Bot started successfully")

async def on_shutdown(bot: Bot, **kwargs):
    logger.info("Shutting down bot...")
    await bot.session.close()
    logger.info("Bot shutdown complete")

async def main():
    try:
        config = load_config()
        logger.info("Config loaded")

        # Инициализация сервисов
        db = Database(config)
        await db.connect()
        crypto = CryptoService(config.cryptography_key)
        s3 = S3Service(config)
        logger.info("Services initialized")

        # Создаем сессию с таймаутом в секундах (целое число)
        session = AiohttpSession(timeout=40)  # 40 секунд

        bot = Bot(token=config.bot_token, session=session)
        dp = Dispatcher()

        dp.workflow_data.update({
            "config": config,
            "db": db,
            "crypto": crypto,
            "bot": bot,
            "s3": s3
        })

        dp.message.middleware(DependencyInjectionMiddleware(dp))
        dp.callback_query.middleware(DependencyInjectionMiddleware(dp))

        # Подключение роутеров
        for router in routers:
            dp.include_router(router)

        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)

        logger.info("Bot starting...")

        # Создаем задачу для polling
        polling_task = asyncio.create_task(dp.start_polling(bot, polling_timeout=10))

        # Ожидаем завершения задачи или KeyboardInterrupt
        try:
            await polling_task
        except asyncio.CancelledError:
            logger.info("Received shutdown signal")
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")

    except Exception as e:
        logger.exception(f"Fatal error during bot initialization: {e}")
    finally:
        if 'bot' in locals():
            await bot.session.close()
        logger.info("Bot stopped gracefully")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")