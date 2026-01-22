"""
Модуль фильтров для проверки типа чата.
Проверяет, отправлено ли сообщение в ЛС, группе или супергруппе.
"""
from typing import Any, Dict, Optional
from aiogram.filters import BaseFilter
from aiogram.types import Message, Chat


class ChatTypeFilter(BaseFilter):
    """
    Базовый фильтр для проверки типа чата.
    
    Args:
        chat_type: Тип чата ('private', 'group', 'supergroup', 'channel')
    """
    
    def __init__(self, chat_type: str | list[str]):
        if isinstance(chat_type, str):
            self.chat_types = [chat_type]
        else:
            self.chat_types = chat_type
    
    async def __call__(self, message: Message) -> bool:
        """
        Проверяет тип чата.
        
        Args:
            message: Объект сообщения
            
        Returns:
            bool: True если чат соответствует указанному типу
        """
        return message.chat.type in self.chat_types


class IsPrivate(ChatTypeFilter):
    """Фильтр для проверки, что сообщение отправлено в личных сообщениях."""
    
    def __init__(self):
        super().__init__(chat_type='private')


class IsGroup(ChatTypeFilter):
    """Фильтр для проверки, что сообщение отправлено в группе."""
    
    def __init__(self):
        super().__init__(chat_type='group')


class IsSuperGroup(ChatTypeFilter):
    """Фильтр для проверки, что сообщение отправлено в супергруппе."""
    
    def __init__(self):
        super().__init__(chat_type='supergroup')


class IsGroupOrSuperGroup(ChatTypeFilter):
    """Фильтр для проверки, что сообщение отправлено в группе или супергруппе."""
    
    def __init__(self):
        super().__init__(chat_type=['group', 'supergroup'])


class IsChannel(ChatTypeFilter):
    """Фильтр для проверки, что сообщение отправлено в канале."""
    
    def __init__(self):
        super().__init__(chat_type='channel')