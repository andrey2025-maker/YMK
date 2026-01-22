"""
Менеджер для логирования изменений в системе.
Реализует запись всех изменений данных и отправку в Telegram группу архива.
"""
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import structlog

from core.context import AppContext
from storage.models.log import LogEntry, ChangeLog
from storage.repositories.log_repository import LogRepository
from utils.date_utils import format_date
from modules.file.archive_manager import ArchiveManager


logger = structlog.get_logger(__name__)


class LogManager:
    """Менеджер для логирования изменений в системе."""
    
    def __init__(self, context: AppContext):
        self.context = context
        self.log_repository: Optional[LogRepository] = None
        self.archive_manager: Optional[ArchiveManager] = None
        self.archive_chat_id: Optional[str] = None
        self.archive_thread_id: Optional[int] = None
    
    async def initialize(self) -> None:
        """Инициализирует менеджер логирования."""
        self.log_repository = LogRepository(self.context.db_session)
        
        # Инициализируем менеджер архива
        from modules.file.archive_manager import ArchiveManager
        self.archive_manager = ArchiveManager(self.context)
        
        # Получаем настройки архива логов из конфигурации
        config = self.context.config
        self.archive_chat_id = getattr(config, 'LOG_ARCHIVE_CHAT_ID', None)
        self.archive_thread_id = getattr(config, 'LOG_ARCHIVE_THREAD_ID', None)
        
        logger.info("LogManager initialized")
    
    async def log_change(
        self,
        user_id: int,
        user_name: str,
        entity_type: str,
        entity_id: str,
        entity_name: str,
        action: str,
        changes: Dict[str, Dict[str, Any]],
        chat_id: Optional[int] = None,
        message_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Логирует изменение данных с форматированием "было → стало".
        
        Args:
            user_id: ID пользователя
            user_name: Имя пользователя
            entity_type: Тип сущности (service_object, installation_object, problem и т.д.)
            entity_id: ID сущности
            entity_name: Название сущности
            action: Действие (create, update, delete)
            changes: Словарь изменений {поле: {"old": старое значение, "new": новое значение}}
            chat_id: ID чата (если изменение из группы)
            message_id: ID сообщения (если изменение из группы)
            
        Returns:
            Dict с информацией о созданном логе
        """
        try:
            # Форматируем изменения в читаемый вид
            formatted_changes = self._format_changes(changes)
            
            # Создаем запись лога
            log_entry = LogEntry(
                user_id=user_id,
                user_name=user_name,
                entity_type=entity_type,
                entity_id=entity_id,
                entity_name=entity_name,
                action=action,
                changes=formatted_changes,
                chat_id=chat_id,
                message_id=message_id,
                timestamp=datetime.now()
            )
            
            # Сохраняем в БД
            saved_log = await self.log_repository.create(log_entry)
            
            # Отправляем в архивную группу если настроено
            if self.archive_chat_id:
                await self._send_to_archive_group(saved_log)
            
            logger.info(
                "Change logged",
                user_id=user_id,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action
            )
            
            return {
                'success': True,
                'log_id': saved_log.id,
                'timestamp': saved_log.timestamp
            }
            
        except Exception as e:
            logger.error("Failed to log change", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    async def log_admin_action(
        self,
        admin_id: int,
        admin_name: str,
        target_type: str,
        target_id: str,
        target_name: str,
        action: str,
        details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Логирует действия администраторов.
        
        Args:
            admin_id: ID администратора
            admin_name: Имя администратора
            target_type: Тип цели (user, admin, permission, etc.)
            target_id: ID цели
            target_name: Название цели
            action: Действие (add, remove, update, etc.)
            details: Детали действия
            
        Returns:
            Dict с информацией о созданном логе
        """
        try:
            change_log = ChangeLog(
                admin_id=admin_id,
                admin_name=admin_name,
                target_type=target_type,
                target_id=target_id,
                target_name=target_name,
                action=action,
                details=details,
                timestamp=datetime.now()
            )
            
            saved_log = await self.log_repository.create_change_log(change_log)
            
            # Отправляем в архив если настроено
            if self.archive_chat_id:
                await self._send_admin_action_to_archive(saved_log)
            
            logger.info(
                "Admin action logged",
                admin_id=admin_id,
                target_type=target_type,
                action=action
            )
            
            return {
                'success': True,
                'log_id': saved_log.id
            }
            
        except Exception as e:
            logger.error("Failed to log admin action", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    async def log_file_upload(
        self,
        user_id: int,
        file_info: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Логирует загрузку файла в архив.
        
        Args:
            user_id: ID пользователя
            file_info: Информация о файле
            context: Контекст загрузки
            
        Returns:
            Dict с информацией о созданном логе
        """
        try:
            log_entry = LogEntry(
                user_id=user_id,
                user_name=file_info.get('uploader_name', 'Неизвестно'),
                entity_type='file',
                entity_id=file_info.get('id'),
                entity_name=file_info.get('name', 'Без названия'),
                action='upload',
                changes={
                    'file_info': file_info,
                    'context': context or {}
                },
                timestamp=datetime.now()
            )
            
            saved_log = await self.log_repository.create(log_entry)
            
            # Формируем сообщение для архива
            archive_message = (
                f"📁 Загрузка файла\n\n"
                f"📄 Файл: {file_info.get('name', 'Без названия')}\n"
                f"📁 Тип: {file_info.get('type', 'Неизвестно')}\n"
                f"📏 Размер: {file_info.get('size_human', 'Неизвестно')}\n"
                f"👤 Автор: {file_info.get('uploader_name', 'Неизвестно')}\n"
                f"📅 Дата: {format_date(datetime.now())}\n"
            )
            
            if context:
                archive_message += f"\n📋 Контекст:\n"
                for key, value in context.items():
                    if key not in ['file_id', 'user_id']:
                        archive_message += f"• {key}: {value}\n"
            
            # Отправляем в архив если настроено
            if self.archive_chat_id:
                await self._send_archive_message(archive_message)
            
            return {
                'success': True,
                'log_id': saved_log.id
            }
            
        except Exception as e:
            logger.error("Failed to log file upload", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    async def log_error(
        self,
        user_id: Optional[int],
        action: str,
        error: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Логирует ошибки системы.
        
        Args:
            user_id: ID пользователя (если есть)
            action: Действие которое вызвало ошибку
            error: Текст ошибки
            details: Дополнительные детали
            
        Returns:
            Dict с информацией о созданном логе
        """
        try:
            error_log = {
                'user_id': user_id,
                'action': action,
                'error': error,
                'details': details or {},
                'timestamp': datetime.now()
            }
            
            saved_log = await self.log_repository.create_error_log(error_log)
            
            # Отправляем уведомление админам если это критическая ошибка
            if 'critical' in error.lower() or 'failed' in action.lower():
                await self._notify_admins_about_error(error_log)
            
            logger.error(
                "Error logged",
                user_id=user_id,
                action=action,
                error=error
            )
            
            return {
                'success': True,
                'log_id': saved_log.id
            }
            
        except Exception as e:
            logger.error("Failed to log error", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_change_history(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        user_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Получает историю изменений с фильтрами.
        
        Args:
            entity_type: Фильтр по типу сущности
            entity_id: Фильтр по ID сущности
            user_id: Фильтр по ID пользователя
            start_date: Начальная дата
            end_date: Конечная дата
            limit: Максимальное количество записей
            offset: Смещение
            
        Returns:
            Dict с историей изменений
        """
        try:
            logs = await self.log_repository.get_logs(
                entity_type=entity_type,
                entity_id=entity_id,
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                offset=offset
            )
            
            total = await self.log_repository.count_logs(
                entity_type=entity_type,
                entity_id=entity_id,
                user_id=user_id,
                start_date=start_date,
                end_date=end_date
            )
            
            # Форматируем логи для отображения
            formatted_logs = []
            for log in logs:
                formatted_logs.append({
                    'id': str(log.id),
                    'timestamp': log.timestamp,
                    'user_name': log.user_name,
                    'entity_type': log.entity_type,
                    'entity_name': log.entity_name,
                    'action': log.action,
                    'changes': log.changes
                })
            
            return {
                'success': True,
                'logs': formatted_logs,
                'total': total,
                'limit': limit,
                'offset': offset
            }
            
        except Exception as e:
            logger.error("Failed to get change history", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    async def cleanup_old_logs(self, days_to_keep: int = 90) -> Dict[str, Any]:
        """
        Очищает старые логи.
        
        Args:
            days_to_keep: Сколько дней хранить логи
            
        Returns:
            Dict с результатом очистки
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            deleted_count = await self.log_repository.delete_old_logs(cutoff_date)
            
            logger.info("Old logs cleaned up", deleted_count=deleted_count, days_to_keep=days_to_keep)
            
            return {
                'success': True,
                'deleted_count': deleted_count,
                'cutoff_date': cutoff_date
            }
            
        except Exception as e:
            logger.error("Failed to cleanup old logs", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def _format_changes(self, changes: Dict[str, Dict[str, Any]]) -> str:
        """
        Форматирует изменения в читаемый вид.
        
        Args:
            changes: Словарь изменений
            
        Returns:
            Отформатированная строка
        """
        if not changes:
            return "Нет изменений"
        
        formatted = []
        
        for field, change in changes.items():
            old_value = change.get('old', '')
            new_value = change.get('new', '')
            
            # Форматируем в зависимости от типа поля
            field_name = self._get_field_display_name(field)
            
            if old_value and new_value:
                formatted.append(f"{field_name}: {old_value} → {new_value}")
            elif new_value and not old_value:
                formatted.append(f"{field_name}: добавлено '{new_value}'")
            elif old_value and not new_value:
                formatted.append(f"{field_name}: удалено '{old_value}'")
        
        return "\n".join(formatted)
    
    def _get_field_display_name(self, field: str) -> str:
        """Возвращает читаемое название поля."""
        field_names = {
            'short_name': 'Сокращенное название',
            'full_name': 'Полное название',
            'address': 'Адрес',
            'contract_number': 'Номер контракта',
            'contract_date': 'Дата контракта',
            'start_date': 'Дата начала',
            'end_date': 'Дата окончания',
            'systems': 'Системы',
            'zip_payment': 'ЗИП',
            'dispatching': 'Диспетчеризация',
            'notes': 'Примечания',
            'status': 'Статус',
            'description': 'Описание',
            'quantity': 'Количество',
            'unit': 'Единица измерения',
            'frequency': 'Частота',
            'month': 'Месяц'
        }
        
        return field_names.get(field, field)
    
    async def _send_to_archive_group(self, log_entry: LogEntry) -> None:
        """Отправляет лог изменения в архивную группу."""
        try:
            # Форматируем сообщение для архива
            message = (
                f"📝 Изменение данных\n\n"
                f"📅 {format_date(log_entry.timestamp)}\n"
                f"👤 {log_entry.user_name}\n"
                f"🎯 {self._get_entity_type_name(log_entry.entity_type)}: {log_entry.entity_name}\n"
                f"⚡ Действие: {self._get_action_name(log_entry.action)}\n\n"
            )
            
            if log_entry.changes:
                message += f"📋 Изменения:\n{log_entry.changes}\n"
            
            if log_entry.chat_id:
                message += f"\n💬 Чат: {log_entry.chat_id}"
            
            await self._send_archive_message(message)
            
        except Exception as e:
            logger.error("Failed to send log to archive", error=str(e))
    
    async def _send_admin_action_to_archive(self, change_log: ChangeLog) -> None:
        """Отправляет лог действия администратора в архив."""
        try:
            message = (
                f"👑 Действие администратора\n\n"
                f"📅 {format_date(change_log.timestamp)}\n"
                f"👤 Админ: {change_log.admin_name}\n"
                f"🎯 Цель: {change_log.target_name} ({change_log.target_type})\n"
                f"⚡ Действие: {self._get_action_name(change_log.action)}\n"
            )
            
            if change_log.details:
                message += f"\n📋 Детали:\n"
                for key, value in change_log.details.items():
                    message += f"• {key}: {value}\n"
            
            await self._send_archive_message(message)
            
        except Exception as e:
            logger.error("Failed to send admin action to archive", error=str(e))
    
    async def _send_archive_message(self, message: str) -> None:
        """Отправляет сообщение в архивную группу."""
        if not self.archive_chat_id or not self.archive_manager:
            return
        
        try:
            await self.archive_manager.send_to_archive(
                chat_id=self.archive_chat_id,
                thread_id=self.archive_thread_id,
                text=message
            )
        except Exception as e:
            logger.error("Failed to send message to archive", error=str(e))
    
    async def _notify_admins_about_error(self, error_log: Dict[str, Any]) -> None:
        """Отправляет уведомление администраторам о критической ошибке."""
        try:
            from modules.admin.admin_manager import AdminManager
            admin_manager = AdminManager(self.context)
            
            # Получаем список администраторов
            admins = await admin_manager.get_all_admins()
            
            # Формируем сообщение об ошибке
            error_message = (
                f"🚨 Критическая ошибка в системе\n\n"
                f"📅 {format_date(error_log['timestamp'])}\n"
                f"👤 Пользователь: {error_log.get('user_id', 'Неизвестно')}\n"
                f"⚡ Действие: {error_log['action']}\n"
                f"❌ Ошибка: {error_log['error']}\n"
            )
            
            if error_log.get('details'):
                error_message += f"\n📋 Детали:\n{error_log['details']}"
            
            # Отправляем каждому администратору
            for admin in admins:
                if admin.user_id:
                    try:
                        await self.context.bot.send_message(
                            chat_id=admin.user_id,
                            text=error_message
                        )
                    except Exception as e:
                        logger.error("Failed to send error notification to admin", 
                                   admin_id=admin.user_id, error=str(e))
            
        except Exception as e:
            logger.error("Failed to notify admins about error", error=str(e))
    
    def _get_entity_type_name(self, entity_type: str) -> str:
        """Возвращает читаемое название типа сущности."""
        entity_names = {
            'service_region': 'Регион обслуживания',
            'service_object': 'Объект обслуживания',
            'installation_object': 'Объект монтажа',
            'problem': 'Проблема',
            'maintenance': 'ТО',
            'equipment': 'Оборудование',
            'letter': 'Письмо',
            'document': 'Документ',
            'permit': 'Допуск',
            'journal': 'Журнал',
            'reminder': 'Напоминание',
            'project': 'Проект',
            'material': 'Материал',
            'supply': 'Поставка',
            'change': 'Изменение',
            'file': 'Файл',
            'user': 'Пользователь',
            'admin': 'Администратор'
        }
        
        return entity_names.get(entity_type, entity_type)
    
    def _get_action_name(self, action: str) -> str:
        """Возвращает читаемое название действия."""
        action_names = {
            'create': 'Создание',
            'update': 'Обновление',
            'delete': 'Удаление',
            'add': 'Добавление',
            'remove': 'Удаление',
            'edit': 'Редактирование',
            'upload': 'Загрузка',
            'download': 'Скачивание',
            'bind': 'Привязка',
            'unbind': 'Отвязка',
            'enable': 'Включение',
            'disable': 'Выключение'
        }
        
        return action_names.get(action, action)