import json
import pickle
from typing import Any, Optional, Union, Dict, List, Set
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import structlog

import aioredis


logger = structlog.get_logger(__name__)


class CacheType(Enum):
    """Типы кэша."""
    JSON = "json"
    PICKLE = "pickle"
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    LIST = "list"
    SET = "set"
    HASH = "hash"


class CacheManager:
    """Менеджер кэша Redis."""
    
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self._prefix = "electric_bot"
        self._initialized = False
    
    async def initialize(self) -> None:
        """Инициализирует менеджер кэша."""
        if self._initialized:
            return
        
        try:
            # Проверяем подключение
            await self.redis.ping()
            
            # Инициализируем ключи для статистики
            await self._init_statistics()
            
            self._initialized = True
            logger.info("Cache manager initialized")
            
        except Exception as e:
            logger.error("Cache manager initialization failed", error=str(e))
            raise
    
    async def _init_statistics(self) -> None:
        """Инициализирует статистику кэша."""
        stats_key = self._key("stats")
        if not await self.redis.exists(stats_key):
            stats = {
                "hits": 0,
                "misses": 0,
                "sets": 0,
                "deletes": 0,
                "clears": 0,
                "last_clear": None,
            }
            await self.set(stats_key, stats, expire=None)
    
    def _key(self, key: str) -> str:
        """Добавляет префикс к ключу."""
        return f"{self._prefix}:{key}"
    
    async def set(self, key: str, value: Any, 
                 expire: Optional[int] = 3600,
                 cache_type: CacheType = CacheType.JSON) -> bool:
        """
        Устанавливает значение в кэше.
        
        Args:
            key: Ключ
            value: Значение
            expire: TTL в секундах (None для бессрочного хранения)
            cache_type: Тип сериализации
            
        Returns:
            Успешность операции
        """
        try:
            full_key = self._key(key)
            
            # Сериализуем значение в зависимости от типа
            if cache_type == CacheType.JSON:
                if isinstance(value, (dict, list)):
                    serialized = json.dumps(value, ensure_ascii=False)
                else:
                    serialized = str(value)
            elif cache_type == CacheType.PICKLE:
                serialized = pickle.dumps(value)
            else:
                serialized = str(value)
            
            # Устанавливаем значение
            if expire:
                await self.redis.setex(full_key, expire, serialized)
            else:
                await self.redis.set(full_key, serialized)
            
            # Обновляем статистику
            await self._update_stats("sets")
            
            return True
            
        except Exception as e:
            logger.error("Cache set failed", key=key, error=str(e))
            return False
    
    async def get(self, key: str, 
                 cache_type: CacheType = CacheType.JSON,
                 default: Any = None) -> Any:
        """
        Получает значение из кэша.
        
        Args:
            key: Ключ
            cache_type: Тип десериализации
            default: Значение по умолчанию
            
        Returns:
            Десериализованное значение или default
        """
        try:
            full_key = self._key(key)
            value = await self.redis.get(full_key)
            
            if value is None:
                await self._update_stats("misses")
                return default
            
            # Десериализуем значение в зависимости от типа
            if cache_type == CacheType.JSON:
                try:
                    result = json.loads(value)
                except json.JSONDecodeError:
                    result = value.decode('utf-8')
            elif cache_type == CacheType.PICKLE:
                result = pickle.loads(value)
            else:
                result = value.decode('utf-8')
            
            await self._update_stats("hits")
            return result
            
        except Exception as e:
            logger.error("Cache get failed", key=key, error=str(e))
            return default
    
    async def delete(self, key: str) -> bool:
        """Удаляет ключ из кэша."""
        try:
            full_key = self._key(key)
            deleted = await self.redis.delete(full_key) > 0
            
            if deleted:
                await self._update_stats("deletes")
            
            return deleted
            
        except Exception as e:
            logger.error("Cache delete failed", key=key, error=str(e))
            return False
    
    async def exists(self, key: str) -> bool:
        """Проверяет существование ключа в кэше."""
        try:
            full_key = self._key(key)
            return await self.redis.exists(full_key) > 0
        except Exception as e:
            logger.error("Cache exists check failed", key=key, error=str(e))
            return False
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Устанавливает TTL для ключа."""
        try:
            full_key = self._key(key)
            return await self.redis.expire(full_key, seconds)
        except Exception as e:
            logger.error("Cache expire failed", key=key, error=str(e))
            return False
    
    async def ttl(self, key: str) -> Optional[int]:
        """Получает TTL ключа в секундах."""
        try:
            full_key = self._key(key)
            ttl = await self.redis.ttl(full_key)
            return ttl if ttl >= 0 else None
        except Exception as e:
            logger.error("Cache TTL check failed", key=key, error=str(e))
            return None
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Инкрементирует числовое значение."""
        try:
            full_key = self._key(key)
            return await self.redis.incrby(full_key, amount)
        except Exception as e:
            logger.error("Cache increment failed", key=key, error=str(e))
            return None
    
    async def decrement(self, key: str, amount: int = 1) -> Optional[int]:
        """Декрементирует числовое значение."""
        try:
            full_key = self._key(key)
            return await self.redis.decrby(full_key, amount)
        except Exception as e:
            logger.error("Cache decrement failed", key=key, error=str(e))
            return None
    
    async def get_or_set(self, key: str, getter: callable, 
                        expire: int = 3600,
                        cache_type: CacheType = CacheType.JSON) -> Any:
        """
        Получает значение из кэша или вычисляет и сохраняет его.
        
        Args:
            key: Ключ
            getter: Функция для получения значения если его нет в кэше
            expire: TTL в секундах
            cache_type: Тип сериализации
            
        Returns:
            Значение
        """
        value = await self.get(key, cache_type=cache_type)
        
        if value is None:
            value = await getter() if asyncio.iscoroutinefunction(getter) else getter()
            if value is not None:
                await self.set(key, value, expire, cache_type)
        
        return value
    
    async def clear_by_pattern(self, pattern: str) -> int:
        """
        Очищает кэш по шаблону.
        
        Args:
            pattern: Шаблон для поиска ключей
            
        Returns:
            Количество удаленных ключей
        """
        try:
            full_pattern = self._key(pattern)
            deleted_count = 0
            
            # Используем SCAN для безопасного удаления
            async for key in self.redis.scan_iter(match=full_pattern):
                await self.redis.delete(key)
                deleted_count += 1
            
            if deleted_count > 0:
                await self._update_stats("deletes", amount=deleted_count)
            
            logger.info("Cache cleared by pattern", pattern=pattern, count=deleted_count)
            return deleted_count
            
        except Exception as e:
            logger.error("Cache clear by pattern failed", pattern=pattern, error=str(e))
            return 0
    
    async def clear_all(self, confirmation: bool = False) -> bool:
        """
        Очищает весь кэш бота.
        
        Args:
            confirmation: Требуется подтверждение
            
        Returns:
            Успешность операции
        """
        if confirmation:
            # В реальном использовании нужно запросить подтверждение у пользователя
            pass
        
        try:
            # Очищаем только ключи нашего приложения
            deleted = await self.clear_by_pattern("*")
            
            # Обновляем статистику
            await self._update_stats("clears")
            await self._update_stats("last_clear", datetime.now().isoformat())
            
            logger.info("All cache cleared", deleted_count=deleted)
            return True
            
        except Exception as e:
            logger.error("Cache clear all failed", error=str(e))
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Получает статистику кэша."""
        stats_key = self._key("stats")
        stats = await self.get(stats_key, cache_type=CacheType.JSON, default={})
        
        # Получаем информацию о памяти Redis
        try:
            info = await self.redis.info("memory")
            stats["redis_memory_used"] = info.get("used_memory_human", "N/A")
            stats["redis_keys"] = info.get("db0", {}).get("keys", 0)
        except Exception:
            stats["redis_memory_used"] = "N/A"
            stats["redis_keys"] = 0
        
        # Получаем количество наших ключей
        try:
            our_keys = 0
            async for _ in self.redis.scan_iter(match=f"{self._prefix}:*"):
                our_keys += 1
            stats["our_keys"] = our_keys
        except Exception:
            stats["our_keys"] = 0
        
        return stats
    
    async def _update_stats(self, metric: str, amount: int = 1) -> None:
        """Обновляет статистику кэша."""
        try:
            stats_key = self._key("stats")
            
            if metric == "last_clear":
                await self.redis.hset(stats_key, metric, amount)
            else:
                await self.redis.hincrby(stats_key, metric, amount)
        except Exception as e:
            logger.error("Cache stats update failed", metric=metric, error=str(e))
    
    async def cache_pagination(self, key_prefix: str, data: List[Any], 
                              page_size: int = 10, ttl: int = 600) -> Dict[str, Any]:
        """
        Кэширует данные для пагинации.
        
        Args:
            key_prefix: Префикс для ключей
            data: Данные для кэширования
            page_size: Размер страницы
            ttl: TTL в секундах
            
        Returns:
            Информация о кэшированных данных
        """
        try:
            # Создаем уникальный ID для этой пагинации
            import uuid
            pagination_id = str(uuid.uuid4())
            base_key = f"pagination:{key_prefix}:{pagination_id}"
            
            # Сохраняем метаданные
            metadata = {
                "total_items": len(data),
                "page_size": page_size,
                "total_pages": (len(data) + page_size - 1) // page_size,
                "created_at": datetime.now().isoformat(),
            }
            
            await self.set(f"{base_key}:metadata", metadata, expire=ttl)
            
            # Сохраняем данные по страницам
            for i in range(0, len(data), page_size):
                page_num = i // page_size + 1
                page_data = data[i:i + page_size]
                await self.set(f"{base_key}:page:{page_num}", page_data, expire=ttl)
            
            return {
                "pagination_id": pagination_id,
                "metadata": metadata,
                "base_key": base_key,
            }
            
        except Exception as e:
            logger.error("Pagination cache failed", error=str(e))
            return {}
    
    async def get_pagination_page(self, base_key: str, page_num: int) -> Optional[List[Any]]:
        """
        Получает страницу из кэшированной пагинации.
        
        Args:
            base_key: Базовый ключ пагинации
            page_num: Номер страницы
            
        Returns:
            Данные страницы или None
        """
        try:
            return await self.get(f"{base_key}:page:{page_num}", cache_type=CacheType.JSON)
        except Exception as e:
            logger.error("Get pagination page failed", base_key=base_key, page=page_num, error=str(e))
            return None
    
    async def cleanup_expired_pagination(self) -> int:
        """Очищает просроченные пагинации."""
        try:
            pattern = f"{self._prefix}:pagination:*:metadata"
            deleted = 0
            
            async for key in self.redis.scan_iter(match=pattern):
                # Проверяем TTL метаданных
                ttl = await self.redis.ttl(key)
                if ttl < 0 or ttl < 60:  # Меньше минуты или уже истек
                    # Удаляем все ключи этой пагинации
                    base_key = key.rsplit(":", 1)[0]
                    await self.clear_by_pattern(f"{base_key}:*")
                    deleted += 1
            
            logger.info("Expired pagination cleaned", count=deleted)
            return deleted
            
        except Exception as e:
            logger.error("Cleanup expired pagination failed", error=str(e))
            return 0
    
    async def close(self) -> None:
        """Закрывает соединение с Redis."""
        if self.redis:
            await self.redis.close()
            self._initialized = False
            logger.info("Cache manager closed")