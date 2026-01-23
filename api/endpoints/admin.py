"""
API эндпоинты для администрирования.
Предоставляет REST API для управления администраторами, разрешениями и системой.
"""
import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from pydantic import BaseModel, Field

from core.context import AppContext
from api.dependencies import get_context, verify_admin_token
from utils.exceptions import PermissionException, NotFoundException
from utils.constants import (
    ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN, 
    ADMIN_LEVEL_SERVICE, ADMIN_LEVEL_INSTALLATION
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


# Модели запросов и ответов
class AdminCreateRequest(BaseModel):
    """Запрос на создание администратора."""
    user_id: int = Field(..., description="ID пользователя Telegram")
    username: Optional[str] = Field(None, description="Имя пользователя Telegram")
    full_name: Optional[str] = Field(None, description="Полное имя")
    level: str = Field(..., description="Уровень админа (main_admin, admin, service, installation)")
    created_by: int = Field(..., description="ID создателя")


class AdminResponse(BaseModel):
    """Ответ с информацией об администраторе."""
    id: UUID
    user_id: int
    username: Optional[str]
    full_name: Optional[str]
    level: str
    level_name: str
    created_at: str
    created_by: int
    is_active: bool


class PermissionUpdateRequest(BaseModel):
    """Запрос на обновление разрешений."""
    command_name: str = Field(..., description="Название команды")
    admin_level: str = Field(..., description="Уровень админа")
    allowed_in_private: bool = Field(..., description="Разрешено в ЛС")
    allowed_in_group: bool = Field(..., description="Разрешено в группе")
    updated_by: int = Field(..., description="ID обновившего")


class LogFilter(BaseModel):
    """Фильтр для логов."""
    user_id: Optional[int] = None
    object_type: Optional[str] = None
    object_id: Optional[UUID] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    level: Optional[str] = None
    limit: int = 100
    offset: int = 0


class ExportRequest(BaseModel):
    """Запрос на экспорт данных."""
    data_type: str = Field(..., description="Тип данных (equipment, materials, installation)")
    format: str = Field("excel", description="Формат экспорта (excel, csv, json)")
    filters: Optional[Dict[str, Any]] = None


# Эндпоинты для управления администраторами
@router.get("/admins", response_model=List[AdminResponse])
async def get_admins(
    level: Optional[str] = Query(None, description="Фильтр по уровню"),
    active_only: bool = Query(True, description="Только активные"),
    context: AppContext = Depends(get_context),
    token: dict = Depends(verify_admin_token)
):
    """
    Получает список администраторов.
    
    Args:
        level: Фильтр по уровню админа
        active_only: Только активные администраторы
        context: Контекст приложения
        token: Токен авторизации
    
    Returns:
        Список администраторов
    """
    try:
        # Проверяем права (только главный админ)
        if token.get('level') != ADMIN_LEVEL_MAIN:
            raise PermissionException("Только главный админ может просматривать список админов")
        
        admins = await context.admin_module.admin_manager.get_all_admins(
            level=level,
            active_only=active_only
        )
        
        return [
            AdminResponse(
                id=admin.id,
                user_id=admin.user_id,
                username=admin.username,
                full_name=admin.full_name,
                level=admin.level,
                level_name=context.admin_module.admin_manager.get_level_name(admin.level),
                created_at=admin.created_at.isoformat(),
                created_by=admin.created_by,
                is_active=admin.is_active
            )
            for admin in admins
        ]
        
    except PermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при получении списка админов: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/admins", response_model=AdminResponse, status_code=status.HTTP_201_CREATED)
async def create_admin(
    request: AdminCreateRequest,
    context: AppContext = Depends(get_context),
    token: dict = Depends(verify_admin_token)
):
    """
    Создает нового администратора.
    
    Args:
        request: Данные для создания админа
        context: Контекст приложения
        token: Токен авторизации
    
    Returns:
        Созданный администратор
    """
    try:
        # Проверяем права (только главный админ)
        if token.get('level') != ADMIN_LEVEL_MAIN:
            raise PermissionException("Только главный админ может добавлять админов")
        
        # Создаем администратора
        admin = await context.admin_module.admin_manager.add_admin(
            user_id=request.user_id,
            username=request.username,
            full_name=request.full_name,
            level=request.level,
            created_by=request.created_by
        )
        
        # Логируем действие
        await context.admin_module.log_manager.log_admin_action(
            user_id=request.created_by,
            action=f"create_admin_{request.level}",
            details={
                "target_user_id": request.user_id,
                "target_username": request.username,
                "level": request.level
            }
        )
        
        return AdminResponse(
            id=admin.id,
            user_id=admin.user_id,
            username=admin.username,
            full_name=admin.full_name,
            level=admin.level,
            level_name=context.admin_module.admin_manager.get_level_name(admin.level),
            created_at=admin.created_at.isoformat(),
            created_by=admin.created_by,
            is_active=admin.is_active
        )
        
    except PermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при создании админа: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/admins/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_admin(
    user_id: int,
    deleted_by: int = Query(..., description="ID удаляющего"),
    context: AppContext = Depends(get_context),
    token: dict = Depends(verify_admin_token)
):
    """
    Удаляет администратора.
    
    Args:
        user_id: ID пользователя для удаления
        deleted_by: ID удаляющего
        context: Контекст приложения
        token: Токен авторизации
    """
    try:
        # Проверяем права (только главный админ)
        if token.get('level') != ADMIN_LEVEL_MAIN:
            raise PermissionException("Только главный админ может удалять админов")
        
        # Не позволяем удалить самого себя
        if user_id == deleted_by:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя удалить самого себя"
            )
        
        # Удаляем администратора
        success = await context.admin_module.admin_manager.remove_admin(user_id, deleted_by)
        
        if not success:
            raise NotFoundException(f"Администратор с user_id={user_id} не найден")
        
        # Логируем действие
        await context.admin_module.log_manager.log_admin_action(
            user_id=deleted_by,
            action="delete_admin",
            details={"target_user_id": user_id}
        )
        
    except PermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при удалении админа: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# Эндпоинты для управления разрешениями
@router.get("/permissions")
async def get_permissions(
    level: Optional[str] = Query(None, description="Фильтр по уровню"),
    command: Optional[str] = Query(None, description="Фильтр по команде"),
    context: AppContext = Depends(get_context),
    token: dict = Depends(verify_admin_token)
):
    """
    Получает список разрешений.
    
    Args:
        level: Фильтр по уровню админа
        command: Фильтр по команде
        context: Контекст приложения
        token: Токен авторизации
    
    Returns:
        Список разрешений
    """
    try:
        # Проверяем права (главный админ и админ)
        if token.get('level') not in [ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN]:
            raise PermissionException("Недостаточно прав для просмотра разрешений")
        
        permissions = await context.admin_module.permission_manager.get_permissions(
            admin_level=level,
            command_name=command
        )
        
        return permissions
        
    except PermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при получении разрешений: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/permissions/{command_name}/{admin_level}")
async def update_permission(
    command_name: str,
    admin_level: str,
    request: PermissionUpdateRequest,
    context: AppContext = Depends(get_context),
    token: dict = Depends(verify_admin_token)
):
    """
    Обновляет разрешение для команды.
    
    Args:
        command_name: Название команды
        admin_level: Уровень админа
        request: Данные для обновления
        context: Контекст приложения
        token: Токен авторизации
    
    Returns:
        Обновленное разрешение
    """
    try:
        # Проверяем права (главный админ и админ)
        if token.get('level') not in [ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN]:
            raise PermissionException("Недостаточно прав для обновления разрешений")
        
        # Обновляем разрешение
        permission = await context.admin_module.permission_manager.update_permission(
            command_name=command_name,
            admin_level=admin_level,
            allowed_in_private=request.allowed_in_private,
            allowed_in_group=request.allowed_in_group,
            updated_by=request.updated_by
        )
        
        # Логируем действие
        await context.admin_module.log_manager.log_admin_action(
            user_id=request.updated_by,
            action="update_permission",
            details={
                "command_name": command_name,
                "admin_level": admin_level,
                "allowed_in_private": request.allowed_in_private,
                "allowed_in_group": request.allowed_in_group
            }
        )
        
        return permission
        
    except PermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при обновлении разрешения: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# Эндпоинты для работы с логами
@router.get("/logs/system")
async def get_system_logs(
    user_id: Optional[int] = Query(None, description="Фильтр по ID пользователя"),
    level: Optional[str] = Query(None, description="Фильтр по уровню лога"),
    start_date: Optional[str] = Query(None, description="Начальная дата (ГГГГ-ММ-ДД)"),
    end_date: Optional[str] = Query(None, description="Конечная дата (ГГГГ-ММ-ДД)"),
    limit: int = Query(100, description="Лимит записей"),
    offset: int = Query(0, description="Смещение"),
    context: AppContext = Depends(get_context),
    token: dict = Depends(verify_admin_token)
):
    """
    Получает системные логи.
    
    Args:
        user_id: Фильтр по ID пользователя
        level: Фильтр по уровню лога
        start_date: Начальная дата
        end_date: Конечная дата
        limit: Лимит записей
        offset: Смещение
        context: Контекст приложения
        token: Токен авторизации
    
    Returns:
        Список системных логов
    """
    try:
        # Проверяем права (главный админ и админ)
        if token.get('level') not in [ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN]:
            raise PermissionException("Недостаточно прав для просмотра логов")
        
        logs = await context.admin_module.log_manager.get_system_logs(
            user_id=user_id,
            level=level,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset
        )
        
        return logs
        
    except PermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при получении системных логов: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/logs/changes")
async def get_change_logs(
    object_type: Optional[str] = Query(None, description="Тип объекта"),
    object_id: Optional[UUID] = Query(None, description="ID объекта"),
    user_id: Optional[int] = Query(None, description="Фильтр по ID пользователя"),
    start_date: Optional[str] = Query(None, description="Начальная дата (ГГГГ-ММ-ДД)"),
    end_date: Optional[str] = Query(None, description="Конечная дата (ГГГГ-ММ-ДД)"),
    limit: int = Query(100, description="Лимит записей"),
    offset: int = Query(0, description="Смещение"),
    context: AppContext = Depends(get_context),
    token: dict = Depends(verify_admin_token)
):
    """
    Получает логи изменений.
    
    Args:
        object_type: Тип объекта
        object_id: ID объекта
        user_id: Фильтр по ID пользователя
        start_date: Начальная дата
        end_date: Конечная дата
        limit: Лимит записей
        offset: Смещение
        context: Контекст приложения
        token: Токен авторизации
    
    Returns:
        Список логов изменений
    """
    try:
        # Проверяем права (главный админ и админ)
        if token.get('level') not in [ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN]:
            raise PermissionException("Недостаточно прав для просмотра логов изменений")
        
        logs = await context.admin_module.log_manager.get_change_logs(
            object_type=object_type,
            object_id=object_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset
        )
        
        return logs
        
    except PermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при получении логов изменений: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/logs/search")
async def search_logs(
    filter: LogFilter,
    context: AppContext = Depends(get_context),
    token: dict = Depends(verify_admin_token)
):
    """
    Поиск логов с фильтрацией.
    
    Args:
        filter: Фильтр для поиска
        context: Контекст приложения
        token: Токен авторизации
    
    Returns:
        Найденные логи
    """
    try:
        # Проверяем права (главный админ и админ)
        if token.get('level') not in [ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN]:
            raise PermissionException("Недостаточно прав для поиска логов")
        
        # Получаем все типы логов
        results = {}
        
        # Системные логи
        system_logs = await context.admin_module.log_manager.get_system_logs(
            user_id=filter.user_id,
            level=filter.level,
            start_date=filter.start_date,
            end_date=filter.end_date,
            limit=filter.limit,
            offset=filter.offset
        )
        results['system'] = system_logs
        
        # Логи изменений
        change_logs = await context.admin_module.log_manager.get_change_logs(
            object_type=filter.object_type,
            object_id=filter.object_id,
            user_id=filter.user_id,
            start_date=filter.start_date,
            end_date=filter.end_date,
            limit=filter.limit,
            offset=filter.offset
        )
        results['changes'] = change_logs
        
        return results
        
    except PermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при поиске логов: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# Эндпоинты для экспорта данных
@router.post("/export")
async def export_data(
    request: ExportRequest,
    context: AppContext = Depends(get_context),
    token: dict = Depends(verify_admin_token)
):
    """
    Экспортирует данные в указанном формате.
    
    Args:
        request: Параметры экспорта
        context: Контекст приложения
        token: Токен авторизации
    
    Returns:
        Ссылка на экспортированный файл
    """
    try:
        # Проверяем права (только главный админ)
        if token.get('level') != ADMIN_LEVEL_MAIN:
            raise PermissionException("Только главный админ может экспортировать данные")
        
        # Выполняем экспорт
        export_result = await context.admin_module.export_manager.export_data(
            data_type=request.data_type,
            export_format=request.format,
            filters=request.filters
        )
        
        # Логируем действие
        await context.admin_module.log_manager.log_admin_action(
            user_id=token.get('user_id'),
            action="export_data",
            details={
                "data_type": request.data_type,
                "format": request.format,
                "filters": request.filters
            }
        )
        
        return export_result
        
    except PermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при экспорте данных: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/export/history")
async def get_export_history(
    limit: int = Query(50, description="Лимит записей"),
    offset: int = Query(0, description="Смещение"),
    context: AppContext = Depends(get_context),
    token: dict = Depends(verify_admin_token)
):
    """
    Получает историю экспортов.
    
    Args:
        limit: Лимит записей
        offset: Смещение
        context: Контекст приложения
        token: Токен авторизации
    
    Returns:
        История экспортов
    """
    try:
        # Проверяем права (главный админ и админ)
        if token.get('level') not in [ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN]:
            raise PermissionException("Недостаточно прав для просмотра истории экспортов")
        
        history = await context.admin_module.export_manager.get_export_history(
            limit=limit,
            offset=offset
        )
        
        return history
        
    except PermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при получении истории экспортов: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# Эндпоинты для системной информации
@router.get("/stats")
async def get_admin_stats(
    period_days: int = Query(30, description="Период в днях"),
    context: AppContext = Depends(get_context),
    token: dict = Depends(verify_admin_token)
):
    """
    Получает статистику системы.
    
    Args:
        period_days: Период для статистики
        context: Контекст приложения
        token: Токен авторизации
    
    Returns:
        Статистика системы
    """
    try:
        # Проверяем права (главный админ и админ)
        if token.get('level') not in [ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN]:
            raise PermissionException("Недостаточно прав для просмотра статистики")
        
        stats = {}
        
        # Статистика по администраторам
        admins_stats = await context.admin_module.admin_manager.get_admin_statistics()
        stats['admins'] = admins_stats
        
        # Статистика по логам
        logs_stats = await context.admin_module.log_manager.get_log_statistics(period_days)
        stats['logs'] = logs_stats
        
        # Статистика по экспортам
        export_stats = await context.admin_module.export_manager.get_export_statistics(period_days)
        stats['exports'] = export_stats
        
        return stats
        
    except PermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/system/info")
async def get_system_info(
    context: AppContext = Depends(get_context),
    token: dict = Depends(verify_admin_token)
):
    """
    Получает информацию о системе.
    
    Args:
        context: Контекст приложения
        token: Токен авторизации
    
    Returns:
        Информация о системе
    """
    try:
        # Проверяем права (главный админ и админ)
        if token.get('level') not in [ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN]:
            raise PermissionException("Недостаточно прав для просмотра информации о системе")
        
        info = {
            "bot_name": context.config.bot_name,
            "bot_version": context.config.bot_version,
            "database": {
                "type": "PostgreSQL",
                "schema": "ymk"
            },
            "cache": {
                "type": "Redis",
                "enabled": True
            },
            "modules": {
                "admin": True,
                "service": True,
                "installation": True,
                "file": True,
                "group": True
            },
            "workers": {
                "reminder": True,
                "backup": True,
                "cleanup": True
            }
        }
        
        return info
        
    except PermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при получении информации о системе: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))