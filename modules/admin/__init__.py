"""
Пакет администрирования системы.
Содержит менеджеры для управления админами, правами, логированием и экспортом.
"""

from .admin_manager import AdminManager
from .permission_manager import PermissionManager
from .log_manager import LogManager
from .export_manager import ExportManager


class AdminModule:
    """Фасад для модуля администрирования."""
    
    def __init__(self, context):
        self.context = context
        self.admin_manager = AdminManager(context)
        self.permission_manager = PermissionManager(context)
        self.log_manager = LogManager(context)
        self.export_manager = ExportManager(context)
    
    async def initialize(self):
        """Инициализирует все компоненты модуля администрирования."""
        await self.admin_manager.initialize()
        await self.permission_manager.initialize()
        await self.log_manager.initialize()
        await self.export_manager.initialize()
        
        return self


__all__ = [
    'AdminModule',
    'AdminManager',
    'PermissionManager',
    'LogManager',
    'ExportManager'
]