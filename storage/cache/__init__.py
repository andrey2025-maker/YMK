"""
Инициализатор пакета кэширования.
Экспортирует все компоненты для работы с кэшем (Redis и in-memory).
"""
from storage.cache.decorators import (
    cache,
    cache_method,
    invalidate_cache,
    CacheGroup,
    CACHE_STRATEGY_READ,
    CACHE_STRATEGY_WRITE,
    CACHE_STRATEGY_READ_WRITE,
    CACHE_STRATEGY_WRITE_AROUND,
    generate_cache_key
)
from storage.cache.redis_client import RedisClient
from storage.cache.memory_cache import MemoryCache
from storage.cache.manager import CacheManager

__all__ = [
    # Декораторы
    "cache",
    "cache_method", 
    "invalidate_cache",
    "CacheGroup",
    
    # Стратегии кэширования
    "CACHE_STRATEGY_READ",
    "CACHE_STRATEGY_WRITE",
    "CACHE_STRATEGY_READ_WRITE", 
    "CACHE_STRATEGY_WRITE_AROUND",
    
    # Утилиты
    "generate_cache_key",
    
    # Клиенты кэша
    "RedisClient",
    "MemoryCache",
    
    # Менеджер кэша
    "CacheManager"
]


class CacheFactory:
    """
    Фабрика для создания клиентов кэша.
    Позволяет выбирать между Redis и in-memory кэшем в зависимости от окружения.
    """
    
    @staticmethod
    def create_client(config, use_memory_cache: bool = False):
        """
        Создает клиент кэша.
        
        Args:
            config: Конфигурация приложения
            use_memory_cache: Использовать ли in-memory кэш вместо Redis
        
        Returns:
            Экземпляр клиента кэша (RedisClient или MemoryCache)
        """
        if use_memory_cache:
            return MemoryCache(max_size=10000)
        else:
            return RedisClient(config.redis_settings)
    
    @staticmethod
    def create_manager(config, use_memory_cache: bool = False):
        """
        Создает менеджер кэша.
        
        Args:
            config: Конфигурация приложения
            use_memory_cache: Использовать ли in-memory кэш вместо Redis
        
        Returns:
            Экземпляр CacheManager
        """
        client = CacheFactory.create_client(config, use_memory_cache)
        return CacheManager(client, config.redis_settings)