"""
Сервис для работы с базой данных.
Реализует CRUD операции, управление транзакциями и миграциями.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Type, TypeVar, Generic, AsyncGenerator
from datetime import datetime

from sqlalchemy import select, update, delete, insert, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError

from storage.database import async_session_maker
from storage.models.base import BaseModel

T = TypeVar('T', bound=BaseModel)

logger = logging.getLogger(__name__)


class DatabaseService:
    """Сервис для работы с базой данных."""

    def __init__(self):
        self.session_maker = async_session_maker

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Контекстный менеджер для получения сессии БД.
        
        Пример использования:
        async with db_service.get_session() as session:
            result = await session.execute(query)
        """
        async with self.session_maker() as session:
            try:
                yield session
                await session.commit()
            except SQLAlchemyError as e:
                await session.rollback()
                logger.error(f"Database error: {e}")
                raise
            finally:
                await session.close()

    async def create(self, session: AsyncSession, model: BaseModel) -> BaseModel:
        """
        Создание новой записи в БД.
        
        Args:
            session: Асинхронная сессия БД
            model: Экземпляр модели для сохранения
            
        Returns:
            Сохраненная модель с ID
        """
        try:
            session.add(model)
            await session.flush()
            await session.refresh(model)
            return model
        except SQLAlchemyError as e:
            logger.error(f"Error creating {model.__class__.__name__}: {e}")
            raise

    async def get_by_id(
        self, 
        session: AsyncSession, 
        model_class: Type[T], 
        id: str,
        load_relationships: bool = False
    ) -> Optional[T]:
        """
        Получение записи по ID.
        
        Args:
            session: Асинхронная сессия БД
            model_class: Класс модели
            id: UUID записи
            load_relationships: Загружать связанные объекты
            
        Returns:
            Найденная запись или None
        """
        try:
            query = select(model_class).where(model_class.id == id)
            
            if load_relationships:
                # Автоматическая загрузка всех отношений
                relationships = list(model_class.__mapper__.relationships.keys())
                for rel in relationships:
                    query = query.options(selectinload(getattr(model_class, rel)))
            
            result = await session.execute(query)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Error getting {model_class.__name__} by id {id}: {e}")
            raise

    async def get_all(
        self, 
        session: AsyncSession, 
        model_class: Type[T],
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None
    ) -> List[T]:
        """
        Получение всех записей с пагинацией и фильтрацией.
        
        Args:
            session: Асинхронная сессия БД
            model_class: Класс модели
            skip: Количество записей для пропуска
            limit: Максимальное количество записей
            filters: Словарь фильтров {поле: значение}
            order_by: Поле для сортировки
            
        Returns:
            Список записей
        """
        try:
            query = select(model_class)
            
            # Применение фильтров
            if filters:
                for field, value in filters.items():
                    if hasattr(model_class, field):
                        query = query.where(getattr(model_class, field) == value)
            
            # Сортировка
            if order_by and hasattr(model_class, order_by):
                query = query.order_by(getattr(model_class, order_by))
            else:
                query = query.order_by(model_class.created_at.desc())
            
            # Пагинация
            query = query.offset(skip).limit(limit)
            
            result = await session.execute(query)
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Error getting all {model_class.__name__}: {e}")
            raise

    async def update(
        self, 
        session: AsyncSession, 
        model: BaseModel, 
        update_data: Dict[str, Any]
    ) -> BaseModel:
        """
        Обновление записи в БД.
        
        Args:
            session: Асинхронная сессия БД
            model: Экземпляр модели для обновления
            update_data: Словарь с данными для обновления {поле: значение}
            
        Returns:
            Обновленная модель
        """
        try:
            # Обновление полей
            for field, value in update_data.items():
                if hasattr(model, field):
                    setattr(model, field, value)
            
            # Обновление временной метки
            model.updated_at = datetime.utcnow()
            
            await session.flush()
            return model
        except SQLAlchemyError as e:
            logger.error(f"Error updating {model.__class__.__name__}: {e}")
            raise

    async def delete(self, session: AsyncSession, model: BaseModel) -> bool:
        """
        Удаление записи из БД.
        
        Args:
            session: Асинхронная сессия БД
            model: Экземпляр модели для удаления
            
        Returns:
            True если удаление успешно
        """
        try:
            await session.delete(model)
            await session.flush()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error deleting {model.__class__.__name__}: {e}")
            raise

    async def bulk_create(
        self, 
        session: AsyncSession, 
        model_class: Type[T], 
        items: List[Dict[str, Any]]
    ) -> List[T]:
        """
        Массовое создание записей.
        
        Args:
            session: Асинхронная сессия БД
            model_class: Класс модели
            items: Список словарей с данными
            
        Returns:
            Список созданных моделей
        """
        try:
            created_models = []
            for item_data in items:
                model = model_class(**item_data)
                session.add(model)
                created_models.append(model)
            
            await session.flush()
            
            # Обновляем созданные модели для получения ID
            for model in created_models:
                await session.refresh(model)
            
            return created_models
        except SQLAlchemyError as e:
            logger.error(f"Error bulk creating {model_class.__name__}: {e}")
            raise

    async def execute_raw_query(
        self, 
        session: AsyncSession, 
        query: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Выполнение сырого SQL запроса.
        
        Args:
            session: Асинхронная сессия БД
            query: SQL запрос
            params: Параметры запроса
            
        Returns:
            Список словарей с результатами
        """
        try:
            result = await session.execute(text(query), params or {})
            rows = result.fetchall()
            
            # Преобразование в список словарей
            return [dict(row._mapping) for row in rows]
        except SQLAlchemyError as e:
            logger.error(f"Error executing raw query: {e}")
            raise

    async def count(
        self, 
        session: AsyncSession, 
        model_class: Type[T],
        filters: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Подсчет количества записей с фильтрами.
        
        Args:
            session: Асинхронная сессия БД
            model_class: Класс модели
            filters: Словарь фильтров
            
        Returns:
            Количество записей
        """
        try:
            query = select(model_class)
            
            if filters:
                for field, value in filters.items():
                    if hasattr(model_class, field):
                        query = query.where(getattr(model_class, field) == value)
            
            result = await session.execute(select([query.subquery()]).count())
            return result.scalar()
        except SQLAlchemyError as e:
            logger.error(f"Error counting {model_class.__name__}: {e}")
            raise

    async def exists(
        self, 
        session: AsyncSession, 
        model_class: Type[T], 
        filters: Dict[str, Any]
    ) -> bool:
        """
        Проверка существования записи по фильтрам.
        
        Args:
            session: Асинхронная сессия БД
            model_class: Класс модели
            filters: Словарь фильтров
            
        Returns:
            True если запись существует
        """
        try:
            query = select(model_class.id)
            
            for field, value in filters.items():
                if hasattr(model_class, field):
                    query = query.where(getattr(model_class, field) == value)
            
            query = query.limit(1)
            result = await session.execute(query)
            return result.scalar_one_or_none() is not None
        except SQLAlchemyError as e:
            logger.error(f"Error checking existence of {model_class.__name__}: {e}")
            raise

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Контекстный менеджер для транзакций.
        
        Пример использования:
        async with db_service.transaction() as session:
            # операции в транзакции
        """
        async with self.get_session() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    async def health_check(self) -> bool:
        """
        Проверка работоспособности БД.
        
        Returns:
            True если БД доступна
        """
        try:
            async with self.get_session() as session:
                await session.execute(text("SELECT 1"))
                return True
        except SQLAlchemyError as e:
            logger.error(f"Database health check failed: {e}")
            return False