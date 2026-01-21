import uuid
from datetime import datetime
from typing import Optional, List
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, 
    ForeignKey, Text, ARRAY, JSON, Date, Numeric
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base


class ServiceRegion(Base):
    """Модель региона обслуживания."""
    
    # Основная информация
    short_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )
    
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    # Кем создан
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Статус активности
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    
    # Связи
    objects: Mapped[List["ServiceObject"]] = relationship(
        "ServiceObject",
        back_populates="region",
        cascade="all, delete-orphan"
    )
    
    groups: Mapped[List["GroupBinding"]] = relationship(
        "GroupBinding",
        back_populates="service_region",
        cascade="all, delete-orphan"
    )
    
    def __str__(self) -> str:
        return f"{self.short_name} - {self.full_name}"


class ServiceObject(Base):
    """Модель объекта обслуживания."""
    
    region_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_region.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Основная информация
    short_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True
    )
    
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    # Адреса (храним как JSON массив строк)
    addresses: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list
    )
    
    # Документ
    document_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="Договор"
    )
    
    document_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    
    document_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False
    )
    
    contract_start_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False
    )
    
    contract_end_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False
    )
    
    # Обслуживаемые системы (храним как массив строк)
    systems: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list
    )
    
    # ЗИП
    zip_purchaser: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="Заказчик"
    )
    
    # Диспетчеризация
    has_dispatching: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    
    # Примечание
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    # Ответственный
    responsible_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Статус
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    
    # Связи
    region: Mapped["ServiceRegion"] = relationship(
        "ServiceRegion",
        back_populates="objects"
    )
    
    responsible: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[responsible_user_id]
    )
    
    problems: Mapped[List["ServiceProblem"]] = relationship(
        "ServiceProblem",
        back_populates="service_object",
        cascade="all, delete-orphan",
        order_by="ServiceProblem.created_at.desc()"
    )
    
    maintenance: Mapped[List["ServiceMaintenance"]] = relationship(
        "ServiceMaintenance",
        back_populates="service_object",
        cascade="all, delete-orphan",
        order_by="ServiceMaintenance.month"
    )
    
    letters: Mapped[List["ServiceLetter"]] = relationship(
        "ServiceLetter",
        back_populates="service_object",
        cascade="all, delete-orphan",
        order_by="ServiceLetter.date.desc()"
    )
    
    journals: Mapped[List["ServiceJournal"]] = relationship(
        "ServiceJournal",
        back_populates="service_object",
        cascade="all, delete-orphan",
        order_by="ServiceJournal.created_at.desc()"
    )
    
    permits: Mapped[List["ServicePermit"]] = relationship(
        "ServicePermit",
        back_populates="service_object",
        cascade="all, delete-orphan",
        order_by="ServicePermit.date.desc()"
    )
    
    equipment: Mapped[List["ServiceEquipment"]] = relationship(
        "ServiceEquipment",
        back_populates="service_object",
        cascade="all, delete-orphan",
        order_by="ServiceEquipment.created_at.asc()"
    )
    
    reminders: Mapped[List["ServiceReminder"]] = relationship(
        "ServiceReminder",
        back_populates="service_object",
        cascade="all, delete-orphan",
        order_by="ServiceReminder.due_date.asc()"
    )
    
    additional_documents: Mapped[List["ServiceAdditionalDocument"]] = relationship(
        "ServiceAdditionalDocument",
        back_populates="service_object",
        cascade="all, delete-orphan",
        order_by="ServiceAdditionalDocument.document_date.desc()"
    )
    
    def get_addresses_display(self) -> str:
        """Возвращает отформатированные адреса."""
        if not self.addresses:
            return "Адреса не указаны"
        
        result = []
        for i, address in enumerate(self.addresses, 1):
            result.append(f"{i}. {address}")
        
        return "\n".join(result)
    
    def get_systems_display(self) -> str:
        """Возвращает отформатированные системы."""
        if not self.systems:
            return "Системы не указаны"
        return " • ".join(self.systems)
    
    def __str__(self) -> str:
        return f"Объект: {self.short_name} ({self.full_name})"


class ServiceProblem(Base):
    """Модель проблем объекта обслуживания."""
    
    service_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_object.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Описание проблемы
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    
    # Статус решения
    is_resolved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    
    # Решение
    solution: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    solved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    solved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Связи
    service_object: Mapped["ServiceObject"] = relationship(
        "ServiceObject",
        back_populates="problems"
    )
    
    solver: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[solved_by]
    )
    
    files: Mapped[List["ServiceProblemFile"]] = relationship(
        "ServiceProblemFile",
        back_populates="problem",
        cascade="all, delete-orphan"
    )
    
    def __str__(self) -> str:
        status = "✅ Решена" if self.is_resolved else "❌ Не решена"
        return f"Проблема: {self.description[:50]}... ({status})"


class ServiceMaintenance(Base):
    """Модель технического обслуживания."""
    
    service_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_object.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Периодичность
    frequency: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="ежемесячно"
    )
    
    # Месяц (для ежемесячного ТО)
    month: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    
    # Описание работ
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    
    # Последнее выполнение
    last_completed: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    completed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Связи
    service_object: Mapped["ServiceObject"] = relationship(
        "ServiceObject",
        back_populates="maintenance"
    )
    
    completer: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[completed_by]
    )
    
    def __str__(self) -> str:
        return f"ТО: {self.description[:50]}... ({self.frequency})"


class ServiceLetter(Base):
    """Модель писем объекта обслуживания."""
    
    service_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_object.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Номер и дата
    letter_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    
    letter_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False
    )
    
    # Описание
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    
    # Связи
    service_object: Mapped["ServiceObject"] = relationship(
        "ServiceObject",
        back_populates="letters"
    )
    
    files: Mapped[List["ServiceLetterFile"]] = relationship(
        "ServiceLetterFile",
        back_populates="letter",
        cascade="all, delete-orphan"
    )
    
    def get_display_name(self) -> str:
        """Возвращает отображаемое имя письма."""
        return f"№ {self.letter_number} от {self.letter_date.strftime('%d.%m.%Y')}"
    
    def __str__(self) -> str:
        return f"Письмо {self.get_display_name()}"


class ServiceJournal(Base):
    """Модель журналов объекта обслуживания."""
    
    service_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_object.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Название журнала
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    # Описание
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    # Связи
    service_object: Mapped["ServiceObject"] = relationship(
        "ServiceObject",
        back_populates="journals"
    )
    
    files: Mapped[List["ServiceJournalFile"]] = relationship(
        "ServiceJournalFile",
        back_populates="journal",
        cascade="all, delete-orphan"
    )
    
    def __str__(self) -> str:
        return f"Журнал: {self.name}"


class ServicePermit(Base):
    """Модель допусков объекта обслуживания."""
    
    service_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_object.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Номер и дата
    permit_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    
    permit_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False
    )
    
    # Описание
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    
    # Срок действия
    valid_until: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True
    )
    
    # Связи
    service_object: Mapped["ServiceObject"] = relationship(
        "ServiceObject",
        back_populates="permits"
    )
    
    files: Mapped[List["ServicePermitFile"]] = relationship(
        "ServicePermitFile",
        back_populates="permit",
        cascade="all, delete-orphan"
    )
    
    def is_valid(self) -> bool:
        """Проверяет, действителен ли допуск."""
        if not self.valid_until:
            return True
        
        from datetime import date
        return date.today() <= self.valid_until
    
    def __str__(self) -> str:
        status = "✅ Действителен" if self.is_valid() else "❌ Просрочен"
        return f"Допуск {self.permit_number} ({status})"


class ServiceEquipment(Base):
    """Модель оборудования объекта обслуживания."""
    
    service_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_object.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Адрес (если у объекта несколько адресов)
    address_index: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    
    # Наименование
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    # Количество и единица измерения
    quantity: Mapped[float] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=1.0
    )
    
    unit: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="шт."
    )
    
    # Описание
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    # Связи
    service_object: Mapped["ServiceObject"] = relationship(
        "ServiceObject",
        back_populates="equipment"
    )
    
    def get_display_name(self) -> str:
        """Возвращает отображаемое имя оборудования."""
        return f"{self.name} - {self.quantity} {self.unit}"
    
    def __str__(self) -> str:
        return self.get_display_name()


class ServiceReminder(Base):
    """Модель напоминаний для объектов обслуживания."""
    
    service_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_object.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Тип напоминания
    reminder_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="custom"
    )
    
    # Дата напоминания
    due_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False
    )
    
    # Текст напоминания
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    
    # Статус
    is_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Уведомления
    notify_day_before: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    
    notify_on_day: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    
    # Связи
    service_object: Mapped["ServiceObject"] = relationship(
        "ServiceObject",
        back_populates="reminders"
    )
    
    def should_notify_today(self) -> bool:
        """Проверяет, нужно ли отправлять уведомление сегодня."""
        from datetime import date, timedelta
        
        today = date.today()
        due = self.due_date.date()
        
        if self.notify_on_day and today == due:
            return True
        
        if self.notify_day_before and today == due - timedelta(days=1):
            return True
        
        return False
    
    def __str__(self) -> str:
        status = "✅ Выполнено" if self.is_completed else "⏳ Ожидает"
        return f"Напоминание: {self.message[:50]}... ({status})"


class ServiceAdditionalDocument(Base):
    """Модель дополнительных соглашений."""
    
    service_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_object.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Тип документа
    document_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="Доп. соглашение"
    )
    
    # Номер и дата
    document_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    
    document_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False
    )
    
    # Сроки
    start_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True
    )
    
    end_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True
    )
    
    # Описание
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    
    # Связи
    service_object: Mapped["ServiceObject"] = relationship(
        "ServiceObject",
        back_populates="additional_documents"
    )
    
    files: Mapped[List["ServiceDocumentFile"]] = relationship(
        "ServiceDocumentFile",
        back_populates="document",
        cascade="all, delete-orphan"
    )
    
    def __str__(self) -> str:
        return f"{self.document_type} № {self.document_number}"


# Модели для файлов (общие для всех подразделов)
class ServiceProblemFile(Base):
    """Файлы для проблем."""
    
    problem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_problem.id", ondelete="CASCADE"),
        nullable=False
    )
    
    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )
    
    file_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    
    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Связи
    problem: Mapped["ServiceProblem"] = relationship(
        "ServiceProblem",
        back_populates="files"
    )
    
    uploader: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[uploaded_by]
    )


class ServiceLetterFile(Base):
    """Файлы для писем."""
    
    letter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_letter.id", ondelete="CASCADE"),
        nullable=False
    )
    
    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )
    
    file_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    
    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Связи
    letter: Mapped["ServiceLetter"] = relationship(
        "ServiceLetter",
        back_populates="files"
    )
    
    uploader: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[uploaded_by]
    )


# Аналогичные модели для других файлов (JournalFile, PermitFile, DocumentFile)
# Структура аналогична ServiceProblemFile