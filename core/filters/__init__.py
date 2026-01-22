"""
Пакет фильтров для бота.
Содержит кастомные фильтры для проверки прав, состояний и типов чатов.
"""

from .admin import AdminFilter, IsMainAdmin, IsAdmin, IsService, IsInstallation
from .chat_type import ChatTypeFilter, IsPrivate, IsGroup, IsSuperGroup
from .command_access import CommandAccessFilter, HasCommandAccess
from .state_filter import StateFilter, InState, NotInState

__all__ = [
    # Админские фильтры
    'AdminFilter',
    'IsMainAdmin',
    'IsAdmin',
    'IsService', 
    'IsInstallation',
    
    # Фильтры типа чата
    'ChatTypeFilter',
    'IsPrivate',
    'IsGroup',
    'IsSuperGroup',
    
    # Фильтры доступа к командам
    'CommandAccessFilter', 
    'HasCommandAccess',
    
    # Фильтры состояний FSM
    'StateFilter',
    'InState',
    'NotInState'
]