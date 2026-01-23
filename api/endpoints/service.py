"""
API эндпоинты для обслуживания объектов.
Предоставляет REST API для управления регионами, объектами и их подразделами.
"""
import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body, Path
from pydantic import BaseModel, Field

from core.context import AppContext
from api.dependencies import get_context, verify_service_token
from utils.exceptions import PermissionException, NotFoundException, ValidationException
from utils.constants import (
    ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN, ADMIN_LEVEL_SERVICE,
    OBJECT_TYPE_SERVICE_REGION, OBJECT_TYPE_SERVICE_OBJECT
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/service", tags=["service"])


# Модели запросов и ответов
class RegionCreateRequest(BaseModel):
    """Запрос на создание региона."""
    short_name: str = Field(..., description="Короткое название", max_length=50)
    full_name: str = Field(..., description="Полное название", max_length=200)
    created_by: int = Field(..., description="ID создателя")


class RegionResponse(BaseModel):
    """Ответ с информацией о регионе."""
    id: UUID
    short_name: str
    full_name: str
    created_at: str
    created_by: int
    object_count: int = 0
    is_active: bool


class ObjectCreateRequest(BaseModel):
    """Запрос на создание объекта."""
    region_id: UUID = Field(..., description="ID региона")
    short_name: str = Field(..., description="Короткое название", max_length=100)
    full_name: str = Field(..., description="Полное название", max_length=200)
    addresses: List[str] = Field(..., description="Список адресов")
    document_type: str = Field(..., description="Тип документа")
    contract_number: str = Field(..., description="Номер контракта", max_length=50)
    contract_date: str = Field(..., description="Дата контракта (ДД.ММ.ГГГГ)")
    start_date: str = Field(..., description="Дата начала (ДД.ММ.ГГГГ)")
    end_date: str = Field(..., description="Дата окончания (ДД.ММ.ГГГГ)")
    systems: List[str] = Field(..., description="Обслуживаемые системы")
    zip_info: str = Field(..., description="Информация о ЗИП")
    has_dispatch: bool = Field(..., description="Наличие диспетчеризации")
    notes: Optional[str] = Field(None, description="Примечания")
    responsible_user_id: Optional[int] = Field(None, description="ID ответственного")
    created_by: int = Field(..., description="ID создателя")


class ObjectResponse(BaseModel):
    """Ответ с информацией об объекте."""
    id: UUID
    region_id: UUID
    short_name: str
    full_name: str
    addresses: List[str]
    document_type: str
    contract_number: str
    contract_date: str
    start_date: str
    end_date: str
    systems: List[str]
    zip_info: str
    has_dispatch: bool
    notes: Optional[str]
    responsible_user_id: Optional[int]
    created_at: str
    created_by: int
    is_active: bool
    problem_count: int = 0
    maintenance_count: int = 0
    equipment_count: int = 0


class ProblemCreateRequest(BaseModel):
    """Запрос на создание проблемы."""
    object_id: UUID = Field(..., description="ID объекта")
    description: str = Field(..., description="Описание проблемы")
    severity: str = Field("medium", description="Серьезность (low, medium, high, critical)")
    created_by: int = Field(..., description="ID создателя")
    file_url: Optional[str] = Field(None, description="URL прикрепленного файла")


class ProblemResponse(BaseModel):
    """Ответ с информацией о проблеме."""
    id: UUID
    object_id: UUID
    description: str
    severity: str
    status: str
    created_at: str
    created_by: int
    resolved_at: Optional[str]
    resolved_by: Optional[int]
    file_url: Optional[str]


class EquipmentCreateRequest(BaseModel):
    """Запрос на создание оборудования."""
    object_id: UUID = Field(..., description="ID объекта")
    address_index: Optional[int] = Field(None, description="Индекс адреса (если несколько)")
    name: str = Field(..., description="Наименование оборудования")
    quantity: float = Field(..., description="Количество")
    unit: str = Field(..., description="Единица измерения")
    description: Optional[str] = Field(None, description="Описание")
    created_by: int = Field(..., description="ID создателя")


class SearchRequest(BaseModel):
    """Запрос на поиск."""
    query: str = Field(..., description="Поисковый запрос")
    search_type: Optional[str] = Field(None, description="Тип поиска (regions, objects, problems, equipment)")
    region_id: Optional[UUID] = Field(None, description="Фильтр по региону")
    limit: int = Field(50, description="Лимит результатов")
    offset: int = Field(0, description="Смещение")


# Эндпоинты для регионов
@router.get("/regions", response_model=List[RegionResponse])
async def get_regions(
    active_only: bool = Query(True, description="Только активные"),
    context: AppContext = Depends(get_context),
    token: dict = Depends(verify_service_token)
):
    """
    Получает список регионов обслуживания.
    
    Args:
        active_only: Только активные регионы
        context: Контекст приложения
        token: Токен авторизации
    
    Returns:
        Список регионов
    """
    try:
        # Проверяем права (сервис и выше)
        if token.get('level') not in [ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN, ADMIN_LEVEL_SERVICE]:
            raise PermissionException("Недостаточно прав для просмотра регионов")
        
        regions = await context.service_module.region_manager.get_all_regions(active_only)
        
        # Добавляем количество объектов для каждого региона
        regions_with_counts = []
        for region in regions:
            object_count = await context.service_module.object_manager.get_objects_count_by_region(region.id)
            regions_with_counts.append({
                **region.dict(),
                "object_count": object_count
            })
        
        return regions_with_counts
        
    except PermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при получении регионов: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/regions", response_model=RegionResponse, status_code=status.HTTP_201_CREATED)
async def create_region(
    request: RegionCreateRequest,
    context: AppContext = Depends(get_context),
    token: dict = Depends(verify_service_token)
):
    """
    Создает новый регион обслуживания.
    
    Args:
        request: Данные для создания региона
        context: Контекст приложения
        token: Токен авторизации
    
    Returns:
        Созданный регион
    """
    try:
        # Проверяем права (админ и выше)
        if token.get('level') not in [ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN]:
            raise PermissionException("Недостаточно прав для создания регионов")
        
        # Создаем регион
        region = await context.service_module.region_manager.create_region(
            short_name=request.short_name,
            full_name=request.full_name,
            created_by=request.created_by
        )
        
        # Логируем действие
        await context.admin_module.log_manager.log_change(
            user_id=request.created_by,
            object_type=OBJECT_TYPE_SERVICE_REGION,
            object_id=region.id,
            change_type="create",
            old_data={},
            new_data={
                "short_name": request.short_name,
                "full_name": request.full_name
            },
            description=f"Создан регион обслуживания: {request.short_name}"
        )
        
        return RegionResponse(
            id=region.id,
            short_name=region.short_name,
            full_name=region.full_name,
            created_at=region.created_at.isoformat(),
            created_by=region.created_by,
            object_count=0,
            is_active=region.is_active
        )
        
    except PermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при создании региона: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# Эндпоинты для объектов
@router.get("/regions/{region_id}/objects", response_model=List[ObjectResponse])
async def get_objects_by_region(
    region_id: UUID = Path(..., description="ID региона"),
    active_only: bool = Query(True, description="Только активные"),
    context: AppContext = Depends(get_context),
    token: dict = Depends(verify_service_token)
):
    """
    Получает список объектов в регионе.
    
    Args:
        region_id: ID региона
        active_only: Только активные объекты
        context: Контекст приложения
        token: Токен авторизации
    
    Returns:
        Список объектов
    """
    try:
        # Проверяем права (сервис и выше)
        if token.get('level') not in [ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN, ADMIN_LEVEL_SERVICE]:
            raise PermissionException("Недостаточно прав для просмотра объектов")
        
        # Проверяем существование региона
        region = await context.service_module.region_manager.get_region_by_id(region_id)
        if not region:
            raise NotFoundException(f"Регион с ID={region_id} не найден")
        
        objects = await context.service_module.object_manager.get_objects_by_region(
            region_id=region_id,
            active_only=active_only
        )
        
        # Добавляем статистику для каждого объекта
        objects_with_stats = []
        for obj in objects:
            problem_count = await context.service_module.problem_manager.get_problems_count(obj.id)
            maintenance_count = await context.service_module.maintenance_manager.get_maintenance_count(obj.id)
            equipment_count = await context.service_module.equipment_manager.get_equipment_count(obj.id)
            
            objects_with_stats.append({
                **obj.dict(),
                "problem_count": problem_count,
                "maintenance_count": maintenance_count,
                "equipment_count": equipment_count
            })
        
        return objects_with_stats
        
    except PermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при получении объектов региона: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/objects", response_model=ObjectResponse, status_code=status.HTTP_201_CREATED)
async def create_object(
    request: ObjectCreateRequest,
    context: AppContext = Depends(get_context),
    token: dict = Depends(verify_service_token)
):
    """
    Создает новый объект обслуживания.
    
    Args:
        request: Данные для создания объекта
        context: Контекст приложения
        token: Токен авторизации
    
    Returns:
        Созданный объект
    """
    try:
        # Проверяем права (сервис и выше)
        if token.get('level') not in [ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN, ADMIN_LEVEL_SERVICE]:
            raise PermissionException("Недостаточно прав для создания объектов")
        
        # Проверяем существование региона
        region = await context.service_module.region_manager.get_region_by_id(request.region_id)
        if not region:
            raise NotFoundException(f"Регион с ID={request.region_id} не найден")
        
        # Создаем объект
        obj = await context.service_module.object_manager.create_object(
            region_id=request.region_id,
            short_name=request.short_name,
            full_name=request.full_name,
            addresses=request.addresses,
            document_type=request.document_type,
            contract_number=request.contract_number,
            contract_date=request.contract_date,
            start_date=request.start_date,
            end_date=request.end_date,
            systems=request.systems,
            zip_info=request.zip_info,
            has_dispatch=request.has_dispatch,
            notes=request.notes,
            responsible_user_id=request.responsible_user_id,
            created_by=request.created_by
        )
        
        # Логируем действие
        await context.admin_module.log_manager.log_change(
            user_id=request.created_by,
            object_type=OBJECT_TYPE_SERVICE_OBJECT,
            object_id=obj.id,
            change_type="create",
            old_data={},
            new_data={
                "short_name": request.short_name,
                "full_name": request.full_name,
                "region_id": str(request.region_id),
                "contract_number": request.contract_number
            },
            description=f"Создан объект обслуживания: {request.short_name}"
        )
        
        return ObjectResponse(
            id=obj.id,
            region_id=obj.region_id,
            short_name=obj.short_name,
            full_name=obj.full_name,
            addresses=obj.addresses,
            document_type=obj.document_type,
            contract_number=obj.contract_number,
            contract_date=obj.contract_date,
            start_date=obj.start_date,
            end_date=obj.end_date,
            systems=obj.systems,
            zip_info=obj.zip_info,
            has_dispatch=obj.has_dispatch,
            notes=obj.notes,
            responsible_user_id=obj.responsible_user_id,
            created_at=obj.created_at.isoformat(),
            created_by=obj.created_by,
            is_active=obj.is_active,
            problem_count=0,
            maintenance_count=0,
            equipment_count=0
        )
        
    except PermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (NotFoundException, ValidationException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при создании объекта: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/objects/{object_id}", response_model=ObjectResponse)
async def get_object(
    object_id: UUID = Path(..., description="ID объекта"),
    context: AppContext = Depends(get_context),
    token: dict = Depends(verify_service_token)
):
    """
    Получает информацию об объекте обслуживания.
    
    Args:
        object_id: ID объекта
        context: Контекст приложения
        token: Токен авторизации
    
    Returns:
        Информация об объекте
    """
    try:
        # Проверяем права (сервис и выше)
        if token.get('level') not in [ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN, ADMIN_LEVEL_SERVICE]:
            raise PermissionException("Недостаточно прав для просмотра объекта")
        
        obj = await context.service_module.object_manager.get_object_by_id(object_id)
        if not obj:
            raise NotFoundException(f"Объект с ID={object_id} не найден")
        
        # Получаем статистику
        problem_count = await context.service_module.problem_manager.get_problems_count(object_id)
        maintenance_count = await context.service_module.maintenance_manager.get_maintenance_count(object_id)
        equipment_count = await context.service_module.equipment_manager.get_equipment_count(object_id)
        
        return ObjectResponse(
            id=obj.id,
            region_id=obj.region_id,
            short_name=obj.short_name,
            full_name=obj.full_name,
            addresses=obj.addresses,
            document_type=obj.document_type,
            contract_number=obj.contract_number,
            contract_date=obj.contract_date,
            start_date=obj.start_date,
            end_date=obj.end_date,
            systems=obj.systems,
            zip_info=obj.zip_info,
            has_dispatch=obj.has_dispatch,
            notes=obj.notes,
            responsible_user_id=obj.responsible_user_id,
            created_at=obj.created_at.isoformat(),
            created_by=obj.created_by,
            is_active=obj.is_active,
            problem_count=problem_count,
            maintenance_count=maintenance_count,
            equipment_count=equipment_count
        )
        
    except PermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при получении объекта: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# Эндпоинты для проблем
@router.get("/objects/{object_id}/problems", response_model=List[ProblemResponse])
async def get_problems(
    object_id: UUID = Path(..., description="ID объекта"),
    status_filter: Optional[str] = Query(None, description="Фильтр по статусу"),
    severity: Optional[str] = Query(None, description="Фильтр по серьезности"),
    limit: int = Query(100, description="Лимит записей"),
    offset: int = Query(0, description="Смещение"),
    context: AppContext = Depends(get_context),
    token: dict = Depends(verify_service_token)
):
    """
    Получает список проблем объекта.
    
    Args:
        object_id: ID объекта
        status_filter: Фильтр по статусу
        severity: Фильтр по серьезности
        limit: Лимит записей
        offset: Смещение
        context: Контекст приложения
        token: Токен авторизации
    
    Returns:
        Список проблем
    """
    try:
        # Проверяем права (сервис и выше)
        if token.get('level') not in [ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN, ADMIN_LEVEL_SERVICE]:
            raise PermissionException("Недостаточно прав для просмотра проблем")
        
        # Проверяем существование объекта
        obj = await context.service_module.object_manager.get_object_by_id(object_id)
        if not obj:
            raise NotFoundException(f"Объект с ID={object_id} не найден")
        
        problems = await context.service_module.problem_manager.get_problems_by_object(
            object_id=object_id,
            status=status_filter,
            severity=severity,
            limit=limit,
            offset=offset
        )
        
        return [
            ProblemResponse(
                id=p.id,
                object_id=p.object_id,
                description=p.description,
                severity=p.severity,
                status=p.status,
                created_at=p.created_at.isoformat(),
                created_by=p.created_by,
                resolved_at=p.resolved_at.isoformat() if p.resolved_at else None,
                resolved_by=p.resolved_by,
                file_url=p.file_url
            )
            for p in problems
        ]
        
    except PermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при получении проблем: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/problems", response_model=ProblemResponse, status_code=status.HTTP_201_CREATED)
async def create_problem(
    request: ProblemCreateRequest,
    context: AppContext = Depends(get_context),
    token: dict = Depends(verify_service_token)
):
    """
    Создает новую проблему.
    
    Args:
        request: Данные для создания проблемы
        context: Контекст приложения
        token: Токен авторизации
    
    Returns:
        Созданная проблема
    """
    try:
        # Проверяем права (сервис и выше)
        if token.get('level') not in [ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN, ADMIN_LEVEL_SERVICE]:
            raise PermissionException("Недостаточно прав для создания проблем")
        
        # Проверяем существование объекта
        obj = await context.service_module.object_manager.get_object_by_id(request.object_id)
        if not obj:
            raise NotFoundException(f"Объект с ID={request.object_id} не найден")
        
        # Создаем проблему
        problem = await context.service_module.problem_manager.add_problem(
            object_id=request.object_id,
            description=request.description,
            severity=request.severity,
            created_by=request.created_by,
            file_url=request.file_url
        )
        
        # Логируем действие
        await context.admin_module.log_manager.log_change(
            user_id=request.created_by,
            object_type="problem",
            object_id=problem.id,
            change_type="create",
            old_data={},
            new_data={
                "object_id": str(request.object_id),
                "description": request.description,
                "severity": request.severity
            },
            description=f"Добавлена проблема к объекту {obj.short_name}"
        )
        
        return ProblemResponse(
            id=problem.id,
            object_id=problem.object_id,
            description=problem.description,
            severity=problem.severity,
            status=problem.status,
            created_at=problem.created_at.isoformat(),
            created_by=problem.created_by,
            resolved_at=problem.resolved_at.isoformat() if problem.resolved_at else None,
            resolved_by=problem.resolved_by,
            file_url=problem.file_url
        )
        
    except PermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (NotFoundException, ValidationException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при создании проблемы: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# Эндпоинты для оборудования
@router.get("/objects/{object_id}/equipment", response_model=List[dict])
async def get_equipment(
    object_id: UUID = Path(..., description="ID объекта"),
    address_index: Optional[int] = Query(None, description="Индекс адреса"),
    context: AppContext = Depends(get_context),
    token: dict = Depends(verify_service_token)
):
    """
    Получает список оборудования объекта.
    
    Args:
        object_id: ID объекта
        address_index: Индекс адреса
        context: Контекст приложения
        token: Токен авторизации
    
    Returns:
        Список оборудования
    """
    try:
        # Проверяем права (сервис и выше)
        if token.get('level') not in [ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN, ADMIN_LEVEL_SERVICE]:
            raise PermissionException("Недостаточно прав для просмотра оборудования")
        
        # Проверяем существование объекта
        obj = await context.service_module.object_manager.get_object_by_id(object_id)
        if not obj:
            raise NotFoundException(f"Объект с ID={object_id} не найден")
        
        equipment_list = await context.service_module.equipment_manager.get_equipment_by_object(
            object_id=object_id,
            address_index=address_index
        )
        
        return equipment_list
        
    except PermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при получении оборудования: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/equipment", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_equipment(
    request: EquipmentCreateRequest,
    context: AppContext = Depends(get_context),
    token: dict = Depends(verify_service_token)
):
    """
    Создает новое оборудование.
    
    Args:
        request: Данные для создания оборудования
        context: Контекст приложения
        token: Токен авторизации
    
    Returns:
        Созданное оборудование
    """
    try:
        # Проверяем права (сервис и выше)
        if token.get('level') not in [ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN, ADMIN_LEVEL_SERVICE]:
            raise PermissionException("Недостаточно прав для создания оборудования")
        
        # Проверяем существование объекта
        obj = await context.service_module.object_manager.get_object_by_id(request.object_id)
        if not obj:
            raise NotFoundException(f"Объект с ID={request.object_id} не найден")
        
        # Создаем оборудование
        equipment = await context.service_module.equipment_manager.add_equipment(
            object_id=request.object_id,
            address_index=request.address_index,
            name=request.name,
            quantity=request.quantity,
            unit=request.unit,
            description=request.description,
            created_by=request.created_by
        )
        
        # Логируем действие
        await context.admin_module.log_manager.log_change(
            user_id=request.created_by,
            object_type="equipment",
            object_id=equipment.id,
            change_type="create",
            old_data={},
            new_data={
                "object_id": str(request.object_id),
                "name": request.name,
                "quantity": request.quantity,
                "unit": request.unit
            },
            description=f"Добавлено оборудование '{request.name}' к объекту {obj.short_name}"
        )
        
        return equipment
        
    except PermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (NotFoundException, ValidationException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при создании оборудования: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# Эндпоинты для поиска
@router.post("/search")
async def search_service_data(
    request: SearchRequest,
    context: AppContext = Depends(get_context),
    token: dict = Depends(verify_service_token)
):
    """
    Выполняет поиск по данным обслуживания.
    
    Args:
        request: Параметры поиска
        context: Контекст приложения
        token: Токен авторизации
    
    Returns:
        Результаты поиска
    """
    try:
        # Проверяем права (сервис и выше)
        if token.get('level') not in [ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN, ADMIN_LEVEL_SERVICE]:
            raise PermissionException("Недостаточно прав для поиска")
        
        results = await context.service_module.search_data(
            query=request.query,
            search_type=request.search_type,
            region_id=request.region_id,
            limit=request.limit,
            offset=request.offset
        )
        
        return results
        
    except PermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при поиске: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# Эндпоинты для статистики
@router.get("/stats/regions/{region_id}")
async def get_region_stats(
    region_id: UUID = Path(..., description="ID региона"),
    context: AppContext = Depends(get_context),
    token: dict = Depends(verify_service_token)
):
    """
    Получает статистику по региону.
    
    Args:
        region_id: ID региона
        context: Контекст приложения
        token: Токен авторизации
    
    Returns:
        Статистика региона
    """
    try:
        # Проверяем права (сервис и выше)
        if token.get('level') not in [ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN, ADMIN_LEVEL_SERVICE]:
            raise PermissionException("Недостаточно прав для просмотра статистики")
        
        # Проверяем существование региона
        region = await context.service_module.region_manager.get_region_by_id(region_id)
        if not region:
            raise NotFoundException(f"Регион с ID={region_id} не найден")
        
        stats = await context.service_module.get_region_statistics(region_id)
        
        return stats
        
    except PermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при получении статистики региона: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/stats/objects/{object_id}")
async def get_object_stats(
    object_id: UUID = Path(..., description="ID объекта"),
    context: AppContext = Depends(get_context),
    token: dict = Depends(verify_service_token)
):
    """
    Получает статистику по объекту.
    
    Args:
        object_id: ID объекта
        context: Контекст приложения
        token: Токен авторизации
    
    Returns:
        Статистика объекта
    """
    try:
        # Проверяем права (сервис и выше)
        if token.get('level') not in [ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN, ADMIN_LEVEL_SERVICE]:
            raise PermissionException("Недостаточно прав для просмотра статистики")
        
        # Проверяем существование объекта
        obj = await context.service_module.object_manager.get_object_by_id(object_id)
        if not obj:
            raise NotFoundException(f"Объект с ID={object_id} не найден")
        
        stats = await context.service_module.get_object_statistics(object_id)
        
        return stats
        
    except PermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при получении статистики объекта: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))