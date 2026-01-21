import uuid
from datetime import datetime
from typing import Optional, Any

from sqlalchemy import Column, DateTime, String, Boolean, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Базовый класс для всех моделей SQLAlchemy."""
    
    __abstract__ = True
    
    # UUID в качестве первичного ключа
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        nullable=False
    )
    
    # Временные метки
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Soft delete (опционально, для некоторых моделей)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    
    # Автоматическое имя таблицы из имени класса
    @declared_attr
    def __tablename__(cls) -> str:
        # Преобразуем CamelCase в snake_case
        import re
        name = cls.__name__
        snake_case = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
        return snake_case
    
    def to_dict(self, exclude: Optional[list] = None) -> dict:
        """Преобразует объект в словарь."""
        exclude = exclude or []
        result = {}
        
        for column in self.__table__.columns:
            column_name = column.name
            if column_name not in exclude:
                value = getattr(self, column_name)
                
                # Обработка специальных типов
                if isinstance(value, uuid.UUID):
                    value = str(value)
                elif isinstance(value, datetime):
                    value = value.isoformat()
                
                result[column_name] = value
        
        return result
    
    def update_from_dict(self, data: dict) -> None:
        """Обновляет атрибуты объекта из словаря."""
        for key, value in data.items():
            if hasattr(self, key) and not key.startswith('_'):
                setattr(self, key, value)
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.id})>"