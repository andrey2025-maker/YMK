"""
Модели для логирования действий в системе.
Хранение логов изменений, действий пользователей и ошибок системы.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional

from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime, 
    ForeignKey, JSON, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base


class LogLevel(str, Enum):
    """Уровни логирования."""
    DEBUG = "debug"                 # Отладочная информация
    INFO = "info"                   # Информационные сообщения
    WARNING = "warning"             # Предупреждения
    ERROR = "error"                 # Ошибки
    CRITICAL = "critical"           # Критические ошибки


class LogType(str, Enum):
    """Типы логов."""
    SYSTEM = "system"               # Системные логи
    USER_ACTION = "user_action"     # Действия пользователей
    DATA_CHANGE = "data_change"     # Изменения данных
    ADMIN_ACTION = "admin_action"   # Действия администраторов
    ERROR = "error"                 # Ошибки
    SECURITY = "security"           # События безопасности
    AUDIT = "audit"                 # Аудит
    PERFORMANCE = "performance"     # Производительность


class ChangeType(str, Enum):
    """Типы изменений данных."""
    CREATE = "create"               # Создание
    UPDATE = "update"               # Обновление
    DELETE = "delete"               # Удаление
    ARCHIVE = "archive"             Архивирование
    RESTORE = "restore"             # Восстановление


class LogEntry(Base):
    """Базовая модель записи лога."""
    
    __tablename__ = "log_entries"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Основная информация
    log_type = Column(SQLEnum(LogType), nullable=False)            # Тип лога
    log_level = Column(SQLEnum(LogLevel), default=LogLevel.INFO)   # Уровень логирования
    source = Column(String(100), nullable=False)                   # Источник (модуль/функция)
    message = Column(Text, nullable=False)                         # Сообщение
    
    # Контекст
    user_id = Column(Integer, nullable=True)                       # ID пользователя
    chat_id = Column(BigInteger, nullable=True)                    # ID чата/группы
    message_id = Column(Integer, nullable=True)                    # ID сообщения
    
    # Данные
    data = Column(JSON, default=dict)                              # Дополнительные данные
    metadata = Column(JSON, default=dict)                          # Метаданные
    
    # Время
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Индексы
    __table_args__ = (
        # Индексы для быстрого поиска по часто используемым полям
    )
    
    def __repr__(self):
        return f"<LogEntry(id={self.id}, type='{self.log_type}', level='{self.log_level}', source='{self.source}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь."""
        return {
            'id': str(self.id),
            'log_type': self.log_type.value,
            'log_level': self.log_level.value,
            'source': self.source,
            'message': self.message,
            'user_id': self.user_id,
            'chat_id': self.chat_id,
            'message_id': self.message_id,
            'data': self.data,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class ChangeLog(Base):
    """Модель лога изменений данных."""
    
    __tablename__ = "change_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Информация об изменении
    change_type = Column(SQLEnum(ChangeType), nullable=False)      # Тип изменения
    object_type = Column(String(50), nullable=False)               # Тип объекта (service_object, installation_object и т.д.)
    object_id = Column(UUID(as_uuid=True), nullable=False)         # ID объекта
    object_name = Column(String(200), nullable=True)               # Название объекта
    
    # Данные об изменении
    old_data = Column(JSON, nullable=True)                         # Старые данные
    new_data = Column(JSON, nullable=True)                         # Новые данные
    changed_fields = Column(JSON, nullable=True)                   # Список измененных полей
    diff = Column(JSON, nullable=True)                             # Различия между старыми и новыми данными
    
    # Контекст
    user_id = Column(Integer, nullable=False)                      # ID пользователя, совершившего изменение
    chat_id = Column(BigInteger, nullable=True)                    # ID чата/группы, где произошло изменение
    ip_address = Column(String(45), nullable=True)                 # IP адрес
    user_agent = Column(String(500), nullable=True)                # User agent
    
    # Дополнительная информация
    description = Column(Text, nullable=True)                      # Описание изменения
    reason = Column(String(200), nullable=True)                    # Причина изменения
    tags = Column(String(500), nullable=True)                      # Теги через запятую
    
    # Связь с архивом
    archived_to = Column(String(500), nullable=True)               # Куда заархивированы данные
    archive_message_id = Column(Integer, nullable=True)            # ID сообщения в архиве
    
    # Время
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f"<ChangeLog(id={self.id}, type='{self.change_type}', object_type='{self.object_type}', object_id={self.object_id})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь."""
        return {
            'id': str(self.id),
            'change_type': self.change_type.value,
            'object_type': self.object_type,
            'object_id': str(self.object_id),
            'object_name': self.object_name,
            'old_data': self.old_data,
            'new_data': self.new_data,
            'changed_fields': self.changed_fields,
            'diff': self.diff,
            'user_id': self.user_id,
            'chat_id': self.chat_id,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'description': self.description,
            'reason': self.reason,
            'tags': self.tags,
            'archived_to': self.archived_to,
            'archive_message_id': self.archive_message_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @property
    def formatted_change(self) -> str:
        """Форматированное описание изменения."""
        if self.change_type == ChangeType.CREATE:
            return f"Создан {self.object_type} '{self.object_name}'"
        elif self.change_type == ChangeType.UPDATE:
            return f"Обновлен {self.object_type} '{self.object_name}'"
        elif self.change_type == ChangeType.DELETE:
            return f"Удален {self.object_type} '{self.object_name}'"
        elif self.change_type == ChangeType.ARCHIVE:
            return f"Заархивирован {self.object_type} '{self.object_name}'"
        elif self.change_type == ChangeType.RESTORE:
            return f"Восстановлен {self.object_type} '{self.object_name}'"
        else:
            return f"Изменен {self.object_type} '{self.object_name}'"


class ErrorLog(Base):
    """Модель лога ошибок."""
    
    __tablename__ = "error_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Информация об ошибке
    error_type = Column(String(100), nullable=False)               # Тип ошибки
    error_message = Column(Text, nullable=False)                   # Сообщение об ошибке
    error_details = Column(Text, nullable=True)                    # Детали ошибки
    traceback = Column(Text, nullable=True)                        # Трассировка стека
    
    # Контекст ошибки
    module = Column(String(100), nullable=True)                    # Модуль, где произошла ошибка
    function = Column(String(100), nullable=True)                  # Функция, где произошла ошибка
    line_number = Column(Integer, nullable=True)                   # Номер строки
    
    # Контекст выполнения
    user_id = Column(Integer, nullable=True)                       # ID пользователя
    chat_id = Column(BigInteger, nullable=True)                    # ID чата/группы
    message_id = Column(Integer, nullable=True)                    # ID сообщения
    
    # Данные запроса
    request_data = Column(JSON, nullable=True)                     # Данные запроса
    request_headers = Column(JSON, nullable=True)                  # Заголовки запроса
    request_method = Column(String(10), nullable=True)             # Метод запроса
    request_url = Column(String(500), nullable=True)               # URL запроса
    
    # Дополнительная информация
    environment = Column(String(50), nullable=True)                # Окружение (development, production)
    version = Column(String(50), nullable=True)                    # Версия приложения
    
    # Статус обработки
    is_resolved = Column(Boolean, default=False)                   # Решена ли ошибка
    resolved_by = Column(Integer, nullable=True)                   # Кем решена
    resolved_at = Column(DateTime, nullable=True)                  # Когда решена
    resolution_notes = Column(Text, nullable=True)                 # Заметки о решении
    
    # Уведомления
    notified_admins = Column(JSON, nullable=True)                  # Админы, уведомленные об ошибке
    notification_sent = Column(Boolean, default=False)             # Отправлено ли уведомление
    
    # Время
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<ErrorLog(id={self.id}, type='{self.error_type}', message='{self.error_message[:50]}...')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь."""
        return {
            'id': str(self.id),
            'error_type': self.error_type,
            'error_message': self.error_message,
            'error_details': self.error_details,
            'traceback': self.traceback,
            'module': self.module,
            'function': self.function,
            'line_number': self.line_number,
            'user_id': self.user_id,
            'chat_id': self.chat_id,
            'message_id': self.message_id,
            'request_data': self.request_data,
            'request_headers': self.request_headers,
            'request_method': self.request_method,
            'request_url': self.request_url,
            'environment': self.environment,
            'version': self.version,
            'is_resolved': self.is_resolved,
            'resolved_by': self.resolved_by,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolution_notes': self.resolution_notes,
            'notified_admins': self.notified_admins,
            'notification_sent': self.notification_sent,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @property
    def is_critical(self) -> bool:
        """Является ли ошибка критической."""
        critical_types = ['DatabaseError', 'ConnectionError', 'AuthenticationError', 'PermissionError']
        return self.error_type in critical_types
    
    def mark_as_resolved(self, resolved_by: int, notes: Optional[str] = None):
        """Пометить ошибку как решенную."""
        self.is_resolved = True
        self.resolved_by = resolved_by
        self.resolved_at = datetime.utcnow()
        self.resolution_notes = notes
        self.updated_at = datetime.utcnow()