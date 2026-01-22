from typing import Tuple

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.storage.base import BaseStorage

from core.context import AppContext
from core.middlewares import setup_middlewares  # ← Здесь используется setup_middlewares


def create_bot(context: AppContext) -> Tuple[Bot, Dispatcher]:
    """Создает и настраивает бота и диспетчер."""
    
    # Создаем бота
    bot = Bot(
        token=context.config.bot.token,
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    
    # Создаем хранилище состояний FSM в Redis
    storage: BaseStorage = RedisStorage(
        redis=context.redis,
        state_ttl=context.config.bot.dialog_timeout,  # ← Таймаут 120 минут из конфига
        data_ttl=context.config.bot.dialog_timeout,
    )
    
    # Создаем диспетчер
    dp = Dispatcher(
        storage=storage,
        config=context.config,
        redis=context.redis,
        database=context.database,
        cache=context.cache,
    )
    
    # Настраиваем middleware (← Здесь вызывается setup_middlewares)
    setup_middlewares(dp, context)
    
    return bot, dp