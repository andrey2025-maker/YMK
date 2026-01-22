"""
Middleware для интеллектуального кэширования часто используемых данных.
Кэширует результаты запросов к БД, снижая нагрузку на базу данных.
"""

import hashlib
import json
from typing import Any, Awaitable, Callable, Dict, Optional
from functools import wraps

from aiogram import BaseMiddleware
from aiogram.types import Update
from aiogram.dispatcher.middlewares.base import NextMiddlewareType

from core.context import AppContext
from structlog import get_logger


class CacheMiddleware(BaseMiddleware):
    """Middleware для кэширования данных"""
    
    def __init__(self, context: AppContext):
        super().__init__()
        self.context = context
        self.logger = get_logger(__name__)
        
        # Настройки кэширования (в секундах)
        self.cache_ttl = {
            "user_data": 300,           # 5 минут
            "admin_permissions": 600,   # 10 минут
            "object_data": 180,         # 3 минуты
            "list_data": 120,           # 2 минуты
            "search_results": 300,      # 5 минут
        }
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        """
        Добавляет кэширование в обработчики.
        
        Args:
            handler: Обработчик события
            event: Событие Telegram
            data: Данные события
            
        Returns:
            Результат обработчика
        """
        # Добавляем менеджер кэша в данные для использования в обработчиках
        data['cache'] = self
        
        # Выполняем обработчик
        return await handler(event, data)
    
    def generate_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """
        Генерирует уникальный ключ кэша на основе аргументов.
        
        Args:
            prefix: Префикс ключа
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
            
        Returns:
            Уникальный ключ кэша
        """
        # Создаем строку из аргументов
        key_parts = [prefix]
        
        # Добавляем позиционные аргументы
        for arg in args:
            key_parts.append(str(arg))
        
        # Добавляем именованные аргументы (отсортированные для консистентности)
        for key in sorted(kwargs.keys()):
            key_parts.append(f"{key}:{kwargs[key]}")
        
        # Создаем строку и хэш
        key_string = ":".join(key_parts)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        
        return f"cache:{prefix}:{key_hash}"
    
    async def get(self, key: str, default: Any = None) -> Any:
        """
        Получает данные из кэша.
        
        Args:
            key: Ключ кэша
            default: Значение по умолчанию
            
        Returns:
            Данные из кэша или default
        """
        try:
            if not hasattr(self.context, 'cache'):
                return default
            
            data = await self.context.cache.get(key)
            if data:
                return json.loads(data.decode())
        except Exception as e:
            self.logger.warning("cache_get_failed", key=key, error=str(e))
        
        return default
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Сохраняет данные в кэш.
        
        Args:
            key: Ключ кэша
            value: Значение для сохранения
            ttl: Время жизни в секундах (None = использовать дефолтное)
            
        Returns:
            True если успешно, False если ошибка
        """
        try:
            if not hasattr(self.context, 'cache'):
                return False
            
            # Определяем TTL на основе префикса ключа
            if ttl is None:
                ttl = self._get_ttl_by_key(key)
            
            # Сериализуем данные
            serialized = json.dumps(value, ensure_ascii=False)
            
            # Сохраняем в кэш
            await self.context.cache.set(key, serialized, ex=ttl)
            return True
        except Exception as e:
            self.logger.warning("cache_set_failed", key=key, error=str(e))
            return False
    
    def _get_ttl_by_key(self, key: str) -> int:
        """
        Определяет TTL на основе префикса ключа.
        
        Args:
            key: Ключ кэша
            
        Returns:
            TTL в секундах
        """
        # Извлекаем префикс из ключа
        parts = key.split(':')
        if len(parts) >= 2:
            cache_type = parts[1]  # Второй элемент после "cache:"
            return self.cache_ttl.get(cache_type, 60)  # Дефолтно 60 секунд
        
        return 60  # Дефолтное значение
    
    async def delete(self, key: str) -> bool:
        """
        Удаляет данные из кэша.
        
        Args:
            key: Ключ кэша
            
        Returns:
            True если успешно, False если ошибка
        """
        try:
            if not hasattr(self.context, 'cache'):
                return False
            
            await self.context.cache.delete(key)
            return True
        except Exception as e:
            self.logger.warning("cache_delete_failed", key=key, error=str(e))
            return False
    
    async def invalidate_by_pattern(self, pattern: str) -> int:
        """
        Удаляет все ключи, соответствующие шаблону.
        
        Args:
            pattern: Шаблон ключа (например, "cache:user:*")
            
        Returns:
            Количество удаленных ключей
        """
        try:
            if not hasattr(self.context, 'cache'):
                return 0
            
            # Используем SCAN для поиска ключей по шаблону
            deleted_count = 0
            cursor = 0
            
            while True:
                cursor, keys = await self.context.cache.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100
                )
                
                if keys:
                    await self.context.cache.delete(*keys)
                    deleted_count += len(keys)
                
                if cursor == 0:
                    break
            
            return deleted_count
        except Exception as e:
            self.logger.warning("cache_invalidate_failed", pattern=pattern, error=str(e))
            return 0
    
    async def get_or_set(self, key: str, ttl: int, coroutine) -> Any:
        """
        Получает данные из кэша или выполняет корутину и сохраняет результат.
        
        Args:
            key: Ключ кэша
            ttl: Время жизни в секундах
            coroutine: Корутина для выполнения если данных нет в кэше
            
        Returns:
            Данные из кэша или результат корутины
        """
        # Пытаемся получить из кэша
        cached_data = await self.get(key)
        if cached_data is not None:
            self.logger.debug("cache_hit", key=key)
            return cached_data
        
        # Данных нет в кэше, выполняем корутину
        self.logger.debug("cache_miss", key=key)
        data = await coroutine
        
        # Сохраняем в кэш
        if data is not None:
            await self.set(key, data, ttl)
        
        return data
    
    async def clear_user_cache(self, user_id: int) -> None:
        """
        Очищает кэш, связанный с пользователем.
        
        Args:
            user_id: ID пользователя
        """
        patterns = [
            f"cache:user:{user_id}:*",
            f"cache:admin:{user_id}:*",
            f"cache:permissions:{user_id}:*",
        ]
        
        for pattern in patterns:
            await self.invalidate_by_pattern(pattern)
    
    async def clear_object_cache(self, object_id: str, object_type: str) -> None:
        """
        Очищает кэш, связанный с объектом.
        
        Args:
            object_id: ID объекта
            object_type: Тип объекта (service, installation)
        """
        patterns = [
            f"cache:{object_type}:object:{object_id}:*",
            f"cache:{object_type}:problems:*",
            f"cache:{object_type}:maintenance:*",
            f"cache:{object_type}:equipment:*",
        ]
        
        for pattern in patterns:
            await self.invalidate_by_pattern(pattern)
    
    def cached(self, ttl: int = 60, key_prefix: str = "func"):
        """
        Декоратор для кэширования результатов функций.
        
        Args:
            ttl: Время жизни кэша в секундах
            key_prefix: Префикс для ключа кэша
            
        Returns:
            Декорированная функция
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Генерируем ключ кэша
                cache_key = self.generate_cache_key(
                    key_prefix,
                    func.__name__,
                    *args,
                    **kwargs
                )
                
                # Используем get_or_set для кэширования
                return await self.get_or_set(
                    cache_key,
                    ttl,
                    func(*args, **kwargs)
                )
            
            return wrapper
        
        return decorator
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Возвращает статистику использования кэша.
        
        Returns:
            Словарь со статистикой
        """
        try:
            if not hasattr(self.context, 'cache'):
                return {}
            
            # Получаем информацию о Redis
            info = await self.context.cache.info()
            
            stats = {
                "used_memory": info.get("used_memory_human", "0"),
                "total_keys": info.get("db0", {}).get("keys", 0),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": 0,
            }
            
            # Рассчитываем hit rate
            total = stats["hits"] + stats["misses"]
            if total > 0:
                stats["hit_rate"] = round((stats["hits"] / total) * 100, 2)
            
            return stats
        except Exception as e:
            self.logger.warning("cache_stats_failed", error=str(e))
            return {}