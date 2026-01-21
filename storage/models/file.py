import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

from .base import Base


class TelegramFile(Base):
    """Модель файла, загруженного в Telegram."""
    
    # Идентификаторы в Telegram
    telegram_file_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True
    )
    
    telegram_message_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    
    telegram_chat_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    telegram_topic_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    
    # Информация о файле
    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    file_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    
    mime_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    file_size: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    
    # Метаданные
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict
    )
    
    # Кто загрузил
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
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
    uploader: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[uploaded_by]
    )
    
    # Методы для работы с файлом
    def get_telegram_link(self) -> str:
        """Возвращает ссылку на файл в Telegram."""
        if self.telegram_topic_id:
            return f"https://t.me/c/{self.telegram_chat_id}/{self.telegram_topic_id}/{self.telegram_message_id}"
        else:
            return f"https://t.me/c/{self.telegram_chat_id}/{self.telegram_message_id}"
    
    def get_file_info(self) -> dict:
        """Возвращает информацию о файле."""
        return {
            "id": str(self.id),
            "file_name": self.file_name,
            "file_type": self.file_type,
            "file_size": self.format_file_size(),
            "uploaded_at": self.created_at.isoformat(),
            "telegram_link": self.get_telegram_link(),
            "description": self.description,
        }
    
    def format_file_size(self) -> str:
        """Форматирует размер файла для отображения."""
        if not self.file_size:
            return "Неизвестно"
        
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def __str__(self) -> str:
        return f"Файл: {self.file_name} ({self.file_type})"


class ServiceProblemFile(Base):
    """Связь файлов с проблемами обслуживания."""
    
    problem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_problem.id", ondelete="CASCADE"),
        nullable=False
    )
    
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("telegram_file.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Порядок отображения
    display_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    
    # Связи
    problem: Mapped["ServiceProblem"] = relationship(
        "ServiceProblem",
        back_populates="file_links"
    )
    
    file: Mapped["TelegramFile"] = relationship(
        "TelegramFile"
    )


class ServiceLetterFile(Base):
    """Связь файлов с письмами обслуживания."""
    
    letter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_letter.id", ondelete="CASCADE"),
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
    letter: Mapped["ServiceLetter"] = relationship(
        "ServiceLetter",
        back_populates="file_links"
    )
    
    file: Mapped["TelegramFile"] = relationship(
        "TelegramFile"
    )


class ServiceDocumentFile(Base):
    """Связь файлов с документами обслуживания."""
    
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_additional_document.id", ondelete="CASCADE"),
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
    document: Mapped["ServiceAdditionalDocument"] = relationship(
        "ServiceAdditionalDocument",
        back_populates="file_links"
    )
    
    file: Mapped["TelegramFile"] = relationship(
        "TelegramFile"
    )


# Аналогичные модели для других типов файлов:
# ServiceJournalFile, ServicePermitFile, InstallationProjectFile и т.д.


class ArchivedObject(Base):
    """Модель архивированных удаленных объектов."""
    
    # Тип объекта
    object_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    
    # Исходный ID объекта
    original_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False
    )
    
    # Данные объекта (JSON)
    object_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False
    )
    
    # Ссылка на архив в Telegram
    telegram_chat_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    telegram_topic_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    
    telegram_message_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    
    # Кто удалил
    deleted_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Причина удаления
    deletion_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    # Связи
    deleter: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[deleted_by]
    )
    
    def get_archive_link(self) -> str:
        """Возвращает ссылку на архив в Telegram."""
        if self.telegram_topic_id:
            return f"https://t.me/c/{self.telegram_chat_id}/{self.telegram_topic_id}/{self.telegram_message_id}"
        else:
            return f"https://t.me/c/{self.telegram_chat_id}/{self.telegram_message_id}"
    
    def __str__(self) -> str:
        return f"Архив {self.object_type}: {self.original_object_id}"