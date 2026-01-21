import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager

import structlog
from aiogram import Bot, Dispatcher

from config import config, create_directories
from core.bot import create_bot
from core.context import AppContext
from core.loader import load_modules
from workers.scheduler import create_scheduler


# Настройка структурированного логирования
def setup_logging(level: str = "INFO"):
    """Настраивает структурированное логирование."""
    
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(message)s",
        stream=sys.stdout,
    )
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if config.bot.debug else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    logger = structlog.get_logger(__name__)
    logger.info("Logging configured", level=level)
    return logger


@asynccontextmanager
async def lifespan():
    """Управление жизненным циклом приложения."""
    logger = structlog.get_logger("lifespan")
    
    try:
        logger.info("Starting application...")
        
        # Создаем директории
        create_directories()
        
        # Инициализируем контекст приложения
        context = AppContext()
        await context.initialize()
        
        # Создаем планировщик задач
        scheduler = create_scheduler(context)
        scheduler.start()
        
        yield context
        
    except Exception as e:
        logger.error("Application startup failed", error=str(e), exc_info=True)
        raise
    finally:
        logger.info("Application shutdown complete")


async def main():
    """Основная функция запуска бота."""
    
    # Настраиваем логирование
    logger = setup_logging(config.bot.log_level)
    
    async with lifespan() as context:
        # Создаем бота и диспетчер
        bot, dp = create_bot(context)
        
        # Загружаем модули
        await load_modules(dp, context)
        
        # Регистрируем обработчики сигналов
        def signal_handler():
            logger.info("Received shutdown signal")
            asyncio.create_task(shutdown(bot, dp, context))
        
        signal.signal(signal.SIGINT, lambda s, f: signal_handler())
        signal.signal(signal.SIGTERM, lambda s, f: signal_handler())
        
        # Запускаем бота
        try:
            logger.info("Bot starting...", username=(await bot.get_me()).username)
            await dp.start_polling(bot, context=context)
        except Exception as e:
            logger.error("Bot polling failed", error=str(e), exc_info=True)
            raise


async def shutdown(bot: Bot, dp: Dispatcher, context: AppContext):
    """Корректное завершение работы бота."""
    logger = structlog.get_logger("shutdown")
    
    logger.info("Shutting down bot...")
    
    # Останавливаем polling
    await dp.stop_polling()
    
    # Закрываем сессии БД
    await context.close()
    
    # Закрываем соединения
    await bot.session.close()
    
    logger.info("Bot shutdown complete")
    
    # Завершаем процесс
    sys.exit(0)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)