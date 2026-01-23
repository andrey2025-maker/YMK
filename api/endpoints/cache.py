"""
Эндпоинты API для управления кэшем.
Предоставляет REST API для просмотра, очистки и управления кэшем Redis.
"""
from typing import Dict, Any, List, Optional
import asyncio

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from aioredis import Redis

from api.dependencies import (
    get_cache_manager, 
    get_current_admin,
    get_db_session,
    require_permission
)
from storage.cache.manager import CacheManager
from utils.exceptions import CacheError

router = APIRouter()


@router.get("/stats", response_model=Dict[str, Any])
async def get_cache_stats(
    cache_manager: CacheManager = Depends(get_cache_manager),
    current_admin: Dict[str, Any] = Depends(get_current_admin),
    _: bool = Depends(require_permission("admin")),
) -> Dict[str, Any]:
    """
    Получает статистику использования кэша.
    
    Args:
        cache_manager: Менеджер кэша
        current_admin: Текущий администратор
        
    Returns:
        Статистика кэша
    """
    try:
        stats = await cache_manager.get_stats()
        
        return {
            "status": "success",
            "stats": stats,
            "timestamp": asyncio.get_event_loop().time()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting cache stats: {str(e)}"
        )


@router.get("/keys", response_model=Dict[str, Any])
async def get_cache_keys(
    pattern: str = Query("ymk:*", description="Паттерн поиска ключей"),
    limit: int = Query(100, ge=1, le=1000, description="Максимальное количество ключей"),
    cursor: int = Query(0, ge=0, description="Курсор для итерации"),
    cache_manager: CacheManager = Depends(get_cache_manager),
    current_admin: Dict[str, Any] = Depends(get_current_admin),
    _: bool = Depends(require_permission("admin")),
) -> Dict[str, Any]:
    """
    Получает список ключей кэша по паттерну.
    
    Args:
        pattern: Паттерн поиска ключей
        limit: Максимальное количество ключей
        cursor: Курсор для итерации
        cache_manager: Менеджер кэша
        current_admin: Текущий администратор
        
    Returns:
        Список ключей с метаданными
    """
    try:
        # Используем SCAN для безопасного перебора ключей
        keys = []
        next_cursor = 0
        
        async def scan_keys():
            nonlocal next_cursor
            scan_cursor = cursor
            collected = 0
            
            while True:
                # SCAN возвращает новую позицию и список ключей
                scan_cursor, found_keys = await cache_manager.redis.scan(
                    cursor=scan_cursor,
                    match=pattern,
                    count=min(100, limit - collected)
                )
                
                for key in found_keys:
                    if collected >= limit:
                        break
                    
                    # Получаем информацию о ключе
                    try:
                        key_type = await cache_manager.redis.type(key)
                        ttl = await cache_manager.redis.ttl(key)
                        memory = await _estimate_key_size(cache_manager.redis, key)
                        
                        keys.append({
                            "key": key.decode('utf-8') if isinstance(key, bytes) else key,
                            "type": key_type,
                            "ttl": ttl if ttl >= 0 else None,  # -1 означает нет TTL
                            "memory_bytes": memory,
                            "memory_human": _format_bytes(memory),
                        })
                        
                        collected += 1
                        
                    except Exception as key_error:
                        # Пропускаем проблемные ключи
                        continue
                
                if scan_cursor == 0 or collected >= limit:
                    next_cursor = scan_cursor
                    break
        
        await scan_keys()
        
        return {
            "status": "success",
            "pattern": pattern,
            "keys": keys,
            "total_found": len(keys),
            "next_cursor": next_cursor,
            "has_more": next_cursor != 0 and len(keys) >= limit,
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting cache keys: {str(e)}"
        )


@router.get("/keys/{key}", response_model=Dict[str, Any])
async def get_cache_key(
    key: str,
    cache_manager: CacheManager = Depends(get_cache_manager),
    current_admin: Dict[str, Any] = Depends(get_current_admin),
    _: bool = Depends(require_permission("admin")),
) -> Dict[str, Any]:
    """
    Получает значение и информацию о конкретном ключе кэша.
    
    Args:
        key: Ключ кэша
        cache_manager: Менеджер кэша
        current_admin: Текущий администратор
        
    Returns:
        Значение и информация о ключе
    """
    try:
        # Проверяем существование ключа
        exists = await cache_manager.redis.exists(key)
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cache key '{key}' not found"
            )
        
        # Получаем тип ключа
        key_type = await cache_manager.redis.type(key)
        ttl = await cache_manager.redis.ttl(key)
        
        # Получаем значение в зависимости от типа
        value = None
        if key_type == "string":
            value = await cache_manager.redis.get(key)
            if isinstance(value, bytes):
                value = value.decode('utf-8', errors='replace')
        elif key_type == "hash":
            value = await cache_manager.redis.hgetall(key)
            # Декодируем байты
            decoded_value = {}
            for k, v in value.items():
                k_str = k.decode('utf-8', errors='replace') if isinstance(k, bytes) else str(k)
                v_str = v.decode('utf-8', errors='replace') if isinstance(v, bytes) else str(v)
                decoded_value[k_str] = v_str
            value = decoded_value
        elif key_type == "list":
            value = await cache_manager.redis.lrange(key, 0, 100)  # Ограничиваем 100 элементами
            # Декодируем байты
            value = [
                v.decode('utf-8', errors='replace') if isinstance(v, bytes) else str(v)
                for v in value
            ]
        elif key_type == "set":
            value = await cache_manager.redis.smembers(key)
            # Декодируем байты
            value = [
                v.decode('utf-8', errors='replace') if isinstance(v, bytes) else str(v)
                for v in value
            ]
        elif key_type == "zset":
            value = await cache_manager.redis.zrange(key, 0, 100, withscores=True)  # Ограничиваем 100 элементами
            # Декодируем байты
            decoded_value = []
            for member, score in value:
                member_str = member.decode('utf-8', errors='replace') if isinstance(member, bytes) else str(member)
                decoded_value.append({"member": member_str, "score": score})
            value = decoded_value
        
        # Оцениваем размер
        memory = await _estimate_key_size(cache_manager.redis, key)
        
        return {
            "status": "success",
            "key": key,
            "type": key_type,
            "ttl": ttl if ttl >= 0 else None,
            "memory_bytes": memory,
            "memory_human": _format_bytes(memory),
            "value": value,
            "value_preview": _preview_value(value),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting cache key: {str(e)}"
        )


@router.delete("/keys/{key}", response_model=Dict[str, Any])
async def delete_cache_key(
    key: str,
    cache_manager: CacheManager = Depends(get_cache_manager),
    current_admin: Dict[str, Any] = Depends(get_current_admin),
    _: bool = Depends(require_permission("admin")),
) -> Dict[str, Any]:
    """
    Удаляет ключ из кэша.
    
    Args:
        key: Ключ кэша
        cache_manager: Менеджер кэша
        current_admin: Текущий администратор
        
    Returns:
        Результат удаления
    """
    try:
        # Проверяем существование ключа
        exists = await cache_manager.redis.exists(key)
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cache key '{key}' not found"
            )
        
        # Удаляем ключ
        deleted = await cache_manager.redis.delete(key)
        
        return {
            "status": "success",
            "key": key,
            "deleted": deleted > 0,
            "message": f"Cache key '{key}' deleted successfully" if deleted > 0 else f"Cache key '{key}' not deleted"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting cache key: {str(e)}"
        )


@router.post("/clear", response_model=Dict[str, Any])
async def clear_cache(
    pattern: str = Query("ymk:*", description="Паттерн ключей для очистки"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    cache_manager: CacheManager = Depends(get_cache_manager),
    current_admin: Dict[str, Any] = Depends(get_current_admin),
    _: bool = Depends(require_permission("admin")),
) -> Dict[str, Any]:
    """
    Очищает кэш по паттерну.
    Операция выполняется в фоновом режиме для больших объемов данных.
    
    Args:
        pattern: Паттерн ключей для очистки
        background_tasks: Фоновые задачи FastAPI
        cache_manager: Менеджер кэша
        current_admin: Текущий администратор
        
    Returns:
        Результат операции очистки
    """
    try:
        # Считаем количество ключей для очистки
        key_count = await _count_keys_by_pattern(cache_manager.redis, pattern)
        
        if key_count == 0:
            return {
                "status": "success",
                "pattern": pattern,
                "cleared": 0,
                "message": "No keys matching pattern found"
            }
        
        # Для большого количества ключей выполняем в фоне
        if key_count > 1000:
            task_id = f"cache_clear_{asyncio.get_event_loop().time()}"
            
            async def clear_keys_background():
                try:
                    cleared = await _clear_keys_by_pattern(cache_manager.redis, pattern)
                    # Логируем результат
                    cache_manager.logger.info(
                        f"Background cache clear completed: pattern={pattern}, cleared={cleared}"
                    )
                except Exception as e:
                    cache_manager.logger.error(
                        f"Background cache clear failed: {str(e)}"
                    )
            
            background_tasks.add_task(clear_keys_background)
            
            return {
                "status": "started",
                "pattern": pattern,
                "estimated_keys": key_count,
                "task_id": task_id,
                "message": f"Cache clear started in background for {key_count} keys"
            }
        else:
            # Для небольшого количества ключей очищаем сразу
            cleared = await _clear_keys_by_pattern(cache_manager.redis, pattern)
            
            return {
                "status": "success",
                "pattern": pattern,
                "cleared": cleared,
                "message": f"Cleared {cleared} keys from cache"
            }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error clearing cache: {str(e)}"
        )


@router.post("/flush", response_model=Dict[str, Any])
async def flush_cache(
    confirm: bool = Query(False, description="Требуется подтверждение"),
    cache_manager: CacheManager = Depends(get_cache_manager),
    current_admin: Dict[str, Any] = Depends(get_current_admin),
    _: bool = Depends(require_permission("admin")),
) -> Dict[str, Any]:
    """
    Полностью очищает весь кэш Redis.
    ОПАСНАЯ ОПЕРАЦИЯ - требует явного подтверждения.
    
    Args:
        confirm: Флаг подтверждения
        cache_manager: Менеджер кэша
        current_admin: Текущий администратор
        
    Returns:
        Результат операции
    """
    try:
        if not confirm:
            # Считаем общее количество ключей
            total_keys = await cache_manager.redis.dbsize()
            
            return {
                "status": "confirmation_required",
                "total_keys": total_keys,
                "message": "This operation will delete ALL keys from cache. "
                          "Add ?confirm=true to confirm."
            }
        
        # Выполняем FLUSHDB (очищает текущую БД Redis)
        await cache_manager.redis.flushdb()
        
        # Получаем статистику после очистки
        stats = await cache_manager.get_stats()
        
        return {
            "status": "success",
            "flushed": True,
            "message": "Cache flushed successfully",
            "stats_after": stats
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error flushing cache: {str(e)}"
        )


@router.get("/patterns", response_model=Dict[str, Any])
async def get_cache_patterns(
    cache_manager: CacheManager = Depends(get_cache_manager),
    current_admin: Dict[str, Any] = Depends(get_current_admin),
    _: bool = Depends(require_permission("admin")),
) -> Dict[str, Any]:
    """
    Получает список основных паттернов ключей в кэше.
    Полезно для анализа структуры данных.
    
    Args:
        cache_manager: Менеджер кэша
        current_admin: Текущий администратор
        
    Returns:
        Список паттернов с количеством ключей
    """
    try:
        # Основные паттерны системы
        system_patterns = [
            "ymk:fsm:*",           # FSM состояния
            "ymk:cache:*",         # Общий кэш
            "ymk:paginate:*",      # Пагинация
            "ymk:search:*",        # Поиск
            "ymk:rate_limit:*",    # Ограничение запросов
            "ymk:user:*",          # Пользователи
            "ymk:admin:*",         # Админы
            "ymk:service:*",       # Обслуживание
            "ymk:installation:*",  # Монтаж
            "ymk:reminder:*",      # Напоминания
            "ymk:file:*",          # Файлы
            "ymk:log:*",           # Логи
        ]
        
        patterns_info = []
        for pattern in system_patterns:
            try:
                count = await _count_keys_by_pattern(cache_manager.redis, pattern)
                if count > 0:
                    patterns_info.append({
                        "pattern": pattern,
                        "key_count": count,
                        "description": _get_pattern_description(pattern)
                    })
            except Exception:
                continue
        
        # Добавляем пользовательские паттерны (первые 10 по количеству ключей)
        try:
            # Ищем все ключи с префиксом ymk:
            all_keys = []
            cursor = 0
            while True:
                cursor, keys = await cache_manager.redis.scan(
                    cursor=cursor, 
                    match="ymk:*", 
                    count=100
                )
                all_keys.extend(keys)
                if cursor == 0:
                    break
            
            # Анализируем структуру ключей
            from collections import Counter
            pattern_counter = Counter()
            
            for key in all_keys:
                if isinstance(key, bytes):
                    key = key.decode('utf-8', errors='replace')
                
                # Разбиваем ключ на части
                parts = key.split(':')
                if len(parts) >= 3:
                    # Берем первые три части как паттерн
                    pattern = ':'.join(parts[:3]) + ':*'
                    pattern_counter[pattern] += 1
            
            # Добавляем топ пользовательских паттернов
            for pattern, count in pattern_counter.most_common(10):
                if pattern not in [p["pattern"] for p in patterns_info]:
                    patterns_info.append({
                        "pattern": pattern,
                        "key_count": count,
                        "description": "User pattern",
                        "is_system": False
                    })
        
        except Exception:
            pass  # Пропускаем ошибки анализа
        
        return {
            "status": "success",
            "patterns": patterns_info,
            "total_patterns": len(patterns_info),
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting cache patterns: {str(e)}"
        )


# Вспомогательные функции

async def _estimate_key_size(redis: Redis, key: str) -> int:
    """
    Оценивает размер ключа в памяти.
    
    Args:
        redis: Клиент Redis
        key: Ключ
        
    Returns:
        Примерный размер в байтах
    """
    try:
        # Используем команду DEBUG OBJECT (требует настройки Redis)
        # В production лучше использовать memory usage
        debug_info = await redis.execute_command("DEBUG", "OBJECT", key)
        if isinstance(debug_info, bytes):
            debug_info = debug_info.decode('utf-8')
        
        # Парсим вывод DEBUG OBJECT
        for part in debug_info.split():
            if part.startswith('serializedlength:'):
                return int(part.split(':')[1])
        
        # Если не нашли, используем оценку
        key_type = await redis.type(key)
        if key_type == "string":
            value = await redis.get(key)
            return len(value) if value else 0
        else:
            # Для сложных типов возвращаем приблизительную оценку
            return 1024  # 1KB по умолчанию
            
    except Exception:
        return 0  # Не удалось определить размер


async def _count_keys_by_pattern(redis: Redis, pattern: str) -> int:
    """
    Считает количество ключей по паттерну.
    
    Args:
        redis: Клиент Redis
        pattern: Паттерн
        
    Returns:
        Количество ключей
    """
    try:
        count = 0
        cursor = 0
        
        while True:
            cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=100)
            count += len(keys)
            if cursor == 0:
                break
        
        return count
    except Exception:
        return 0


async def _clear_keys_by_pattern(redis: Redis, pattern: str) -> int:
    """
    Очищает ключи по паттерну.
    
    Args:
        redis: Клиент Redis
        pattern: Паттерн
        
    Returns:
        Количество удаленных ключей
    """
    try:
        # Для большого количества ключей используем pipeline
        cleared = 0
        cursor = 0
        
        while True:
            cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=100)
            
            if keys:
                # Удаляем пачкой
                deleted = await redis.delete(*keys)
                cleared += deleted
            
            if cursor == 0 or not keys:
                break
        
        return cleared
    except Exception:
        return 0


def _format_bytes(bytes_num: int) -> str:
    """
    Форматирует байты в читаемый вид.
    
    Args:
        bytes_num: Количество байт
        
    Returns:
        Отформатированная строка
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_num < 1024.0 or unit == 'GB':
            return f"{bytes_num:.2f} {unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.2f} GB"


def _preview_value(value, max_length: int = 200) -> str:
    """
    Создает превью значения для отображения.
    
    Args:
        value: Значение
        max_length: Максимальная длина превью
        
    Returns:
        Строка превью
    """
    if value is None:
        return "None"
    
    if isinstance(value, str):
        if len(value) > max_length:
            return value[:max_length] + "..."
        return value
    
    if isinstance(value, (list, dict)):
        import json
        try:
            preview = json.dumps(value, ensure_ascii=False)
            if len(preview) > max_length:
                return preview[:max_length] + "..."
            return preview
        except:
            return str(type(value))
    
    return str(value)[:max_length]


def _get_pattern_description(pattern: str) -> str:
    """
    Возвращает описание паттерна.
    
    Args:
        pattern: Паттерн ключа
        
    Returns:
        Описание
    """
    descriptions = {
        "ymk:fsm:*": "FSM состояния пользователей",
        "ymk:cache:*": "Общий кэш данных",
        "ymk:paginate:*": "Данные пагинации",
        "ymk:search:*": "Кэш поисковых запросов",
        "ymk:rate_limit:*": "Ограничители запросов",
        "ymk:user:*": "Данные пользователей",
        "ymk:admin:*": "Данные администраторов",
        "ymk:service:*": "Кэш модуля обслуживания",
        "ymk:installation:*": "Кэш модуля монтажа",
        "ymk:reminder:*": "Напоминания и уведомления",
        "ymk:file:*": "Информация о файлах",
        "ymk:log:*": "Логи и история изменений",
    }
    
    return descriptions.get(pattern, "Unknown pattern")