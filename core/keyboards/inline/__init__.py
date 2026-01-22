"""
Пакет inline-клавиатур для бота.
Содержит специализированные inline-клавиатуры для различных модулей.
"""

from .admin import AdminInlineKeyboard
from .service import ServiceInlineKeyboard
from .installation import InstallationInlineKeyboard
from .navigation import NavigationInlineKeyboard

__all__ = [
    'AdminInlineKeyboard',
    'ServiceInlineKeyboard',
    'InstallationInlineKeyboard',
    'NavigationInlineKeyboard'
]