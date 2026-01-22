"""
Пакет состояний FSM (Finite State Machine).
Содержит все состояния для различных сценариев ввода данных.
"""

from .states import BaseStates, CommonStates
from .admin_states import AdminStates
from .service_states import ServiceStates
from .installation_states import InstallationStates
from .file_states import FileStates
from .reminder_states import ReminderStates


# Экспорт для удобного импорта из других модулей
__all__ = [
    'BaseStates',
    'CommonStates',
    'AdminStates',
    'ServiceStates',
    'InstallationStates',
    'FileStates',
    'ReminderStates',
]