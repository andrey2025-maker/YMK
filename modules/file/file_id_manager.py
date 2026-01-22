"""
Менеджер ID файлов.
Управление связями между файлами в Telegram и объектами системы.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from uuid import uuid4

from core.context import AppContext
from storage.models.file import TelegramFile, FileAttachment
from storage.repositories.file_repository import FileRepository
from utils.exceptions import FileNotFoundError, DuplicateFileError

logger = logging.getLogger(__name__)


class FileIDManager:
    """Менеджер ID файлов."""
    
    def __init__(self, context: AppContext):
        self.context = context
        self.db = context.db
        self.file_repository = FileRepository(self.db)
        
        # Кэш для быстрого доступа
        self.file_cache = {}  # file_id -> file_info
        self.attachments_cache = {}  # object_id -> [file_ids]
    
    async def initialize(self):
        """Инициализация менеджера."""
        logger.info("Initializing FileIDManager")
        return self
    
    async def register_file(
        self,
        telegram_file_info: Dict[str, Any],
        uploaded_by: int,
        object_id: Optional[str] = None,
        object_type: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Регистрация файла в системе.
        
        Args:
            telegram_file_info: Информация о файле из Telegram
            uploaded_by: ID пользователя, загрузившего файл
            object_id: ID объекта, к которому привязан файл
            object_type: Тип объекта
            description: Описание файла
            metadata: Дополнительные метаданные
            
        Returns:
            Внутренний ID файла в системе
        """
        try:
            # Проверяем, не зарегистрирован ли уже файл
            existing_file = await self.file_repository.get_file_by_telegram_id(
                telegram_file_info['file_id']
            )
            
            if existing_file:
                logger.warning(f"File already registered: {telegram_file_info['file_id']}")
                return str(existing_file.id)
            
            # Создаем запись о файле
            file_record = TelegramFile(
                telegram_file_id=telegram_file_info['file_id'],
                telegram_unique_id=telegram_file_info.get('file_unique_id'),
                file_name=telegram_file_info.get('file_name', ''),
                mime_type=telegram_file_info.get('mime_type', ''),
                file_size=telegram_file_info.get('file_size', 0),
                file_type=telegram_file_info.get('file_type', 'document'),
                category=telegram_file_info.get('category', 'other'),
                description=description or '',
                metadata=metadata or {},
                uploaded_by=uploaded_by,
                uploaded_at=datetime.now(),
                message_id=telegram_file_info.get('message_id'),
                chat_id=telegram_file_info.get('chat_id'),
                download_url=telegram_file_info.get('download_url', ''),
                is_active=True
            )
            
            # Сохраняем в БД
            saved_file = await self.file_repository.save_file(file_record)
            file_id = str(saved_file.id)
            
            # Кэшируем
            self._cache_file_info(file_id, telegram_file_info)
            
            # Привязываем к объекту если указан
            if object_id and object_type:
                await self.attach_file_to_object(
                    file_id=file_id,
                    object_id=object_id,
                    object_type=object_type,
                    attachment_type=metadata.get('attachment_type', 'general') if metadata else 'general'
                )
            
            logger.info(f"File registered: {file_id} -> {telegram_file_info['file_id']}")
            return file_id
            
        except Exception as e:
            logger.error(f"Error registering file: {e}", exc_info=True)
            raise
    
    async def get_file_by_id(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Получение информации о файле по внутреннему ID.
        
        Args:
            file_id: Внутренний ID файла
            
        Returns:
            Информация о файле или None
        """
        # Проверяем кэш
        if file_id in self.file_cache:
            cached_info = self.file_cache[file_id]
            # Проверяем актуальность кэша (1 час)
            if datetime.now().timestamp() - cached_info.get('cached_at', 0) < 3600:
                return cached_info
        
        try:
            # Получаем из БД
            file_record = await self.file_repository.get_file_by_id(file_id)
            
            if not file_record:
                return None
            
            file_info = self._record_to_dict(file_record)
            
            # Кэшируем
            self._cache_file_info(file_id, file_info)
            
            return file_info
            
        except Exception as e:
            logger.error(f"Error getting file {file_id}: {e}")
            return None
    
    async def get_file_by_telegram_id(self, telegram_file_id: str) -> Optional[Dict[str, Any]]:
        """
        Получение информации о файле по Telegram file_id.
        
        Args:
            telegram_file_id: ID файла в Telegram
            
        Returns:
            Информация о файле или None
        """
        try:
            file_record = await self.file_repository.get_file_by_telegram_id(telegram_file_id)
            
            if not file_record:
                return None
            
            file_info = self._record_to_dict(file_record)
            file_id = str(file_record.id)
            
            # Кэшируем
            self._cache_file_info(file_id, file_info)
            
            return file_info
            
        except Exception as e:
            logger.error(f"Error getting file by telegram ID {telegram_file_id}: {e}")
            return None
    
    async def attach_file_to_object(
        self,
        file_id: str,
        object_id: str,
        object_type: str,
        attachment_type: str = 'general',
        description: Optional[str] = None
    ) -> bool:
        """
        Привязка файла к объекту.
        
        Args:
            file_id: Внутренний ID файла
            object_id: ID объекта
            object_type: Тип объекта ('service_object', 'installation_object', etc.)
            attachment_type: Тип привязки ('problem', 'letter', 'project', etc.)
            description: Описание привязки
            
        Returns:
            Успех операции
        """
        try:
            # Проверяем существование файла
            file_record = await self.file_repository.get_file_by_id(file_id)
            if not file_record:
                raise FileNotFoundError(f"Файл не найден: {file_id}")
            
            # Проверяем, не привязан ли уже файл к этому объекту
            existing = await self.file_repository.get_attachment(
                file_id=file_id,
                object_id=object_id,
                object_type=object_type
            )
            
            if existing:
                logger.warning(f"File {file_id} already attached to {object_type}/{object_id}")
                return True
            
            # Создаем привязку
            attachment = FileAttachment(
                file_id=file_id,
                object_id=object_id,
                object_type=object_type,
                attachment_type=attachment_type,
                description=description or '',
                attached_at=datetime.now(),
                is_active=True
            )
            
            # Сохраняем
            await self.file_repository.save_attachment(attachment)
            
            # Обновляем кэш
            cache_key = f"{object_type}:{object_id}"
            if cache_key not in self.attachments_cache:
                self.attachments_cache[cache_key] = []
            
            if file_id not in self.attachments_cache[cache_key]:
                self.attachments_cache[cache_key].append(file_id)
            
            logger.info(f"File {file_id} attached to {object_type}/{object_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error attaching file {file_id} to object: {e}", exc_info=True)
            return False
    
    async def detach_file_from_object(
        self,
        file_id: str,
        object_id: str,
        object_type: str
    ) -> bool:
        """
        Отвязка файла от объекта.
        
        Args:
            file_id: Внутренний ID файла
            object_id: ID объекта
            object_type: Тип объекта
            
        Returns:
            Успех операции
        """
        try:
            # Находим привязку
            attachment = await self.file_repository.get_attachment(
                file_id=file_id,
                object_id=object_id,
                object_type=object_type
            )
            
            if not attachment:
                logger.warning(f"Attachment not found: {file_id} -> {object_type}/{object_id}")
                return False
            
            # Удаляем привязку
            success = await self.file_repository.delete_attachment(str(attachment.id))
            
            if success:
                # Обновляем кэш
                cache_key = f"{object_type}:{object_id}"
                if cache_key in self.attachments_cache and file_id in self.attachments_cache[cache_key]:
                    self.attachments_cache[cache_key].remove(file_id)
                
                logger.info(f"File {file_id} detached from {object_type}/{object_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error detaching file {file_id} from object: {e}")
            return False
    
    async def get_object_files(
        self,
        object_id: str,
        object_type: str,
        attachment_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Получение файлов, привязанных к объекту.
        
        Args:
            object_id: ID объекта
            object_type: Тип объекта
            attachment_type: Тип привязки для фильтрации
            limit: Максимальное количество
            offset: Смещение
            
        Returns:
            Список файлов
        """
        try:
            # Проверяем кэш
            cache_key = f"{object_type}:{object_id}"
            if attachment_type:
                cache_key += f":{attachment_type}"
            
            # Кэшируем только для общих запросов без смещения
            if offset == 0 and cache_key in self.attachments_cache:
                file_ids = self.attachments_cache[cache_key]
                files = []
                for file_id in file_ids[:limit]:
                    file_info = await self.get_file_by_id(file_id)
                    if file_info:
                        files.append(file_info)
                return files
            
            # Получаем из БД
            attachments = await self.file_repository.get_object_attachments(
                object_id=object_id,
                object_type=object_type,
                attachment_type=attachment_type,
                limit=limit,
                offset=offset
            )
            
            # Получаем информацию о файлах
            files = []
            file_ids = []
            
            for attachment in attachments:
                file_info = await self.get_file_by_id(str(attachment.file_id))
                if file_info:
                    # Добавляем информацию о привязке
                    file_info['attachment'] = {
                        'id': str(attachment.id),
                        'attachment_type': attachment.attachment_type,
                        'description': attachment.description,
                        'attached_at': attachment.attached_at.isoformat() if attachment.attached_at else None
                    }
                    files.append(file_info)
                    file_ids.append(str(attachment.file_id))
            
            # Кэшируем для будущих запросов
            if offset == 0 and not attachment_type:
                self.attachments_cache[cache_key] = file_ids
            
            return files
            
        except Exception as e:
            logger.error(f"Error getting object files {object_type}/{object_id}: {e}")
            return []
    
    async def get_files_by_type(
        self,
        file_type: str,
        category: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Получение файлов по типу.
        
        Args:
            file_type: Тип файла ('document', 'photo', 'video', 'audio')
            category: Категория для фильтрации
            limit: Максимальное количество
            offset: Смещение
            
        Returns:
            Список файлов
        """
        try:
            files = await self.file_repository.get_files_by_type(
                file_type=file_type,
                category=category,
                limit=limit,
                offset=offset
            )
            
            return [self._record_to_dict(file) for file in files]
            
        except Exception as e:
            logger.error(f"Error getting files by type {file_type}: {e}")
            return []
    
    async def search_files(
        self,
        search_text: str,
        object_id: Optional[str] = None,
        object_type: Optional[str] = None,
        file_type: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Поиск файлов по тексту.
        
        Args:
            search_text: Текст для поиска
            object_id: ID объекта для фильтрации
            object_type: Тип объекта для фильтрации
            file_type: Тип файла для фильтрации
            limit: Максимальное количество результатов
            
        Returns:
            Список найденных файлов
        """
        try:
            if not search_text or len(search_text.strip()) < 2:
                return []
            
            search_text = search_text.strip().lower()
            
            # Получаем файлы для поиска
            files = []
            if object_id and object_type:
                # Ищем среди файлов объекта
                files = await self.get_object_files(object_id, object_type, limit=100)
            else:
                # Ищем среди всех файлов
                files_records = await self.file_repository.search_files(
                    search_text=search_text,
                    file_type=file_type,
                    limit=limit
                )
                files = [self._record_to_dict(f) for f in files_records]
            
            # Фильтруем по search_text
            results = []
            for file_info in files:
                # Поиск в названии, описании и метаданных
                if (search_text in (file_info.get('file_name') or '').lower() or
                    search_text in (file_info.get('description') or '').lower() or
                    search_text in str(file_info.get('metadata', {})).lower()):
                    
                    results.append(file_info)
                    if len(results) >= limit:
                        break
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching files: {e}")
            return []
    
    async def update_file_metadata(
        self,
        file_id: str,
        metadata: Dict[str, Any],
        merge: bool = True
    ) -> bool:
        """
        Обновление метаданных файла.
        
        Args:
            file_id: Внутренний ID файла
            metadata: Новые метаданные
            merge: Объединить с существующими метаданными
            
        Returns:
            Успех операции
        """
        try:
            file_record = await self.file_repository.get_file_by_id(file_id)
            if not file_record:
                raise FileNotFoundError(f"Файл не найден: {file_id}")
            
            if merge:
                # Объединяем с существующими метаданными
                current_metadata = file_record.metadata or {}
                current_metadata.update(metadata)
                new_metadata = current_metadata
            else:
                new_metadata = metadata
            
            # Обновляем
            file_record.metadata = new_metadata
            file_record.updated_at = datetime.now()
            
            await self.file_repository.save_file(file_record)
            
            # Очищаем кэш
            if file_id in self.file_cache:
                del self.file_cache[file_id]
            
            logger.info(f"Metadata updated for file {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating file metadata {file_id}: {e}")
            return False
    
    async def delete_file(self, file_id: str, soft_delete: bool = True) -> bool:
        """
        Удаление файла из системы.
        
        Args:
            file_id: Внутренний ID файла
            soft_delete: Мягкое удаление (пометить как неактивный)
            
        Returns:
            Успех операции
        """
        try:
            file_record = await self.file_repository.get_file_by_id(file_id)
            if not file_record:
                raise FileNotFoundError(f"Файл не найден: {file_id}")
            
            if soft_delete:
                # Мягкое удаление
                file_record.is_active = False
                file_record.deleted_at = datetime.now()
                await self.file_repository.save_file(file_record)
                
                # Также помечаем неактивными все привязки
                await self.file_repository.deactivate_file_attachments(file_id)
            else:
                # Полное удаление
                # Сначала удаляем привязки
                await self.file_repository.delete_file_attachments(file_id)
                # Затем файл
                await self.file_repository.delete_file(file_id)
            
            # Очищаем кэш
            self._clear_file_cache(file_id)
            
            logger.info(f"File {'soft' if soft_delete else 'hard'} deleted: {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting file {file_id}: {e}", exc_info=True)
            return False
    
    async def get_file_statistics(self) -> Dict[str, Any]:
        """
        Получение статистики по файлам.
        
        Returns:
            Статистика
        """
        try:
            stats = await self.file_repository.get_file_statistics()
            return stats
        except Exception as e:
            logger.error(f"Error getting file statistics: {e}")
            return {}
    
    async def cleanup_old_files(self, days_old: int = 30) -> int:
        """
        Очистка старых неактивных файлов.
        
        Args:
            days_old: Возраст файлов в днях
            
        Returns:
            Количество удаленных файлов
        """
        try:
            deleted_count = await self.file_repository.delete_old_inactive_files(days_old)
            logger.info(f"Cleaned up {deleted_count} old inactive files")
            return deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up old files: {e}")
            return 0
    
    # ========== Внутренние методы ==========
    
    def _record_to_dict(self, file_record: TelegramFile) -> Dict[str, Any]:
        """
        Преобразование записи файла в словарь.
        
        Args:
            file_record: Запись файла
            
        Returns:
            Словарь с информацией о файле
        """
        return {
            'id': str(file_record.id),
            'telegram_file_id': file_record.telegram_file_id,
            'telegram_unique_id': file_record.telegram_unique_id,
            'file_name': file_record.file_name,
            'mime_type': file_record.mime_type,
            'file_size': file_record.file_size,
            'file_type': file_record.file_type,
            'category': file_record.category,
            'description': file_record.description,
            'metadata': file_record.metadata or {},
            'uploaded_by': file_record.uploaded_by,
            'uploaded_at': file_record.uploaded_at.isoformat() if file_record.uploaded_at else None,
            'message_id': file_record.message_id,
            'chat_id': file_record.chat_id,
            'download_url': file_record.download_url,
            'is_active': file_record.is_active,
            'created_at': file_record.created_at.isoformat() if file_record.created_at else None,
            'updated_at': file_record.updated_at.isoformat() if file_record.updated_at else None,
            'deleted_at': file_record.deleted_at.isoformat() if file_record.deleted_at else None
        }
    
    def _cache_file_info(self, file_id: str, file_info: Dict[str, Any]):
        """
        Кэширование информации о файле.
        
        Args:
            file_id: ID файла
            file_info: Информация о файле
        """
        # Добавляем время кэширования
        file_info['cached_at'] = datetime.now().timestamp()
        
        # Ограничиваем размер кэша
        if len(self.file_cache) > 1000:
            # Удаляем самые старые записи
            oldest_keys = sorted(self.file_cache.keys(), 
                               key=lambda k: self.file_cache[k].get('cached_at', 0))[:100]
            for key in oldest_keys:
                del self.file_cache[key]
        
        self.file_cache[file_id] = file_info
    
    def _clear_file_cache(self, file_id: str):
        """
        Очистка кэша файла.
        
        Args:
            file_id: ID файла
        """
        # Удаляем из основного кэша
        if file_id in self.file_cache:
            del self.file_cache[file_id]
        
        # Удаляем из кэша привязок
        keys_to_remove = []
        for cache_key, file_ids in self.attachments_cache.items():
            if file_id in file_ids:
                self.attachments_cache[cache_key].remove(file_id)
                if not self.attachments_cache[cache_key]:
                    keys_to_remove.append(cache_key)
        
        for key in keys_to_remove:
            del self.attachments_cache[key]
    
    async def get_file_download_info(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Получение информации для скачивания файла.
        
        Args:
            file_id: Внутренний ID файла
            
        Returns:
            Информация для скачивания или None
        """
        file_info = await self.get_file_by_id(file_id)
        if not file_info:
            return None
        
        return {
            'telegram_file_id': file_info['telegram_file_id'],
            'file_name': file_info['file_name'],
            'file_size': file_info['file_size'],
            'mime_type': file_info['mime_type'],
            'download_url': file_info['download_url'],
            'description': file_info['description']
        }