"""
Сервис для работы с базой данных PostgreSQL.
Реализует абстракцию над операциями с БД, обеспечивает валидацию,
обработку транзакций и управление подключениями.
"""
from typing import Any, Dict, List, Optional, Type, TypeVar
from sqlalchemy import text, select, update, delete, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import logging

from storage.database import async_session
from storage.models.base import BaseModel
from utils.exceptions import DatabaseError, ValidationError

T = TypeVar('T', bound=BaseModel)

logger = logging.getLogger(__name__)


class DatabaseService:
    """Сервис для работы с базой данных"""
    
    def __init__(self):
        self.session_factory = async_session
    
    async def get_session(self) -> AsyncSession:
        """Получить асинхронную сессию БД"""
        return self.session_factory()
    
    async def create(self, session: AsyncSession, model_class: Type[T], **kwargs) -> T:
        """
        Создать новую запись в БД
        
        Args:
            session: Асинхронная сессия БД
            model_class: Класс модели SQLAlchemy
            **kwargs: Атрибуты для создания записи
            
        Returns:
            Созданный объект модели
            
        Raises:
            DatabaseError: При ошибке работы с БД
            ValidationError: При нарушении ограничений БД
        """
        try:
            # Проверка обязательных полей
            self._validate_required_fields(model_class, kwargs)
            
            # Создание объекта
            obj = model_class(**kwargs)
            session.add(obj)
            await session.flush()
            
            logger.debug(f"Создана запись {model_class.__name__} с ID: {obj.id}")
            return obj
            
        except IntegrityError as e:
            await session.rollback()
            logger.error(f"Ошибка целостности данных при создании {model_class.__name__}: {e}")
            raise ValidationError(f"Нарушение целостности данных: {str(e)}")
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Ошибка БД при создании {model_class.__name__}: {e}")
            raise DatabaseError(f"Ошибка базы данных: {str(e)}")
    
    async def get_by_id(self, session: AsyncSession, model_class: Type[T], obj_id: str) -> Optional[T]:
        """
        Получить запись по ID
        
        Args:
            session: Асинхронная сессия БД
            model_class: Класс модели SQLAlchemy
            obj_id: UUID записи
            
        Returns:
            Объект модели или None если не найден
        """
        try:
            query = select(model_class).where(model_class.id == obj_id)
            result = await session.execute(query)
            return result.scalar_one_or_none()
            
        except SQLAlchemyError as e:
            logger.error(f"Ошибка БД при получении {model_class.__name__} по ID {obj_id}: {e}")
            raise DatabaseError(f"Ошибка базы данных: {str(e)}")
    
    async def get_all(
        self, 
        session: AsyncSession, 
        model_class: Type[T], 
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order_by: Optional[str] = None
    ) -> List[T]:
        """
        Получить все записи с пагинацией
        
        Args:
            session: Асинхронная сессия БД
            model_class: Класс модели SQLAlchemy
            limit: Максимальное количество записей
            offset: Смещение для пагинации
            order_by: Поле для сортировки
            
        Returns:
            Список объектов
        """
        try:
            query = select(model_class)
            
            # Применение сортировки
            if order_by:
                order_column = getattr(model_class, order_by, None)
                if order_column:
                    query = query.order_by(order_column)
            
            # Применение пагинации
            if limit:
                query = query.limit(limit)
            if offset:
                query = query.offset(offset)
            
            result = await session.execute(query)
            return list(result.scalars().all())
            
        except SQLAlchemyError as e:
            logger.error(f"Ошибка БД при получении всех записей {model_class.__name__}: {e}")
            raise DatabaseError(f"Ошибка базы данных: {str(e)}")
    
    async def update(
        self, 
        session: AsyncSession, 
        model_class: Type[T], 
        obj_id: str, 
        **kwargs
    ) -> Optional[T]:
        """
        Обновить запись
        
        Args:
            session: Асинхронная сессия БД
            model_class: Класс модели SQLAlchemy
            obj_id: UUID записи
            **kwargs: Атрибуты для обновления
            
        Returns:
            Обновленный объект или None если не найден
        """
        try:
            # Проверка существования записи
            obj = await self.get_by_id(session, model_class, obj_id)
            if not obj:
                return None
            
            # Обновление атрибутов
            for key, value in kwargs.items():
                if hasattr(obj, key):
                    setattr(obj, key, value)
            
            await session.flush()
            
            # Обновление updated_at
            if hasattr(obj, 'updated_at'):
                update_query = update(model_class).where(
                    model_class.id == obj_id
                ).values(updated_at=func.now())
                await session.execute(update_query)
            
            logger.debug(f"Обновлена запись {model_class.__name__} с ID: {obj_id}")
            return obj
            
        except IntegrityError as e:
            await session.rollback()
            logger.error(f"Ошибка целостности данных при обновлении {model_class.__name__}: {e}")
            raise ValidationError(f"Нарушение целостности данных: {str(e)}")
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Ошибка БД при обновлении {model_class.__name__}: {e}")
            raise DatabaseError(f"Ошибка базы данных: {str(e)}")
    
    async def delete(self, session: AsyncSession, model_class: Type[T], obj_id: str) -> bool:
        """
        Удалить запись
        
        Args:
            session: Асинхронная сессия БД
            model_class: Класс модели SQLAlchemy
            obj_id: UUID записи
            
        Returns:
            True если удалено успешно, False если запись не найдена
        """
        try:
            # Проверка существования записи
            obj = await self.get_by_id(session, model_class, obj_id)
            if not obj:
                return False
            
            # Удаление записи
            delete_query = delete(model_class).where(model_class.id == obj_id)
            await session.execute(delete_query)
            
            logger.debug(f"Удалена запись {model_class.__name__} с ID: {obj_id}")
            return True
            
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Ошибка БД при удалении {model_class.__name__}: {e}")
            raise DatabaseError(f"Ошибка базы данных: {str(e)}")
    
    async def filter(
        self, 
        session: AsyncSession, 
        model_class: Type[T], 
        **filters
    ) -> List[T]:
        """
        Фильтрация записей по условиям
        
        Args:
            session: Асинхронная сессия БД
            model_class: Класс модели SQLAlchemy
            **filters: Параметры фильтрации
            
        Returns:
            Список отфильтрованных объектов
        """
        try:
            query = select(model_class)
            
            # Построение условий фильтрации
            conditions = []
            for key, value in filters.items():
                if hasattr(model_class, key):
                    column = getattr(model_class, key)
                    
                    # Обработка специальных операторов
                    if isinstance(value, dict):
                        for op, op_value in value.items():
                            if op == 'eq':
                                conditions.append(column == op_value)
                            elif op == 'ne':
                                conditions.append(column != op_value)
                            elif op == 'gt':
                                conditions.append(column > op_value)
                            elif op == 'lt':
                                conditions.append(column < op_value)
                            elif op == 'gte':
                                conditions.append(column >= op_value)
                            elif op == 'lte':
                                conditions.append(column <= op_value)
                            elif op == 'like':
                                conditions.append(column.ilike(f"%{op_value}%"))
                            elif op == 'in':
                                conditions.append(column.in_(op_value))
                    else:
                        conditions.append(column == value)
            
            if conditions:
                query = query.where(and_(*conditions))
            
            result = await session.execute(query)
            return list(result.scalars().all())
            
        except SQLAlchemyError as e:
            logger.error(f"Ошибка БД при фильтрации {model_class.__name__}: {e}")
            raise DatabaseError(f"Ошибка базы данных: {str(e)}")
    
    async def count(self, session: AsyncSession, model_class: Type[T], **filters) -> int:
        """
        Подсчет количества записей
        
        Args:
            session: Асинхронная сессия БД
            model_class: Класс модели SQLAlchemy
            **filters: Параметры фильтрации
            
        Returns:
            Количество записей
        """
        try:
            query = select(func.count()).select_from(model_class)
            
            # Построение условий фильтрации
            conditions = []
            for key, value in filters.items():
                if hasattr(model_class, key):
                    column = getattr(model_class, key)
                    conditions.append(column == value)
            
            if conditions:
                query = query.where(and_(*conditions))
            
            result = await session.execute(query)
            return result.scalar() or 0
            
        except SQLAlchemyError as e:
            logger.error(f"Ошибка БД при подсчете {model_class.__name__}: {e}")
            raise DatabaseError(f"Ошибка базы данных: {str(e)}")
    
    async def execute_raw(self, session: AsyncSession, sql: str, params: Dict = None) -> List[Dict]:
        """
        Выполнить сырой SQL запрос
        
        Args:
            session: Асинхронная сессия БД
            sql: SQL запрос
            params: Параметры запроса
            
        Returns:
            Список результатов в виде словарей
        """
        try:
            result = await session.execute(text(sql), params or {})
            rows = result.fetchall()
            
            # Преобразование в словари
            return [
                {column: value for column, value in zip(result.keys(), row)}
                for row in rows
            ]
            
        except SQLAlchemyError as e:
            logger.error(f"Ошибка БД при выполнении сырого запроса: {e}")
            raise DatabaseError(f"Ошибка базы данных: {str(e)}")
    
    def _validate_required_fields(self, model_class: Type[T], data: Dict[str, Any]):
        """
        Проверка обязательных полей
        
        Args:
            model_class: Класс модели
            data: Данные для проверки
            
        Raises:
            ValidationError: Если отсутствуют обязательные поля
        """
        required_fields = []
        
        # Получение информации о столбцах модели
        for column in model_class.__table__.columns:
            if not column.nullable and column.name != 'id':
                required_fields.append(column.name)
        
        # Проверка наличия обязательных полей
        missing_fields = []
        for field in required_fields:
            if field not in data or data[field] is None:
                missing_fields.append(field)
        
        if missing_fields:
            raise ValidationError(
                f"Отсутствуют обязательные поля: {', '.join(missing_fields)}"
            )


# Синглтон экземпляра сервиса
_database_service = None

def get_database_service() -> DatabaseService:
    """Получить экземпляр DatabaseService (синглтон)"""
    global _database_service
    if _database_service is None:
        _database_service = DatabaseService()
    return _database_service