"""
Модуль групп - управление привязкой объектов к группам и контроль доступа.
"""

from .bind_manager import GroupBindManager
from .access_manager import GroupAccessManager


class GroupModule:
    """Модуль групп."""
    
    def __init__(self, context):
        self.context = context
        self.bind_manager = GroupBindManager(context)
        self.access_manager = GroupAccessManager(context)
    
    async def initialize(self):
        """Инициализация модуля групп."""
        return self


# Экспорт для удобного импорта из других модулей
__all__ = [
    'GroupModule',
    'GroupBindManager',
    'GroupAccessManager',
]