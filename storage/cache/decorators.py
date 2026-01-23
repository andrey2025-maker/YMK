"""
Декораторы для кэширования функций.
Реализует автоматическое кэширование результатов функций с поддержкой
инвалидации, TTL и разных стратегий кэширования.
"""
import asyncio
import functools
import hashlib
import inspect
import json
from datetime import timedelta
from typing import Any, Callable, Dict, Optional, TypeVar, Union

from storage.cache.manager import CacheManager

# Типовые переменные для аннотаций
T = TypeVar('T')
R = TypeVar('R')

# Константы для стратегий кэширования
CACHE_STRATEGY_READ = "read"  # Только чтение, не обновляет кэш
CACHE_STRATEGY_WRITE = "write"  # Всегда обновляет кэш
CACHE_STRATEGY_READ_WRITE = "read_write"  # Чтение и обновление кэша
CACHE_STRATEGY_WRITE_AROUND = "write_around"  # Запись в кэш только при промахе


def generate_cache_key(
    func: Callable,
    args: tuple,
    kwargs: Dict[str, Any],
    prefix: Optional[str] = None
) -> str:
    """
    Генерирует уникальный ключ кэша на основе функции и ее аргументов.
    
    Args:
        func: Функция для кэширования
        args: Позиционные аргументы функции
        kwargs: Именованные аргументы функции
        prefix: Префикс ключа (опционально)
    
    Returns:
        Уникальный ключ кэша
    """
    # Получаем имя функции
    func_name = func.__name__
    
    # Создаем строковое представление аргументов
    args_str = str(args)
    
    # Сортируем kwargs для консистентности
    sorted_kwargs = sorted(kwargs.items())
    kwargs_str = str(sorted_kwargs)
    
    # Создаем строку для хэширования
    key_string = f"{func_name}:{args_str}:{kwargs_str}"
    
    # Хэшируем для получения компактного ключа
    key_hash = hashlib.md5(key_string.encode('utf-8')).hexdigest()
    
    # Формируем итоговый ключ
    cache_key = f"cache:{func.__module__}:{func_name}:{key_hash}"
    
    if prefix:
        cache_key = f"{prefix}:{cache_key}"
    
    return cache_key


def cache(
    ttl: Optional[Union[int, timedelta]] = 300,
    key_prefix: Optional[str] = None,
    strategy: str = CACHE_STRATEGY_READ_WRITE,
    namespace: Optional[str] = None,
    cache_condition: Optional[Callable[..., bool]] = None,
    invalidate_on_call: bool = False
):
    """
    Декоратор для кэширования результатов функций.
    
    Args:
        ttl: Время жизни кэша в секундах или как timedelta
        key_prefix: Префикс для ключей кэша
        strategy: Стратегия кэширования (read/write/read_write/write_around)
        namespace: Пространство имен для кэша
        cache_condition: Функция, определяющая нужно ли кэшировать результат
        invalidate_on_call: Инвалидировать кэш при вызове функции
    
    Returns:
        Декорированная функция
    """
    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        # Определяем, асинхронная ли функция
        is_async = asyncio.iscoroutinefunction(func)
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> R:
            # Получаем экземпляр менеджера кэша из первого аргумента если есть
            cache_manager = None
            if args and hasattr(args[0], 'cache_manager'):
                cache_manager = getattr(args[0], 'cache_manager', None)
            
            if not cache_manager:
                # Пытаемся получить из контекста приложения
                try:
                    from core.context import AppContext
                    app_context = AppContext.get_instance()
                    cache_manager = app_context.cache_manager
                except (ImportError, AttributeError):
                    # Если не удалось получить менеджер кэша, просто выполняем функцию
                    return await func(*args, **kwargs)
            
            # Генерируем ключ кэша
            cache_key = generate_cache_key(func, args, kwargs, key_prefix)
            
            if namespace:
                cache_key = f"{namespace}:{cache_key}"
            
            # Проверяем условие кэширования
            if cache_condition and not cache_condition(*args, **kwargs):
                # Условие не выполнено, выполняем функцию без кэширования
                return await func(*args, **kwargs)
            
            # Инвалидация кэша при вызове
            if invalidate_on_call:
                await cache_manager.delete(cache_key)
                return await func(*args, **kwargs)
            
            # Чтение из кэша (для стратегий read и read_write)
            if strategy in [CACHE_STRATEGY_READ, CACHE_STRATEGY_READ_WRITE]:
                cached_value = await cache_manager.get(cache_key)
                if cached_value is not None:
                    # Десериализуем значение если нужно
                    if isinstance(cached_value, str) and cached_value.startswith('json:'):
                        try:
                            return json.loads(cached_value[5:])
                        except json.JSONDecodeError:
                            return cached_value
                    return cached_value
            
            # Выполняем функцию
            result = await func(*args, **kwargs)
            
            # Запись в кэш (для стратегий write, read_write и write_around при промахе)
            should_cache = (
                strategy in [CACHE_STRATEGY_WRITE, CACHE_STRATEGY_READ_WRITE] or
                (strategy == CACHE_STRATEGY_WRITE_AROUND and cached_value is None)
            )
            
            if should_cache:
                # Сериализуем значение если нужно
                cache_value = result
                if isinstance(result, (dict, list, tuple, set)):
                    cache_value = f"json:{json.dumps(result, default=str)}"
                
                # Преобразуем ttl в секунды если это timedelta
                ttl_seconds = ttl
                if isinstance(ttl, timedelta):
                    ttl_seconds = int(ttl.total_seconds())
                
                await cache_manager.set(cache_key, cache_value, ttl=ttl_seconds)
            
            return result
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> R:
            # Для синхронных функций пока не поддерживаем кэширование
            # В будущем можно добавить поддержку через запуск в event loop
            return func(*args, **kwargs)
        
        return async_wrapper if is_async else sync_wrapper
    
    return decorator


def invalidate_cache(
    key_pattern: Optional[str] = None,
    namespace: Optional[str] = None,
    func_reference: Optional[Callable] = None
):
    """
    Декоратор для инвалидации кэша при вызове функции.
    
    Args:
        key_pattern: Шаблон ключа для инвалидации
        namespace: Пространство имен для поиска ключей
        func_reference: Ссылка на функцию, кэш которой нужно инвалидировать
    
    Returns:
        Декорированная функция
    """
    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        is_async = asyncio.iscoroutinefunction(func)
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> R:
            # Получаем менеджер кэша
            cache_manager = None
            if args and hasattr(args[0], 'cache_manager'):
                cache_manager = getattr(args[0], 'cache_manager', None)
            
            if not cache_manager:
                try:
                    from core.context import AppContext
                    app_context = AppContext.get_instance()
                    cache_manager = app_context.cache_manager
                except (ImportError, AttributeError):
                    pass
            
            # Выполняем функцию
            result = await func(*args, **kwargs)
            
            # Инвалидируем кэш если есть менеджер
            if cache_manager:
                if func_reference:
                    # Генерируем ключ на основе функции
                    cache_key = generate_cache_key(func_reference, args, kwargs)
                    if namespace:
                        cache_key = f"{namespace}:{cache_key}"
                    await cache_manager.delete(cache_key)
                elif key_pattern:
                    # Ищем ключи по шаблону
                    pattern = key_pattern
                    if namespace:
                        pattern = f"{namespace}:{pattern}"
                    await cache_manager.delete_pattern(pattern)
            
            return result
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> R:
            # Для синхронных функций
            return func(*args, **kwargs)
        
        return async_wrapper if is_async else sync_wrapper
    
    return decorator


def cache_method(
    ttl: Optional[Union[int, timedelta]] = 300,
    key_prefix: Optional[str] = None
):
    """
    Специальный декоратор для кэширования методов класса.
    
    Args:
        ttl: Время жизни кэша
        key_prefix: Префикс для ключей кэша
    
    Returns:
        Декорированный метод
    """
    def decorator(method: Callable[..., R]) -> Callable[..., R]:
        @functools.wraps(method)
        async def wrapper(self, *args, **kwargs) -> R:
            # Проверяем наличие менеджера кэша в классе
            if not hasattr(self, 'cache_manager'):
                # Если нет менеджера кэша, пытаемся получить из контекста
                try:
                    from core.context import AppContext
                    app_context = AppContext.get_instance()
                    self.cache_manager = app_context.cache_manager
                except (ImportError, AttributeError):
                    # Если не удалось, просто выполняем метод
                    return await method(self, *args, **kwargs)
            
            # Генерируем ключ с учетом self
            class_name = self.__class__.__name__
            method_name = method.__name__
            
            # Создаем строковое представление self (без циклических ссылок)
            self_repr = f"{class_name}:{id(self)}"
            
            # Формируем ключ
            cache_key_parts = [
                "method",
                class_name,
                method_name,
                self_repr,
                str(args),
                str(sorted(kwargs.items()))
            ]
            
            cache_key_string = ":".join(cache_key_parts)
            key_hash = hashlib.md5(cache_key_string.encode('utf-8')).hexdigest()
            
            cache_key = f"cache:{key_hash}"
            if key_prefix:
                cache_key = f"{key_prefix}:{cache_key}"
            
            # Пытаемся получить из кэша
            cached_value = await self.cache_manager.get(cache_key)
            if cached_value is not None:
                if isinstance(cached_value, str) and cached_value.startswith('json:'):
                    try:
                        return json.loads(cached_value[5:])
                    except json.JSONDecodeError:
                        return cached_value
                return cached_value
            
            # Выполняем метод
            result = await method(self, *args, **kwargs)
            
            # Сохраняем в кэш
            cache_value = result
            if isinstance(result, (dict, list, tuple, set)):
                cache_value = f"json:{json.dumps(result, default=str)}"
            
            ttl_seconds = ttl
            if isinstance(ttl, timedelta):
                ttl_seconds = int(ttl.total_seconds())
            
            await self.cache_manager.set(cache_key, cache_value, ttl=ttl_seconds)
            
            return result
        
        return wrapper
    
    return decorator


class CacheGroup:
    """
    Класс для группового управления кэшем.
    Позволяет инвалидировать группу связанных ключей кэша.
    """
    
    def __init__(self, namespace: str, cache_manager: CacheManager):
        """
        Инициализирует группу кэша.
        
        Args:
            namespace: Пространство имен группы
            cache_manager: Менеджер кэша
        """
        self.namespace = namespace
        self.cache_manager = cache_manager
        self.keys = set()
    
    async def add_key(self, key: str):
        """
        Добавляет ключ в группу.
        
        Args:
            key: Ключ кэша
        """
        full_key = f"{self.namespace}:group:{key}"
        self.keys.add(full_key)
        
        # Сохраняем связь ключа с группой
        await self.cache_manager.set(
            f"{self.namespace}:key:{key}",
            self.namespace,
            ttl=86400  # 24 часа
        )
    
    async def invalidate_group(self):
        """
        Инвалидирует все ключи в группе.
        """
        for key in self.keys:
            await self.cache_manager.delete(key)
        
        # Очищаем список ключей
        self.keys.clear()
        
        # Находим и удаляем все ключи группы по паттерну
        pattern = f"{self.namespace}:key:*"
        group_keys = await self.cache_manager.keys(pattern)
        
        for key in group_keys:
            await self.cache_manager.delete(key)
    
    @classmethod
    async def invalidate_namespace(
        cls,
        namespace: str,
        cache_manager: CacheManager
    ):
        """
        Инвалидирует все ключи в пространстве имен.
        
        Args:
            namespace: Пространство имен
            cache_manager: Менеджер кэша
        """
        pattern = f"{namespace}:*"
        keys = await cache_manager.keys(pattern)
        
        for key in keys:
            await cache_manager.delete(key)