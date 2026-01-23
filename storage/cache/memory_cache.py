"""
In-memory кэш для тестирования.
Реализует интерфейс кэша идентичный RedisClient, но хранит данные в памяти.
Используется для тестирования без необходимости запуска Redis.
"""
import asyncio
import json
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


class MemoryCache:
    """
    In-memory реализация кэша для тестирования.
    """
    
    def __init__(self, max_size: int = 10000):
        """
        Инициализирует in-memory кэш.
        
        Args:
            max_size: Максимальное количество элементов в кэше
        """
        self.max_size = max_size
        self._cache: Dict[str, Tuple[Any, Optional[float]]] = {}
        self._hash_cache: Dict[str, Dict[str, Any]] = {}
        self._access_order = OrderedDict()
        self._cleanup_lock = asyncio.Lock()
        
        # Запускаем фоновую задачу очистки устаревших записей
        asyncio.create_task(self._periodic_cleanup())
    
    async def _periodic_cleanup(self):
        """
        Периодически очищает устаревшие записи из кэша.
        """
        while True:
            await asyncio.sleep(60)  # Проверяем каждую минуту
            await self._cleanup_expired()
    
    async def _cleanup_expired(self):
        """
        Удаляет устаревшие записи из кэша.
        """
        async with self._cleanup_lock:
            current_time = time.time()
            expired_keys = []
            
            for key, (value, expiry) in self._cache.items():
                if expiry is not None and expiry <= current_time:
                    expired_keys.append(key)
            
            for key in expired_keys:
                self._cache.pop(key, None)
                self._access_order.pop(key, None)
    
    async def _enforce_size_limit(self):
        """
        Обеспечивает соблюдение ограничения по размеру кэша.
        """
        if len(self._cache) > self.max_size:
            # Удаляем самые старые (наименее используемые) записи
            keys_to_remove = []
            for i, key in enumerate(self._access_order):
                if i >= len(self._cache) - self.max_size:
                    break
                keys_to_remove.append(key)
            
            for key in keys_to_remove:
                self._cache.pop(key, None)
                self._access_order.pop(key, None)
    
    async def _update_access_time(self, key: str):
        """
        Обновляет время доступа к ключу.
        
        Args:
            key: Ключ кэша
        """
        if key in self._access_order:
            self._access_order.move_to_end(key)
        else:
            self._access_order[key] = None
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Получает значение по ключу.
        
        Args:
            key: Ключ для получения
            
        Returns:
            Значение или None если ключ не найден или истек
        """
        async with self._cleanup_lock:
            if key not in self._cache:
                return None
            
            value, expiry = self._cache[key]
            
            # Проверяем истек ли TTL
            if expiry is not None and expiry <= time.time():
                self._cache.pop(key, None)
                self._access_order.pop(key, None)
                return None
            
            # Обновляем время доступа
            await self._update_access_time(key)
            
            # Пытаемся десериализовать JSON
            if isinstance(value, str) and value.startswith('json:'):
                try:
                    return json.loads(value[5:])
                except json.JSONDecodeError:
                    return value
            
            return value
    
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
            True если операция успешна
        """
        async with self._cleanup_lock:
            # Сериализуем значение если нужно
            if isinstance(value, (dict, list, tuple, set)):
                value = f"json:{json.dumps(value, default=str)}"
            
            # Вычисляем время истечения
            expiry = None
            if ttl is not None:
                expiry = time.time() + ttl
            
            # Сохраняем значение
            self._cache[key] = (value, expiry)
            await self._update_access_time(key)
            
            # Проверяем ограничение по размеру
            await self._enforce_size_limit()
            
            return True
    
    async def delete(self, key: str) -> bool:
        """
        Удаляет значение по ключу.
        
        Args:
            key: Ключ для удаления
            
        Returns:
            True если удалено, False если ключ не найден
        """
        async with self._cleanup_lock:
            if key in self._cache:
                self._cache.pop(key, None)
                self._access_order.pop(key, None)
                
                # Также удаляем из хэш-кэша если есть
                if key in self._hash_cache:
                    self._hash_cache.pop(key, None)
                
                return True
            
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """
        Удаляет все ключи, соответствующие паттерну.
        
        Args:
            pattern: Паттерн для поиска ключей
            
        Returns:
            Количество удаленных ключей
        """
        async with self._cleanup_lock:
            deleted_count = 0
            
            # Простой pattern matching (только * в конце)
            if pattern.endswith('*'):
                prefix = pattern[:-1]
                keys_to_delete = []
                
                for key in list(self._cache.keys()):
                    if key.startswith(prefix):
                        keys_to_delete.append(key)
                
                for key in keys_to_delete:
                    self._cache.pop(key, None)
                    self._access_order.pop(key, None)
                    
                    if key in self._hash_cache:
                        self._hash_cache.pop(key, None)
                    
                    deleted_count += 1
            else:
                # Точное совпадение
                if pattern in self._cache:
                    self._cache.pop(pattern, None)
                    self._access_order.pop(pattern, None)
                    
                    if pattern in self._hash_cache:
                        self._hash_cache.pop(pattern, None)
                    
                    deleted_count += 1
            
            return deleted_count
    
    async def exists(self, key: str) -> bool:
        """
        Проверяет существование ключа.
        
        Args:
            key: Ключ для проверки
            
        Returns:
            True если ключ существует, False в противном случае
        """
        async with self._cleanup_lock:
            if key not in self._cache:
                return False
            
            # Проверяем истек ли TTL
            _, expiry = self._cache[key]
            if expiry is not None and expiry <= time.time():
                self._cache.pop(key, None)
                self._access_order.pop(key, None)
                return False
            
            return True
    
    async def expire(self, key: str, ttl: int) -> bool:
        """
        Устанавливает время жизни для ключа.
        
        Args:
            key: Ключ
            ttl: Время жизни в секундах
            
        Returns:
            True если операция успешна, False в противном случае
        """
        async with self._cleanup_lock:
            if key not in self._cache:
                return False
            
            value, _ = self._cache[key]
            expiry = time.time() + ttl
            self._cache[key] = (value, expiry)
            
            return True
    
    async def ttl(self, key: str) -> Optional[int]:
        """
        Получает оставшееся время жизни ключа.
        
        Args:
            key: Ключ
            
        Returns:
            Оставшееся время в секундах, -1 если без TTL, None если ключ не найден
        """
        async with self._cleanup_lock:
            if key not in self._cache:
                return None
            
            _, expiry = self._cache[key]
            
            if expiry is None:
                return -1
            
            remaining = expiry - time.time()
            if remaining <= 0:
                # Ключ истек
                self._cache.pop(key, None)
                self._access_order.pop(key, None)
                return None
            
            return int(remaining)
    
    async def keys(self, pattern: str) -> List[str]:
        """
        Находит ключи по паттерну.
        
        Args:
            pattern: Паттерн для поиска
            
        Returns:
            Список найденных ключей
        """
        async with self._cleanup_lock:
            result = []
            current_time = time.time()
            
            # Простой pattern matching (только * в конце)
            if pattern.endswith('*'):
                prefix = pattern[:-1]
                for key in self._cache.keys():
                    # Проверяем не истек ли ключ
                    _, expiry = self._cache[key]
                    if expiry is not None and expiry <= current_time:
                        continue
                    
                    if key.startswith(prefix):
                        result.append(key)
            else:
                # Точное совпадение
                if pattern in self._cache:
                    # Проверяем не истек ли ключ
                    _, expiry = self._cache[pattern]
                    if expiry is None or expiry > current_time:
                        result.append(pattern)
            
            return result
    
    async def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Увеличивает значение ключа на указанное количество.
        
        Args:
            key: Ключ
            amount: Количество для увеличения
            
        Returns:
            Новое значение или None при ошибке
        """
        async with self._cleanup_lock:
            current_value = await self.get(key)
            
            if current_value is None:
                # Ключ не существует, создаем с начальным значением
                new_value = amount
            elif isinstance(current_value, (int, float)):
                new_value = current_value + amount
            else:
                # Нечисловое значение
                return None
            
            await self.set(key, new_value)
            return new_value
    
    async def decr(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Уменьшает значение ключа на указанное количество.
        
        Args:
            key: Ключ
            amount: Количество для уменьшения
            
        Returns:
            Новое значение или None при ошибке
        """
        return await self.incr(key, -amount)
    
    async def hset(self, key: str, field: str, value: Any) -> bool:
        """
        Устанавливает значение поля в хэше.
        
        Args:
            key: Ключ хэша
            field: Поле
            value: Значение
            
        Returns:
            True если операция успешна
        """
        async with self._cleanup_lock:
            if key not in self._hash_cache:
                self._hash_cache[key] = {}
            
            # Сериализуем значение если нужно
            if isinstance(value, (dict, list, tuple, set)):
                value = f"json:{json.dumps(value, default=str)}"
            
            self._hash_cache[key][field] = value
            await self._update_access_time(key)
            
            return True
    
    async def hget(self, key: str, field: str) -> Optional[Any]:
        """
        Получает значение поля из хэша.
        
        Args:
            key: Ключ хэша
            field: Поле
            
        Returns:
            Значение или None если поле не найдено
        """
        async with self._cleanup_lock:
            if key not in self._hash_cache:
                return None
            
            if field not in self._hash_cache[key]:
                return None
            
            value = self._hash_cache[key][field]
            await self._update_access_time(key)
            
            # Пытаемся десериализовать JSON
            if isinstance(value, str) and value.startswith('json:'):
                try:
                    return json.loads(value[5:])
                except json.JSONDecodeError:
                    return value
            
            return value
    
    async def hgetall(self, key: str) -> Dict[str, Any]:
        """
        Получает все поля и значения из хэша.
        
        Args:
            key: Ключ хэша
            
        Returns:
            Словарь полей и значений
        """
        async with self._cleanup_lock:
            if key not in self._hash_cache:
                return {}
            
            result = {}
            for field, value in self._hash_cache[key].items():
                # Пытаемся десериализовать JSON
                if isinstance(value, str) and value.startswith('json:'):
                    try:
                        result[field] = json.loads(value[5:])
                    except json.JSONDecodeError:
                        result[field] = value
                else:
                    result[field] = value
            
            await self._update_access_time(key)
            return result
    
    async def pipeline(self):
        """
        Создает пайплайн для выполнения нескольких команд за одну операцию.
        
        Returns:
            MemoryPipeline объект
        """
        return MemoryPipeline(self)
    
    async def flushdb(self) -> bool:
        """
        Очищает весь кэш.
        
        Returns:
            True если операция успешна
        """
        async with self._cleanup_lock:
            self._cache.clear()
            self._hash_cache.clear()
            self._access_order.clear()
            return True
    
    async def info(self) -> Dict[str, Any]:
        """
        Получает информацию о кэше.
        
        Returns:
            Словарь с информацией
        """
        async with self._cleanup_lock:
            current_time = time.time()
            total_keys = len(self._cache)
            expired_keys = 0
            
            for _, expiry in self._cache.values():
                if expiry is not None and expiry <= current_time:
                    expired_keys += 1
            
            hash_keys = len(self._hash_cache)
            
            return {
                "total_keys": total_keys,
                "expired_keys": expired_keys,
                "hash_keys": hash_keys,
                "max_size": self.max_size,
                "memory_usage": "N/A for memory cache"
            }
    
    async def ping(self) -> bool:
        """
        Проверяет доступность кэша.
        
        Returns:
            Всегда True для in-memory кэша
        """
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Получает статистику использования кэша.
        
        Returns:
            Словарь со статистикой
        """
        return {
            "cache_size": len(self._cache),
            "hash_cache_size": len(self._hash_cache),
            "access_order_size": len(self._access_order),
            "max_size": self.max_size
        }


class MemoryPipeline:
    """
    In-memory реализация пайплайна для тестирования.
    """
    
    def __init__(self, cache: MemoryCache):
        """
        Инициализирует пайплайн.
        
        Args:
            cache: Экземпляр MemoryCache
        """
        self.cache = cache
        self.commands = []
    
    async def get(self, key: str):
        """
        Добавляет команду GET в пайплайн.
        
        Args:
            key: Ключ для получения
            
        Returns:
            Сам пайплайн для цепочки вызовов
        """
        self.commands.append(('get', (key,)))
        return self
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        Добавляет команду SET в пайплайн.
        
        Args:
            key: Ключ для установки
            value: Значение
            ttl: Время жизни
            
        Returns:
            Сам пайплайн для цепочки вызовов
        """
        self.commands.append(('set', (key, value, ttl)))
        return self
    
    async def delete(self, key: str):
        """
        Добавляет команду DELETE в пайплайн.
        
        Args:
            key: Ключ для удаления
            
        Returns:
            Сам пайплайн для цепочки вызовов
        """
        self.commands.append(('delete', (key,)))
        return self
    
    async def execute(self):
        """
        Выполняет все команды в пайплайне.
        
        Returns:
            Список результатов команд
        """
        results = []
        
        for command, args in self.commands:
            method = getattr(self.cache, command)
            result = await method(*args)
            results.append(result)
        
        self.commands.clear()
        return results