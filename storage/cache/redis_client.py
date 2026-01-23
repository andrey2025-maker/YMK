"""
Redis клиент для кэширования.
Реализует асинхронное взаимодействие с Redis сервером
с поддержкой переподключения и обработкой ошибок.
"""
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Union

import aioredis
from aioredis.exceptions import ConnectionError, RedisError

from config import RedisSettings


logger = logging.getLogger(__name__)


class RedisClient:
    """
    Асинхронный клиент Redis для кэширования.
    """
    
    def __init__(self, settings: RedisSettings):
        """
        Инициализирует Redis клиент.
        
        Args:
            settings: Настройки Redis
        """
        self.settings = settings
        self.redis: Optional[aioredis.Redis] = None
        self.connection_pool: Optional[aioredis.ConnectionPool] = None
        self._connection_lock = asyncio.Lock()
        self.is_connected = False
    
    async def connect(self) -> bool:
        """
        Устанавливает соединение с Redis.
        
        Returns:
            True если подключение успешно, False в противном случае
        """
        async with self._connection_lock:
            if self.is_connected and self.redis:
                try:
                    # Проверяем, что соединение действительно работает
                    await self.redis.ping()
                    return True
                except (ConnectionError, RedisError):
                    # Соединение сломалось, переподключаемся
                    self.is_connected = False
                    if self.redis:
                        await self.redis.close()
                    if self.connection_pool:
                        await self.connection_pool.disconnect()
            
            try:
                # Создаем connection pool
                self.connection_pool = aioredis.ConnectionPool.from_url(
                    self.settings.redis_url,
                    max_connections=self.settings.redis_max_connections,
                    decode_responses=True
                )
                
                # Создаем Redis клиент
                self.redis = aioredis.Redis(connection_pool=self.connection_pool)
                
                # Тестируем подключение
                await self.redis.ping()
                self.is_connected = True
                
                logger.info(f"Successfully connected to Redis at {self.settings.redis_url}")
                return True
                
            except (ConnectionError, RedisError) as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self.is_connected = False
                self.redis = None
                self.connection_pool = None
                return False
    
    async def disconnect(self):
        """
        Закрывает соединение с Redis.
        """
        async with self._connection_lock:
            if self.redis:
                await self.redis.close()
            if self.connection_pool:
                await self.connection_pool.disconnect()
            
            self.redis = None
            self.connection_pool = None
            self.is_connected = False
            logger.info("Disconnected from Redis")
    
    async def ensure_connection(self) -> bool:
        """
        Гарантирует, что соединение с Redis установлено.
        
        Returns:
            True если соединение установлено, False в противном случае
        """
        if not self.is_connected or not self.redis:
            return await self.connect()
        return True
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Получает значение по ключу.
        
        Args:
            key: Ключ для получения
            
        Returns:
            Значение или None если ключ не найден
        """
        if not await self.ensure_connection():
            return None
        
        try:
            value = await self.redis.get(key)
            if value is None:
                return None
            
            # Пытаемся десериализовать JSON если значение в формате json:
            if isinstance(value, str) and value.startswith('json:'):
                try:
                    return json.loads(value[5:])
                except json.JSONDecodeError:
                    return value
            
            return value
            
        except (ConnectionError, RedisError) as e:
            logger.error(f"Redis get error for key {key}: {e}")
            await self._handle_connection_error()
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Устанавливает значение по ключу.
        
        Args:
            key: Ключ для установки
            value: Значение для сохранения
            ttl: Время жизни в секундах (опционально)
            
        Returns:
            True если операция успешна, False в противном случае
        """
        if not await self.ensure_connection():
            return False
        
        try:
            # Сериализуем значение если нужно
            if isinstance(value, (dict, list, tuple, set)):
                value = f"json:{json.dumps(value, default=str)}"
            
            if ttl:
                await self.redis.setex(key, ttl, value)
            else:
                await self.redis.set(key, value)
            
            return True
            
        except (ConnectionError, RedisError) as e:
            logger.error(f"Redis set error for key {key}: {e}")
            await self._handle_connection_error()
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Удаляет значение по ключу.
        
        Args:
            key: Ключ для удаления
            
        Returns:
            True если удалено, False в противном случае
        """
        if not await self.ensure_connection():
            return False
        
        try:
            result = await self.redis.delete(key)
            return result > 0
            
        except (ConnectionError, RedisError) as e:
            logger.error(f"Redis delete error for key {key}: {e}")
            await self._handle_connection_error()
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """
        Удаляет все ключи, соответствующие паттерну.
        
        Args:
            pattern: Паттерн для поиска ключей (например, "cache:*")
            
        Returns:
            Количество удаленных ключей
        """
        if not await self.ensure_connection():
            return 0
        
        try:
            # Находим все ключи по паттерну
            keys = await self.redis.keys(pattern)
            
            if not keys:
                return 0
            
            # Удаляем ключи
            deleted = await self.redis.delete(*keys)
            return deleted
            
        except (ConnectionError, RedisError) as e:
            logger.error(f"Redis delete_pattern error for pattern {pattern}: {e}")
            await self._handle_connection_error()
            return 0
    
    async def exists(self, key: str) -> bool:
        """
        Проверяет существование ключа.
        
        Args:
            key: Ключ для проверки
            
        Returns:
            True если ключ существует, False в противном случае
        """
        if not await self.ensure_connection():
            return False
        
        try:
            return await self.redis.exists(key) > 0
            
        except (ConnectionError, RedisError) as e:
            logger.error(f"Redis exists error for key {key}: {e}")
            await self._handle_connection_error()
            return False
    
    async def expire(self, key: str, ttl: int) -> bool:
        """
        Устанавливает время жизни для ключа.
        
        Args:
            key: Ключ
            ttl: Время жизни в секундах
            
        Returns:
            True если операция успешна, False в противном случае
        """
        if not await self.ensure_connection():
            return False
        
        try:
            return await self.redis.expire(key, ttl)
            
        except (ConnectionError, RedisError) as e:
            logger.error(f"Redis expire error for key {key}: {e}")
            await self._handle_connection_error()
            return False
    
    async def ttl(self, key: str) -> Optional[int]:
        """
        Получает оставшееся время жизни ключа.
        
        Args:
            key: Ключ
            
        Returns:
            Оставшееся время в секундах, -1 если без TTL, None если ключ не найден
        """
        if not await self.ensure_connection():
            return None
        
        try:
            ttl = await self.redis.ttl(key)
            return ttl
            
        except (ConnectionError, RedisError) as e:
            logger.error(f"Redis ttl error for key {key}: {e}")
            await self._handle_connection_error()
            return None
    
    async def keys(self, pattern: str) -> List[str]:
        """
        Находит ключи по паттерну.
        
        Args:
            pattern: Паттерн для поиска
            
        Returns:
            Список найденных ключей
        """
        if not await self.ensure_connection():
            return []
        
        try:
            return await self.redis.keys(pattern)
            
        except (ConnectionError, RedisError) as e:
            logger.error(f"Redis keys error for pattern {pattern}: {e}")
            await self._handle_connection_error()
            return []
    
    async def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Увеличивает значение ключа на указанное количество.
        
        Args:
            key: Ключ
            amount: Количество для увеличения
            
        Returns:
            Новое значение или None при ошибке
        """
        if not await self.ensure_connection():
            return None
        
        try:
            if amount == 1:
                return await self.redis.incr(key)
            else:
                return await self.redis.incrby(key, amount)
            
        except (ConnectionError, RedisError) as e:
            logger.error(f"Redis incr error for key {key}: {e}")
            await self._handle_connection_error()
            return None
    
    async def decr(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Уменьшает значение ключа на указанное количество.
        
        Args:
            key: Ключ
            amount: Количество для уменьшения
            
        Returns:
            Новое значение или None при ошибке
        """
        if not await self.ensure_connection():
            return None
        
        try:
            if amount == 1:
                return await self.redis.decr(key)
            else:
                return await self.redis.decrby(key, amount)
            
        except (ConnectionError, RedisError) as e:
            logger.error(f"Redis decr error for key {key}: {e}")
            await self._handle_connection_error()
            return None
    
    async def hset(self, key: str, field: str, value: Any) -> bool:
        """
        Устанавливает значение поля в хэше.
        
        Args:
            key: Ключ хэша
            field: Поле
            value: Значение
            
        Returns:
            True если операция успешна, False в противном случае
        """
        if not await self.ensure_connection():
            return False
        
        try:
            # Сериализуем значение если нужно
            if isinstance(value, (dict, list, tuple, set)):
                value = f"json:{json.dumps(value, default=str)}"
            
            return await self.redis.hset(key, field, value) > 0
            
        except (ConnectionError, RedisError) as e:
            logger.error(f"Redis hset error for key {key}, field {field}: {e}")
            await self._handle_connection_error()
            return False
    
    async def hget(self, key: str, field: str) -> Optional[Any]:
        """
        Получает значение поля из хэша.
        
        Args:
            key: Ключ хэша
            field: Поле
            
        Returns:
            Значение или None если поле не найдено
        """
        if not await self.ensure_connection():
            return None
        
        try:
            value = await self.redis.hget(key, field)
            if value is None:
                return None
            
            # Пытаемся десериализовать JSON
            if isinstance(value, str) and value.startswith('json:'):
                try:
                    return json.loads(value[5:])
                except json.JSONDecodeError:
                    return value
            
            return value
            
        except (ConnectionError, RedisError) as e:
            logger.error(f"Redis hget error for key {key}, field {field}: {e}")
            await self._handle_connection_error()
            return None
    
    async def hgetall(self, key: str) -> Dict[str, Any]:
        """
        Получает все поля и значения из хэша.
        
        Args:
            key: Ключ хэша
            
        Returns:
            Словарь полей и значений
        """
        if not await self.ensure_connection():
            return {}
        
        try:
            result = await self.redis.hgetall(key)
            decoded_result = {}
            
            for field, value in result.items():
                # Пытаемся десериализовать JSON
                if isinstance(value, str) and value.startswith('json:'):
                    try:
                        decoded_result[field] = json.loads(value[5:])
                    except json.JSONDecodeError:
                        decoded_result[field] = value
                else:
                    decoded_result[field] = value
            
            return decoded_result
            
        except (ConnectionError, RedisError) as e:
            logger.error(f"Redis hgetall error for key {key}: {e}")
            await self._handle_connection_error()
            return {}
    
    async def pipeline(self):
        """
        Создает пайплайн для выполнения нескольких команд за одну операцию.
        
        Returns:
            Redis пайплайн
        """
        if not await self.ensure_connection():
            raise ConnectionError("Not connected to Redis")
        
        try:
            return self.redis.pipeline()
            
        except (ConnectionError, RedisError) as e:
            logger.error(f"Redis pipeline error: {e}")
            await self._handle_connection_error()
            raise
    
    async def flushdb(self) -> bool:
        """
        Очищает текущую базу данных Redis.
        
        Returns:
            True если операция успешна, False в противном случае
        """
        if not await self.ensure_connection():
            return False
        
        try:
            await self.redis.flushdb()
            return True
            
        except (ConnectionError, RedisError) as e:
            logger.error(f"Redis flushdb error: {e}")
            await self._handle_connection_error()
            return False
    
    async def info(self) -> Optional[Dict[str, Any]]:
        """
        Получает информацию о Redis сервере.
        
        Returns:
            Словарь с информацией или None при ошибке
        """
        if not await self.ensure_connection():
            return None
        
        try:
            info_str = await self.redis.info()
            # Преобразуем bytes в строки если нужно
            info_dict = {}
            for key, value in info_str.items():
                if isinstance(value, bytes):
                    info_dict[key] = value.decode('utf-8')
                else:
                    info_dict[key] = value
            
            return info_dict
            
        except (ConnectionError, RedisError) as e:
            logger.error(f"Redis info error: {e}")
            await self._handle_connection_error()
            return None
    
    async def ping(self) -> bool:
        """
        Проверяет соединение с Redis.
        
        Returns:
            True если соединение активно, False в противном случае
        """
        if not await self.ensure_connection():
            return False
        
        try:
            result = await self.redis.ping()
            return result == b"PONG" or result == "PONG"
            
        except (ConnectionError, RedisError):
            self.is_connected = False
            return False
    
    async def _handle_connection_error(self):
        """
        Обрабатывает ошибку соединения.
        Помечает соединение как неактивное для последующей переподключения.
        """
        self.is_connected = False
        logger.warning("Redis connection error, marked as disconnected")