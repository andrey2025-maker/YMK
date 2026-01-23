"""
Зависимости для FastAPI приложения.
Реализует инъекцию зависимостей, аутентификацию и авторизацию.
"""
from typing import Optional, Dict, Any, AsyncGenerator
from functools import lru_cache

from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.context import AppContext
from storage.models.user import User, Admin, AdminPermission
from storage.cache.manager import CacheManager
from utils.exceptions import AuthenticationError, AuthorizationError

# Глобальная переменная для хранения контекста приложения
_app_context: Optional[AppContext] = None


def set_app_context(context: AppContext):
    """
    Устанавливает контекст приложения для зависимостей.
    
    Args:
        context: Контекст приложения
    """
    global _app_context
    _app_context = context


def get_app_context() -> AppContext:
    """
    Получает контекст приложения.
    
    Returns:
        Контекст приложения
        
    Raises:
        HTTPException: Если контекст не установлен
    """
    if _app_context is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Application context not initialized"
        )
    return _app_context


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Зависимость для получения сессии БД.
    
    Yields:
        Асинхронная сессия БД
    """
    context = get_app_context()
    
    async with context.db_session() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error: {str(e)}"
            )
        finally:
            await session.close()


def get_cache_manager() -> CacheManager:
    """
    Зависимость для получения менеджера кэша.
    
    Returns:
        Менеджер кэша
    """
    context = get_app_context()
    return context.cache_manager


@lru_cache()
def get_api_keys() -> Dict[str, Dict[str, Any]]:
    """
    Получает список валидных API ключей из конфигурации.
    
    Returns:
        Словарь API ключей с метаданными
    """
    context = get_app_context()
    config = context.config
    
    # API ключи хранятся в переменных окружения или БД
    # Формат: API_KEY_1=ключ:уровень:описание
    api_keys = {}
    
    # Пробуем получить из переменных окружения
    import os
    for key, value in os.environ.items():
        if key.startswith("API_KEY_"):
            parts = value.split(":")
            if len(parts) >= 2:
                key_value = parts[0]
                level = parts[1]
                description = parts[2] if len(parts) > 2 else ""
                
                api_keys[key_value] = {
                    "level": level,  # admin, service, installation, read_only
                    "description": description,
                    "env_var": key
                }
    
    return api_keys


async def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """
    Проверяет API ключ в заголовке запроса.
    
    Args:
        x_api_key: API ключ из заголовка
        
    Returns:
        Информация о ключе
        
    Raises:
        HTTPException: Если ключ невалиден
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    api_keys = get_api_keys()
    
    if x_api_key not in api_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    key_info = api_keys[x_api_key]
    
    # Логируем использование ключа
    context = get_app_context()
    context.logger.info(
        f"API key used: {key_info.get('description', 'Unknown')} "
        f"level: {key_info.get('level', 'unknown')}"
    )
    
    return {
        "api_key": x_api_key,
        "level": key_info.get("level"),
        "description": key_info.get("description"),
        "permissions": await _get_permissions_for_level(key_info.get("level"))
    }


async def _get_permissions_for_level(level: str) -> Dict[str, bool]:
    """
    Получает разрешения для уровня доступа API ключа.
    
    Args:
        level: Уровень доступа
        
    Returns:
        Словарь разрешений
    """
    permissions = {
        "read": True,
        "write": False,
        "delete": False,
        "admin": False,
    }
    
    if level == "read_only":
        return permissions
    
    if level == "installation":
        permissions.update({
            "write": True,
            "delete": True,
        })
    
    if level == "service":
        permissions.update({
            "write": True,
            "delete": True,
        })
    
    if level == "admin":
        permissions.update({
            "write": True,
            "delete": True,
            "admin": True,
        })
    
    return permissions


async def get_current_user(
    api_key_info: Dict[str, Any] = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db_session),
) -> Optional[Dict[str, Any]]:
    """
    Получает текущего пользователя по API ключу.
    Для API ключей пользователь может быть не привязан.
    
    Args:
        api_key_info: Информация о API ключе
        db: Сессия БД
        
    Returns:
        Информация о пользователе или None
    """
    # API ключи могут использоваться без привязки к конкретному пользователю
    # Возвращаем информацию об API ключе как "пользователе"
    return {
        "id": 0,  # Специальный ID для API пользователей
        "username": f"api_key_{api_key_info['level']}",
        "role": "api_user",
        "api_key_info": api_key_info,
        "permissions": api_key_info.get("permissions", {}),
    }


async def get_current_admin(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """
    Получает текущего администратора.
    Требует API ключ с уровнем доступа 'admin'.
    
    Args:
        current_user: Текущий пользователь
        db: Сессия БД
        
    Returns:
        Информация об администраторе
        
    Raises:
        HTTPException: Если у пользователя нет прав администратора
    """
    permissions = current_user.get("permissions", {})
    
    if not permissions.get("admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    # Ищем администратора по API ключу или другому идентификатору
    admin_info = {
        "id": current_user["id"],
        "username": current_user["username"],
        "level": "api_admin",
        "permissions": permissions,
    }
    
    return admin_info


async def require_permission(
    permission_type: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> bool:
    """
    Зависимость для проверки конкретного разрешения.
    
    Args:
        permission_type: Тип разрешения (read, write, delete, admin)
        current_user: Текущий пользователь
        
    Returns:
        True если разрешение есть
        
    Raises:
        HTTPException: Если разрешения нет
    """
    permissions = current_user.get("permissions", {})
    
    if not permissions.get(permission_type, False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{permission_type.capitalize()} permission required"
        )
    
    return True


async def require_service_access(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> bool:
    """
    Требует доступ к модулю обслуживания.
    
    Args:
        current_user: Текущий пользователь
        
    Returns:
        True если доступ есть
    """
    permissions = current_user.get("permissions", {})
    
    # Доступ к обслуживанию имеют ключи с уровнями service и admin
    user_level = current_user.get("api_key_info", {}).get("level", "")
    
    if user_level not in ["service", "admin"] and not permissions.get("admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Service module access required"
        )
    
    return True


async def require_installation_access(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> bool:
    """
    Требует доступ к модулю монтажа.
    
    Args:
        current_user: Текущий пользователь
        
    Returns:
        True если доступ есть
    """
    permissions = current_user.get("permissions", {})
    
    # Доступ к монтажу имеют ключи с уровнями installation и admin
    user_level = current_user.get("api_key_info", {}).get("level", "")
    
    if user_level not in ["installation", "admin"] and not permissions.get("admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Installation module access required"
        )
    
    return True


def get_optional_db_session() -> Optional[AsyncSession]:
    """
    Опциональная зависимость для получения сессии БД.
    Возвращает None если БД недоступна.
    
    Returns:
        Сессия БД или None
    """
    try:
        context = get_app_context()
        return context.db_session()
    except Exception:
        return None


def get_optional_cache_manager() -> Optional[CacheManager]:
    """
    Опциональная зависимость для получения менеджера кэша.
    Возвращает None если кэш недоступен.
    
    Returns:
        Менеджер кэша или None
    """
    try:
        context = get_app_context()
        return context.cache_manager
    except Exception:
        return None


# Экспортируем зависимости для использования в эндпоинтах
__all__ = [
    "get_db_session",
    "get_cache_manager",
    "get_current_user",
    "get_current_admin",
    "verify_api_key",
    "require_permission",
    "require_service_access",
    "require_installation_access",
    "get_optional_db_session",
    "get_optional_cache_manager",
    "set_app_context",
]