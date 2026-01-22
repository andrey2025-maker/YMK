"""
Менеджер работы с файлами в Telegram.
Реализует загрузку, скачивание и управление файлами в Telegram группах/каналах.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple, BinaryIO
from datetime import datetime
from enum import Enum

from aiogram import Bot
from aiogram.types import (
    Message, InputFile, FSInputFile, URLInputFile,
    Document, PhotoSize, Video, Audio
)

from core.context import AppContext
from config import BotConfig
from utils.exceptions import FileUploadError, FileNotFoundError, TelegramAPIError

logger = logging.getLogger(__name__)


class FileCategory(Enum):
    """Категории файлов для архивации."""
    PDF = "pdf"
    EXCEL = "excel"
    WORD = "word"
    IMAGE = "image"
    OTHER = "other"
    ARCHIVE = "archive"


class FileType(Enum):
    """Типы файлов в Telegram."""
    DOCUMENT = "document"
    PHOTO = "photo"
    VIDEO = "video"
    AUDIO = "audio"
    VOICE = "voice"
    VIDEO_NOTE = "video_note"
    STICKER = "sticker"


class TelegramFileManager:
    """Менеджер работы с файлами в Telegram."""
    
    def __init__(self, context: AppContext):
        self.context = context
        self.config: BotConfig = context.config
        self.bot: Bot = context.bot
        
        # Настройки групп архивов из конфигурации
        self.archive_chat_id = self.config.archive_chat_id
        self.archive_topics = self.config.archive_topics
        
        # Кэш для хранения информации о файлах
        self.file_cache = {}
    
    async def initialize(self):
        """Инициализация менеджера."""
        logger.info("Initializing TelegramFileManager")
        
        # Проверяем доступ к архивам
        if self.archive_chat_id:
            try:
                chat = await self.bot.get_chat(self.archive_chat_id)
                logger.info(f"Archive chat accessible: {chat.title}")
            except Exception as e:
                logger.warning(f"Cannot access archive chat: {e}")
        
        return self
    
    async def upload_file(
        self,
        file_data: Dict[str, Any],
        category: FileCategory,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Загрузка файла в Telegram архив.
        
        Args:
            file_data: Данные файла (message_id, file_id, или bytes)
            category: Категория файла
            description: Описание файла
            metadata: Дополнительные метаданные
            
        Returns:
            Информация о загруженном файле
        """
        try:
            # Получаем тему для категории
            topic_id = self._get_topic_id_for_category(category)
            
            # Подготавливаем файл для загрузки
            file_to_send = await self._prepare_file_for_upload(file_data)
            
            # Подготавливаем подпись
            caption = self._prepare_caption(description, metadata)
            
            # Загружаем файл в Telegram
            message = await self._send_to_telegram(
                file_to_send, 
                category, 
                caption, 
                topic_id
            )
            
            # Сохраняем информацию о файле
            file_info = await self._extract_file_info(message, category)
            
            # Добавляем метаданные
            if metadata:
                file_info['metadata'] = metadata
            
            # Кэшируем информацию
            self._cache_file_info(file_info['file_id'], file_info)
            
            logger.info(f"File uploaded successfully: {file_info['file_id']}")
            return file_info
            
        except Exception as e:
            logger.error(f"Error uploading file: {e}", exc_info=True)
            raise FileUploadError(f"Ошибка загрузки файла: {str(e)}")
    
    async def download_file(
        self,
        file_id: str,
        destination_path: Optional[str] = None
    ) -> Tuple[bytes, str]:
        """
        Скачивание файла из Telegram.
        
        Args:
            file_id: ID файла в Telegram
            destination_path: Путь для сохранения (опционально)
            
        Returns:
            Кортеж (данные файла, имя файла)
        """
        try:
            # Получаем информацию о файле из кэша или Telegram
            file_info = await self.get_file_info(file_id)
            
            # Скачиваем файл
            file_data = await self.bot.download_file_by_id(file_id)
            
            if not file_data:
                raise FileNotFoundError(f"Файл не найден: {file_id}")
            
            # Если указан путь для сохранения
            if destination_path:
                with open(destination_path, 'wb') as f:
                    f.write(file_data.read())
            
            file_name = file_info.get('file_name', f"file_{file_id}")
            return file_data.read(), file_name
            
        except Exception as e:
            logger.error(f"Error downloading file {file_id}: {e}", exc_info=True)
            raise FileNotFoundError(f"Ошибка скачивания файла: {str(e)}")
    
    async def get_file_info(self, file_id: str) -> Dict[str, Any]:
        """
        Получение информации о файле.
        
        Args:
            file_id: ID файла в Telegram
            
        Returns:
            Информация о файле
        """
        # Проверяем кэш
        if file_id in self.file_cache:
            return self.file_cache[file_id]
        
        try:
            # Получаем информацию из Telegram
            file = await self.bot.get_file(file_id)
            
            file_info = {
                'file_id': file_id,
                'file_unique_id': file.file_unique_id,
                'file_size': file.file_size,
                'file_path': file.file_path,
                'download_url': f"https://api.telegram.org/file/bot{self.bot.token}/{file.file_path}",
                'cached_at': datetime.now().isoformat()
            }
            
            # Кэшируем
            self._cache_file_info(file_id, file_info)
            
            return file_info
            
        except Exception as e:
            logger.error(f"Error getting file info {file_id}: {e}")
            raise FileNotFoundError(f"Файл не найден: {file_id}")
    
    async def delete_file(self, file_id: str, message_id: Optional[int] = None) -> bool:
        """
        Удаление файла из Telegram.
        
        Args:
            file_id: ID файла в Telegram
            message_id: ID сообщения с файлом (если известно)
            
        Returns:
            Успех операции
        """
        try:
            # Если известен message_id, удаляем сообщение
            if message_id and self.archive_chat_id:
                await self.bot.delete_message(
                    chat_id=self.archive_chat_id,
                    message_id=message_id
                )
            
            # Удаляем из кэша
            if file_id in self.file_cache:
                del self.file_cache[file_id]
            
            logger.info(f"File deleted: {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting file {file_id}: {e}")
            return False
    
    async def upload_to_category(
        self,
        file_data: Dict[str, Any],
        category_name: str,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Загрузка файла в конкретную категорию.
        
        Args:
            file_data: Данные файла
            category_name: Название категории (pdf, excel, word, image, other)
            description: Описание файла
            metadata: Дополнительные метаданные
            
        Returns:
            Информация о загруженном файле
        """
        try:
            # Определяем категорию
            category = self._parse_category(category_name)
            
            # Загружаем файл
            return await self.upload_file(file_data, category, description, metadata)
            
        except Exception as e:
            logger.error(f"Error uploading to category {category_name}: {e}", exc_info=True)
            raise FileUploadError(f"Ошибка загрузки в категорию {category_name}: {str(e)}")
    
    async def get_files_by_category(
        self,
        category: FileCategory,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Получение файлов по категории.
        
        Args:
            category: Категория файлов
            limit: Максимальное количество
            offset: Смещение
            
        Returns:
            Список файлов
        """
        # Внимание: Для получения файлов по категории требуется доступ к истории чата
        # Этот метод может быть ограничен правами бота
        
        try:
            topic_id = self._get_topic_id_for_category(category)
            files = []
            
            # Здесь должна быть реализация получения истории сообщений из топика
            # Это сложная операция, требует дополнительных прав
            
            # Временная заглушка
            logger.warning("get_files_by_category is not fully implemented")
            return files
            
        except Exception as e:
            logger.error(f"Error getting files by category {category}: {e}")
            return []
    
    async def search_files(
        self,
        search_text: str,
        category: Optional[FileCategory] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Поиск файлов по тексту в описании.
        
        Args:
            search_text: Текст для поиска
            category: Категория для фильтрации
            limit: Максимальное количество результатов
            
        Returns:
            Список найденных файлов
        """
        # Внимание: Поиск по файлам требует хранения метаданных в БД
        # Этот метод должен работать с репозиторием файлов
        
        try:
            # Здесь должна быть реализация поиска в БД
            # Временная заглушка
            return []
            
        except Exception as e:
            logger.error(f"Error searching files: {e}")
            return []
    
    async def get_file_download_url(self, file_id: str) -> Optional[str]:
        """
        Получение URL для скачивания файла.
        
        Args:
            file_id: ID файла в Telegram
            
        Returns:
            URL для скачивания или None
        """
        try:
            file_info = await self.get_file_info(file_id)
            return file_info.get('download_url')
        except Exception as e:
            logger.error(f"Error getting download URL for {file_id}: {e}")
            return None
    
    # ========== Внутренние методы ==========
    
    def _get_topic_id_for_category(self, category: FileCategory) -> Optional[int]:
        """
        Получение ID темы для категории.
        
        Args:
            category: Категория файла
            
        Returns:
            ID темы или None
        """
        if not self.archive_topics:
            return None
        
        topic_mapping = {
            FileCategory.PDF: self.archive_topics.get('pdf'),
            FileCategory.EXCEL: self.archive_topics.get('excel'),
            FileCategory.WORD: self.archive_topics.get('word'),
            FileCategory.IMAGE: self.archive_topics.get('image'),
            FileCategory.OTHER: self.archive_topics.get('other'),
            FileCategory.ARCHIVE: self.archive_topics.get('archive'),
        }
        
        return topic_mapping.get(category)
    
    def _parse_category(self, category_name: str) -> FileCategory:
        """
        Парсинг названия категории.
        
        Args:
            category_name: Название категории
            
        Returns:
            Объект FileCategory
        """
        category_name = category_name.lower().strip()
        
        if category_name in ['pdf', 'пдф']:
            return FileCategory.PDF
        elif category_name in ['excel', 'эксель', 'xlsx', 'xls']:
            return FileCategory.EXCEL
        elif category_name in ['word', 'ворд', 'docx', 'doc']:
            return FileCategory.WORD
        elif category_name in ['image', 'изображение', 'photo', 'фото', 'картинка']:
            return FileCategory.IMAGE
        elif category_name in ['archive', 'архив']:
            return FileCategory.ARCHIVE
        else:
            return FileCategory.OTHER
    
    async def _prepare_file_for_upload(self, file_data: Dict[str, Any]) -> Any:
        """
        Подготовка файла для загрузки в Telegram.
        
        Args:
            file_data: Данные файла
            
        Returns:
            Объект для отправки в Telegram
        """
        if 'file_id' in file_data:
            # Файл уже в Telegram
            return file_data['file_id']
        
        elif 'message_id' in file_data and 'chat_id' in file_data:
            # Файл в сообщении, получаем file_id
            message = await self.bot.copy_message(
                chat_id=file_data['chat_id'],
                from_chat_id=file_data['chat_id'],
                message_id=file_data['message_id']
            )
            return self._extract_file_id_from_message(message)
        
        elif 'file_path' in file_data:
            # Файл на диске
            return FSInputFile(file_data['file_path'])
        
        elif 'url' in file_data:
            # Файл по URL
            return URLInputFile(file_data['url'])
        
        elif 'bytes' in file_data:
            # Файл в памяти
            # Создаем временный файл
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_data.get('suffix', '.bin')) as tmp:
                tmp.write(file_data['bytes'])
                tmp_path = tmp.name
            
            file_input = FSInputFile(tmp_path)
            
            # Удаляем временный файл после отправки
            async def cleanup():
                await asyncio.sleep(1)
                try:
                    os.unlink(tmp_path)
                except:
                    pass
            
            asyncio.create_task(cleanup())
            return file_input
        
        else:
            raise ValueError("Неподдерживаемый формат файла")
    
    def _prepare_caption(
        self, 
        description: Optional[str] = None, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Подготовка подписи для файла.
        
        Args:
            description: Описание файла
            metadata: Метаданные
            
        Returns:
            Подпись для Telegram
        """
        caption_parts = []
        
        if description:
            caption_parts.append(description[:500])  # Ограничиваем длину
        
        if metadata:
            metadata_str = " | ".join([f"{k}: {v}" for k, v in metadata.items() if v])
            if metadata_str:
                caption_parts.append(metadata_str)
        
        # Добавляем дату
        date_str = datetime.now().strftime("📅 %d.%m.%Y %H:%M")
        caption_parts.append(date_str)
        
        return "\n".join(caption_parts)
    
    async def _send_to_telegram(
        self, 
        file_input: Any, 
        category: FileCategory,
        caption: str, 
        topic_id: Optional[int] = None
    ) -> Message:
        """
        Отправка файла в Telegram.
        
        Args:
            file_input: Файл для отправки
            category: Категория файла
            caption: Подпись
            topic_id: ID темы
            
        Returns:
            Сообщение в Telegram
        """
        try:
            if not self.archive_chat_id:
                raise ValueError("Не указан chat_id архива")
            
            send_params = {
                'chat_id': self.archive_chat_id,
                'caption': caption[:1024] if caption else None,  # Ограничение Telegram
            }
            
            # Добавляем topic_id если есть
            if topic_id:
                send_params['message_thread_id'] = topic_id
            
            # Определяем тип файла и отправляем
            if isinstance(file_input, str) and len(file_input) < 100:
                # Предполагаем, что это file_id
                send_params['document'] = file_input
                message = await self.bot.send_document(**send_params)
            elif isinstance(file_input, FSInputFile):
                send_params['document'] = file_input
                message = await self.bot.send_document(**send_params)
            elif isinstance(file_input, URLInputFile):
                send_params['document'] = file_input
                message = await self.bot.send_document(**send_params)
            else:
                # Пробуем как документ
                send_params['document'] = file_input
                message = await self.bot.send_document(**send_params)
            
            return message
            
        except Exception as e:
            logger.error(f"Error sending to Telegram: {e}", exc_info=True)
            raise TelegramAPIError(f"Ошибка отправки в Telegram: {str(e)}")
    
    async def _extract_file_info(self, message: Message, category: FileCategory) -> Dict[str, Any]:
        """
        Извлечение информации о файле из сообщения.
        
        Args:
            message: Сообщение Telegram
            category: Категория файла
            
        Returns:
            Информация о файле
        """
        file_info = {
            'message_id': message.message_id,
            'chat_id': message.chat.id,
            'category': category.value,
            'uploaded_at': datetime.now().isoformat(),
            'caption': message.caption,
            'has_caption': bool(message.caption)
        }
        
        # Извлекаем информацию о файле в зависимости от типа
        if message.document:
            file_info.update({
                'file_id': message.document.file_id,
                'file_unique_id': message.document.file_unique_id,
                'file_name': message.document.file_name,
                'mime_type': message.document.mime_type,
                'file_size': message.document.file_size,
                'file_type': FileType.DOCUMENT.value,
            })
        
        elif message.photo:
            # Берем самую большую фото
            largest_photo = max(message.photo, key=lambda p: p.file_size)
            file_info.update({
                'file_id': largest_photo.file_id,
                'file_unique_id': largest_photo.file_unique_id,
                'file_size': largest_photo.file_size,
                'width': largest_photo.width,
                'height': largest_photo.height,
                'file_type': FileType.PHOTO.value,
            })
        
        elif message.video:
            file_info.update({
                'file_id': message.video.file_id,
                'file_unique_id': message.video.file_unique_id,
                'file_size': message.video.file_size,
                'width': message.video.width,
                'height': message.video.height,
                'duration': message.video.duration,
                'mime_type': message.video.mime_type,
                'file_type': FileType.VIDEO.value,
            })
        
        elif message.audio:
            file_info.update({
                'file_id': message.audio.file_id,
                'file_unique_id': message.audio.file_unique_id,
                'file_size': message.audio.file_size,
                'duration': message.audio.duration,
                'performer': message.audio.performer,
                'title': message.audio.title,
                'mime_type': message.audio.mime_type,
                'file_type': FileType.AUDIO.value,
            })
        
        else:
            raise ValueError("Неподдерживаемый тип файла в сообщении")
        
        return file_info
    
    def _extract_file_id_from_message(self, message: Message) -> Optional[str]:
        """
        Извлечение file_id из сообщения.
        
        Args:
            message: Сообщение Telegram
            
        Returns:
            file_id или None
        """
        if message.document:
            return message.document.file_id
        elif message.photo:
            largest_photo = max(message.photo, key=lambda p: p.file_size)
            return largest_photo.file_id
        elif message.video:
            return message.video.file_id
        elif message.audio:
            return message.audio.file_id
        return None
    
    def _cache_file_info(self, file_id: str, file_info: Dict[str, Any]):
        """
        Кэширование информации о файле.
        
        Args:
            file_id: ID файла
            file_info: Информация о файле
        """
        # Ограничиваем размер кэша
        if len(self.file_cache) > 1000:
            # Удаляем старые записи
            oldest_keys = sorted(self.file_cache.keys(), 
                               key=lambda k: self.file_cache[k].get('cached_at', ''))[:100]
            for key in oldest_keys:
                del self.file_cache[key]
        
        self.file_cache[file_id] = file_info
    
    async def cleanup_cache(self, max_age_hours: int = 24):
        """
        Очистка старого кэша.
        
        Args:
            max_age_hours: Максимальный возраст записей в часах
        """
        try:
            cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
            
            keys_to_delete = []
            for file_id, info in self.file_cache.items():
                cached_at = info.get('cached_at')
                if cached_at:
                    try:
                        cache_time = datetime.fromisoformat(cached_at).timestamp()
                        if cache_time < cutoff_time:
                            keys_to_delete.append(file_id)
                    except:
                        keys_to_delete.append(file_id)
            
            for key in keys_to_delete:
                del self.file_cache[key]
            
            logger.info(f"Cleaned up {len(keys_to_delete)} cache entries")
            
        except Exception as e:
            logger.error(f"Error cleaning cache: {e}")