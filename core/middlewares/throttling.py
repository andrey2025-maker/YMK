"""
Middleware для защиты от флуда (rate limiting).
Ограничивает частоту запросов пользователей для защиты от спама и злоупотреблений.
"""

import time
from typing import Any, Callable, Dict, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
import structlog

logger = structlog.get_logger(__name__)


class ThrottlingMiddleware(BaseMiddleware):
    """
    Middleware для ограничения частоты запросов (rate limiting).
    
    Реализует защиту от флуда на основе:
    - Количества сообщений в единицу времени
    - Разных лимитов для разных типов пользователей
    - Автоматического блокирования спамеров
    """
    
    def __init__(self, context):
        """
        Инициализация middleware.
        
        Args:
            context: Контекст приложения с доступом к Redis и конфигурации
        """
        super().__init__()
        self.context = context
        self.config = context.config.throttling
        
        # Настройки по умолчанию (могут быть переопределены в конфиге)
        self.default_limits = {
            'user': {
                'messages_per_minute': 30,  # 30 сообщений в минуту
                'burst_limit': 10,  # Максимум 10 сообщений подряд
                'penalty_time': 30,  # Блокировка на 30 секунд при превышении
            },
            'group': {
                'messages_per_minute': 100,
                'burst_limit': 30,
                'penalty_time': 60,
            },
            'admin': {
                'messages_per_minute': 100,
                'burst_limit': 50,
                'penalty_time': 10,
            }
        }
        
        # Ключи для Redis
        self.REDIS_KEY_PREFIX = "throttle:"
        self.BLOCKED_KEY_PREFIX = "blocked:"
        
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        """
        Основной метод обработки middleware.
        
        Args:
            handler: Следующий обработчик в цепочке
            event: Событие (Message или CallbackQuery)
            data: Данные контекста
            
        Returns:
            Результат обработки или сообщение об ошибке
        """
        # Определяем тип чата
        if hasattr(event, 'chat'):
            chat_type = event.chat.type if event.chat else 'private'
        else:
            chat_type = 'private'
        
        # Определяем ID пользователя
        user_id = event.from_user.id if event.from_user else 0
        
        # Получаем настройки лимитов для этого типа пользователя
        limits = self._get_limits_for_user(user_id, chat_type)
        
        # Проверяем, не заблокирован ли пользователь
        is_blocked = await self._check_if_blocked(user_id)
        if is_blocked:
            return await self._handle_blocked_user(event, user_id)
        
        # Проверяем rate limiting
        should_throttle = await self._check_rate_limit(user_id, limits)
        
        if should_throttle:
            # Применяем блокировку
            await self._apply_throttling(user_id, limits['penalty_time'])
            return await self._handle_throttled_request(event, limits['penalty_time'])
        
        # Обновляем счетчик запросов
        await self._update_request_counter(user_id, limits)
        
        # Пропускаем обработку дальше
        return await handler(event, data)
    
    def _get_limits_for_user(self, user_id: int, chat_type: str) -> Dict:
        """
        Получает лимиты для пользователя.
        
        Args:
            user_id: ID пользователя
            chat_type: Тип чата (private, group, supergroup, channel)
            
        Returns:
            Словарь с настройками лимитов
        """
        # TODO: Добавить проверку является ли пользователь админом
        # из data можно получить информацию о пользователе
        
        # Пока используем базовые настройки
        if chat_type in ['group', 'supergroup']:
            return self.default_limits['group']
        else:
            return self.default_limits['user']
    
    async def _check_if_blocked(self, user_id: int) -> bool:
        """
        Проверяет, заблокирован ли пользователь.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если заблокирован, иначе False
        """
        try:
            blocked_key = f"{self.BLOCKED_KEY_PREFIX}{user_id}"
            is_blocked = await self.context.redis.exists(blocked_key)
            return bool(is_blocked)
        except Exception as e:
            await logger.error("Error checking block status", user_id=user_id, error=str(e))
            return False
    
    async def _check_rate_limit(self, user_id: int, limits: Dict) -> bool:
        """
        Проверяет, превышены ли лимиты запросов.
        
        Args:
            user_id: ID пользователя
            limits: Настройки лимитов
            
        Returns:
            True если лимит превышен, иначе False
        """
        try:
            # Ключи для Redis
            counter_key = f"{self.REDIS_KEY_PREFIX}counter:{user_id}"
            timestamp_key = f"{self.REDIS_KEY_PREFIX}timestamp:{user_id}"
            
            # Получаем текущие значения
            counter = await self.context.redis.get(counter_key)
            timestamp = await self.context.redis.get(timestamp_key)
            
            current_time = int(time.time())
            
            if not counter or not timestamp:
                # Первый запрос или сброс
                return False
            
            counter = int(counter)
            timestamp = int(timestamp)
            
            # Проверяем burst limit (слишком много запросов подряд)
            if counter > limits['burst_limit']:
                await logger.warning(
                    "Burst limit exceeded",
                    user_id=user_id,
                    counter=counter,
                    burst_limit=limits['burst_limit']
                )
                return True
            
            # Проверяем лимит в минуту
            time_diff = current_time - timestamp
            if time_diff < 60:  # В пределах минуты
                # Рассчитываем текущую скорость
                current_rate = counter / (time_diff / 60) if time_diff > 0 else counter * 60
                if current_rate > limits['messages_per_minute']:
                    await logger.warning(
                        "Rate limit exceeded",
                        user_id=user_id,
                        current_rate=current_rate,
                        limit=limits['messages_per_minute']
                    )
                    return True
            
            # Сбрасываем счетчик если прошла минута
            if time_diff >= 60:
                await self.context.redis.delete(counter_key)
                await self.context.redis.delete(timestamp_key)
            
            return False
            
        except Exception as e:
            await logger.error("Error checking rate limit", user_id=user_id, error=str(e))
            return False  # При ошибке пропускаем проверку
    
    async def _update_request_counter(self, user_id: int, limits: Dict) -> None:
        """
        Обновляет счетчик запросов пользователя.
        
        Args:
            user_id: ID пользователя
            limits: Настройки лимитов
        """
        try:
            counter_key = f"{self.REDIS_KEY_PREFIX}counter:{user_id}"
            timestamp_key = f"{self.REDIS_KEY_PREFIX}timestamp:{user_id}"
            
            current_time = int(time.time())
            
            # Увеличиваем счетчик
            await self.context.redis.incr(counter_key)
            
            # Устанавливаем TTL для счетчика (2 минуты)
            await self.context.redis.expire(counter_key, 120)
            
            # Обновляем метку времени если это первый запрос в интервале
            timestamp_exists = await self.context.redis.exists(timestamp_key)
            if not timestamp_exists:
                await self.context.redis.set(timestamp_key, current_time)
                await self.context.redis.expire(timestamp_key, 120)
                
        except Exception as e:
            await logger.error("Error updating request counter", user_id=user_id, error=str(e))
    
    async def _apply_throttling(self, user_id: int, penalty_time: int) -> None:
        """
        Применяет блокировку к пользователю.
        
        Args:
            user_id: ID пользователя
            penalty_time: Время блокировки в секундах
        """
        try:
            blocked_key = f"{self.BLOCKED_KEY_PREFIX}{user_id}"
            await self.context.redis.setex(blocked_key, penalty_time, "1")
            
            # Сбрасываем счетчики
            counter_key = f"{self.REDIS_KEY_PREFIX}counter:{user_id}"
            timestamp_key = f"{self.REDIS_KEY_PREFIX}timestamp:{user_id}"
            await self.context.redis.delete(counter_key, timestamp_key)
            
            await logger.warning(
                "User throttled",
                user_id=user_id,
                penalty_time=penalty_time
            )
            
        except Exception as e:
            await logger.error("Error applying throttling", user_id=user_id, error=str(e))
    
    async def _handle_blocked_user(self, event: Message | CallbackQuery, user_id: int) -> None:
        """
        Обрабатывает запрос от заблокированного пользователя.
        
        Args:
            event: Событие
            user_id: ID пользователя
        """
        # Получаем оставшееся время блокировки
        try:
            blocked_key = f"{self.BLOCKED_KEY_PREFIX}{user_id}"
            ttl = await self.context.redis.ttl(blocked_key)
            
            if ttl > 0:
                if isinstance(event, Message):
                    await event.answer(
                        f"⏳ Вы отправляете сообщения слишком быстро.\n"
                        f"Пожалуйста, подождите {ttl} секунд."
                    )
                
                await logger.debug(
                    "Blocked user request ignored",
                    user_id=user_id,
                    remaining_ttl=ttl
                )
        except Exception as e:
            await logger.error("Error handling blocked user", user_id=user_id, error=str(e))
    
    async def _handle_throttled_request(self, event: Message | CallbackQuery, penalty_time: int) -> None:
        """
        Обрабатывает запрос при срабатывании throttling.
        
        Args:
            event: Событие
            penalty_time: Время блокировки в секундах
        """
        if isinstance(event, Message):
            await event.answer(
                f"⚠️ <b>Слишком много запросов!</b>\n\n"
                f"Вы превысили лимит сообщений.\n"
                f"Подождите {penalty_time} секунд перед следующим запросом.",
                parse_mode="HTML"
            )
        
        await logger.info(
            "Request throttled",
            user_id=event.from_user.id if event.from_user else 0,
            penalty_time=penalty_time
        )
    
    async def reset_user_throttling(self, user_id: int) -> None:
        """
        Сбрасывает throttling для конкретного пользователя.
        
        Args:
            user_id: ID пользователя
        """
        try:
            # Удаляем все ключи связанные с throttling для пользователя
            pattern_counter = f"{self.REDIS_KEY_PREFIX}counter:{user_id}"
            pattern_timestamp = f"{self.REDIS_KEY_PREFIX}timestamp:{user_id}"
            pattern_blocked = f"{self.BLOCKED_KEY_PREFIX}{user_id}"
            
            await self.context.redis.delete(
                pattern_counter,
                pattern_timestamp,
                pattern_blocked
            )
            
            await logger.info("User throttling reset", user_id=user_id)
            
        except Exception as e:
            await logger.error("Error resetting user throttling", user_id=user_id, error=str(e))
    
    async def get_user_stats(self, user_id: int) -> Dict:
        """
        Получает статистику throttling для пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Словарь со статистикой
        """
        stats = {
            'is_blocked': False,
            'blocked_ttl': 0,
            'request_count': 0,
            'timestamp': 0,
        }
        
        try:
            # Проверяем блокировку
            blocked_key = f"{self.BLOCKED_KEY_PREFIX}{user_id}"
            is_blocked = await self.context.redis.exists(blocked_key)
            stats['is_blocked'] = bool(is_blocked)
            
            if stats['is_blocked']:
                stats['blocked_ttl'] = await self.context.redis.ttl(blocked_key)
            
            # Получаем счетчик
            counter_key = f"{self.REDIS_KEY_PREFIX}counter:{user_id}"
            counter = await self.context.redis.get(counter_key)
            stats['request_count'] = int(counter) if counter else 0
            
            # Получаем метку времени
            timestamp_key = f"{self.REDIS_KEY_PREFIX}timestamp:{user_id}"
            timestamp = await self.context.redis.get(timestamp_key)
            stats['timestamp'] = int(timestamp) if timestamp else 0
            
        except Exception as e:
            await logger.error("Error getting user stats", user_id=user_id, error=str(e))
        
        return stats


# Функция для настройки middleware (используется в __init__.py)
def setup_throttling_middleware(dp, context):
    """Настройка throttling middleware."""
    middleware = ThrottlingMiddleware(context)
    dp.update.middleware(middleware)
    return middleware