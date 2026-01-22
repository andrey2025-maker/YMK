"""
Middleware для структурированного логирования действий в боте.
Логирует все действия пользователей, изменения данных и системные события.
Использует structlog для форматирования с контекстом.
"""

import time
from typing import Any, Awaitable, Callable, Dict
from datetime import datetime

import structlog
from aiogram import BaseMiddleware
from aiogram.types import Update, Message, CallbackQuery
from aiogram.dispatcher.middlewares.base import NextMiddlewareType

from core.context import AppContext


class LoggingMiddleware(BaseMiddleware):
    """Middleware для логирования действий пользователей и системных событий"""
    
    def __init__(self, context: AppContext):
        super().__init__()
        self.context = context
        self.logger = structlog.get_logger(__name__)
        
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        """
        Обрабатывает логирование для входящих событий.
        
        Args:
            handler: Следующий обработчик в цепочке
            event: Входящее событие (Update)
            data: Данные события
            
        Returns:
            Результат выполнения обработчика
        """
        start_time = time.time()
        
        # Получаем информацию о пользователе и чате
        user_id, username, chat_type, chat_id = self._extract_event_info(event)
        
        # Формируем базовый контекст логирования
        log_context = {
            "user_id": user_id,
            "username": username,
            "chat_type": chat_type,
            "chat_id": chat_id,
            "event_type": event.event_type,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            # Логируем входящее событие
            self._log_incoming_event(event, log_context)
            
            # Выполняем обработчик
            result = await handler(event, data)
            
            # Логируем успешное завершение
            processing_time = time.time() - start_time
            log_context["processing_time_ms"] = round(processing_time * 1000, 2)
            self.logger.info("handler_completed", **log_context)
            
            return result
            
        except Exception as e:
            # Логируем ошибку
            processing_time = time.time() - start_time
            log_context.update({
                "processing_time_ms": round(processing_time * 1000, 2),
                "error_type": type(e).__name__,
                "error_message": str(e)
            })
            self.logger.error("handler_failed", **log_context)
            
            # Прокидываем исключение дальше
            raise
    
    def _extract_event_info(self, event: Update) -> tuple:
        """
        Извлекает информацию о пользователе и чате из события.
        
        Args:
            event: Входящее событие
            
        Returns:
            Кортеж (user_id, username, chat_type, chat_id)
        """
        user_id = None
        username = None
        chat_type = None
        chat_id = None
        
        if event.message:
            user = event.message.from_user
            chat = event.message.chat
            user_id = user.id
            username = user.username
            chat_type = chat.type
            chat_id = chat.id
            
        elif event.callback_query:
            user = event.callback_query.from_user
            chat = event.callback_query.message.chat if event.callback_query.message else None
            user_id = user.id
            username = user.username
            chat_type = chat.type if chat else "callback"
            chat_id = chat.id if chat else None
            
        elif event.my_chat_member:
            user = event.my_chat_member.from_user
            chat = event.my_chat_member.chat
            user_id = user.id
            username = user.username
            chat_type = chat.type
            chat_id = chat.id
            
        elif event.chat_member:
            user = event.chat_member.from_user
            chat = event.chat_member.chat
            user_id = user.id
            username = user.username
            chat_type = chat.type
            chat_id = chat.id
            
        return user_id, username, chat_type, chat_id
    
    def _log_incoming_event(self, event: Update, context: Dict[str, Any]) -> None:
        """
        Логирует входящее событие в зависимости от его типа.
        
        Args:
            event: Входящее событие
            context: Контекст логирования
        """
        if event.message:
            self._log_message(event.message, context)
        elif event.callback_query:
            self._log_callback_query(event.callback_query, context)
        elif event.my_chat_member:
            self._log_chat_member_update(event.my_chat_member, context)
        elif event.chat_member:
            self._log_chat_member_update(event.chat_member, context)
        else:
            self.logger.info("unknown_event", **context)
    
    def _log_message(self, message: Message, context: Dict[str, Any]) -> None:
        """
        Логирует входящее сообщение.
        
        Args:
            message: Объект сообщения
            context: Контекст логирования
        """
        log_data = context.copy()
        
        if message.text:
            log_data["message_type"] = "text"
            log_data["content"] = message.text[:100] + "..." if len(message.text) > 100 else message.text
            log_data["has_command"] = message.text.startswith('!')
            
        elif message.document:
            log_data["message_type"] = "document"
            log_data["file_name"] = message.document.file_name
            log_data["file_size"] = message.document.file_size
            
        elif message.photo:
            log_data["message_type"] = "photo"
            log_data["photo_count"] = len(message.photo)
            
        elif message.video:
            log_data["message_type"] = "video"
            log_data["file_size"] = message.video.file_size
            
        else:
            log_data["message_type"] = "other_media"
        
        self.logger.info("message_received", **log_data)
    
    def _log_callback_query(self, callback_query: CallbackQuery, context: Dict[str, Any]) -> None:
        """
        Логирует callback query.
        
        Args:
            callback_query: Объект callback query
            context: Контекст логирования
        """
        log_data = context.copy()
        log_data["callback_data"] = callback_query.data
        
        self.logger.info("callback_received", **log_data)
    
    def _log_chat_member_update(self, chat_member_update: Any, context: Dict[str, Any]) -> None:
        """
        Логирует обновление статуса участника чата.
        
        Args:
            chat_member_update: Объект обновления статуса
            context: Контекст логирования
        """
        log_data = context.copy()
        log_data["old_status"] = chat_member_update.old_chat_member.status
        log_data["new_status"] = chat_member_update.new_chat_member.status
        
        self.logger.info("chat_member_updated", **log_data)
    
    async def log_admin_action(
        self,
        admin_id: int,
        action: str,
        target_type: str = None,
        target_id: str = None,
        details: str = None,
        changes: Dict[str, Any] = None
    ) -> None:
        """
        Логирует действия администратора.
        Используется для логирования изменений согласно ТЗ.
        
        Args:
            admin_id: ID администратора
            action: Тип действия (add, remove, update, etc.)
            target_type: Тип цели (admin, region, object, etc.)
            target_id: ID цели
            details: Детали действия
            changes: Словарь изменений в формате {'было': 'стало'}
        """
        log_context = {
            "admin_id": admin_id,
            "action_type": f"admin_{action}",
            "target_type": target_type,
            "target_id": target_id,
            "timestamp": datetime.now().isoformat(),
            "details": details
        }
        
        if changes:
            log_context["changes"] = changes
        
        self.logger.info("admin_action", **log_context)
    
    async def log_data_change(
        self,
        user_id: int,
        module: str,
        object_type: str,
        object_id: str,
        action: str,
        old_data: Any = None,
        new_data: Any = None
    ) -> None:
        """
        Логирует изменения данных согласно ТЗ.
        Все изменения сохраняются в Telegram группу, указанную главным админом.
        
        Args:
            user_id: ID пользователя, совершившего изменение
            module: Модуль (service, installation, admin, etc.)
            object_type: Тип объекта (region, object, problem, etc.)
            object_id: ID объекта
            action: Действие (create, update, delete)
            old_data: Старые данные (для update/delete)
            new_data: Новые данные (для create/update)
        """
        log_context = {
            "user_id": user_id,
            "module": module,
            "object_type": object_type,
            "object_id": object_id,
            "action": action,
            "timestamp": datetime.now().isoformat()
        }
        
        # Формируем сообщение об изменении для отправки в Telegram
        if action == "update" and old_data and new_data:
            changes = self._format_changes(old_data, new_data)
            log_context["changes"] = changes
            
            # Отправляем в группу для логов (если настроена)
            await self._send_to_log_channel(user_id, module, object_type, changes)
        
        self.logger.info("data_changed", **log_context)
    
    def _format_changes(self, old_data: Any, new_data: Any) -> Dict[str, str]:
        """
        Форматирует изменения в читаемый вид.
        
        Args:
            old_data: Старые данные
            new_data: Новые данные
            
        Returns:
            Словарь с форматированными изменениями
        """
        changes = {}
        
        if isinstance(old_data, dict) and isinstance(new_data, dict):
            all_keys = set(old_data.keys()) | set(new_data.keys())
            for key in all_keys:
                old_value = old_data.get(key)
                new_value = new_data.get(key)
                
                if old_value != new_value:
                    changes[key] = {
                        "old": str(old_value) if old_value is not None else "None",
                        "new": str(new_value) if new_value is not None else "None"
                    }
        
        return changes
    
    async def _send_to_log_channel(
        self,
        user_id: int,
        module: str,
        object_type: str,
        changes: Dict[str, Any]
    ) -> None:
        """
        Отправляет информацию об изменениях в Telegram группу для логов.
        
        Args:
            user_id: ID пользователя
            module: Модуль
            object_type: Тип объекта
            changes: Изменения
        """
        # Получаем настройки логов из контекста
        log_channel_id = await self.context.get_log_channel_id()
        
        if not log_channel_id:
            return
        
        # Форматируем сообщение
        message = self._format_log_message(user_id, module, object_type, changes)
        
        # Отправляем сообщение (реализация зависит от вашего бота)
        # await self.context.bot.send_message(chat_id=log_channel_id, text=message)
        
        # Временно логируем вместо отправки
        self.logger.info("log_channel_message", 
                        log_channel_id=log_channel_id,
                        message=message)
    
    def _format_log_message(
        self,
        user_id: int,
        module: str,
        object_type: str,
        changes: Dict[str, Any]
    ) -> str:
        """
        Форматирует сообщение для логов в Telegram.
        
        Args:
            user_id: ID пользователя
            module: Модуль
            object_type: Тип объекта
            changes: Изменения
            
        Returns:
            Форматированное сообщение
        """
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
        
        message_lines = [
            f"📅 {timestamp}",
            f"👤 Пользователь: {user_id}",
            f"📁 Модуль: {module}",
            f"🎯 Объект: {object_type}",
            "",
            "📝 Изменения:"
        ]
        
        for field, change_data in changes.items():
            message_lines.append(f"• {field}:")
            message_lines.append(f"  Было: {change_data['old']}")
            message_lines.append(f"  Стало: {change_data['new']}")
        
        return "\n".join(message_lines)


def setup_logging_middleware(dispatcher, context: AppContext) -> None:
    """
    Настраивает middleware для логирования.
    
    Args:
        dispatcher: Диспетчер aiogram
        context: Контекст приложения
    """
    logging_middleware = LoggingMiddleware(context)
    dispatcher.update.outer_middleware(logging_middleware)