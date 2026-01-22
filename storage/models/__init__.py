"""
Пакет моделей SQLAlchemy.
Содержит все модели базы данных для системы.
"""

from .base import Base
from .user import User, Admin, AdminPermission, UserAccess
from .service import (
    ServiceRegion, ServiceObject, ServiceAddress, ServiceProblem,
    ServiceMaintenance, ServiceEquipment, ServiceLetter, ServiceJournal,
    ServicePermit, ServiceDocument, ServiceContractReminder
)
from .installation import (
    InstallationObject, InstallationAddress, InstallationProject,
    InstallationMaterial, InstallationMaterialSection, InstallationMaterialQuantity,
    InstallationMontage, InstallationSupply, InstallationChange,
    InstallationDocument, InstallationGroupBinding
)
from .file import TelegramFile, FileAttachment
from .group import GroupBinding, GroupPermission, GroupAdmin
from .reminder import Reminder, RecurringReminder, Notification
from .log import LogEntry, ChangeLog, ErrorLog


# Экспорт всех моделей для удобного импорта
__all__ = [
    # Базовые
    'Base',
    
    # Пользователи и доступ
    'User', 'Admin', 'AdminPermission', 'UserAccess',
    
    # Обслуживание
    'ServiceRegion', 'ServiceObject', 'ServiceAddress', 'ServiceProblem',
    'ServiceMaintenance', 'ServiceEquipment', 'ServiceLetter', 'ServiceJournal',
    'ServicePermit', 'ServiceDocument', 'ServiceContractReminder',
    
    # Монтаж
    'InstallationObject', 'InstallationAddress', 'InstallationProject',
    'InstallationMaterial', 'InstallationMaterialSection', 'InstallationMaterialQuantity',
    'InstallationMontage', 'InstallationSupply', 'InstallationChange',
    'InstallationDocument', 'InstallationGroupBinding',
    
    # Файлы
    'TelegramFile', 'FileAttachment',
    
    # Группы
    'GroupBinding', 'GroupPermission', 'GroupAdmin',
    
    # Напоминания
    'Reminder', 'RecurringReminder', 'Notification',
    
    # Логи
    'LogEntry', 'ChangeLog', 'ErrorLog',
]