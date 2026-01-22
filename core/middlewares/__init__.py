from aiogram import Dispatcher
from aiogram.dispatcher.middlewares.base import BaseMiddleware

from core.context import AppContext
from .auth import AuthMiddleware
from .fsm_lock import FSMLockMiddleware
from .timeout import TimeoutMiddleware
from .throttling import ThrottlingMiddleware
from .logging import LoggingMiddleware
from .data_collector import DataCollectorMiddleware
from .error import ErrorMiddleware
from .cache_middleware import CacheMiddleware


def setup_middlewares(dp: Dispatcher, context: AppContext) -> None:
    """Настраивает цепочку middleware для диспетчера."""
    
    # Определяем порядок выполнения middleware
    # (чем раньше в списке, тем раньше выполняется)
    middlewares = [
        # 1. Обработка ошибок (должен быть первым, чтобы ловить все ошибки)
        ErrorMiddleware(),
        
        # 2. Логирование - ИСПРАВЛЕНО: добавляем context
        LoggingMiddleware(context),  # ← ДОБАВИЛИ context
        
        # 3. Сбор статистики
        DataCollectorMiddleware(context),
        
        # 4. Кэширование
        CacheMiddleware(context),
        
        # 5. Троттлинг (защита от флуда)
        ThrottlingMiddleware(context),
        
        # 6. Проверка авторизации (сначала проверяем права)
        AuthMiddleware(context),
        
        # 7. Блокировка команд при активном FSM (после проверки прав, но перед таймаутом)
        FSMLockMiddleware(),
        
        # 8. Проверка таймаута диалога (последний перед хендлерами)
        TimeoutMiddleware(context),
    ]
    
    # Устанавливаем middleware в диспетчер
    for middleware in middlewares:
        dp.update.outer_middleware(middleware)
    
    # Логируем настройку middleware
    from structlog import get_logger
    logger = get_logger(__name__)
    logger.info("Middlewares configured", count=len(middlewares))


# Удалите эти строки (они не нужны, так как уже импортированы выше):
# from .logging import LoggingMiddleware, setup_logging_middleware
# 
# __all__ = [
#     # ... здесь уже есть другие middleware
#     'LoggingMiddleware',
#     'setup_logging_middleware',
# ]

# Вместо этого добавьте __all__ для всех middleware:
__all__ = [
    'AuthMiddleware',
    'FSMLockMiddleware',
    'TimeoutMiddleware',
    'ThrottlingMiddleware',
    'LoggingMiddleware',
    'DataCollectorMiddleware',
    'ErrorMiddleware',
    'CacheMiddleware',
    'setup_middlewares',
]