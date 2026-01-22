"""
Модуль фильтров для проверки доступа к командам.
Реализует проверку разрешений на выполнение команд согласно ТЗ.
"""
import re
from typing import Any, Dict, Optional
from aiogram.filters import BaseFilter, CommandObject
from aiogram.types import Message, CallbackQuery

from core.context import AppContext
from modules.admin.permission_manager import PermissionManager


class CommandAccessFilter(BaseFilter):
    """
    Фильтр для проверки доступа к команде.
    
    Args:
        command_name: Имя команды (без префиксов / или !)
        check_in_group: Проверять ли доступ в группах (отдельные настройки)
    """
    
    def __init__(self, command_name: Optional[str] = None, check_in_group: bool = False):
        self.command_name = command_name
        self.check_in_group = check_in_group
    
    async def __call__(self, update: Message | CallbackQuery, context: AppContext) -> bool:
        """
        Проверяет доступ пользователя к команде.
        
        Args:
            update: Объект сообщения или callback query
            context: Контекст приложения
            
        Returns:
            bool: True если у пользователя есть доступ к команде
        """
        if isinstance(update, CallbackQuery):
            # Для callback query проверяем по данным callback
            return await self._check_callback_access(update, context)
        
        # Для сообщения проверяем команду
        return await self._check_message_access(update, context)
    
    async def _check_message_access(self, message: Message, context: AppContext) -> bool:
        """Проверяет доступ к команде в сообщении."""
        user_id = message.from_user.id
        chat_type = message.chat.type
        
        # Извлекаем команду из сообщения
        command = self.command_name or self._extract_command_from_message(message)
        if not command:
            return False
        
        # Получаем менеджер разрешений
        permission_manager: PermissionManager = context.permission_manager
        
        # Проверяем доступ в зависимости от типа чата
        if chat_type == 'private':
            return await permission_manager.check_private_command_access(user_id, command)
        else:
            if self.check_in_group:
                return await permission_manager.check_group_command_access(user_id, command)
            # Для групп проверяем общий доступ если не указано явно
            return await permission_manager.check_command_access(user_id, command, chat_type)
    
    async def _check_callback_access(self, callback: CallbackQuery, context: AppContext) -> bool:
        """Проверяет доступ для callback query."""
        user_id = callback.from_user.id
        
        # Извлекаем команду из callback данных
        # Формат: command:action:params
        callback_data = callback.data
        if not callback_data:
            return False
        
        parts = callback_data.split(':')
        if len(parts) < 2:
            return False
        
        command = parts[0]
        
        # Получаем менеджер разрешений
        permission_manager: PermissionManager = context.permission_manager
        
        # Для callback проверяем общий доступ
        return await permission_manager.check_command_access(user_id, command)
    
    def _extract_command_from_message(self, message: Message) -> Optional[str]:
        """
        Извлекает команду из сообщения.
        
        Поддерживает форматы:
        - /command
        - !command
        - /command@botname
        - !command@botname
        
        Args:
            message: Объект сообщения
            
        Returns:
            str: Имя команды или None если не найдена
        """
        text = message.text or message.caption
        if not text:
            return None
        
        # Паттерн для команд с префиксами / или !
        pattern = r'^[/!](\w+)(?:@\w+)?(?:\s|$)'
        match = re.match(pattern, text.strip())
        
        if match:
            return match.group(1).lower()
        
        # Также проверяем entities для команд
        if message.entities:
            for entity in message.entities:
                if entity.type == "bot_command":
                    command_text = text[entity.offset:entity.offset + entity.length]
                    # Убираем префикс и возможное упоминание бота
                    command = command_text.lstrip('/!').split('@')[0]
                    return command.lower()
        
        return None


class HasCommandAccess(CommandAccessFilter):
    """
    Универсальный фильтр проверки доступа к команде.
    
    Использует команду из сообщения или callback.
    """
    
    def __init__(self, check_in_group: bool = False):
        super().__init__(command_name=None, check_in_group=check_in_group)