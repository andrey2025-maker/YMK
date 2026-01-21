from typing import Type, TypeVar, Generic, List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from storage.models.base import Base


ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Базовый репозиторий с CRUD операциями."""
    
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session
    
    async def get(self, id: UUID) -> Optional[ModelType]:
        """Получает объект по ID."""
        query = select(self.model).where(
            self.model.id == id,
            self.model.is_deleted == False
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_all(
        self, 
        skip: int = 0, 
        limit: int = 100,
        **filters
    ) -> List[ModelType]:
        """Получает все объекты с пагинацией и фильтрацией."""
        query = select(self.model).where(self.model.is_deleted == False)
        
        # Применяем фильтры
        for key, value in filters.items():
            if hasattr(self.model, key):
                if value is None:
                    query = query.where(getattr(self.model, key).is_(None))
                else:
                    query = query.where(getattr(self.model, key) == value)
        
        # Применяем пагинацию
        query = query.offset(skip).limit(limit)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def create(self, **kwargs) -> ModelType:
        """Создает новый объект."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        return instance
    
    async def update(self, id: UUID, **kwargs) -> Optional[ModelType]:
        """Обновляет объект."""
        query = (
            update(self.model)
            .where(self.model.id == id)
            .values(**kwargs, updated_at=datetime.now())
            .returning(self.model)
        )
        
        result = await self.session.execute(query)
        await self.session.flush()
        
        instance = result.scalar_one_or_none()
        if instance:
            # Обновляем объект в сессии
            await self.session.refresh(instance)
        
        return instance
    
    async def delete(self, id: UUID, soft_delete: bool = True) -> bool:
        """Удаляет объект."""
        if soft_delete:
            # Мягкое удаление
            query = (
                update(self.model)
                .where(self.model.id == id)
                .values(is_deleted=True, updated_at=datetime.now())
            )
        else:
            # Физическое удаление
            query = delete(self.model).where(self.model.id == id)
        
        result = await self.session.execute(query)
        await self.session.flush()
        
        return result.rowcount > 0
    
    async def count(self, **filters) -> int:
        """Считает количество объектов."""
        query = select(func.count()).select_from(self.model).where(self.model.is_deleted == False)
        
        for key, value in filters.items():
            if hasattr(self.model, key):
                if value is None:
                    query = query.where(getattr(self.model, key).is_(None))
                else:
                    query = query.where(getattr(self.model, key) == value)
        
        result = await self.session.execute(query)
        return result.scalar() or 0
    
    async def exists(self, id: UUID) -> bool:
        """Проверяет существование объекта."""
        query = select(self.model.id).where(
            self.model.id == id,
            self.model.is_deleted == False
        ).limit(1)
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None
    
    async def filter_by(self, **filters) -> List[ModelType]:
        """Фильтрует объекты по критериям."""
        query = select(self.model).where(self.model.is_deleted == False)
        
        for key, value in filters.items():
            if hasattr(self.model, key):
                if isinstance(value, list):
                    query = query.where(getattr(self.model, key).in_(value))
                elif value is None:
                    query = query.where(getattr(self.model, key).is_(None))
                else:
                    query = query.where(getattr(self.model, key) == value)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_one_by(self, **filters) -> Optional[ModelType]:
        """Получает один объект по критериям."""
        query = select(self.model).where(self.model.is_deleted == False)
        
        for key, value in filters.items():
            if hasattr(self.model, key):
                if value is None:
                    query = query.where(getattr(self.model, key).is_(None))
                else:
                    query = query.where(getattr(self.model, key) == value)
        
        query = query.limit(1)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()