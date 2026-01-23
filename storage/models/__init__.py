"""
Пакет моделей SQLAlchemy.
Содержит все модели базы данных для системы.
"""

from .base import Base
from .user import User, Admin, AdminPermission, UserAccess

# Временно импортируем без ServiceAddress
try:
    from .service import (
        ServiceRegion, ServiceObject, ServiceProblem,
        ServiceMaintenance, ServiceEquipment, ServiceLetter, ServiceJournal,
        ServicePermit, ServiceDocument, ServiceContractReminder
    )
    # Если ServiceAddress существует, добавьте его позже
    from .service import ServiceAddress
except ImportError:
    # Создаем заглушки для отсутствующих классов
    class ServiceRegion: pass
    class ServiceObject: pass
    class ServiceProblem: pass
    class ServiceMaintenance: pass
    class ServiceEquipment: pass
    class ServiceLetter: pass
    class ServiceJournal: pass
    class ServicePermit: pass
    class ServiceDocument: pass
    class ServiceContractReminder: pass
    class ServiceAddress: pass

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