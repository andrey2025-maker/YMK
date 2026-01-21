from datetime import datetime
from enum import Enum
from typing import Optional, List
import uuid

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, 
    ForeignKey, Text, ARRAY, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from .base import Base


class AdminLevel(Enum):
    """Уровни администраторов."""
    MAIN_ADMIN = "main_admin"       # Главный админ
    ADMIN = "admin"                 # Админ
    SERVICE = "service"             # Обслуга
    INSTALLATION = "installation"   # Монтаж


class User(Base):
    """Модель пользователя Telegram."""
    
    telegram_id: Mapped[int] = mapped_column(
        Integer,
        unique=True,
        nullable=False,
        index=True
    )
    
    username: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True
    )
    
    first_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    last_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    # Признак активации (пользователь начал диалог с ботом)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    
    # Дата последней активности
    last_active: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Связи
    admin: Mapped[Optional["Admin"]] = relationship(
        "Admin",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    access_records: Mapped[List["UserAccess"]] = relationship(
        "UserAccess",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    def __str__(self) -> str:
        return f"User(id={self.telegram_id}, username=@{self.username})"


class Admin(Base):
    """Модель администратора."""
    
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    
    level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=AdminLevel.ADMIN.value
    )
    
    # Кто назначил этого админа (если не главный)
    assigned_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Дата назначения
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    # Признак активности (админ может быть временно отключен)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    
    # Связи
    user: Mapped["User"] = relationship(
        "User",
        back_populates="admin"
    )
    
    permissions: Mapped[Optional["AdminPermission"]] = relationship(
        "AdminPermission",
        back_populates="admin",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    assigned_admins: Mapped[List["Admin"]] = relationship(
        "Admin",
        remote_side=[id],
        backref="assigner"
    )
    
    def get_level_display(self) -> str:
        """Возвращает отображаемое название уровня."""
        levels = {
            AdminLevel.MAIN_ADMIN.value: "Главный админ",
            AdminLevel.ADMIN.value: "Админ",
            AdminLevel.SERVICE.value: "Обслуга",
            AdminLevel.INSTALLATION.value: "Монтаж",
        }
        return levels.get(self.level, self.level)
    
    def has_permission(self, permission_type: str, command: str) -> bool:
        """Проверяет, есть ли у админа разрешение на команду."""
        if not self.permissions:
            return False
        
        # Главный админ имеет все права
        if self.level == AdminLevel.MAIN_ADMIN.value:
            return True
        
        # Проверяем конкретное разрешение
        permissions = getattr(self.permissions, permission_type, {})
        return permissions.get(command, False)
    
    def __str__(self) -> str:
        return f"Admin(level={self.level}, user={self.user})"


class AdminPermission(Base):
    """Модель разрешений для администраторов."""
    
    admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    
    # Разрешения для личных сообщений
    # Структура: {"command_name": True/False}
    pm_permissions: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict
    )
    
    # Разрешения для групп
    group_permissions: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict
    )
    
    # Дата последнего обновления
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Связи
    admin: Mapped["Admin"] = relationship(
        "Admin",
        back_populates="permissions"
    )
    
    updater: Mapped[Optional["Admin"]] = relationship(
        "Admin",
        foreign_keys=[updated_by],
        remote_side=[Admin.id]
    )


class UserAccess(Base):
    """Модель доступа пользователей к объектам."""
    
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Тип объекта: service или installation
    object_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    
    # ID объекта (может быть регионом или конкретным объектом)
    object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False
    )
    
    # Уровень доступа: view, edit, full
    access_level: Mapped[str] = mapped_column(
        String(50),
        default="view",
        nullable=False
    )
    
    # Кто предоставил доступ
    granted_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Дата предоставления доступа
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    # Дата истечения доступа (если нужно)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Связи
    user: Mapped["User"] = relationship(
        "User",
        back_populates="access_records"
    )
    
    granter: Mapped[Optional["Admin"]] = relationship(
        "Admin",
        foreign_keys=[granted_by]
    )
    
    def is_expired(self) -> bool:
        """Проверяет, истек ли срок доступа."""
        if not self.expires_at:
            return False
        from datetime import datetime
        return datetime.now() > self.expires_at
    
    def __str__(self) -> str:
        return f"UserAccess(user={self.user}, object_type={self.object_type})"