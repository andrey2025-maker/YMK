"""
Эндпоинты API для модуля монтажа.
Предоставляет REST API для работы с объектами монтажа, проектами,
материалами, поставками и другими сущностями модуля монтажа.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

from api.dependencies import (
    get_db_session, 
    get_current_user,
    require_permission,
    require_installation_access
)
from storage.models.installation import (
    InstallationObject,
    InstallationProject,
    InstallationMaterial,
    InstallationMaterialSection,
    InstallationMontage,
    InstallationSupply,
    InstallationChange,
    InstallationIDDocument,
    InstallationPermit,
    InstallationLetter,
    InstallationJournal
)
from storage.models.base import Base
from utils.exceptions import NotFoundError, ValidationError

router = APIRouter()


# === Объекты монтажа ===

@router.get("/objects", response_model=Dict[str, Any])
async def get_installation_objects(
    skip: int = Query(0, ge=0, description="Смещение для пагинации"),
    limit: int = Query(50, ge=1, le=100, description="Лимит на страницу"),
    region: Optional[str] = Query(None, description="Фильтр по региону"),
    status: Optional[str] = Query(None, description="Фильтр по статусу"),
    search: Optional[str] = Query(None, description="Поиск по названию"),
    db: AsyncSession = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: bool = Depends(require_installation_access),
) -> Dict[str, Any]:
    """
    Получает список объектов монтажа с пагинацией.
    
    Args:
        skip: Смещение для пагинации
        limit: Лимит на страницу
        region: Фильтр по региону
        status: Фильтр по статусу
        search: Поиск по названию
        db: Сессия БД
        current_user: Текущий пользователь
        
    Returns:
        Список объектов с пагинацией
    """
    try:
        # Базовый запрос
        stmt = select(InstallationObject).where(
            InstallationObject.deleted_at.is_(None)
        )
        
        # Применяем фильтры
        if region:
            stmt = stmt.where(InstallationObject.region.ilike(f"%{region}%"))
        
        if status:
            stmt = stmt.where(InstallationObject.status == status)
        
        if search:
            stmt = stmt.where(
                or_(
                    InstallationObject.short_name.ilike(f"%{search}%"),
                    InstallationObject.full_name.ilike(f"%{search}%"),
                    InstallationObject.contract_number.ilike(f"%{search}%")
                )
            )
        
        # Считаем общее количество
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await db.execute(count_stmt)
        total = total_result.scalar() or 0
        
        # Пагинация и сортировка
        stmt = stmt.order_by(
            InstallationObject.created_at.desc()
        ).offset(skip).limit(limit)
        
        # Выполняем запрос
        result = await db.execute(stmt)
        objects = result.scalars().all()
        
        # Форматируем ответ
        objects_data = []
        for obj in objects:
            objects_data.append({
                "id": obj.id,
                "short_name": obj.short_name,
                "full_name": obj.full_name,
                "region": obj.region,
                "status": obj.status,
                "contract_number": obj.contract_number,
                "contract_date": obj.contract_date.isoformat() if obj.contract_date else None,
                "start_date": obj.start_date.isoformat() if obj.start_date else None,
                "end_date": obj.end_date.isoformat() if obj.end_date else None,
                "created_at": obj.created_at.isoformat() if obj.created_at else None,
                "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
            })
        
        return {
            "objects": objects_data,
            "total": total,
            "skip": skip,
            "limit": limit,
            "has_more": (skip + len(objects_data)) < total
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching installation objects: {str(e)}"
        )


@router.get("/objects/{object_id}", response_model=Dict[str, Any])
async def get_installation_object(
    object_id: int = Path(..., description="ID объекта монтажа"),
    db: AsyncSession = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: bool = Depends(require_installation_access),
) -> Dict[str, Any]:
    """
    Получает детальную информацию об объекте монтажа.
    
    Args:
        object_id: ID объекта монтажа
        db: Сессия БД
        current_user: Текущий пользователь
        
    Returns:
        Детальная информация об объекте
    """
    try:
        stmt = select(InstallationObject).where(
            and_(
                InstallationObject.id == object_id,
                InstallationObject.deleted_at.is_(None)
            )
        )
        
        result = await db.execute(stmt)
        obj = result.scalar_one_or_none()
        
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Installation object with ID {object_id} not found"
            )
        
        # Получаем связанные данные
        projects_stmt = select(InstallationProject).where(
            InstallationProject.installation_object_id == object_id
        )
        projects_result = await db.execute(projects_stmt)
        projects = projects_result.scalars().all()
        
        supplies_stmt = select(InstallationSupply).where(
            InstallationSupply.installation_object_id == object_id
        )
        supplies_result = await db.execute(supplies_stmt)
        supplies = supplies_result.scalars().all()
        
        # Получаем дополнительные соглашения
        additional_agreements = []
        if obj.additional_agreements:
            for agreement in obj.additional_agreements:
                additional_agreements.append({
                    "document_name": agreement.get("document_name"),
                    "document_number": agreement.get("document_number"),
                    "document_date": agreement.get("document_date"),
                    "start_date": agreement.get("start_date"),
                    "end_date": agreement.get("end_date"),
                    "description": agreement.get("description"),
                })
        
        # Форматируем ответ
        response = {
            "id": obj.id,
            "short_name": obj.short_name,
            "full_name": obj.full_name,
            "region": obj.region,
            "addresses": obj.addresses or [],
            "contract_type": obj.contract_type,
            "contract_number": obj.contract_number,
            "contract_date": obj.contract_date.isoformat() if obj.contract_date else None,
            "start_date": obj.start_date.isoformat() if obj.start_date else None,
            "end_date": obj.end_date.isoformat() if obj.end_date else None,
            "systems": obj.systems or [],
            "note": obj.note,
            "status": obj.status,
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
            "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
            "additional_agreements": additional_agreements,
            "projects_count": len(projects),
            "supplies_count": len(supplies),
            "created_by": obj.created_by,
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching installation object: {str(e)}"
        )


@router.post("/objects", response_model=Dict[str, Any])
async def create_installation_object(
    object_data: Dict[str, Any] = Body(..., description="Данные объекта монтажа"),
    db: AsyncSession = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: bool = Depends(require_permission("write")),
    __: bool = Depends(require_installation_access),
) -> Dict[str, Any]:
    """
    Создает новый объект монтажа.
    
    Args:
        object_data: Данные объекта монтажа
        db: Сессия БД
        current_user: Текущий пользователь
        
    Returns:
        Созданный объект
    """
    try:
        # Валидация данных
        required_fields = ["short_name", "full_name", "region"]
        for field in required_fields:
            if field not in object_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required field: {field}"
                )
        
        # Парсим даты если они есть
        date_fields = ["contract_date", "start_date", "end_date"]
        for date_field in date_fields:
            if date_field in object_data and object_data[date_field]:
                try:
                    if isinstance(object_data[date_field], str):
                        object_data[date_field] = datetime.fromisoformat(object_data[date_field].replace('Z', '+00:00'))
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid date format for {date_field}. Use ISO format."
                    )
        
        # Обрабатываем дополнительные соглашения
        additional_agreements = []
        if "additional_agreements" in object_data:
            for agreement in object_data["additional_agreements"]:
                # Парсим даты в соглашениях
                agreement_dates = ["document_date", "start_date", "end_date"]
                for date_field in agreement_dates:
                    if date_field in agreement and agreement[date_field]:
                        try:
                            if isinstance(agreement[date_field], str):
                                agreement[date_field] = datetime.fromisoformat(agreement[date_field].replace('Z', '+00:00'))
                        except ValueError:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Invalid date format in additional agreement for {date_field}"
                            )
                additional_agreements.append(agreement)
        
        # Создаем объект
        obj = InstallationObject(
            short_name=object_data["short_name"],
            full_name=object_data["full_name"],
            region=object_data["region"],
            addresses=object_data.get("addresses", []),
            contract_type=object_data.get("contract_type"),
            contract_number=object_data.get("contract_number"),
            contract_date=object_data.get("contract_date"),
            start_date=object_data.get("start_date"),
            end_date=object_data.get("end_date"),
            systems=object_data.get("systems", []),
            note=object_data.get("note"),
            status=object_data.get("status", "active"),
            additional_agreements=additional_agreements,
            created_by=current_user.get("id", 0),
        )
        
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        
        return {
            "id": obj.id,
            "short_name": obj.short_name,
            "full_name": obj.full_name,
            "region": obj.region,
            "status": obj.status,
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
            "message": "Installation object created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating installation object: {str(e)}"
        )


@router.put("/objects/{object_id}", response_model=Dict[str, Any])
async def update_installation_object(
    object_id: int = Path(..., description="ID объекта монтажа"),
    object_data: Dict[str, Any] = Body(..., description="Обновленные данные"),
    db: AsyncSession = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: bool = Depends(require_permission("write")),
    __: bool = Depends(require_installation_access),
) -> Dict[str, Any]:
    """
    Обновляет объект монтажа.
    
    Args:
        object_id: ID объекта монтажа
        object_data: Обновленные данные
        db: Сессия БД
        current_user: Текущий пользователь
        
    Returns:
        Обновленный объект
    """
    try:
        # Находим объект
        stmt = select(InstallationObject).where(
            and_(
                InstallationObject.id == object_id,
                InstallationObject.deleted_at.is_(None)
            )
        )
        
        result = await db.execute(stmt)
        obj = result.scalar_one_or_none()
        
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Installation object with ID {object_id} not found"
            )
        
        # Парсим даты если они есть
        date_fields = ["contract_date", "start_date", "end_date"]
        for date_field in date_fields:
            if date_field in object_data and object_data[date_field]:
                try:
                    if isinstance(object_data[date_field], str):
                        object_data[date_field] = datetime.fromisoformat(object_data[date_field].replace('Z', '+00:00'))
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid date format for {date_field}. Use ISO format."
                    )
        
        # Обрабатываем дополнительные соглашения
        if "additional_agreements" in object_data:
            additional_agreements = []
            for agreement in object_data["additional_agreements"]:
                # Парсим даты в соглашениях
                agreement_dates = ["document_date", "start_date", "end_date"]
                for date_field in agreement_dates:
                    if date_field in agreement and agreement[date_field]:
                        try:
                            if isinstance(agreement[date_field], str):
                                agreement[date_field] = datetime.fromisoformat(agreement[date_field].replace('Z', '+00:00'))
                        except ValueError:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Invalid date format in additional agreement for {date_field}"
                            )
                additional_agreements.append(agreement)
            object_data["additional_agreements"] = additional_agreements
        
        # Обновляем поля
        update_fields = [
            "short_name", "full_name", "region", "addresses",
            "contract_type", "contract_number", "contract_date",
            "start_date", "end_date", "systems", "note", "status",
            "additional_agreements"
        ]
        
        for field in update_fields:
            if field in object_data:
                setattr(obj, field, object_data[field])
        
        obj.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(obj)
        
        return {
            "id": obj.id,
            "short_name": obj.short_name,
            "full_name": obj.full_name,
            "region": obj.region,
            "status": obj.status,
            "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
            "message": "Installation object updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating installation object: {str(e)}"
        )


@router.delete("/objects/{object_id}", response_model=Dict[str, Any])
async def delete_installation_object(
    object_id: int = Path(..., description="ID объекта монтажа"),
    confirm: bool = Query(False, description="Требуется подтверждение удаления"),
    db: AsyncSession = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: bool = Depends(require_permission("delete")),
    __: bool = Depends(require_installation_access),
) -> Dict[str, Any]:
    """
    Удаляет объект монтажа (soft delete).
    
    Args:
        object_id: ID объекта монтажа
        confirm: Подтверждение удаления
        db: Сессия БД
        current_user: Текущий пользователь
        
    Returns:
        Результат удаления
    """
    try:
        if not confirm:
            return {
                "status": "confirmation_required",
                "message": "Add ?confirm=true to confirm deletion. This will archive the object and all its data."
            }
        
        # Находим объект
        stmt = select(InstallationObject).where(
            and_(
                InstallationObject.id == object_id,
                InstallationObject.deleted_at.is_(None)
            )
        )
        
        result = await db.execute(stmt)
        obj = result.scalar_one_or_none()
        
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Installation object with ID {object_id} not found"
            )
        
        # Выполняем soft delete
        obj.deleted_at = datetime.utcnow()
        obj.deleted_by = current_user.get("id", 0)
        obj.status = "deleted"
        
        await db.commit()
        
        return {
            "id": object_id,
            "deleted": True,
            "deleted_at": obj.deleted_at.isoformat() if obj.deleted_at else None,
            "message": "Installation object deleted and archived successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting installation object: {str(e)}"
        )


# === Проекты ===

@router.get("/objects/{object_id}/projects", response_model=Dict[str, Any])
async def get_installation_projects(
    object_id: int = Path(..., description="ID объекта монтажа"),
    skip: int = Query(0, ge=0, description="Смещение для пагинации"),
    limit: int = Query(50, ge=1, le=100, description="Лимит на страницу"),
    db: AsyncSession = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: bool = Depends(require_installation_access),
) -> Dict[str, Any]:
    """
    Получает список проектов для объекта монтажа.
    
    Args:
        object_id: ID объекта монтажа
        skip: Смещение для пагинации
        limit: Лимит на страницу
        db: Сессия БД
        current_user: Текущий пользователь
        
    Returns:
        Список проектов с пагинацией
    """
    try:
        # Проверяем существование объекта
        obj_stmt = select(InstallationObject).where(
            and_(
                InstallationObject.id == object_id,
                InstallationObject.deleted_at.is_(None)
            )
        )
        obj_result = await db.execute(obj_stmt)
        obj = obj_result.scalar_one_or_none()
        
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Installation object with ID {object_id} not found"
            )
        
        # Получаем проекты
        stmt = select(InstallationProject).where(
            InstallationProject.installation_object_id == object_id
        )
        
        # Считаем общее количество
        count_stmt = select(func.count()).select_from(
            select(InstallationProject)
            .where(InstallationProject.installation_object_id == object_id)
            .subquery()
        )
        total_result = await db.execute(count_stmt)
        total = total_result.scalar() or 0
        
        # Пагинация и сортировка
        stmt = stmt.order_by(
            InstallationProject.created_at.desc()
        ).offset(skip).limit(limit)
        
        result = await db.execute(stmt)
        projects = result.scalars().all()
        
        # Форматируем ответ
        projects_data = []
        for project in projects:
            projects_data.append({
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "file_id": project.file_id,
                "file_size": project.file_size,
                "created_at": project.created_at.isoformat() if project.created_at else None,
                "created_by": project.created_by,
            })
        
        return {
            "object_id": object_id,
            "projects": projects_data,
            "total": total,
            "skip": skip,
            "limit": limit,
            "has_more": (skip + len(projects_data)) < total
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching projects: {str(e)}"
        )


@router.get("/objects/{object_id}/projects/{project_id}", response_model=Dict[str, Any])
async def get_installation_project(
    object_id: int = Path(..., description="ID объекта монтажа"),
    project_id: int = Path(..., description="ID проекта"),
    db: AsyncSession = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: bool = Depends(require_installation_access),
) -> Dict[str, Any]:
    """
    Получает информацию о конкретном проекте.
    
    Args:
        object_id: ID объекта монтажа
        project_id: ID проекта
        db: Сессия БД
        current_user: Текущий пользователь
        
    Returns:
        Информация о проекте
    """
    try:
        # Проверяем существование объекта
        obj_stmt = select(InstallationObject).where(
            and_(
                InstallationObject.id == object_id,
                InstallationObject.deleted_at.is_(None)
            )
        )
        obj_result = await db.execute(obj_stmt)
        obj = obj_result.scalar_one_or_none()
        
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Installation object with ID {object_id} not found"
            )
        
        # Получаем проект
        stmt = select(InstallationProject).where(
            and_(
                InstallationProject.id == project_id,
                InstallationProject.installation_object_id == object_id
            )
        )
        
        result = await db.execute(stmt)
        project = result.scalar_one_or_none()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found for object {object_id}"
            )
        
        return {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "file_id": project.file_id,
            "file_size": project.file_size,
            "created_at": project.created_at.isoformat() if project.created_at else None,
            "updated_at": project.updated_at.isoformat() if project.updated_at else None,
            "created_by": project.created_by,
            "object_id": object_id,
            "object_name": obj.short_name,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching project: {str(e)}"
        )


@router.post("/objects/{object_id}/projects", response_model=Dict[str, Any])
async def create_installation_project(
    object_id: int = Path(..., description="ID объекта монтажа"),
    project_data: Dict[str, Any] = Body(..., description="Данные проекта"),
    db: AsyncSession = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: bool = Depends(require_permission("write")),
    __: bool = Depends(require_installation_access),
) -> Dict[str, Any]:
    """
    Создает новый проект для объекта монтажа.
    
    Args:
        object_id: ID объекта монтажа
        project_data: Данные проекта
        db: Сессия БД
        current_user: Текущий пользователь
        
    Returns:
        Созданный проект
    """
    try:
        # Проверяем существование объекта
        obj_stmt = select(InstallationObject).where(
            and_(
                InstallationObject.id == object_id,
                InstallationObject.deleted_at.is_(None)
            )
        )
        obj_result = await db.execute(obj_stmt)
        obj = obj_result.scalar_one_or_none()
        
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Installation object with ID {object_id} not found"
            )
        
        # Валидация данных
        if "name" not in project_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project name is required"
            )
        
        # Создаем проект
        project = InstallationProject(
            installation_object_id=object_id,
            name=project_data["name"],
            description=project_data.get("description"),
            file_id=project_data.get("file_id"),
            file_size=project_data.get("file_size"),
            created_by=current_user.get("id", 0),
        )
        
        db.add(project)
        await db.commit()
        await db.refresh(project)
        
        return {
            "id": project.id,
            "name": project.name,
            "object_id": object_id,
            "created_at": project.created_at.isoformat() if project.created_at else None,
            "message": "Project created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating project: {str(e)}"
        )


@router.put("/objects/{object_id}/projects/{project_id}", response_model=Dict[str, Any])
async def update_installation_project(
    object_id: int = Path(..., description="ID объекта монтажа"),
    project_id: int = Path(..., description="ID проекта"),
    project_data: Dict[str, Any] = Body(..., description="Обновленные данные проекта"),
    db: AsyncSession = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: bool = Depends(require_permission("write")),
    __: bool = Depends(require_installation_access),
) -> Dict[str, Any]:
    """
    Обновляет проект объекта монтажа.
    
    Args:
        object_id: ID объекта монтажа
        project_id: ID проекта
        project_data: Обновленные данные
        db: Сессия БД
        current_user: Текущий пользователь
        
    Returns:
        Обновленный проект
    """
    try:
        # Проверяем существование объекта
        obj_stmt = select(InstallationObject).where(
            and_(
                InstallationObject.id == object_id,
                InstallationObject.deleted_at.is_(None)
            )
        )
        obj_result = await db.execute(obj_stmt)
        obj = obj_result.scalar_one_or_none()
        
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Installation object with ID {object_id} not found"
            )
        
        # Находим проект
        stmt = select(InstallationProject).where(
            and_(
                InstallationProject.id == project_id,
                InstallationProject.installation_object_id == object_id
            )
        )
        
        result = await db.execute(stmt)
        project = result.scalar_one_or_none()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found for object {object_id}"
            )
        
        # Обновляем поля
        update_fields = ["name", "description", "file_id", "file_size"]
        for field in update_fields:
            if field in project_data:
                setattr(project, field, project_data[field])
        
        project.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(project)
        
        return {
            "id": project.id,
            "name": project.name,
            "object_id": object_id,
            "updated_at": project.updated_at.isoformat() if project.updated_at else None,
            "message": "Project updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating project: {str(e)}"
        )


@router.delete("/objects/{object_id}/projects/{project_id}", response_model=Dict[str, Any])
async def delete_installation_project(
    object_id: int = Path(..., description="ID объекта монтажа"),
    project_id: int = Path(..., description="ID проекта"),
    confirm: bool = Query(False, description="Требуется подтверждение удаления"),
    db: AsyncSession = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: bool = Depends(require_permission("delete")),
    __: bool = Depends(require_installation_access),
) -> Dict[str, Any]:
    """
    Удаляет проект объекта монтажа.
    
    Args:
        object_id: ID объекта монтажа
        project_id: ID проекта
        confirm: Подтверждение удаления
        db: Сессия БД
        current_user: Текущий пользователь
        
    Returns:
        Результат удаления
    """
    try:
        if not confirm:
            return {
                "status": "confirmation_required",
                "message": "Add ?confirm=true to confirm project deletion."
            }
        
        # Проверяем существование объекта
        obj_stmt = select(InstallationObject).where(
            and_(
                InstallationObject.id == object_id,
                InstallationObject.deleted_at.is_(None)
            )
        )
        obj_result = await db.execute(obj_stmt)
        obj = obj_result.scalar_one_or_none()
        
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Installation object with ID {object_id} not found"
            )
        
        # Находим проект
        stmt = select(InstallationProject).where(
            and_(
                InstallationProject.id == project_id,
                InstallationProject.installation_object_id == object_id
            )
        )
        
        result = await db.execute(stmt)
        project = result.scalar_one_or_none()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found for object {object_id}"
            )
        
        # Удаляем проект
        await db.delete(project)
        await db.commit()
        
        return {
            "id": project_id,
            "object_id": object_id,
            "deleted": True,
            "message": "Project deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting project: {str(e)}"
        )


# === Материалы ===

@router.get("/objects/{object_id}/materials", response_model=Dict[str, Any])
async def get_installation_materials(
    object_id: int = Path(..., description="ID объекта монтажа"),
    section_id: Optional[int] = Query(None, description="ID раздела материалов"),
    skip: int = Query(0, ge=0, description="Смещение для пагинации"),
    limit: int = Query(100, ge=1, le=200, description="Лимит на страницу"),
    include_sections: bool = Query(True, description="Включать информацию о разделах"),
    db: AsyncSession = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: bool = Depends(require_installation_access),
) -> Dict[str, Any]:
    """
    Получает список материалов для объекта монтажа.
    
    Args:
        object_id: ID объекта монтажа
        section_id: ID раздела материалов (опционально)
        skip: Смещение для пагинации
        limit: Лимит на страницу
        include_sections: Включать информацию о разделах
        db: Сессия БД
        current_user: Текущий пользователь
        
    Returns:
        Список материалов с пагинацией
    """
    try:
        # Проверяем существование объекта
        obj_stmt = select(InstallationObject).where(
            and_(
                InstallationObject.id == object_id,
                InstallationObject.deleted_at.is_(None)
            )
        )
        obj_result = await db.execute(obj_stmt)
        obj = obj_result.scalar_one_or_none()
        
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Installation object with ID {object_id} not found"
            )
        
        # Получаем материалы
        stmt = select(InstallationMaterial).where(
            InstallationMaterial.installation_object_id == object_id
        )
        
        if section_id is not None:
            stmt = stmt.where(InstallationMaterial.section_id == section_id)
        else:
            stmt = stmt.where(InstallationMaterial.section_id.is_(None))
        
        # Считаем общее количество
        count_stmt = select(func.count()).select_from(
            select(InstallationMaterial)
            .where(InstallationMaterial.installation_object_id == object_id)
            .subquery()
        )
        if section_id is not None:
            count_stmt = select(func.count()).select_from(
                select(InstallationMaterial)
                .where(
                    and_(
                        InstallationMaterial.installation_object_id == object_id,
                        InstallationMaterial.section_id == section_id
                    )
                )
                .subquery()
            )
        
        total_result = await db.execute(count_stmt)
        total = total_result.scalar() or 0
        
        # Пагинация и сортировка
        stmt = stmt.order_by(
            InstallationMaterial.name.asc()
        ).offset(skip).limit(limit)
        
        result = await db.execute(stmt)
        materials = result.scalars().all()
        
        # Получаем разделы если нужно
        sections_data = []
        if include_sections and section_id is None:
            sections_stmt = select(InstallationMaterialSection).where(
                InstallationMaterialSection.installation_object_id == object_id
            ).order_by(InstallationMaterialSection.name.asc())
            
            sections_result = await db.execute(sections_stmt)
            sections = sections_result.scalars().all()
            
            for section in sections:
                # Считаем материалы в разделе
                section_materials_stmt = select(func.count()).where(
                    InstallationMaterial.section_id == section.id
                )
                section_materials_result = await db.execute(section_materials_stmt)
                materials_count = section_materials_result.scalar() or 0
                
                sections_data.append({
                    "id": section.id,
                    "name": section.name,
                    "description": section.description,
                    "materials_count": materials_count,
                    "created_at": section.created_at.isoformat() if section.created_at else None,
                    "created_by": section.created_by,
                })
        
        # Форматируем ответ
        materials_data = []
        for material in materials:
            materials_data.append({
                "id": material.id,
                "name": material.name,
                "description": material.description,
                "quantity": float(material.quantity) if material.quantity else 0.0,
                "unit": material.unit,
                "section_id": material.section_id,
                "total_installed": float(material.total_installed) if material.total_installed else 0.0,
                "remaining": float(material.quantity - (material.total_installed or 0)) if material.quantity else 0.0,
                "created_at": material.created_at.isoformat() if material.created_at else None,
                "created_by": material.created_by,
            })
        
        return {
            "object_id": object_id,
            "section_id": section_id,
            "materials": materials_data,
            "sections": sections_data,
            "total": total,
            "skip": skip,
            "limit": limit,
            "has_more": (skip + len(materials_data)) < total
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching materials: {str(e)}"
        )


@router.post("/objects/{object_id}/materials", response_model=Dict[str, Any])
async def create_installation_material(
    object_id: int = Path(..., description="ID объекта монтажа"),
    material_data: Dict[str, Any] = Body(..., description="Данные материала"),
    db: AsyncSession = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: bool = Depends(require_permission("write")),
    __: bool = Depends(require_installation_access),
) -> Dict[str, Any]:
    """
    Создает новый материал для объекта монтажа.
    
    Args:
        object_id: ID объекта монтажа
        material_data: Данные материала
        db: Сессия БД
        current_user: Текущий пользователь
        
    Returns:
        Созданный материал
    """
    try:
        # Проверяем существование объекта
        obj_stmt = select(InstallationObject).where(
            and_(
                InstallationObject.id == object_id,
                InstallationObject.deleted_at.is_(None)
            )
        )
        obj_result = await db.execute(obj_stmt)
        obj = obj_result.scalar_one_or_none()
        
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Installation object with ID {object_id} not found"
            )
        
        # Валидация данных
        required_fields = ["name", "quantity", "unit"]
        for field in required_fields:
            if field not in material_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required field: {field}"
                )
        
        # Проверяем единицы измерения
        valid_units = ["м.", "шт.", "уп.", "компл.", "кг", "л", "м²", "м³"]
        if material_data["unit"] not in valid_units:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid unit. Valid units are: {', '.join(valid_units)}"
            )
        
        # Если указан section_id, проверяем существование раздела
        section_id = material_data.get("section_id")
        if section_id:
            section_stmt = select(InstallationMaterialSection).where(
                and_(
                    InstallationMaterialSection.id == section_id,
                    InstallationMaterialSection.installation_object_id == object_id
                )
            )
            section_result = await db.execute(section_stmt)
            section = section_result.scalar_one_or_none()
            
            if not section:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Material section with ID {section_id} not found"
                )
        
        # Создаем материал
        material = InstallationMaterial(
            installation_object_id=object_id,
            name=material_data["name"],
            description=material_data.get("description"),
            quantity=float(material_data["quantity"]),
            unit=material_data["unit"],
            section_id=section_id,
            created_by=current_user.get("id", 0),
        )
        
        db.add(material)
        await db.commit()
        await db.refresh(material)
        
        return {
            "id": material.id,
            "name": material.name,
            "quantity": float(material.quantity),
            "unit": material.unit,
            "section_id": material.section_id,
            "object_id": object_id,
            "created_at": material.created_at.isoformat() if material.created_at else None,
            "message": "Material created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating material: {str(e)}"
        )


@router.post("/objects/{object_id}/materials/batch", response_model=Dict[str, Any])
async def create_installation_materials_batch(
    object_id: int = Path(..., description="ID объекта монтажа"),
    materials_data: List[Dict[str, Any]] = Body(..., description="Список материалов"),
    db: AsyncSession = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: bool = Depends(require_permission("write")),
    __: bool = Depends(require_installation_access),
) -> Dict[str, Any]:
    """
    Создает несколько материалов для объекта монтажа.
    
    Args:
        object_id: ID объекта монтажа
        materials_data: Список материалов
        db: Сессия БД
        current_user: Текущий пользователь
        
    Returns:
        Результат создания
    """
    try:
        # Проверяем существование объекта
        obj_stmt = select(InstallationObject).where(
            and_(
                InstallationObject.id == object_id,
                InstallationObject.deleted_at.is_(None)
            )
        )
        obj_result = await db.execute(obj_stmt)
        obj = obj_result.scalar_one_or_none()
        
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Installation object with ID {object_id} not found"
            )
        
        valid_units = ["м.", "шт.", "уп.", "компл.", "кг", "л", "м²", "м³"]
        created_materials = []
        errors = []
        
        for i, material_data in enumerate(materials_data):
            try:
                # Валидация данных
                required_fields = ["name", "quantity", "unit"]
                for field in required_fields:
                    if field not in material_data:
                        errors.append(f"Material {i}: Missing required field: {field}")
                        continue
                
                # Проверяем единицы измерения
                if material_data["unit"] not in valid_units:
                    errors.append(f"Material {i}: Invalid unit '{material_data['unit']}'")
                    continue
                
                # Если указан section_id, проверяем существование раздела
                section_id = material_data.get("section_id")
                if section_id:
                    section_stmt = select(InstallationMaterialSection).where(
                        and_(
                            InstallationMaterialSection.id == section_id,
                            InstallationMaterialSection.installation_object_id == object_id
                        )
                    )
                    section_result = await db.execute(section_stmt)
                    section = section_result.scalar_one_or_none()
                    
                    if not section:
                        errors.append(f"Material {i}: Section with ID {section_id} not found")
                        continue
                
                # Создаем материал
                material = InstallationMaterial(
                    installation_object_id=object_id,
                    name=material_data["name"],
                    description=material_data.get("description"),
                    quantity=float(material_data["quantity"]),
                    unit=material_data["unit"],
                    section_id=section_id,
                    created_by=current_user.get("id", 0),
                )
                
                db.add(material)
                created_materials.append(material_data["name"])
                
            except Exception as e:
                errors.append(f"Material {i}: {str(e)}")
        
        if errors and not created_materials:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Batch creation failed: {', '.join(errors)}"
            )
        
        await db.commit()
        
        return {
            "object_id": object_id,
            "created_count": len(created_materials),
            "error_count": len(errors),
            "created_materials": created_materials,
            "errors": errors if errors else None,
            "message": f"Created {len(created_materials)} materials, {len(errors)} errors"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating materials batch: {str(e)}"
        )


# === Разделы материалов ===

@router.get("/objects/{object_id}/sections", response_model=Dict[str, Any])
async def get_installation_sections(
    object_id: int = Path(..., description="ID объекта монтажа"),
    skip: int = Query(0, ge=0, description="Смещение для пагинации"),
    limit: int = Query(50, ge=1, le=100, description="Лимит на страницу"),
    db: AsyncSession = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: bool = Depends(require_installation_access),
) -> Dict[str, Any]:
    """
    Получает список разделов материалов для объекта монтажа.
    
    Args:
        object_id: ID объекта монтажа
        skip: Смещение для пагинации
        limit: Лимит на страницу
        db: Сессия БД
        current_user: Текущий пользователь
        
    Returns:
        Список разделов с пагинацией
    """
    try:
        # Проверяем существование объекта
        obj_stmt = select(InstallationObject).where(
            and_(
                InstallationObject.id == object_id,
                InstallationObject.deleted_at.is_(None)
            )
        )
        obj_result = await db.execute(obj_stmt)
        obj = obj_result.scalar_one_or_none()
        
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Installation object with ID {object_id} not found"
            )
        
        # Получаем разделы
        stmt = select(InstallationMaterialSection).where(
            InstallationMaterialSection.installation_object_id == object_id
        )
        
        # Считаем общее количество
        count_stmt = select(func.count()).select_from(
            select(InstallationMaterialSection)
            .where(InstallationMaterialSection.installation_object_id == object_id)
            .subquery()
        )
        total_result = await db.execute(count_stmt)
        total = total_result.scalar() or 0
        
        # Пагинация и сортировка
        stmt = stmt.order_by(
            InstallationMaterialSection.name.asc()
        ).offset(skip).limit(limit)
        
        result = await db.execute(stmt)
        sections = result.scalars().all()
        
        # Для каждого раздела получаем количество материалов
        sections_data = []
        for section in sections:
            # Считаем материалы в разделе
            materials_stmt = select(func.count()).where(
                InstallationMaterial.section_id == section.id
            )
            materials_result = await db.execute(materials_stmt)
            materials_count = materials_result.scalar() or 0
            
            # Считаем общее количество материалов в разделе
            quantity_stmt = select(func.sum(InstallationMaterial.quantity)).where(
                InstallationMaterial.section_id == section.id
            )
            quantity_result = await db.execute(quantity_stmt)
            total_quantity = quantity_result.scalar() or 0.0
            
            # Считаем установленное количество
            installed_stmt = select(func.sum(InstallationMaterial.total_installed)).where(
                InstallationMaterial.section_id == section.id
            )
            installed_result = await db.execute(installed_stmt)
            total_installed = installed_result.scalar() or 0.0
            
            sections_data.append({
                "id": section.id,
                "name": section.name,
                "description": section.description,
                "materials_count": materials_count,
                "total_quantity": float(total_quantity),
                "total_installed": float(total_installed),
                "remaining": float(total_quantity - total_installed),
                "completion_percentage": (float(total_installed) / float(total_quantity) * 100) if total_quantity > 0 else 0.0,
                "created_at": section.created_at.isoformat() if section.created_at else None,
                "created_by": section.created_by,
            })
        
        return {
            "object_id": object_id,
            "sections": sections_data,
            "total": total,
            "skip": skip,
            "limit": limit,
            "has_more": (skip + len(sections_data)) < total
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching sections: {str(e)}"
        )


@router.post("/objects/{object_id}/sections", response_model=Dict[str, Any])
async def create_installation_section(
    object_id: int = Path(..., description="ID объекта монтажа"),
    section_data: Dict[str, Any] = Body(..., description="Данные раздела"),
    db: AsyncSession = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: bool = Depends(require_permission("write")),
    __: bool = Depends(require_installation_access),
) -> Dict[str, Any]:
    """
    Создает новый раздел материалов для объекта монтажа.
    
    Args:
        object_id: ID объекта монтажа
        section_data: Данные раздела
        db: Сессия БД
        current_user: Текущий пользователь
        
    Returns:
        Созданный раздел
    """
    try:
        # Проверяем существование объекта
        obj_stmt = select(InstallationObject).where(
            and_(
                InstallationObject.id == object_id,
                InstallationObject.deleted_at.is_(None)
            )
        )
        obj_result = await db.execute(obj_stmt)
        obj = obj_result.scalar_one_or_none()
        
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Installation object with ID {object_id} not found"
            )
        
        # Валидация данных
        if "name" not in section_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Section name is required"
            )
        
        # Проверяем уникальность имени раздела
        existing_stmt = select(InstallationMaterialSection).where(
            and_(
                InstallationMaterialSection.installation_object_id == object_id,
                InstallationMaterialSection.name == section_data["name"]
            )
        )
        existing_result = await db.execute(existing_stmt)
        existing_section = existing_result.scalar_one_or_none()
        
        if existing_section:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Section with name '{section_data['name']}' already exists"
            )
        
        # Создаем раздел
        section = InstallationMaterialSection(
            installation_object_id=object_id,
            name=section_data["name"],
            description=section_data.get("description"),
            created_by=current_user.get("id", 0),
        )
        
        db.add(section)
        await db.commit()
        await db.refresh(section)
        
        return {
            "id": section.id,
            "name": section.name,
            "object_id": object_id,
            "created_at": section.created_at.isoformat() if section.created_at else None,
            "message": "Material section created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating section: {str(e)}"
        )


# === Монтаж ===

@router.get("/objects/{object_id}/montage", response_model=Dict[str, Any])
async def get_installation_montage(
    object_id: int = Path(..., description="ID объекта монтажа"),
    material_id: Optional[int] = Query(None, description="ID материала"),
    section_id: Optional[int] = Query(None, description="ID раздела"),
    skip: int = Query(0, ge=0, description="Смещение для пагинации"),
    limit: int = Query(50, ge=1, le=100, description="Лимит на страницу"),
    start_date: Optional[str] = Query(None, description="Начальная дата (ISO format)"),
    end_date: Optional[str] = Query(None, description="Конечная дата (ISO format)"),
    db: AsyncSession = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: bool = Depends(require_installation_access),
) -> Dict[str, Any]:
    """
    Получает данные о монтаже для объекта.
    
    Args:
        object_id: ID объекта монтажа
        material_id: ID материала (опционально)
        section_id: ID раздела (опционально)
        skip: Смещение для пагинации
        limit: Лимит на страницу
        start_date: Начальная дата фильтрации
        end_date: Конечная дата фильтрации
        db: Сессия БД
        current_user: Текущий пользователь
        
    Returns:
        Данные о монтаже
    """
    try:
        # Проверяем существование объекта
        obj_stmt = select(InstallationObject).where(
            and_(
                InstallationObject.id == object_id,
                InstallationObject.deleted_at.is_(None)
            )
        )
        obj_result = await db.execute(obj_stmt)
        obj = obj_result.scalar_one_or_none()
        
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Installation object with ID {object_id} not found"
            )
        
        # Получаем данные монтажа
        stmt = select(InstallationMontage).where(
            InstallationMontage.installation_object_id == object_id
        )
        
        if material_id is not None:
            stmt = stmt.where(InstallationMontage.material_id == material_id)
        
        if section_id is not None:
            stmt = stmt.where(InstallationMontage.section_id == section_id)
        
        # Фильтрация по дате
        if start_date:
            try:
                start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                stmt = stmt.where(InstallationMontage.installed_at >= start_datetime)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid start_date format. Use ISO format."
                )
        
        if end_date:
            try:
                end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                stmt = stmt.where(InstallationMontage.installed_at <= end_datetime)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid end_date format. Use ISO format."
                )
        
        # Считаем общее количество
        count_stmt = select(func.count()).select_from(
            select(InstallationMontage)
            .where(InstallationMontage.installation_object_id == object_id)
            .subquery()
        )
        if material_id is not None:
            count_stmt = select(func.count()).select_from(
                select(InstallationMontage)
                .where(
                    and_(
                        InstallationMontage.installation_object_id == object_id,
                        InstallationMontage.material_id == material_id
                    )
                )
                .subquery()
            )
        
        total_result = await db.execute(count_stmt)
        total = total_result.scalar() or 0
        
        # Пагинация и сортировка
        stmt = stmt.order_by(
            InstallationMontage.installed_at.desc()
        ).offset(skip).limit(limit)
        
        result = await db.execute(stmt)
        montage_entries = result.scalars().all()
        
        # Получаем статистику
        stats_stmt = select(
            func.sum(InstallationMontage.quantity_installed).label("total_installed"),
            func.count(InstallationMontage.id).label("total_entries")
        ).where(
            InstallationMontage.installation_object_id == object_id
        )
        
        if material_id is not None:
            stats_stmt = stats_stmt.where(InstallationMontage.material_id == material_id)
        
        if section_id is not None:
            stats_stmt = stats_stmt.where(InstallationMontage.section_id == section_id)
        
        stats_result = await db.execute(stats_stmt)
        stats = stats_result.first()
        
        # Форматируем ответ
        montage_data = []
        for entry in montage_entries:
            montage_data.append({
                "id": entry.id,
                "material_id": entry.material_id,
                "material_name": entry.material_name,
                "section_id": entry.section_id,
                "quantity_installed": float(entry.quantity_installed) if entry.quantity_installed else 0.0,
                "installed_by": entry.installed_by,
                "installed_at": entry.installed_at.isoformat() if entry.installed_at else None,
                "notes": entry.notes,
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
            })
        
        return {
            "object_id": object_id,
            "montage_entries": montage_data,
            "statistics": {
                "total_installed": float(stats.total_installed) if stats.total_installed else 0.0,
                "total_entries": stats.total_entries or 0,
            },
            "total": total,
            "skip": skip,
            "limit": limit,
            "has_more": (skip + len(montage_data)) < total
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching montage data: {str(e)}"
        )


@router.post("/objects/{object_id}/montage", response_model=Dict[str, Any])
async def create_installation_montage_entry(
    object_id: int = Path(..., description="ID объекта монтажа"),
    montage_data: Dict[str, Any] = Body(..., description="Данные монтажа"),
    db: AsyncSession = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: bool = Depends(require_permission("write")),
    __: bool = Depends(require_installation_access),
) -> Dict[str, Any]:
    """
    Создает запись о монтаже материала.
    
    Args:
        object_id: ID объекта монтажа
        montage_data: Данные монтажа
        db: Сессия БД
        current_user: Текущий пользователь
        
    Returns:
        Созданная запись монтажа
    """
    try:
        # Проверяем существование объекта
        obj_stmt = select(InstallationObject).where(
            and_(
                InstallationObject.id == object_id,
                InstallationObject.deleted_at.is_(None)
            )
        )
        obj_result = await db.execute(obj_stmt)
        obj = obj_result.scalar_one_or_none()
        
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Installation object with ID {object_id} not found"
            )
        
        # Валидация данных
        required_fields = ["material_id", "quantity_installed"]
        for field in required_fields:
            if field not in montage_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required field: {field}"
                )
        
        # Проверяем существование материала
        material_stmt = select(InstallationMaterial).where(
            and_(
                InstallationMaterial.id == montage_data["material_id"],
                InstallationMaterial.installation_object_id == object_id
            )
        )
        material_result = await db.execute(material_stmt)
        material = material_result.scalar_one_or_none()
        
        if not material:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Material with ID {montage_data['material_id']} not found"
            )
        
        # Проверяем доступное количество
        quantity_installed = float(montage_data["quantity_installed"])
        available = material.quantity - (material.total_installed or 0)
        
        if quantity_installed > available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Not enough material available. Available: {available}, Requested: {quantity_installed}"
            )
        
        # Создаем запись монтажа
        montage_entry = InstallationMontage(
            installation_object_id=object_id,
            material_id=montage_data["material_id"],
            material_name=material.name,
            section_id=material.section_id,
            quantity_installed=quantity_installed,
            installed_by=current_user.get("id", 0),
            notes=montage_data.get("notes"),
            installed_at=datetime.utcnow(),
        )
        
        # Обновляем общее установленное количество в материале
        material.total_installed = (material.total_installed or 0) + quantity_installed
        material.updated_at = datetime.utcnow()
        
        db.add(montage_entry)
        await db.commit()
        await db.refresh(montage_entry)
        
        return {
            "id": montage_entry.id,
            "material_id": montage_entry.material_id,
            "material_name": montage_entry.material_name,
            "quantity_installed": float(montage_entry.quantity_installed),
            "installed_at": montage_entry.installed_at.isoformat() if montage_entry.installed_at else None,
            "available_now": float(available - quantity_installed),
            "message": "Montage entry created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating montage entry: {str(e)}"
        )


# === Поставки ===

@router.get("/objects/{object_id}/supplies", response_model=Dict[str, Any])
async def get_installation_supplies(
    object_id: int = Path(..., description="ID объекта монтажа"),
    skip: int = Query(0, ge=0, description="Смещение для пагинации"),
    limit: int = Query(50, ge=1, le=100, description="Лимит на страницу"),
    status_filter: Optional[str] = Query(None, description="Фильтр по статусу"),
    db: AsyncSession = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: bool = Depends(require_installation_access),
) -> Dict[str, Any]:
    """
    Получает список поставок для объекта монтажа.
    
    Args:
        object_id: ID объекта монтажа
        skip: Смещение для пагинации
        limit: Лимит на страницу
        status_filter: Фильтр по статусу
        db: Сессия БД
        current_user: Текущий пользователь
        
    Returns:
        Список поставок с пагинацией
    """
    try:
        # Проверяем существование объекта
        obj_stmt = select(InstallationObject).where(
            and_(
                InstallationObject.id == object_id,
                InstallationObject.deleted_at.is_(None)
            )
        )
        obj_result = await db.execute(obj_stmt)
        obj = obj_result.scalar_one_or_none()
        
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Installation object with ID {object_id} not found"
            )
        
        # Получаем поставки
        stmt = select(InstallationSupply).where(
            InstallationSupply.installation_object_id == object_id
        )
        
        if status_filter:
            stmt = stmt.where(InstallationSupply.status == status_filter)
        
        # Считаем общее количество
        count_stmt = select(func.count()).select_from(
            select(InstallationSupply)
            .where(InstallationSupply.installation_object_id == object_id)
            .subquery()
        )
        if status_filter:
            count_stmt = select(func.count()).select_from(
                select(InstallationSupply)
                .where(
                    and_(
                        InstallationSupply.installation_object_id == object_id,
                        InstallationSupply.status == status_filter
                    )
                )
                .subquery()
            )
        
        total_result = await db.execute(count_stmt)
        total = total_result.scalar() or 0
        
        # Пагинация и сортировка
        stmt = stmt.order_by(
            InstallationSupply.delivery_date.desc()
        ).offset(skip).limit(limit)
        
        result = await db.execute(stmt)
        supplies = result.scalars().all()
        
        # Форматируем ответ
        supplies_data = []
        for supply in supplies:
            supplies_data.append({
                "id": supply.id,
                "delivery_service": supply.delivery_service,
                "delivery_date": supply.delivery_date.isoformat() if supply.delivery_date else None,
                "document": supply.document,
                "description": supply.description,
                "status": supply.status,
                "created_at": supply.created_at.isoformat() if supply.created_at else None,
                "created_by": supply.created_by,
                "updated_at": supply.updated_at.isoformat() if supply.updated_at else None,
            })
        
        return {
            "object_id": object_id,
            "supplies": supplies_data,
            "total": total,
            "skip": skip,
            "limit": limit,
            "has_more": (skip + len(supplies_data)) < total
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching supplies: {str(e)}"
        )


@router.post("/objects/{object_id}/supplies", response_model=Dict[str, Any])
async def create_installation_supply(
    object_id: int = Path(..., description="ID объекта монтажа"),
    supply_data: Dict[str, Any] = Body(..., description="Данные поставки"),
    db: AsyncSession = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: bool = Depends(require_permission("write")),
    __: bool = Depends(require_installation_access),
) -> Dict[str, Any]:
    """
    Создает новую поставку для объекта монтажа.
    
    Args:
        object_id: ID объекта монтажа
        supply_data: Данные поставки
        db: Сессия БД
        current_user: Текущий пользователь
        
    Returns:
        Созданная поставка
    """
    try:
        # Проверяем существование объекта
        obj_stmt = select(InstallationObject).where(
            and_(
                InstallationObject.id == object_id,
                InstallationObject.deleted_at.is_(None)
            )
        )
        obj_result = await db.execute(obj_stmt)
        obj = obj_result.scalar_one_or_none()
        
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Installation object with ID {object_id} not found"
            )
        
        # Валидация данных
        required_fields = ["delivery_service", "delivery_date"]
        for field in required_fields:
            if field not in supply_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required field: {field}"
                )
        
        # Парсим дату доставки
        try:
            delivery_date = datetime.fromisoformat(supply_data["delivery_date"].replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid delivery_date format. Use ISO format."
            )
        
        # Создаем поставку
        supply = InstallationSupply(
            installation_object_id=object_id,
            delivery_service=supply_data["delivery_service"],
            delivery_date=delivery_date,
            document=supply_data.get("document"),
            description=supply_data.get("description"),
            status=supply_data.get("status", "planned"),
            created_by=current_user.get("id", 0),
        )
        
        db.add(supply)
        await db.commit()
        await db.refresh(supply)
        
        return {
            "id": supply.id,
            "delivery_service": supply.delivery_service,
            "delivery_date": supply.delivery_date.isoformat() if supply.delivery_date else None,
            "status": supply.status,
            "object_id": object_id,
            "created_at": supply.created_at.isoformat() if supply.created_at else None,
            "message": "Supply created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating supply: {str(e)}"
        )


# === Экспорт данных ===

@router.get("/objects/{object_id}/export", response_model=Dict[str, Any])
async def export_installation_data(
    object_id: int = Path(..., description="ID объекта монтажа"),
    export_type: str = Query("summary", description="Тип экспорта: summary, materials, montage, supplies, all"),
    format: str = Query("json", description="Формат: json, csv"),
    db: AsyncSession = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: bool = Depends(require_installation_access),
) -> Dict[str, Any]:
    """
    Экспортирует данные объекта монтажа.
    
    Args:
        object_id: ID объекта монтажа
        export_type: Тип экспорта
        format: Формат экспорта
        db: Сессия БД
        current_user: Текущий пользователь
        
    Returns:
        Экспортированные данные
    """
    try:
        # Проверяем существование объекта
        obj_stmt = select(InstallationObject).where(
            and_(
                InstallationObject.id == object_id,
                InstallationObject.deleted_at.is_(None)
            )
        )
        obj_result = await db.execute(obj_stmt)
        obj = obj_result.scalar_one_or_none()
        
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Installation object with ID {object_id} not found"
            )
        
        # Собираем данные в зависимости от типа экспорта
        export_data = {
            "object_id": object_id,
            "export_type": export_type,
            "format": format,
            "exported_at": datetime.utcnow().isoformat(),
            "exported_by": current_user.get("id", 0),
            "data": {}
        }
        
        # Базовые данные объекта
        if export_type in ["summary", "all"]:
            export_data["data"]["object"] = {
                "id": obj.id,
                "short_name": obj.short_name,
                "full_name": obj.full_name,
                "region": obj.region,
                "addresses": obj.addresses,
                "contract_type": obj.contract_type,
                "contract_number": obj.contract_number,
                "contract_date": obj.contract_date.isoformat() if obj.contract_date else None,
                "start_date": obj.start_date.isoformat() if obj.start_date else None,
                "end_date": obj.end_date.isoformat() if obj.end_date else None,
                "systems": obj.systems,
                "note": obj.note,
                "status": obj.status,
                "created_at": obj.created_at.isoformat() if obj.created_at else None,
            }
        
        # Проекты
        if export_type in ["all"]:
            projects_stmt = select(InstallationProject).where(
                InstallationProject.installation_object_id == object_id
            )
            projects_result = await db.execute(projects_stmt)
            projects = projects_result.scalars().all()
            
            projects_data = []
            for project in projects:
                projects_data.append({
                    "id": project.id,
                    "name": project.name,
                    "description": project.description,
                    "file_id": project.file_id,
                    "file_size": project.file_size,
                    "created_at": project.created_at.isoformat() if project.created_at else None,
                    "created_by": project.created_by,
                })
            
            export_data["data"]["projects"] = projects_data
        
        # Материалы
        if export_type in ["materials", "all"]:
            materials_stmt = select(InstallationMaterial).where(
                InstallationMaterial.installation_object_id == object_id
            ).order_by(InstallationMaterial.name.asc())
            
            materials_result = await db.execute(materials_stmt)
            materials = materials_result.scalars().all()
            
            materials_data = []
            for material in materials:
                materials_data.append({
                    "id": material.id,
                    "name": material.name,
                    "description": material.description,
                    "quantity": float(material.quantity) if material.quantity else 0.0,
                    "unit": material.unit,
                    "section_id": material.section_id,
                    "total_installed": float(material.total_installed) if material.total_installed else 0.0,
                    "remaining": float(material.quantity - (material.total_installed or 0)) if material.quantity else 0.0,
                    "created_at": material.created_at.isoformat() if material.created_at else None,
                    "created_by": material.created_by,
                })
            
            export_data["data"]["materials"] = materials_data
        
        # Разделы материалов
        if export_type in ["materials", "all"]:
            sections_stmt = select(InstallationMaterialSection).where(
                InstallationMaterialSection.installation_object_id == object_id
            ).order_by(InstallationMaterialSection.name.asc())
            
            sections_result = await db.execute(sections_stmt)
            sections = sections_result.scalars().all()
            
            sections_data = []
            for section in sections:
                sections_data.append({
                    "id": section.id,
                    "name": section.name,
                    "description": section.description,
                    "created_at": section.created_at.isoformat() if section.created_at else None,
                    "created_by": section.created_by,
                })
            
            export_data["data"]["sections"] = sections_data
        
        # Монтаж
        if export_type in ["montage", "all"]:
            montage_stmt = select(InstallationMontage).where(
                InstallationMontage.installation_object_id == object_id
            ).order_by(InstallationMontage.installed_at.desc())
            
            montage_result = await db.execute(montage_stmt)
            montage_entries = montage_result.scalars().all()
            
            montage_data = []
            for entry in montage_entries:
                montage_data.append({
                    "id": entry.id,
                    "material_id": entry.material_id,
                    "material_name": entry.material_name,
                    "section_id": entry.section_id,
                    "quantity_installed": float(entry.quantity_installed) if entry.quantity_installed else 0.0,
                    "installed_by": entry.installed_by,
                    "installed_at": entry.installed_at.isoformat() if entry.installed_at else None,
                    "notes": entry.notes,
                    "created_at": entry.created_at.isoformat() if entry.created_at else None,
                })
            
            export_data["data"]["montage"] = montage_data
        
        # Поставки
        if export_type in ["supplies", "all"]:
            supplies_stmt = select(InstallationSupply).where(
                InstallationSupply.installation_object_id == object_id
            ).order_by(InstallationSupply.delivery_date.desc())
            
            supplies_result = await db.execute(supplies_stmt)
            supplies = supplies_result.scalars().all()
            
            supplies_data = []
            for supply in supplies:
                supplies_data.append({
                    "id": supply.id,
                    "delivery_service": supply.delivery_service,
                    "delivery_date": supply.delivery_date.isoformat() if supply.delivery_date else None,
                    "document": supply.document,
                    "description": supply.description,
                    "status": supply.status,
                    "created_at": supply.created_at.isoformat() if supply.created_at else None,
                    "created_by": supply.created_by,
                })
            
            export_data["data"]["supplies"] = supplies_data
        
        # Статистика
        if export_type in ["summary", "all"]:
            # Статистика материалов
            materials_stats_stmt = select(
                func.count(InstallationMaterial.id).label("total_materials"),
                func.sum(InstallationMaterial.quantity).label("total_quantity"),
                func.sum(InstallationMaterial.total_installed).label("total_installed")
            ).where(
                InstallationMaterial.installation_object_id == object_id
            )
            
            materials_stats_result = await db.execute(materials_stats_stmt)
            materials_stats = materials_stats_result.first()
            
            # Статистика монтажа
            montage_stats_stmt = select(
                func.count(InstallationMontage.id).label("total_montage_entries"),
                func.sum(InstallationMontage.quantity_installed).label("total_montage_quantity")
            ).where(
                InstallationMontage.installation_object_id == object_id
            )
            
            montage_stats_result = await db.execute(montage_stats_stmt)
            montage_stats = montage_stats_result.first()
            
            # Статистика проектов и поставок
            projects_count_stmt = select(func.count(InstallationProject.id)).where(
                InstallationProject.installation_object_id == object_id
            )
            projects_count_result = await db.execute(projects_count_stmt)
            projects_count = projects_count_result.scalar() or 0
            
            supplies_count_stmt = select(func.count(InstallationSupply.id)).where(
                InstallationSupply.installation_object_id == object_id
            )
            supplies_count_result = await db.execute(supplies_count_stmt)
            supplies_count = supplies_count_result.scalar() or 0
            
            export_data["data"]["statistics"] = {
                "materials": {
                    "total": materials_stats.total_materials or 0,
                    "total_quantity": float(materials_stats.total_quantity) if materials_stats.total_quantity else 0.0,
                    "total_installed": float(materials_stats.total_installed) if materials_stats.total_installed else 0.0,
                    "completion_percentage": (
                        float(materials_stats.total_installed) / float(materials_stats.total_quantity) * 100
                    ) if materials_stats.total_quantity and materials_stats.total_quantity > 0 else 0.0,
                },
                "montage": {
                    "total_entries": montage_stats.total_montage_entries or 0,
                    "total_quantity": float(montage_stats.total_montage_quantity) if montage_stats.total_montage_quantity else 0.0,
                },
                "projects": projects_count,
                "supplies": supplies_count,
            }
        
        # Форматируем ответ
        if format == "csv":
            # В реальной реализации здесь была бы генерация CSV
            export_data["message"] = "CSV export available in production version"
            export_data["csv_url"] = f"/api/v1/installation/objects/{object_id}/export/csv?type={export_type}"
        elif format == "json":
            # JSON уже готов
            pass
        
        return export_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error exporting data: {str(e)}"
        )


# === Статистика ===

@router.get("/objects/{object_id}/stats", response_model=Dict[str, Any])
async def get_installation_stats(
    object_id: int = Path(..., description="ID объекта монтажа"),
    db: AsyncSession = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: bool = Depends(require_installation_access),
) -> Dict[str, Any]:
    """
    Получает статистику по объекту монтажа.
    
    Args:
        object_id: ID объекта монтажа
        db: Сессия БД
        current_user: Текущий пользователь
        
    Returns:
        Статистика объекта
    """
    try:
        # Проверяем существование объекта
        obj_stmt = select(InstallationObject).where(
            and_(
                InstallationObject.id == object_id,
                InstallationObject.deleted_at.is_(None)
            )
        )
        obj_result = await db.execute(obj_stmt)
        obj = obj_result.scalar_one_or_none()
        
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Installation object with ID {object_id} not found"
            )
        
        # Собираем статистику
        stats = {
            "object_id": object_id,
            "object_name": obj.short_name,
            "calculated_at": datetime.utcnow().isoformat(),
            "basic_info": {
                "region": obj.region,
                "status": obj.status,
                "contract_number": obj.contract_number,
                "start_date": obj.start_date.isoformat() if obj.start_date else None,
                "end_date": obj.end_date.isoformat() if obj.end_date else None,
                "days_remaining": None,
            },
            "counts": {},
            "completion": {},
            "recent_activity": {},
        }
        
        # Вычисляем оставшиеся дни до окончания контракта
        if obj.end_date:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            if obj.end_date > now:
                days_remaining = (obj.end_date - now).days
                stats["basic_info"]["days_remaining"] = days_remaining
        
        # Количественная статистика
        # Проекты
        projects_count_stmt = select(func.count(InstallationProject.id)).where(
            InstallationProject.installation_object_id == object_id
        )
        projects_count_result = await db.execute(projects_count_stmt)
        stats["counts"]["projects"] = projects_count_result.scalar() or 0
        
        # Материалы
        materials_count_stmt = select(func.count(InstallationMaterial.id)).where(
            InstallationMaterial.installation_object_id == object_id
        )
        materials_count_result = await db.execute(materials_count_stmt)
        stats["counts"]["materials"] = materials_count_result.scalar() or 0
        
        # Разделы материалов
        sections_count_stmt = select(func.count(InstallationMaterialSection.id)).where(
            InstallationMaterialSection.installation_object_id == object_id
        )
        sections_count_result = await db.execute(sections_count_stmt)
        stats["counts"]["sections"] = sections_count_result.scalar() or 0
        
        # Записи монтажа
        montage_count_stmt = select(func.count(InstallationMontage.id)).where(
            InstallationMontage.installation_object_id == object_id
        )
        montage_count_result = await db.execute(montage_count_stmt)
        stats["counts"]["montage_entries"] = montage_count_result.scalar() or 0
        
        # Поставки
        supplies_count_stmt = select(func.count(InstallationSupply.id)).where(
            InstallationSupply.installation_object_id == object_id
        )
        supplies_count_result = await db.execute(supplies_count_stmt)
        stats["counts"]["supplies"] = supplies_count_result.scalar() or 0
        
        # Статистика завершенности
        # Общее количество материалов
        total_materials_stmt = select(
            func.sum(InstallationMaterial.quantity).label("total_quantity"),
            func.sum(InstallationMaterial.total_installed).label("total_installed")
        ).where(
            InstallationMaterial.installation_object_id == object_id
        )
        
        total_materials_result = await db.execute(total_materials_stmt)
        total_materials = total_materials_result.first()
        
        total_quantity = float(total_materials.total_quantity) if total_materials.total_quantity else 0.0
        total_installed = float(total_materials.total_installed) if total_materials.total_installed else 0.0
        
        if total_quantity > 0:
            completion_percentage = (total_installed / total_quantity) * 100
        else:
            completion_percentage = 0.0
        
        stats["completion"] = {
            "total_quantity": total_quantity,
            "total_installed": total_installed,
            "remaining": total_quantity - total_installed,
            "percentage": round(completion_percentage, 2),
        }
        
        # Статистика по статусам поставок
        supplies_status_stmt = select(
            InstallationSupply.status,
            func.count(InstallationSupply.id).label("count")
        ).where(
            InstallationSupply.installation_object_id == object_id
        ).group_by(InstallationSupply.status)
        
        supplies_status_result = await db.execute(supplies_status_stmt)
        supplies_status_rows = supplies_status_result.all()
        
        supplies_by_status = {}
        for status, count in supplies_status_rows:
            supplies_by_status[status] = count
        
        stats["counts"]["supplies_by_status"] = supplies_by_status
        
        # Последняя активность
        # Последняя запись монтажа
        last_montage_stmt = select(InstallationMontage).where(
            InstallationMontage.installation_object_id == object_id
        ).order_by(InstallationMontage.installed_at.desc()).limit(1)
        
        last_montage_result = await db.execute(last_montage_stmt)
        last_montage = last_montage_result.scalar_one_or_none()
        
        if last_montage:
            stats["recent_activity"]["last_montage"] = {
                "date": last_montage.installed_at.isoformat() if last_montage.installed_at else None,
                "material": last_montage.material_name,
                "quantity": float(last_montage.quantity_installed) if last_montage.quantity_installed else 0.0,
            }
        
        # Последняя поставка
        last_supply_stmt = select(InstallationSupply).where(
            InstallationSupply.installation_object_id == object_id
        ).order_by(InstallationSupply.delivery_date.desc()).limit(1)
        
        last_supply_result = await db.execute(last_supply_stmt)
        last_supply = last_supply_result.scalar_one_or_none()
        
        if last_supply:
            stats["recent_activity"]["last_supply"] = {
                "date": last_supply.delivery_date.isoformat() if last_supply.delivery_date else None,
                "service": last_supply.delivery_service,
                "status": last_supply.status,
            }
        
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching stats: {str(e)}"
        )