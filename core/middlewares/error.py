"""
Middleware для централизованной обработки ошибок.
Ловит все исключения и отправляет уведомления администраторам.
"""

import traceback
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Update, ErrorEvent
from aiogram.dispatcher.middlewares.base import NextMiddlewareType

from core.context import AppContext
from structlog import get_logger


class ErrorMiddleware(BaseMiddleware):
    """Middleware для обработки ошибок во всех обработчиках"""
    
    def __init__(self, context: AppContext = None):
        super().__init__()
        self.context = context
        self.logger = get_logger(__name__)
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        """
        Обертывает обработчик в try-except для перехвата ошибок.
        
        Args:
            handler: Обработчик события
            event: Событие Telegram
            data: Данные события
            
        Returns:
            Результат обработчика или None при ошибке
        """
        try:
            return await handler(event, data)
        except Exception as e:
            await self.handle_error(e, event, data)
            return None
    
    async def handle_error(self, error: Exception, event: Update, data: Dict[str, Any]) -> None:
        """
        Обрабатывает возникшую ошибку.
        
        Args:
            error: Исключение
            event: Событие, вызвавшее ошибку
            data: Данные события
        """
        # Извлекаем информацию о событии
        user_info = self._extract_user_info(event)
        error_info = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "user_info": user_info,
            "event_type": event.event_type,
        }
        
        # Логируем ошибку
        self.logger.error(
            "handler_error",
            **error_info
        )
        
        # Отправляем уведомление администраторам (если есть контекст)
        if self.context and hasattr(self.context, 'bot'):
            await self._notify_admins(error_info)
    
    def _extract_user_info(self, event: Update) -> Dict[str, Any]:
        """
        Извлекает информацию о пользователе из события.
        
        Args:
            event: Событие Telegram
            
        Returns:
            Словарь с информацией о пользователе
        """
        user_info = {
            "user_id": None,
            "username": None,
            "chat_id": None,
            "chat_type": None,
        }
        
        try:
            if event.message:
                user = event.message.from_user
                chat = event.message.chat
                user_info.update({
                    "user_id": user.id,
                    "username": user.username,
                    "chat_id": chat.id,
                    "chat_type": chat.type,
                })
            elif event.callback_query:
                user = event.callback_query.from_user
                message = event.callback_query.message
                user_info.update({
                    "user_id": user.id,
                    "username": user.username,
                    "chat_id": message.chat.id if message else None,
                    "chat_type": message.chat.type if message else "callback",
                })
        except Exception:
            pass
            
        return user_info
    
    async def _notify_admins(self, error_info: Dict[str, Any]) -> None:
        """
        Отправляет уведомление об ошибке администраторам.
        
        Args:
            error_info: Информация об ошибке
        """
        try:
            # Получаем список главных админов из БД
            if hasattr(self.context, 'db'):
                admins = await self.context.db.get_main_admins()
                
                for admin in admins:
                    try:
                        message = self._format_error_message(error_info)
                        await self.context.bot.send_message(
                            chat_id=admin.user_id,
                            text=message,
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass
        except Exception as e:
            self.logger.error("failed_to_notify_admins", error=str(e))
    
    def _format_error_message(self, error_info: Dict[str, Any]) -> str:
        """
        Форматирует сообщение об ошибке для отправки админам.
        
        Args:
            error_info: Информация об ошибке
            
        Returns:
            Форматированное сообщение
        """
        user = error_info["user_info"]
        
        message_lines = [
            "🚨 <b>Произошла ошибка в боте!</b>",
            "",
            f"<b>Тип ошибки:</b> {error_info['error_type']}",
            f"<b>Сообщение:</b> {error_info['error_message'][:200]}",
            "",
            "<b>Информация о пользователе:</b>",
            f"• ID: {user['user_id'] or 'Неизвестно'}",
            f"• Username: @{user['username'] or 'Неизвестно'}",
            f"• Чат: {user['chat_type'] or 'Неизвестно'}",
            "",
            "<i>Подробности в логах бота</i>"
        ]
        
        return "\n".join(message_lines)
    
    async def on_error_event(self, event: ErrorEvent) -> bool:
        """
        Обрабатывает события ошибок от aiogram 3.x.
        
        Args:
            event: Событие ошибки
            
        Returns:
            True если ошибка обработана
        """
        error_info = {
            "error_type": type(event.exception).__name__,
            "error_message": str(event.exception),
            "traceback": "".join(traceback.format_exception(
                type(event.exception),
                event.exception,
                event.exception.__traceback__
            )),
            "update_type": event.update.event_type if event.update else "unknown",
        }
        
        self.logger.error(
            "aiogram_error_event",
            **error_info
        )
        
        return True