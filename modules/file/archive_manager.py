import asyncio
import os
import mimetypes
from datetime import datetime
from typing import Optional, Dict, Any, BinaryIO, Tuple
from pathlib import Path
import tempfile

from aiogram import Bot
from aiogram.types import InputFile, Message
from aiogram.exceptions import TelegramBadRequest
import structlog

from core.context import AppContext
from config import config
from utils.date_utils import DateUtils


logger = structlog.get_logger(__name__)


class TelegramArchiveManager:
    """Менеджер для архивации файлов в Telegram."""
    
    def __init__(self, context: AppContext):
        self.context = context
        self.bot = Bot(token=config.bot.token)
        self.date_utils = DateUtils()
    
    async def upload_file(
        self,
        file_data: BinaryIO,
        file_name: str,
        file_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Загружает файл в соответствующую Telegram группу/тему.
        
        Args:
            file_data: Данные файла (бинарный поток)
            file_name: Имя файла
            file_type: Тип файла (pdf, excel, word, images, other)
            metadata: Дополнительные метаданные
            
        Returns:
            Информация о загруженном файле
        """
        try:
            # Определяем тип файла, если не указан
            if not file_type:
                file_type = self._detect_file_type(file_name)
            
            # Получаем настройки для этого типа файла
            chat_id, topic_id = self._get_chat_settings(file_type)
            
            if not chat_id:
                return {
                    "success": False,
                    "message": f"Не настроен чат для файлов типа: {file_type}"
                }
            
            # Подготавливаем метаданные
            metadata = metadata or {}
            metadata.update({
                "file_name": file_name,
                "file_type": file_type,
                "uploaded_at": datetime.now().isoformat(),
            })
            
            # Формируем подпись к файлу
            caption = self._format_caption(metadata)
            
            # Загружаем файл в Telegram
            result = await self._upload_to_telegram(
                file_data=file_data,
                file_name=file_name,
                chat_id=chat_id,
                topic_id=topic_id,
                caption=caption,
                metadata=metadata
            )
            
            if result["success"]:
                logger.info(
                    "File uploaded to Telegram",
                    file_name=file_name,
                    file_type=file_type,
                    chat_id=chat_id,
                    topic_id=topic_id,
                    message_id=result.get("message_id")
                )
            
            return result
        
        except Exception as e:
            logger.error("File upload failed", file_name=file_name, error=str(e))
            return {
                "success": False,
                "message": f"Ошибка при загрузке файла: {str(e)}"
            }
    
    async def archive_deleted_object(
        self,
        object_type: str,
        object_data: Dict[str, Any],
        files: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Архивирует удаленный объект со всеми данными.
        
        Args:
            object_type: Тип объекта (service, installation)
            object_data: Данные объекта
            files: Список файлов объекта
            
        Returns:
            Результат архивации
        """
        try:
            # Получаем настройки для архивов
            chat_id = config.archive.files_chat_id
            topic_id = config.archive.archives_topic_id
            
            if not chat_id:
                return {
                    "success": False,
                    "message": "Не настроен чат для архивов"
                }
            
            # Формируем сообщение с данными объекта
            object_text = self._format_object_archive(object_type, object_data)
            
            # Отправляем текстовое сообщение с данными
            message = await self.bot.send_message(
                chat_id=chat_id,
                message_thread_id=topic_id,
                text=object_text,
                parse_mode="HTML"
            )
            
            # Если есть файлы, прикрепляем их как ответ
            if files:
                for file_info in files:
                    await self._attach_file_to_message(
                        file_info=file_info,
                        reply_to_message_id=message.message_id,
                        chat_id=chat_id,
                        topic_id=topic_id
                    )
            
            logger.info(
                "Object archived",
                object_type=object_type,
                object_id=object_data.get("id"),
                message_id=message.message_id
            )
            
            return {
                "success": True,
                "message": "Объект заархивирован",
                "chat_id": chat_id,
                "topic_id": topic_id,
                "message_id": message.message_id,
            }
        
        except Exception as e:
            logger.error("Object archive failed", object_type=object_type, error=str(e))
            return {
                "success": False,
                "message": f"Ошибка при архивации объекта: {str(e)}"
            }
    
    async def log_change(
        self,
        change_type: str,
        old_data: Optional[Dict[str, Any]],
        new_data: Optional[Dict[str, Any]],
        changed_by: Dict[str, Any],
        object_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Логирует изменение в Telegram группу.
        
        Args:
            change_type: Тип изменения (create, update, delete)
            old_data: Старые данные
            new_data: Новые данные
            changed_by: Кто изменил
            object_info: Информация об объекте
            
        Returns:
            Результат логирования
        """
        try:
            chat_id = config.archive.changes_chat_id
            topic_id = config.archive.changes_topic_id
            
            if not chat_id:
                return {
                    "success": False,
                    "message": "Не настроен чат для логов изменений"
                }
            
            # Формируем сообщение об изменении
            change_text = self._format_change_log(
                change_type=change_type,
                old_data=old_data,
                new_data=new_data,
                changed_by=changed_by,
                object_info=object_info
            )
            
            # Отправляем сообщение
            message = await self.bot.send_message(
                chat_id=chat_id,
                message_thread_id=topic_id,
                text=change_text,
                parse_mode="HTML"
            )
            
            logger.info(
                "Change logged",
                change_type=change_type,
                changed_by=changed_by.get("id"),
                message_id=message.message_id
            )
            
            return {
                "success": True,
                "message": "Изменение записано в лог",
                "chat_id": chat_id,
                "topic_id": topic_id,
                "message_id": message.message_id,
            }
        
        except Exception as e:
            logger.error("Change log failed", change_type=change_type, error=str(e))
            return {
                "success": False,
                "message": f"Ошибка при логировании изменения: {str(e)}"
            }
    
    async def send_log_message(
        self,
        log_level: str,
        message: str,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Отправляет лог-сообщение в Telegram группу.
        
        Args:
            log_level: Уровень лога (INFO, WARNING, ERROR, DEBUG)
            message: Текст сообщения
            extra_data: Дополнительные данные
            
        Returns:
            Результат отправки
        """
        try:
            chat_id = config.archive.logs_chat_id
            topic_id = config.archive.logs_topic_id
            
            if not chat_id:
                return {
                    "success": False,
                    "message": "Не настроен чат для логов"
                }
            
            # Форматируем лог-сообщение
            log_text = self._format_log_message(log_level, message, extra_data)
            
            # Отправляем сообщение
            msg = await self.bot.send_message(
                chat_id=chat_id,
                message_thread_id=topic_id,
                text=log_text,
                parse_mode="HTML"
            )
            
            return {
                "success": True,
                "message": "Лог отправлен",
                "chat_id": chat_id,
                "topic_id": topic_id,
                "message_id": msg.message_id,
            }
        
        except Exception as e:
            logger.error("Send log failed", log_level=log_level, error=str(e))
            return {
                "success": False,
                "message": f"Ошибка при отправке лога: {str(e)}"
            }
    
    def _detect_file_type(self, file_name: str) -> str:
        """Определяет тип файла по расширению."""
        # Получаем расширение файла
        _, extension = os.path.splitext(file_name.lower())
        
        # Проверяем разрешенные типы файлов
        for file_type, extensions in config.bot.allowed_file_types.items():
            if extension in extensions:
                return file_type
        
        # Если тип не определен, возвращаем 'other'
        return "other"
    
    def _get_chat_settings(self, file_type: str) -> Tuple[Optional[str], Optional[int]]:
        """Получает настройки чата для указанного типа файла."""
        chat_id = config.archive.files_chat_id
        
        if not chat_id:
            return None, None
        
        # Получаем ID темы для типа файла
        topic_mapping = {
            "pdf": config.archive.pdf_topic_id,
            "excel": config.archive.excel_topic_id,
            "word": config.archive.word_topic_id,
            "images": config.archive.images_topic_id,
            "other": config.archive.other_topic_id,
        }
        
        topic_id = topic_mapping.get(file_type, config.archive.other_topic_id)
        
        return chat_id, topic_id
    
    def _format_caption(self, metadata: Dict[str, Any]) -> str:
        """Форматирует подпись для файла."""
        template = config.archive.file_name_template
        
        # Заменяем плейсхолдеры в шаблоне
        caption = template.format(
            date=self.date_utils.format_date(datetime.now()),
            object=metadata.get("object_name", "Неизвестно"),
            type=metadata.get("file_type", "Файл").upper(),
            description=metadata.get("description", ""),
            uploaded_by=metadata.get("uploaded_by", "Система"),
        )
        
        # Добавляем дополнительные метаданные
        if "additional_info" in metadata:
            caption += f"\n\n{metadata['additional_info']}"
        
        # Ограничиваем длину (Telegram ограничение для caption - 1024 символа)
        if len(caption) > 1000:
            caption = caption[:997] + "..."
        
        return caption
    
    def _format_object_archive(self, object_type: str, object_data: Dict[str, Any]) -> str:
        """Форматирует архив удаленного объекта."""
        timestamp = self.date_utils.format_date(datetime.now(), include_time=True)
        
        text = [
            f"🗑️ <b>АРХИВ УДАЛЕННОГО ОБЪЕКТА</b>",
            f"📅 {timestamp}",
            f"",
            f"<b>Тип объекта:</b> {object_type}",
            f"<b>ID объекта:</b> {object_data.get('id', 'Неизвестно')}",
        ]
        
        # Добавляем основную информацию об объекте
        if "name" in object_data:
            text.append(f"<b>Название:</b> {object_data['name']}")
        
        if "region" in object_data:
            text.append(f"<b>Регион:</b> {object_data['region']}")
        
        # Добавляем дополнительные данные
        if "data" in object_data and isinstance(object_data["data"], dict):
            text.append(f"")
            text.append(f"<b>Данные объекта:</b>")
            for key, value in object_data["data"].items():
                if isinstance(value, str) and len(value) > 100:
                    value = value[:97] + "..."
                text.append(f"{key}: {value}")
        
        # Добавляем причину удаления
        if "deleted_by" in object_data:
            text.append(f"")
            text.append(f"<b>Удалено:</b> {object_data['deleted_by']}")
        
        if "deletion_reason" in object_data:
            text.append(f"<b>Причина:</b> {object_data['deletion_reason']}")
        
        return "\n".join(text)
    
    def _format_change_log(
        self,
        change_type: str,
        old_data: Optional[Dict[str, Any]],
        new_data: Optional[Dict[str, Any]],
        changed_by: Dict[str, Any],
        object_info: Optional[Dict[str, Any]]
    ) -> str:
        """Форматирует лог изменения."""
        timestamp = self.date_utils.format_date(datetime.now(), include_time=True)
        
        # Типы изменений с иконками
        change_icons = {
            "create": "🆕",
            "update": "✏️",
            "delete": "🗑️",
            "permission": "🔐",
            "admin": "👨‍💼",
        }
        
        icon = change_icons.get(change_type, "📝")
        
        text = [
            f"{icon} <b>ИЗМЕНЕНИЕ: {change_type.upper()}</b>",
            f"📅 {timestamp}",
            f"👤 {changed_by.get('username', 'Система')}",
        ]
        
        # Добавляем информацию об объекте
        if object_info:
            text.append(f"")
            text.append(f"<b>Объект:</b>")
            for key, value in object_info.items():
                text.append(f"{key}: {value}")
        
        # Показываем изменения
        if change_type == "update" and old_data and new_data:
            text.append(f"")
            text.append(f"<b>Изменения:</b>")
            
            # Находим различающиеся поля
            all_keys = set(old_data.keys()) | set(new_data.keys())
            for key in all_keys:
                old_val = old_data.get(key)
                new_val = new_data.get(key)
                
                if old_val != new_val:
                    old_str = str(old_val)[:50] + "..." if len(str(old_val)) > 50 else str(old_val)
                    new_str = str(new_val)[:50] + "..." if len(str(new_val)) > 50 else str(new_val)
                    text.append(f"{key}: {old_str} → {new_str}")
        
        return "\n".join(text)
    
    def _format_log_message(
        self,
        log_level: str,
        message: str,
        extra_data: Optional[Dict[str, Any]]
    ) -> str:
        """Форматирует лог-сообщение."""
        timestamp = self.date_utils.format_date(datetime.now(), include_time=True)
        
        # Иконки для уровней логов
        level_icons = {
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "DEBUG": "🔍",
        }
        
        icon = level_icons.get(log_level, "📝")
        
        text = [
            f"{icon} <b>{log_level}</b>",
            f"📅 {timestamp}",
            f"",
            f"{message}",
        ]
        
        # Добавляем дополнительные данные
        if extra_data:
            text.append(f"")
            text.append(f"<b>Дополнительно:</b>")
            for key, value in extra_data.items():
                if isinstance(value, str) and len(value) > 100:
                    value = value[:97] + "..."
                text.append(f"{key}: {value}")
        
        return "\n".join(text)
    
    async def _upload_to_telegram(
        self,
        file_data: BinaryIO,
        file_name: str,
        chat_id: str,
        topic_id: Optional[int],
        caption: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Загружает файл в Telegram."""
        try:
            # Создаем временный файл для загрузки
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp_file:
                # Копируем данные во временный файл
                file_data.seek(0)
                tmp_file.write(file_data.read())
                tmp_file_path = tmp_file.name
            
            try:
                # Отправляем файл в Telegram
                with open(tmp_file_path, 'rb') as file:
                    input_file = InputFile(file, filename=file_name)
                    
                    # Определяем метод отправки в зависимости от типа файла
                    file_type = metadata.get("file_type", "other")
                    
                    if file_type == "images":
                        # Изображения отправляем как фото
                        message = await self.bot.send_photo(
                            chat_id=chat_id,
                            message_thread_id=topic_id,
                            photo=input_file,
                            caption=caption,
                            parse_mode="HTML"
                        )
                    else:
                        # Остальные файлы как документы
                        message = await self.bot.send_document(
                            chat_id=chat_id,
                            message_thread_id=topic_id,
                            document=input_file,
                            caption=caption,
                            parse_mode="HTML"
                        )
                
                # Получаем информацию о файле для сохранения в БД
                file_info = await self._extract_file_info(message, metadata)
                
                return {
                    "success": True,
                    "message": "Файл успешно загружен",
                    "file_info": file_info,
                    "telegram_info": {
                        "chat_id": chat_id,
                        "topic_id": topic_id,
                        "message_id": message.message_id,
                        "file_id": self._get_file_id(message),
                    }
                }
            
            finally:
                # Удаляем временный файл
                os.unlink(tmp_file_path)
        
        except TelegramBadRequest as e:
            logger.error("Telegram upload failed", error=str(e), file_name=file_name)
            return {
                "success": False,
                "message": f"Ошибка Telegram: {str(e)}"
            }
        except Exception as e:
            logger.error("Upload to Telegram failed", error=str(e), file_name=file_name)
            return {
                "success": False,
                "message": f"Ошибка при загрузке: {str(e)}"
            }
    
    async def _attach_file_to_message(
        self,
        file_info: Dict[str, Any],
        reply_to_message_id: int,
        chat_id: str,
        topic_id: Optional[int]
    ) -> bool:
        """Прикрепляет файл к существующему сообщению."""
        # Реализация загрузки и прикрепления файла
        # В реальном приложении здесь будет загрузка файла
        pass
    
    def _get_file_id(self, message: Message) -> Optional[str]:
        """Извлекает file_id из сообщения Telegram."""
        if message.photo:
            return message.photo[-1].file_id
        elif message.document:
            return message.document.file_id
        elif message.video:
            return message.video.file_id
        elif message.audio:
            return message.audio.file_id
        elif message.voice:
            return message.voice.file_id
        return None
    
    async def _extract_file_info(
        self,
        message: Message,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Извлекает информацию о загруженном файле."""
        file_info = {
            "telegram_file_id": self._get_file_id(message),
            "message_id": message.message_id,
            "chat_id": message.chat.id,
            "file_size": None,
            "mime_type": None,
            "uploaded_at": datetime.now().isoformat(),
            **metadata
        }
        
        # Извлекаем дополнительную информацию в зависимости от типа
        if message.document:
            file_info.update({
                "file_size": message.document.file_size,
                "mime_type": message.document.mime_type,
                "file_name": message.document.file_name,
            })
        elif message.photo:
            # Для фото получаем размер самого большого варианта
            largest_photo = message.photo[-1]
            file_info.update({
                "file_size": largest_photo.file_size,
                "mime_type": "image/jpeg",
                "file_name": f"photo_{message.message_id}.jpg",
            })
        
        return file_info
    
    async def close(self) -> None:
        """Закрывает соединение с ботом."""
        await self.bot.session.close()