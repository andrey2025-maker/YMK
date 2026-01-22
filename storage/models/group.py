"""
Модели для работы с группами.
Хранение привязок объектов к группам, прав пользователей и администраторов групп.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List

from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime, 
    ForeignKey, JSON, BigInteger
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base


class GroupBinding(Base):
    """Модель привязки объекта к группе."""
    
    __tablename__ = "group_bindings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Информация о группе
    chat_id = Column(BigInteger, nullable=False, index=True)       # ID чата/группы в Telegram
    chat_title = Column(String(200), nullable=True)                # Название группы (кешированное)
    
    # Информация об объекте
    object_type = Column(String(50), nullable=False, index=True)   # Тип объекта (service, installation, service_region)
    object_id = Column(UUID(as_uuid=True), nullable=False)         # ID объекта
    object_name = Column(String(100), nullable=False)              # Название объекта (сокращенное)
    full_object_name = Column(String(200), nullable=True)          # Полное название объекта
    
    # Дополнительная информация
    description = Column(Text, nullable=True)                      # Описание привязки
    metadata = Column(JSON, default=dict)                          # Дополнительные метаданные
    
    # Статус
    is_active = Column(Boolean, default=True, index=True)          # Активна ли привязка
    is_default = Column(Boolean, default=False)                    # Является ли привязкой по умолчанию
    
    # Время создания/обновления
    created_by = Column(Integer, nullable=False)                   # Кем создана
    updated_by = Column(Integer, nullable=True)                    # Кем обновлена
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deactivated_at = Column(DateTime, nullable=True)               # Когда деактивирована
    
    # Индексы
    __table_args__ = (
        # Уникальность: объект может быть привязан к группе только один раз
        # (но один объект может быть в нескольких группах)
        # Один объект -> одна группа (но разные объекты могут быть в одной группе)
        # Это сложный индекс, нужно подумать о структуре
    )
    
    def __repr__(self):
        return f"<GroupBinding(id={self.id}, chat_id={self.chat_id}, object_type='{self.object_type}', object_name='{self.object_name}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь."""
        return {
            'id': str(self.id),
            'chat_id': self.chat_id,
            'chat_title': self.chat_title,
            'object_type': self.object_type,
            'object_id': str(self.object_id),
            'object_name': self.object_name,
            'full_object_name': self.full_object_name,
            'description': self.description,
            'metadata': self.metadata,
            'is_active': self.is_active,
            'is_default': self.is_default,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'deactivated_at': self.deactivated_at.isoformat() if self.deactivated_at else None
        }


class GroupPermission(Base):
    """Модель прав пользователя в группе."""
    
    __tablename__ = "group_permissions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Связь с группой и пользователем
    chat_id = Column(BigInteger, nullable=False, index=True)       # ID чата/группы
    user_id = Column(Integer, nullable=False, index=True)          # ID пользователя
    
    # Роль пользователя в группе
    role = Column(String(50), default='member')                    # Роль (owner, administrator, member, restricted)
    
    # Права пользователя
    permissions = Column(JSON, default=dict)                       # Словарь прав: {'view': True, 'edit': False, ...}
    
    # Дополнительная информация
    description = Column(Text, nullable=True)                      # Описание прав
    metadata = Column(JSON, default=dict)                          # Дополнительные метаданные
    
    # Статус
    is_active = Column(Boolean, default=True, index=True)          # Активны ли права
    
    # Время
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)                   # Когда истекают права
    
    # Индексы
    __table_args__ = (
        # Уникальность: пользователь может иметь только одну запись прав в группе
        # (но может быть в нескольких группах)
    )
    
    def __repr__(self):
        return f"<GroupPermission(id={self.id}, chat_id={self.chat_id}, user_id={self.user_id}, role='{self.role}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь."""
        return {
            'id': str(self.id),
            'chat_id': self.chat_id,
            'user_id': self.user_id,
            'role': self.role,
            'permissions': self.permissions,
            'description': self.description,
            'metadata': self.metadata,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }
    
    def has_permission(self, permission: str) -> bool:
        """Проверка наличия права."""
        return self.permissions.get(permission, False)
    
    def set_permission(self, permission: str, value: bool):
        """Установка права."""
        self.permissions[permission] = value
        self.updated_at = datetime.utcnow()


class GroupAdmin(Base):
    """Модель администратора группы."""
    
    __tablename__ = "group_admins"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Связь с группой и пользователем
    chat_id = Column(BigInteger, nullable=False, index=True)       # ID чата/группы
    user_id = Column(Integer, nullable=False, index=True)          # ID пользователя-администратора
    
    # Тип администратора
    admin_type = Column(String(50), default='group_admin')         # Тип (group_admin, main_admin)
    
    # Права администратора
    permissions = Column(JSON, default=dict)                       # Дополнительные права администратора
    
    # Дополнительная информация
    description = Column(Text, nullable=True)                      # Описание
    metadata = Column(JSON, default=dict)                          # Метаданные
    
    # Статус
    is_active = Column(Boolean, default=True, index=True)          # Активен ли администратор
    
    # Время
    created_by = Column(Integer, nullable=False)                   # Кем назначен
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deactivated_at = Column(DateTime, nullable=True)               # Когда деактивирован
    
    def __repr__(self):
        return f"<GroupAdmin(id={self.id}, chat_id={self.chat_id}, user_id={self.user_id}, admin_type='{self.admin_type}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь."""
        return {
            'id': str(self.id),
            'chat_id': self.chat_id,
            'user_id': self.user_id,
            'admin_type': self.admin_type,
            'permissions': self.permissions,
            'description': self.description,
            'metadata': self.metadata,
            'is_active': self.is_active,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'deactivated_at': self.deactivated_at.isoformat() if self.deactivated_at else None
        }