"""
Модуль фильтров для проверки административных прав.
Реализует проверку ролей админов согласно ТЗ.
"""
from typing import Any, Dict, Optional
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from core.context import AppContext
from modules.admin.admin_manager import AdminManager


class AdminFilter(BaseFilter):
    """
    Базовый фильтр для проверки роли администратора.
    
    Args:
        required_role: Требуемая роль ('main_admin', 'admin', 'service', 'installation')
        or_higher: Если True, то проверяет указанную роль или выше
    """
    
    def __init__(self, required_role: str, or_higher: bool = False):
        self.required_role = required_role
        self.or_higher = or_higher
        self.role_hierarchy = {
            'main_admin': 4,
            'admin': 3,
            'service': 2,
            'installation': 1
        }
    
    async def __call__(self, update: Message | CallbackQuery, context: AppContext) -> bool:
        """
        Проверяет, имеет ли пользователь требуемую роль.
        
        Args:
            update: Объект сообщения или callback query
            context: Контекст приложения
            
        Returns:
            bool: True если пользователь имеет требуемую роль
        """
        user_id = update.from_user.id
        
        # Получаем менеджер админов из контекста
        admin_manager: AdminManager = context.admin_manager
        
        # Получаем роль пользователя
        user_role = await admin_manager.get_user_role(user_id)
        
        if not user_role:
            return False
        
        # Если проверяем конкретную роль
        if not self.or_higher:
            return user_role == self.required_role
        
        # Если проверяем роль или выше
        required_level = self.role_hierarchy.get(self.required_role, 0)
        user_level = self.role_hierarchy.get(user_role, 0)
        
        return user_level >= required_level


class IsMainAdmin(AdminFilter):
    """Фильтр для проверки, является ли пользователь главным админом."""
    
    def __init__(self):
        super().__init__(required_role='main_admin')


class IsAdmin(AdminFilter):
    """Фильтр для проверки, является ли пользователь админом или выше."""
    
    def __init__(self, or_higher: bool = True):
        super().__init__(required_role='admin', or_higher=or_higher)


class IsService(AdminFilter):
    """Фильтр для проверки, является ли пользователь обслуживающим или выше."""
    
    def __init__(self, or_higher: bool = True):
        super().__init__(required_role='service', or_higher=or_higher)


class IsInstallation(AdminFilter):
    """Фильтр для проверки, является ли пользователь монтажником или выше."""
    
    def __init__(self, or_higher: bool = True):
        super().__init__(required_role='installation', or_higher=or_higher)