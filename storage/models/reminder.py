"""
Модели для работы с напоминаниями.
Хранение напоминаний для контрактов, ТО, поставок и пользовательских напоминаний.
"""

import uuid
from datetime import datetime, date
from enum import Enum
from typing import Optional, Dict, Any, List

from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime, Date, 
    ForeignKey, JSON, Enum as SQLEnum, Float, Interval
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, backref

from .base import Base


class ReminderType(str, Enum):
    """Типы напоминаний."""
    CONTRACT = "contract"           # Напоминание о контракте
    MAINTENANCE = "maintenance"     # Напоминание о ТО
    SUPPLY = "supply"               # Напоминание о поставке
    USER = "user"                   # Пользовательское напоминание
    DOCUMENT = "document"           # Напоминание о документе
    SYSTEM = "system"               # Системное напоминание


class ReminderPriority(str, Enum):
    """Приоритеты напоминаний."""
    LOW = "low"                     # Низкий приоритет
    MEDIUM = "medium"               # Средний приоритет
    HIGH = "high"                   # Высокий приоритет
    URGENT = "urgent"               # Срочный приоритет


class ReminderStatus(str, Enum):
    """Статусы напоминаний."""
    PENDING = "pending"             # Ожидает выполнения
    COMPLETED = "completed"         # Выполнено
    CANCELLED = "cancelled"         # Отменено
    OVERDUE = "overdue"             # Просрочено
    SNOOZED = "snoozed"             # Отложено


class RepeatType(str, Enum):
    """Типы повторения напоминаний."""
    NONE = "none"                   # Не повторяется
    DAILY = "daily"                 # Ежедневно
    WEEKLY = "weekly"               # Еженедельно
    MONTHLY = "monthly"             # Ежемесячно
    YEARLY = "yearly"               # Ежегодно
    CUSTOM = "custom"               # Пользовательское повторение


class NotificationType(str, Enum):
    """Типы уведомлений."""
    TELEGRAM = "telegram"           # Уведомление в Telegram
    EMAIL = "email"                 # Уведомление по email
    BOTH = "both"                   # Оба типа уведомлений


class Reminder(Base):
    """Модель напоминания."""
    
    __tablename__ = "reminders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Основная информация
    title = Column(String(200), nullable=False)                     # Заголовок напоминания
    description = Column(Text, nullable=True)                       # Описание
    reminder_type = Column(SQLEnum(ReminderType), nullable=False)   # Тип напоминания
    priority = Column(SQLEnum(ReminderPriority), default=ReminderPriority.MEDIUM)  # Приоритет
    status = Column(SQLEnum(ReminderStatus), default=ReminderStatus.PENDING)  # Статус
    
    # Даты и время
    due_date = Column(Date, nullable=False)                         # Дата выполнения
    due_time = Column(String(5), nullable=True)                     # Время выполнения (формат ЧЧ:ММ)
    reminder_date = Column(Date, nullable=True)                     # Дата напоминания (если отличается от due_date)
    reminder_time = Column(String(5), nullable=True)                # Время напоминания
    
    # Повторение
    repeat_type = Column(SQLEnum(RepeatType), default=RepeatType.NONE)  # Тип повторения
    repeat_interval = Column(Integer, default=1)                    # Интервал повторения
    repeat_days = Column(String(50), nullable=True)                 # Дни повторения (для еженедельного)
    repeat_months = Column(String(100), nullable=True)              # Месяцы повторения (для ежегодного)
    repeat_until = Column(Date, nullable=True)                      # Повторять до даты
    last_occurrence = Column(Date, nullable=True)                   # Последнее срабатывание
    
    # Уведомления
    notification_type = Column(SQLEnum(NotificationType), default=NotificationType.TELEGRAM)  # Тип уведомления
    notify_days_before = Column(Integer, default=1)                # Уведомлять за N дней до
    notify_hours_before = Column(Integer, default=0)               # Уведомлять за N часов до
    notification_sent = Column(Boolean, default=False)             # Уведомление отправлено
    last_notification_sent = Column(DateTime, nullable=True)       # Время последнего уведомления
    
    # Связи с объектами
    object_type = Column(String(50), nullable=True)                # Тип объекта (service, installation)
    object_id = Column(UUID(as_uuid=True), nullable=True)          # ID объекта
    object_name = Column(String(200), nullable=True)               # Название объекта для отображения
    
    # Дополнительные данные
    metadata = Column(JSON, default=dict)                          # Дополнительные метаданные
    tags = Column(String(500), nullable=True)                      # Теги через запятую
    category = Column(String(100), nullable=True)                  # Категория напоминания
    
    # Выполнение
    completed_at = Column(DateTime, nullable=True)                 # Время выполнения
    completed_by = Column(Integer, nullable=True)                  # Кем выполнено
    completion_notes = Column(Text, nullable=True)                 # Заметки о выполнении
    
    # Откладывание
    snoozed_until = Column(DateTime, nullable=True)                # Отложено до
    snooze_count = Column(Integer, default=0)                      # Количество откладываний
    
    # Создатель и время
    created_by = Column(Integer, nullable=False)                   # Кем создано
    updated_by = Column(Integer, nullable=True)                    # Кем обновлено
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    notifications = relationship("Notification", back_populates="reminder", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Reminder(id={self.id}, title='{self.title}', due_date={self.due_date}, type={self.reminder_type})>"
    
    @property
    def is_overdue(self) -> bool:
        """Проверка, просрочено ли напоминание."""
        if self.status == ReminderStatus.COMPLETED or self.status == ReminderStatus.CANCELLED:
            return False
        
        today = date.today()
        return self.due_date < today if self.due_date else False
    
    @property
    def days_until_due(self) -> Optional[int]:
        """Количество дней до выполнения."""
        if not self.due_date or self.status in [ReminderStatus.COMPLETED, ReminderStatus.CANCELLED]:
            return None
        
        today = date.today()
        delta = (self.due_date - today).days
        return delta
    
    @property
    def is_recurring(self) -> bool:
        """Является ли напоминание повторяющимся."""
        return self.repeat_type != RepeatType.NONE
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь."""
        return {
            'id': str(self.id),
            'title': self.title,
            'description': self.description,
            'reminder_type': self.reminder_type.value,
            'priority': self.priority.value,
            'status': self.status.value,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'due_time': self.due_time,
            'reminder_date': self.reminder_date.isoformat() if self.reminder_date else None,
            'reminder_time': self.reminder_time,
            'repeat_type': self.repeat_type.value,
            'repeat_interval': self.repeat_interval,
            'repeat_until': self.repeat_until.isoformat() if self.repeat_until else None,
            'notification_type': self.notification_type.value,
            'notify_days_before': self.notify_days_before,
            'object_type': self.object_type,
            'object_id': str(self.object_id) if self.object_id else None,
            'object_name': self.object_name,
            'metadata': self.metadata,
            'tags': self.tags,
            'category': self.category,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_overdue': self.is_overdue,
            'days_until_due': self.days_until_due,
            'is_recurring': self.is_recurring
        }


class RecurringReminder(Base):
    """Модель шаблона повторяющегося напоминания."""
    
    __tablename__ = "recurring_reminders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Основная информация
    title = Column(String(200), nullable=False)                     # Заголовок
    description = Column(Text, nullable=True)                       # Описание
    reminder_type = Column(SQLEnum(ReminderType), nullable=False)   # Тип напоминания
    priority = Column(SQLEnum(ReminderPriority), default=ReminderPriority.MEDIUM)  # Приоритет
    
    # Расписание
    schedule_type = Column(SQLEnum(RepeatType), nullable=False)     # Тип расписания
    schedule_config = Column(JSON, default=dict)                    # Конфигурация расписания
    start_date = Column(Date, nullable=False)                       # Дата начала
    end_date = Column(Date, nullable=True)                          # Дата окончания
    is_active = Column(Boolean, default=True)                       # Активно ли расписание
    
    # Уведомления
    notification_type = Column(SQLEnum(NotificationType), default=NotificationType.TELEGRAM)  # Тип уведомления
    notify_days_before = Column(Integer, default=1)                # Уведомлять за N дней до
    notify_hours_before = Column(Integer, default=0)               # Уведомлять за N часов до
    
    # Связи с объектами
    object_type = Column(String(50), nullable=True)                # Тип объекта
    object_id = Column(UUID(as_uuid=True), nullable=True)          # ID объекта
    object_name = Column(String(200), nullable=True)               # Название объекта
    
    # Дополнительные данные
    metadata = Column(JSON, default=dict)                          # Метаданные
    tags = Column(String(500), nullable=True)                      # Теги
    category = Column(String(100), nullable=True)                  # Категория
    
    # Статистика
    generated_count = Column(Integer, default=0)                   # Количество сгенерированных напоминаний
    last_generated = Column(Date, nullable=True)                   # Дата последней генерации
    
    # Создатель и время
    created_by = Column(Integer, nullable=False)                   # Кем создано
    updated_by = Column(Integer, nullable=True)                    # Кем обновлено
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<RecurringReminder(id={self.id}, title='{self.title}', schedule_type={self.schedule_type})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь."""
        return {
            'id': str(self.id),
            'title': self.title,
            'description': self.description,
            'reminder_type': self.reminder_type.value,
            'priority': self.priority.value,
            'schedule_type': self.schedule_type.value,
            'schedule_config': self.schedule_config,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'is_active': self.is_active,
            'notification_type': self.notification_type.value,
            'notify_days_before': self.notify_days_before,
            'object_type': self.object_type,
            'object_id': str(self.object_id) if self.object_id else None,
            'object_name': self.object_name,
            'metadata': self.metadata,
            'tags': self.tags,
            'category': self.category,
            'generated_count': self.generated_count,
            'last_generated': self.last_generated.isoformat() if self.last_generated else None,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Notification(Base):
    """Модель уведомления."""
    
    __tablename__ = "notifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Связь с напоминанием
    reminder_id = Column(UUID(as_uuid=True), ForeignKey('reminders.id', ondelete='CASCADE'), nullable=False)
    
    # Информация об уведомлении
    notification_type = Column(SQLEnum(NotificationType), nullable=False)  # Тип уведомления
    notification_method = Column(String(50), nullable=False)        # Метод уведомления (telegram, email)
    recipient_id = Column(Integer, nullable=False)                  # ID получателя
    recipient_info = Column(JSON, default=dict)                     # Информация о получателе
    
    # Содержимое уведомления
    title = Column(String(200), nullable=False)                     # Заголовок уведомления
    message = Column(Text, nullable=False)                          # Текст уведомления
    metadata = Column(JSON, default=dict)                           # Метаданные уведомления
    
    # Статус и время
    status = Column(String(20), default='pending')                  # Статус (pending, sent, delivered, read, failed)
    scheduled_for = Column(DateTime, nullable=False)                # Когда должно быть отправлено
    sent_at = Column(DateTime, nullable=True)                       # Когда было отправлено
    delivered_at = Column(DateTime, nullable=True)                  # Когда было доставлено
    read_at = Column(DateTime, nullable=True)                       # Когда было прочитано
    
    # Ошибки
    error_message = Column(Text, nullable=True)                     # Сообщение об ошибке
    retry_count = Column(Integer, default=0)                        # Количество попыток отправки
    max_retries = Column(Integer, default=3)                        # Максимальное количество попыток
    
    # Создатель и время
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    reminder = relationship("Reminder", back_populates="notifications")
    
    def __repr__(self):
        return f"<Notification(id={self.id}, reminder_id={self.reminder_id}, status='{self.status}')>"
    
    @property
    def is_pending(self) -> bool:
        """Является ли уведомление ожидающим отправки."""
        return self.status == 'pending'
    
    @property
    def is_sent(self) -> bool:
        """Было ли уведомление отправлено."""
        return self.status == 'sent' and self.sent_at is not None
    
    @property
    def is_delivered(self) -> bool:
        """Было ли уведомление доставлено."""
        return self.status == 'delivered' and self.delivered_at is not None
    
    @property
    def is_failed(self) -> bool:
        """Завершилось ли уведомление ошибкой."""
        return self.status == 'failed'
    
    @property
    def can_retry(self) -> bool:
        """Можно ли повторить отправку."""
        return self.status == 'failed' and self.retry_count < self.max_retries
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь."""
        return {
            'id': str(self.id),
            'reminder_id': str(self.reminder_id),
            'notification_type': self.notification_type.value,
            'notification_method': self.notification_method,
            'recipient_id': self.recipient_id,
            'recipient_info': self.recipient_info,
            'title': self.title,
            'message': self.message,
            'metadata': self.metadata,
            'status': self.status,
            'scheduled_for': self.scheduled_for.isoformat() if self.scheduled_for else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_pending': self.is_pending,
            'is_sent': self.is_sent,
            'is_delivered': self.is_delivered,
            'is_failed': self.is_failed,
            'can_retry': self.can_retry
        }