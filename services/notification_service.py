"""
Сервис для отправки уведомлений в Telegram.
Реализует отправку сообщений, напоминаний и системных уведомлений.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
from enum import Enum

from aiogram import Bot
from aiogram.types import Message, InlineKeyboardMarkup, ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter

from utils.date_utils import format_date
from config import settings

logger = logging.getLogger(__name__)


class NotificationType(Enum):
    """Типы уведомлений."""
    REMINDER = "напоминание"
    CHANGE = "изменение"
    ERROR = "ошибка"
    INFO = "информация"
    WARNING = "предупреждение"
    SUCCESS = "успех"


class NotificationService:
    """Сервис для отправки уведомлений в Telegram."""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self._queue = asyncio.Queue()
        self._is_running = False
        
    async def start(self):
        """Запуск обработчика очереди уведомлений."""
        if not self._is_running:
            self._is_running = True
            asyncio.create_task(self._process_queue())
            logger.info("Notification service started")
    
    async def stop(self):
        """Остановка обработчика очереди уведомлений."""
        self._is_running = False
        logger.info("Notification service stopped")
    
    async def _process_queue(self):
        """Обработка очереди уведомлений."""
        while self._is_running:
            try:
                notification = await self._queue.get()
                await self._send_notification(notification)
                self._queue.task_done()
            except Exception as e:
                logger.error(f"Error processing notification: {e}")
    
    async def send_private_message(
        self,
        user_id: int,
        text: str,
        notification_type: NotificationType = NotificationType.INFO,
        keyboard: Optional[InlineKeyboardMarkup] = None,
        parse_mode: str = ParseMode.HTML,
        disable_notification: bool = False
    ) -> bool:
        """
        Отправка сообщения в личные сообщения.
        
        Args:
            user_id: ID пользователя в Telegram
            text: Текст сообщения
            notification_type: Тип уведомления
            keyboard: Inline клавиатура
            parse_mode: Режим парсинга (HTML/Markdown)
            disable_notification: Отключить звук уведомления
            
        Returns:
            True если сообщение отправлено успешно
        """
        try:
            formatted_text = self._format_message(text, notification_type)
            
            await self.bot.send_message(
                chat_id=user_id,
                text=formatted_text,
                reply_markup=keyboard,
                parse_mode=parse_mode,
                disable_notification=disable_notification
            )
            logger.info(f"Notification sent to user {user_id}: {notification_type.value}")
            return True
            
        except TelegramRetryAfter as e:
            logger.warning(f"Rate limit exceeded for user {user_id}, retrying in {e.retry_after} seconds")
            await asyncio.sleep(e.retry_after)
            return await self.send_private_message(
                user_id, text, notification_type, keyboard, parse_mode, disable_notification
            )
            
        except TelegramAPIError as e:
            logger.error(f"Failed to send notification to user {user_id}: {e}")
            return False
    
    async def send_group_message(
        self,
        chat_id: int,
        text: str,
        notification_type: NotificationType = NotificationType.INFO,
        keyboard: Optional[InlineKeyboardMarkup] = None,
        parse_mode: str = ParseMode.HTML,
        disable_notification: bool = False,
        message_thread_id: Optional[int] = None
    ) -> bool:
        """
        Отправка сообщения в группу/канал.
        
        Args:
            chat_id: ID чата/канала
            text: Текст сообщения
            notification_type: Тип уведомления
            keyboard: Inline клавиатура
            parse_mode: Режим парсинга
            disable_notification: Отключить звук уведомления
            message_thread_id: ID темы в форуме
            
        Returns:
            True если сообщение отправлено успешно
        """
        try:
            formatted_text = self._format_message(text, notification_type)
            
            await self.bot.send_message(
                chat_id=chat_id,
                text=formatted_text,
                reply_markup=keyboard,
                parse_mode=parse_mode,
                disable_notification=disable_notification,
                message_thread_id=message_thread_id
            )
            logger.info(f"Notification sent to chat {chat_id}: {notification_type.value}")
            return True
            
        except TelegramRetryAfter as e:
            logger.warning(f"Rate limit exceeded for chat {chat_id}, retrying in {e.retry_after} seconds")
            await asyncio.sleep(e.retry_after)
            return await self.send_group_message(
                chat_id, text, notification_type, keyboard, parse_mode, disable_notification, message_thread_id
            )
            
        except TelegramAPIError as e:
            logger.error(f"Failed to send notification to chat {chat_id}: {e}")
            return False
    
    async def send_change_notification(
        self,
        user_id: int,
        entity_type: str,
        entity_name: str,
        changes: Dict[str, Dict[str, str]],
        chat_id: Optional[int] = None,
        message_thread_id: Optional[int] = None
    ) -> bool:
        """
        Отправка уведомления об изменении данных.
        
        Args:
            user_id: ID пользователя, внесшего изменения
            entity_type: Тип сущности (объект, проблема, ТО и т.д.)
            entity_name: Название сущности
            changes: Словарь изменений {поле: {"было": "", "стало": ""}}
            chat_id: ID чата для отправки (если None - в ЛС)
            message_thread_id: ID темы
            
        Returns:
            True если уведомление отправлено
        """
        try:
            # Получаем информацию о пользователе
            user_info = await self._get_user_info(user_id)
            
            # Формируем текст изменения
            text = self._format_change_message(user_info, entity_type, entity_name, changes)
            
            # Определяем тип уведомления
            notification_type = NotificationType.CHANGE
            
            if chat_id:
                return await self.send_group_message(
                    chat_id=chat_id,
                    text=text,
                    notification_type=notification_type,
                    message_thread_id=message_thread_id
                )
            else:
                return await self.send_private_message(
                    user_id=user_id,
                    text=text,
                    notification_type=notification_type
                )
                
        except Exception as e:
            logger.error(f"Failed to send change notification: {e}")
            return False
    
    async def send_reminder_notification(
        self,
        user_id: int,
        reminder_type: str,
        title: str,
        description: str,
        due_date: datetime,
        entity_id: Optional[str] = None,
        entity_type: Optional[str] = None
    ) -> bool:
        """
        Отправка уведомления о напоминании.
        
        Args:
            user_id: ID пользователя
            reminder_type: Тип напоминания (контракт, ТО, поставка и т.д.)
            title: Заголовок напоминания
            description: Описание
            due_date: Дата выполнения
            entity_id: ID связанной сущности
            entity_type: Тип связанной сущности
            
        Returns:
            True если уведомление отправлено
        """
        try:
            formatted_date = format_date(due_date)
            
            # Формируем текст напоминания
            text = self._format_reminder_message(
                reminder_type, title, description, formatted_date, entity_id, entity_type
            )
            
            # Определяем тип уведомления
            notification_type = NotificationType.REMINDER
            
            return await self.send_private_message(
                user_id=user_id,
                text=text,
                notification_type=notification_type
            )
            
        except Exception as e:
            logger.error(f"Failed to send reminder notification: {e}")
            return False
    
    async def broadcast_to_admins(
        self,
        text: str,
        notification_type: NotificationType = NotificationType.INFO,
        exclude_user_ids: Optional[List[int]] = None
    ) -> Dict[int, bool]:
        """
        Рассылка сообщения всем администраторам.
        
        Args:
            text: Текст сообщения
            notification_type: Тип уведомления
            exclude_user_ids: Список ID пользователей для исключения
            
        Returns:
            Словарь {user_id: success}
        """
        try:
            # Здесь должен быть вызов к базе данных для получения списка админов
            # Временно возвращаем пустой словарь
            admin_ids = []  # TODO: Получить из БД
            
            results = {}
            for admin_id in admin_ids:
                if exclude_user_ids and admin_id in exclude_user_ids:
                    continue
                    
                success = await self.send_private_message(
                    user_id=admin_id,
                    text=text,
                    notification_type=notification_type
                )
                results[admin_id] = success
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to broadcast to admins: {e}")
            return {}
    
    async def queue_notification(
        self,
        user_id: int,
        text: str,
        notification_type: NotificationType = NotificationType.INFO,
        delay_seconds: int = 0
    ):
        """
        Добавление уведомления в очередь.
        
        Args:
            user_id: ID пользователя
            text: Текст сообщения
            notification_type: Тип уведомления
            delay_seconds: Задержка перед отправкой
        """
        notification = {
            "user_id": user_id,
            "text": text,
            "notification_type": notification_type,
            "delay_seconds": delay_seconds,
            "timestamp": datetime.utcnow()
        }
        
        await self._queue.put(notification)
        logger.debug(f"Notification queued for user {user_id}")
    
    def _format_message(self, text: str, notification_type: NotificationType) -> str:
        """
        Форматирование сообщения в зависимости от типа.
        
        Args:
            text: Исходный текст
            notification_type: Тип уведомления
            
        Returns:
            Отформатированный текст
        """
        emoji_map = {
            NotificationType.REMINDER: "⏰",
            NotificationType.CHANGE: "📝",
            NotificationType.ERROR: "❌",
            NotificationType.INFO: "ℹ️",
            NotificationType.WARNING: "⚠️",
            NotificationType.SUCCESS: "✅"
        }
        
        emoji = emoji_map.get(notification_type, "📨")
        formatted_text = f"{emoji} <b>{notification_type.value.upper()}</b>\n\n{text}"
        
        # Добавляем дату и время
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M")
        formatted_text += f"\n\n📅 <i>{current_time}</i>"
        
        return formatted_text
    
    def _format_change_message(
        self,
        user_info: Dict[str, Any],
        entity_type: str,
        entity_name: str,
        changes: Dict[str, Dict[str, str]]
    ) -> str:
        """
        Форматирование сообщения об изменении.
        
        Args:
            user_info: Информация о пользователе
            entity_type: Тип сущности
            entity_name: Название сущности
            changes: Изменения
            
        Returns:
            Отформатированный текст
        """
        username = user_info.get("username", "Неизвестный пользователь")
        
        text = f"📝 <b>Изменение данных</b>\n\n"
        text += f"👤 <b>Пользователь:</b> @{username}\n"
        text += f"📋 <b>Тип:</b> {entity_type}\n"
        text += f"🏷 <b>Название:</b> {entity_name}\n\n"
        
        if changes:
            text += "<b>Изменения:</b>\n"
            for field, change in changes.items():
                if change.get("было") and change.get("стало"):
                    text += f"• <b>{field}:</b>\n"
                    text += f"  Было: {change['было']}\n"
                    text += f"  Стало: {change['стало']}\n\n"
        
        return text
    
    def _format_reminder_message(
        self,
        reminder_type: str,
        title: str,
        description: str,
        due_date: str,
        entity_id: Optional[str] = None,
        entity_type: Optional[str] = None
    ) -> str:
        """
        Форматирование сообщения напоминания.
        
        Args:
            reminder_type: Тип напоминания
            title: Заголовок
            description: Описание
            due_date: Дата выполнения
            entity_id: ID сущности
            entity_type: Тип сущности
            
        Returns:
            Отформатированный текст
        """
        text = f"⏰ <b>НАПОМИНАНИЕ: {reminder_type.upper()}</b>\n\n"
        text += f"<b>{title}</b>\n\n"
        
        if description:
            text += f"{description}\n\n"
        
        text += f"📅 <b>Срок выполнения:</b> {due_date}\n"
        
        if entity_type:
            text += f"📋 <b>Тип объекта:</b> {entity_type}\n"
        
        if entity_id:
            text += f"🆔 <b>ID объекта:</b> {entity_id}\n"
        
        return text
    
    async def _get_user_info(self, user_id: int) -> Dict[str, Any]:
        """
        Получение информации о пользователе.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Словарь с информацией о пользователе
        """
        try:
            # Здесь должен быть вызов к базе данных или API Telegram
            # Временно возвращаем базовую информацию
            return {
                "id": user_id,
                "username": f"user_{user_id}",
                "first_name": "Пользователь",
                "last_name": ""
            }
        except Exception as e:
            logger.error(f"Failed to get user info for {user_id}: {e}")
            return {"id": user_id, "username": "Неизвестный пользователь"}
    
    async def _send_notification(self, notification: Dict[str, Any]):
        """
        Отправка уведомления из очереди.
        
        Args:
            notification: Данные уведомления
        """
        try:
            # Задержка если указана
            if notification.get("delay_seconds", 0) > 0:
                await asyncio.sleep(notification["delay_seconds"])
            
            await self.send_private_message(
                user_id=notification["user_id"],
                text=notification["text"],
                notification_type=notification["notification_type"]
            )
            
        except Exception as e:
            logger.error(f"Failed to send queued notification: {e}")