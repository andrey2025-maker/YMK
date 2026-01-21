import uuid
from datetime import datetime
from typing import Optional, List, Dict
from decimal import Decimal

from sqlalchemy import (
    String, Integer, Boolean, DateTime, 
    ForeignKey, Text, JSON, Date, Numeric, Enum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

from .base import Base


class InstallationObject(Base):
    """Модель объекта монтажа."""
    
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
    
    # Основной документ
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
    
    # Монтируемые системы
    systems: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list
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
    status: Mapped[str] = mapped_column(
        String(50),
        default="active",
        nullable=False
    )
    
    # Связи
    responsible: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[responsible_user_id]
    )
    
    additional_documents: Mapped[List["InstallationDocument"]] = relationship(
        "InstallationDocument",
        back_populates="installation_object",
        cascade="all, delete-orphan",
        order_by="InstallationDocument.document_date.desc()"
    )
    
    projects: Mapped[List["InstallationProject"]] = relationship(
        "InstallationProject",
        back_populates="installation_object",
        cascade="all, delete-orphan",
        order_by="InstallationProject.created_at.asc()"
    )
    
    materials: Mapped[List["InstallationMaterial"]] = relationship(
        "InstallationMaterial",
        back_populates="installation_object",
        cascade="all, delete-orphan",
        order_by="InstallationMaterial.created_at.asc()"
    )
    
    material_sections: Mapped[List["MaterialSection"]] = relationship(
        "MaterialSection",
        back_populates="installation_object",
        cascade="all, delete-orphan",
        order_by="MaterialSection.section_order.asc()"
    )
    
    supplies: Mapped[List["InstallationSupply"]] = relationship(
        "InstallationSupply",
        back_populates="installation_object",
        cascade="all, delete-orphan",
        order_by="InstallationSupply.delivery_date.desc()"
    )
    
    changes: Mapped[List["InstallationChange"]] = relationship(
        "InstallationChange",
        back_populates="installation_object",
        cascade="all, delete-orphan",
        order_by="InstallationChange.created_at.desc()"
    )
    
    letters: Mapped[List["InstallationLetter"]] = relationship(
        "InstallationLetter",
        back_populates="installation_object",
        cascade="all, delete-orphan",
        order_by="InstallationLetter.letter_date.desc()"
    )
    
    permits: Mapped[List["InstallationPermit"]] = relationship(
        "InstallationPermit",
        back_populates="installation_object",
        cascade="all, delete-orphan",
        order_by="InstallationPermit.permit_date.desc()"
    )
    
    journals: Mapped[List["InstallationJournal"]] = relationship(
        "InstallationJournal",
        back_populates="installation_object",
        cascade="all, delete-orphan",
        order_by="InstallationJournal.created_at.desc()"
    )
    
    id_documents: Mapped[List["InstallationIdDocument"]] = relationship(
        "InstallationIdDocument",
        back_populates="installation_object",
        cascade="all, delete-orphan",
        order_by="InstallationIdDocument.created_at.desc()"
    )
    
    reminders: Mapped[List["InstallationReminder"]] = relationship(
        "InstallationReminder",
        back_populates="installation_object",
        cascade="all, delete-orphan",
        order_by="InstallationReminder.due_date.asc()"
    )
    
    montage_records: Mapped[List["MontageRecord"]] = relationship(
        "MontageRecord",
        back_populates="installation_object",
        cascade="all, delete-orphan",
        order_by="MontageRecord.created_at.desc()"
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
        return f"Монтаж: {self.short_name} ({self.full_name})"


class InstallationDocument(Base):
    """Модель дополнительных документов монтажа."""
    
    installation_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("installation_object.id", ondelete="CASCADE"),
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
    installation_object: Mapped["InstallationObject"] = relationship(
        "InstallationObject",
        back_populates="additional_documents"
    )
    
    file_links: Mapped[List["InstallationDocumentFile"]] = relationship(
        "InstallationDocumentFile",
        back_populates="document",
        cascade="all, delete-orphan"
    )
    
    def __str__(self) -> str:
        return f"{self.document_type} № {self.document_number}"


class InstallationProject(Base):
    """Модель проекта монтажа."""
    
    installation_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("installation_object.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Название проекта
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    # Версия проекта
    version: Mapped[str] = mapped_column(
        String(50),
        nullable=True
    )
    
    # Описание
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    # Статус
    status: Mapped[str] = mapped_column(
        String(50),
        default="draft",
        nullable=False
    )
    
    # Связи
    installation_object: Mapped["InstallationObject"] = relationship(
        "InstallationObject",
        back_populates="projects"
    )
    
    file_links: Mapped[List["InstallationProjectFile"]] = relationship(
        "InstallationProjectFile",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    
    def __str__(self) -> str:
        return f"Проект: {self.name}"


class InstallationMaterial(Base):
    """Модель материала монтажа."""
    
    installation_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("installation_object.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Наименование
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    # Количество и единица измерения
    quantity: Mapped[Decimal] = mapped_column(
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
    
    # Категория/тип
    category: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    # Артикул/код
    article: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    # Связи
    installation_object: Mapped["InstallationObject"] = relationship(
        "InstallationObject",
        back_populates="materials"
    )
    
    section_materials: Mapped[List["SectionMaterial"]] = relationship(
        "SectionMaterial",
        back_populates="material",
        cascade="all, delete-orphan"
    )
    
    def get_display_name(self) -> str:
        """Возвращает отображаемое имя материала."""
        return f"{self.name} - {self.quantity} {self.unit}"
    
    def __str__(self) -> str:
        return self.get_display_name()


class MaterialSection(Base):
    """Модель раздела материалов (например, 1 этаж)."""
    
    installation_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("installation_object.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Название раздела
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    # Порядок отображения
    section_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    
    # Описание
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    # Связи
    installation_object: Mapped["InstallationObject"] = relationship(
        "InstallationObject",
        back_populates="material_sections"
    )
    
    section_materials: Mapped[List["SectionMaterial"]] = relationship(
        "SectionMaterial",
        back_populates="section",
        cascade="all, delete-orphan"
    )
    
    montage_records: Mapped[List["MontageRecord"]] = relationship(
        "MontageRecord",
        back_populates="material_section",
        cascade="all, delete-orphan"
    )
    
    def __str__(self) -> str:
        return f"Раздел: {self.name}"


class SectionMaterial(Base):
    """Связь материалов с разделами."""
    
    section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("material_section.id", ondelete="CASCADE"),
        nullable=False
    )
    
    material_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("installation_material.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Количество материала в этом разделе
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False
    )
    
    # Плановое количество
    planned_quantity: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True
    )
    
    # Порядок отображения
    display_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    
    # Связи
    section: Mapped["MaterialSection"] = relationship(
        "MaterialSection",
        back_populates="section_materials"
    )
    
    material: Mapped["InstallationMaterial"] = relationship(
        "InstallationMaterial",
        back_populates="section_materials"
    )
    
    def __str__(self) -> str:
        return f"{self.material.name} в {self.section.name}: {self.quantity}"


class InstallationSupply(Base):
    """Модель поставки материалов."""
    
    installation_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("installation_object.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Информация о поставке
    delivery_service: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    delivery_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False
    )
    
    # Документ поставки
    document_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    document_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True
    )
    
    # Описание
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    
    # Статус
    status: Mapped[str] = mapped_column(
        String(50),
        default="planned",
        nullable=False
    )
    
    # Связи
    installation_object: Mapped["InstallationObject"] = relationship(
        "InstallationObject",
        back_populates="supplies"
    )
    
    supply_items: Mapped[List["SupplyItem"]] = relationship(
        "SupplyItem",
        back_populates="supply",
        cascade="all, delete-orphan"
    )
    
    file_links: Mapped[List["InstallationSupplyFile"]] = relationship(
        "InstallationSupplyFile",
        back_populates="supply",
        cascade="all, delete-orphan"
    )
    
    def __str__(self) -> str:
        return f"Поставка {self.delivery_service} от {self.delivery_date.strftime('%d.%m.%Y')}"


class SupplyItem(Base):
    """Элемент поставки."""
    
    supply_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("installation_supply.id", ondelete="CASCADE"),
        nullable=False
    )
    
    material_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("installation_material.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Количество в поставке
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False
    )
    
    # Связи
    supply: Mapped["InstallationSupply"] = relationship(
        "InstallationSupply",
        back_populates="supply_items"
    )
    
    material: Mapped["InstallationMaterial"] = relationship(
        "InstallationMaterial"
    )
    
    def __str__(self) -> str:
        return f"{self.material.name} - {self.quantity}"


class InstallationChange(Base):
    """Модель изменений в проекте."""
    
    installation_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("installation_object.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Описание изменения
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    
    # Дата изменения
    change_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False
    )
    
    # Номер изменения
    change_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    # Связи
    installation_object: Mapped["InstallationObject"] = relationship(
        "InstallationObject",
        back_populates="changes"
    )
    
    file_links: Mapped[List["InstallationChangeFile"]] = relationship(
        "InstallationChangeFile",
        back_populates="change",
        cascade="all, delete-orphan"
    )
    
    def __str__(self) -> str:
        return f"Изменение {self.change_number or ''}: {self.description[:50]}..."


class InstallationLetter(Base):
    """Модель писем монтажа."""
    
    installation_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("installation_object.id", ondelete="CASCADE"),
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
    installation_object: Mapped["InstallationObject"] = relationship(
        "InstallationObject",
        back_populates="letters"
    )
    
    file_links: Mapped[List["InstallationLetterFile"]] = relationship(
        "InstallationLetterFile",
        back_populates="letter",
        cascade="all, delete-orphan"
    )
    
    def get_display_name(self) -> str:
        """Возвращает отображаемое имя письма."""
        return f"№ {self.letter_number} от {self.letter_date.strftime('%d.%m.%Y')}"
    
    def __str__(self) -> str:
        return f"Письмо {self.get_display_name()}"


class InstallationPermit(Base):
    """Модель допусков монтажа."""
    
    installation_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("installation_object.id", ondelete="CASCADE"),
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
    installation_object: Mapped["InstallationObject"] = relationship(
        "InstallationObject",
        back_populates="permits"
    )
    
    file_links: Mapped[List["InstallationPermitFile"]] = relationship(
        "InstallationPermitFile",
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


class InstallationJournal(Base):
    """Модель журналов монтажа."""
    
    installation_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("installation_object.id", ondelete="CASCADE"),
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
    installation_object: Mapped["InstallationObject"] = relationship(
        "InstallationObject",
        back_populates="journals"
    )
    
    file_links: Mapped[List["InstallationJournalFile"]] = relationship(
        "InstallationJournalFile",
        back_populates="journal",
        cascade="all, delete-orphan"
    )
    
    def __str__(self) -> str:
        return f"Журнал: {self.name}"


class InstallationIdDocument(Base):
    """Модель ИД документов (как в ТЗ)."""
    
    installation_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("installation_object.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Название документа
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
    installation_object: Mapped["InstallationObject"] = relationship(
        "InstallationObject",
        back_populates="id_documents"
    )
    
    file_links: Mapped[List["InstallationIdDocumentFile"]] = relationship(
        "InstallationIdDocumentFile",
        back_populates="id_document",
        cascade="all, delete-orphan"
    )
    
    def __str__(self) -> str:
        return f"ИД документ: {self.name}"


class InstallationReminder(Base):
    """Модель напоминаний для монтажа."""
    
    installation_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("installation_object.id", ondelete="CASCADE"),
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
    installation_object: Mapped["InstallationObject"] = relationship(
        "InstallationObject",
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


class MontageRecord(Base):
    """Запись о смонтированном материале."""
    
    installation_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("installation_object.id", ondelete="CASCADE"),
        nullable=False
    )
    
    material_section_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("material_section.id", ondelete="CASCADE"),
        nullable=True
    )
    
    material_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("installation_material.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Количество смонтировано
    quantity_installed: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False
    )
    
    # Дата монтажа
    installation_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False
    )
    
    # Кто выполнил
    installed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Примечание
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    # Связи
    installation_object: Mapped["InstallationObject"] = relationship(
        "InstallationObject",
        back_populates="montage_records"
    )
    
    material_section: Mapped[Optional["MaterialSection"]] = relationship(
        "MaterialSection",
        back_populates="montage_records"
    )
    
    material: Mapped["InstallationMaterial"] = relationship(
        "InstallationMaterial"
    )
    
    installer: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[installed_by]
    )
    
    def __str__(self) -> str:
        return f"Монтаж: {self.material.name} - {self.quantity_installed} ({self.installation_date})"


# Модели для файлов (аналогично обслуживанию)
class InstallationDocumentFile(Base):
    """Файлы для документов монтажа."""
    
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("installation_document.id", ondelete="CASCADE"),
        nullable=False
    )
    
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("telegram_file.id", ondelete="CASCADE"),
        nullable=False
    )
    
    display_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    
    # Связи
    document: Mapped["InstallationDocument"] = relationship(
        "InstallationDocument",
        back_populates="file_links"
    )
    
    file: Mapped["TelegramFile"] = relationship(
        "TelegramFile"
    )


# Аналогичные модели для других типов файлов:
# InstallationProjectFile, InstallationSupplyFile, InstallationChangeFile и т.д.