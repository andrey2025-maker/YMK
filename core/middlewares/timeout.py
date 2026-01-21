from datetime import datetime, timedelta
from typing import Any, Dict, Callable, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from aiogram.dispatcher.flags import get_flag
from aiogram.fsm.context import FSMContext
import structlog

from core.context import AppContext


logger = structlog.get_logger(__name__)


class TimeoutMiddleware(BaseMiddleware):
    """Middleware для обработки таймаута диалогов."""
    
    def __init__(self, context: AppContext):
        super().__init__()
        self.context = context
        self.timeout_seconds = context.config.bot.dialog_timeout
    
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем FSM контекст
        state: FSMContext = data.get("state")
        
        if not state:
            # Если нет состояния, просто передаем дальше
            return await handler(event, data)
        
        # Проверяем, есть ли активное состояние
        current_state = await state.get_state()
        
        if not current_state:
            # Нет активного состояния
            return await handler(event, data)
        
        # Проверяем таймаут
        user_id = event.from_user.id
        state_key = f"fsm_timeout:{user_id}:{current_state}"
        
        try:
            # Получаем время последней активности
            last_active_str = await self.context.redis.get(state_key)
            
            if last_active_str:
                last_active = datetime.fromisoformat(last_active_str)
                time_diff = datetime.now() - last_active
                
                # Проверяем, превышен ли таймаут
                if time_diff.total_seconds() > self.timeout_seconds:
                    # Таймаут превышен, очищаем состояние
                    await state.clear()
                    
                    # Отправляем сообщение о таймауте
                    if isinstance(event, Message):
                        await event.answer("⏱ Диалог завершён по таймауту.")
                    elif isinstance(event, CallbackQuery):
                        await event.answer("⏱ Диалог завершён по таймауту.", show_alert=False)
                    
                    logger.info(
                        "FSM timeout expired",
                        user_id=user_id,
                        state=current_state,
                        time_diff=time_diff.total_seconds()
                    )
                    return
            
            # Обновляем время последней активности
            await self.context.redis.set(
                state_key,
                datetime.now().isoformat(),
                ex=self.timeout_seconds + 300  # Храним немного дольше таймаута
            )
        
        except Exception as e:
            logger.error("Timeout middleware error", error=str(e))
        
        # Продолжаем обработку
        return await handler(event, data)
    
    async def cleanup_expired_sessions(self) -> None:
        """Очищает все просроченные сессии FSM."""
        try:
            # Используем SCAN для поиска всех ключей таймаута
            pattern = "fsm_timeout:*"
            cursor = 0
            expired_keys = []
            
            while True:
                cursor, keys = await self.context.redis.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100
                )
                
                for key in keys:
                    # Проверяем TTL ключа
                    ttl = await self.context.redis.ttl(key)
                    if ttl < 0:
                        expired_keys.append(key)
                
                if cursor == 0:
                    break
            
            # Удаляем просроченные ключи
            if expired_keys:
                await self.context.redis.delete(*expired_keys)
                logger.info(
                    "Expired FSM sessions cleaned up",
                    count=len(expired_keys)
                )
        
        except Exception as e:
            logger.error("Failed to cleanup expired sessions", error=str(e))