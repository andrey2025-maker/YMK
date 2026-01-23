"""
Репозиторий для работы с файлами в Telegram.
Реализует хранение информации о файлах, их связь с объектами системы
и управление файловыми архивами согласно ТЗ.
"""
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import and_, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models.file import TelegramFile, FileAttachment, FileCategory
from storage.repositories.base import BaseRepository


class FileRepository(BaseRepository[TelegramFile]):
    """
    Репозиторий для управления файлами в Telegram.
    """
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, TelegramFile)
    
    async def create_file(
        self,
        telegram_file_id: str,
        file_type: str,
        file_name: str,
        file_size: int,
        chat_id: int,
        message_id: int,
        category: FileCategory,
        uploader_id: int,
        description: Optional[str] = None,
        original_path: Optional[str] = None
    ) -> TelegramFile:
        """
        Создает запись о файле в Telegram.
        
        Args:
            telegram_file_id: ID файла в Telegram
            file_type: Тип файла (document, photo, video и т.д.)
            file_name: Имя файла
            file_size: Размер файла в байтах
            chat_id: ID чата где хранится файл
            message_id: ID сообщения с файлом
            category: Категория файла (PDF, Excel, Word, Image, Other)
            uploader_id: ID пользователя загрузившего файл
            description: Описание файла (опционально)
            original_path: Оригинальный путь файла (опционально)
            
        Returns:
            Созданный объект TelegramFile
        """
        file_data = {
            "telegram_file_id": telegram_file_id,
            "file_type": file_type,
            "file_name": file_name,
            "file_size": file_size,
            "chat_id": chat_id,
            "message_id": message_id,
            "category": category,
            "uploader_id": uploader_id,
            "upload_date": datetime.utcnow(),
            "description": description,
            "original_path": original_path
        }
        
        return await self.create(file_data)
    
    async def attach_file_to_object(
        self,
        file_id: uuid.UUID,
        object_type: str,
        object_id: uuid.UUID,
        attachment_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> FileAttachment:
        """
        Привязывает файл к объекту системы (обслуживание, монтаж и т.д.).
        
        Args:
            file_id: ID файла
            object_type: Тип объекта (service_object, installation_object, problem и т.д.)
            object_id: ID объекта
            attachment_type: Тип привязки (main_document, attachment, project и т.д.)
            metadata: Дополнительные метаданные привязки (опционально)
            
        Returns:
            Созданная привязка файла
        """
        attachment_data = {
            "file_id": file_id,
            "object_type": object_type,
            "object_id": object_id,
            "attachment_type": attachment_type,
            "attached_at": datetime.utcnow(),
            "metadata": metadata or {}
        }
        
        stmt = select(FileAttachment).where(
            and_(
                FileAttachment.file_id == file_id,
                FileAttachment.object_type == object_type,
                FileAttachment.object_id == object_id,
                FileAttachment.attachment_type == attachment_type
            )
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            # Обновляем существующую привязку
            for key, value in attachment_data.items():
                setattr(existing, key, value)
            await self.session.commit()
            return existing
        else:
            # Создаем новую привязку
            attachment = FileAttachment(**attachment_data)
            self.session.add(attachment)
            await self.session.commit()
            await self.session.refresh(attachment)
            return attachment
    
    async def get_files_by_object(
        self,
        object_type: str,
        object_id: uuid.UUID,
        attachment_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[TelegramFile]:
        """
        Получает файлы, привязанные к объекту.
        
        Args:
            object_type: Тип объекта
            object_id: ID объекта
            attachment_type: Фильтр по типу привязки (опционально)
            skip: Количество пропущенных записей
            limit: Максимальное количество записей
            
        Returns:
            Список файлов объекта
        """
        conditions = [
            FileAttachment.object_type == object_type,
            FileAttachment.object_id == object_id
        ]
        
        if attachment_type:
            conditions.append(FileAttachment.attachment_type == attachment_type)
        
        stmt = (
            select(TelegramFile)
            .join(FileAttachment, TelegramFile.id == FileAttachment.file_id)
            .where(and_(*conditions))
            .order_by(desc(FileAttachment.attached_at))
            .offset(skip)
            .limit(limit)
        )
        
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def get_file_by_telegram_id(self, telegram_file_id: str) -> Optional[TelegramFile]:
        """
        Получает файл по ID в Telegram.
        
        Args:
            telegram_file_id: ID файла в Telegram
            
        Returns:
            Объект TelegramFile или None
        """
        stmt = select(TelegramFile).where(TelegramFile.telegram_file_id == telegram_file_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_files_by_category(
        self,
        category: FileCategory,
        skip: int = 0,
        limit: int = 100
    ) -> List[TelegramFile]:
        """
        Получает файлы по категории.
        
        Args:
            category: Категория файла
            skip: Количество пропущенных записей
            limit: Максимальное количество записей
            
        Returns:
            Список файлов указанной категории
        """
        stmt = (
            select(TelegramFile)
            .where(TelegramFile.category == category)
            .order_by(desc(TelegramFile.upload_date))
            .offset(skip)
            .limit(limit)
        )
        
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def update_file_description(
        self,
        file_id: uuid.UUID,
        description: str
    ) -> Optional[TelegramFile]:
        """
        Обновляет описание файла.
        
        Args:
            file_id: ID файла
            description: Новое описание
            
        Returns:
            Обновленный объект TelegramFile или None
        """
        file = await self.get_by_id(file_id)
        if file:
            file.description = description
            await self.session.commit()
            await self.session.refresh(file)
        return file
    
    async def get_file_statistics(self) -> Dict[str, Any]:
        """
        Получает статистику по файлам.
        
        Returns:
            Словарь со статистикой
        """
        # Общее количество файлов
        total_stmt = select(func.count(TelegramFile.id))
        total_result = await self.session.execute(total_stmt)
        total_files = total_result.scalar() or 0
        
        # Количество файлов по категориям
        category_stmt = (
            select(TelegramFile.category, func.count(TelegramFile.id))
            .group_by(TelegramFile.category)
        )
        category_result = await self.session.execute(category_stmt)
        by_category = dict(category_result.all())
        
        # Общий размер файлов
        size_stmt = select(func.sum(TelegramFile.file_size))
        size_result = await self.session.execute(size_stmt)
        total_size = size_result.scalar() or 0
        
        # Количество файлов по месяцам
        monthly_stmt = (
            select(
                func.date_trunc('month', TelegramFile.upload_date).label('month'),
                func.count(TelegramFile.id)
            )
            .group_by('month')
            .order_by(desc('month'))
            .limit(12)
        )
        monthly_result = await self.session.execute(monthly_stmt)
        by_month = [
            {"month": row[0].strftime("%Y-%m"), "count": row[1]}
            for row in monthly_result.all()
        ]
        
        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "by_category": by_category,
            "by_month": by_month
        }
    
    async def delete_file(self, file_id: uuid.UUID) -> bool:
        """
        Удаляет файл и все его привязки.
        
        Args:
            file_id: ID файла для удаления
            
        Returns:
            True если удаление успешно, False если файл не найден
        """
        # Удаляем все привязки файла
        attachments_stmt = select(FileAttachment).where(FileAttachment.file_id == file_id)
        attachments_result = await self.session.execute(attachments_stmt)
        attachments = attachments_result.scalars().all()
        
        for attachment in attachments:
            await self.session.delete(attachment)
        
        # Удаляем сам файл
        file = await self.get_by_id(file_id)
        if file:
            await self.session.delete(file)
            await self.session.commit()
            return True
        
        return False
    
    async def search_files(
        self,
        query: str,
        category: Optional[FileCategory] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[TelegramFile]:
        """
        Поиск файлов по названию и описанию.
        
        Args:
            query: Строка поиска
            category: Фильтр по категории (опционально)
            skip: Количество пропущенных записей
            limit: Максимальное количество записей
            
        Returns:
            Список найденных файлов
        """
        search_query = f"%{query}%"
        conditions = [
            (TelegramFile.file_name.ilike(search_query) |
             TelegramFile.description.ilike(search_query))
        ]
        
        if category:
            conditions.append(TelegramFile.category == category)
        
        stmt = (
            select(TelegramFile)
            .where(and_(*conditions))
            .order_by(desc(TelegramFile.upload_date))
            .offset(skip)
            .limit(limit)
        )
        
        result = await self.session.execute(stmt)
        return result.scalars().all()