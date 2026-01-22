"""
Пакет построителей клавиатур.
Экспортирует все builder'ы для использования в обработчиках.
"""

from .paginator import PaginatorBuilder
from .admin import AdminKeyboardBuilder
from .common import CommonKeyboardBuilder
from .dynamic import DynamicKeyboardBuilder

# Импорты для существующих модулей (предполагаемые)
from .service import ServiceKeyboardBuilder
from .installation import InstallationKeyboardBuilder

# Для обратной совместимости - создаем функции-обертки если их нет
try:
    from .admin import create_admin_permissions_keyboard, create_admin_management_keyboard
except ImportError:
    def create_admin_permissions_keyboard(*args, **kwargs):
        return AdminKeyboardBuilder.create_permissions_panel_keyboard(*args, **kwargs)
    
    def create_admin_management_keyboard(*args, **kwargs):
        return AdminKeyboardBuilder.create_admin_main_keyboard(*args, **kwargs)

try:
    from .service import (
        create_service_main_keyboard,
        create_region_keyboard,
        create_object_panel_keyboard,
        create_problems_keyboard,
        create_maintenance_keyboard
    )
except ImportError:
    def create_service_main_keyboard(*args, **kwargs):
        """Заглушка - нужно реализовать в service.py"""
        from .common import CommonKeyboardBuilder
        return CommonKeyboardBuilder.create_back_keyboard()

try:
    from .installation import (
        create_installation_main_keyboard,
        create_installation_object_panel_keyboard,
        create_projects_keyboard,
        create_materials_keyboard,
        create_montage_keyboard
    )
except ImportError:
    def create_installation_main_keyboard(*args, **kwargs):
        """Заглушка - нужно реализовать в installation.py"""
        from .common import CommonKeyboardBuilder
        return CommonKeyboardBuilder.create_back_keyboard()

try:
    from .common import (
        create_yes_no_keyboard,
        create_back_keyboard,
        create_cancel_keyboard,
        create_main_menu_keyboard
    )
except ImportError:
    def create_yes_no_keyboard(*args, **kwargs):
        return CommonKeyboardBuilder.create_yes_no_keyboard(*args, **kwargs)
    
    def create_back_keyboard(*args, **kwargs):
        return CommonKeyboardBuilder.create_back_keyboard(*args, **kwargs)
    
    def create_cancel_keyboard(*args, **kwargs):
        return CommonKeyboardBuilder.create_cancel_keyboard(*args, **kwargs)
    
    def create_main_menu_keyboard(*args, **kwargs):
        return CommonKeyboardBuilder.create_main_menu_keyboard(*args, **kwargs)

try:
    from .dynamic import (
        create_dynamic_keyboard,
        create_numbered_keyboard,
        create_emoji_keyboard
    )
except ImportError:
    def create_dynamic_keyboard(*args, **kwargs):
        """Заглушка - нужно реализовать в dynamic.py"""
        return CommonKeyboardBuilder.create_back_keyboard()

__all__ = [
    # Пагинация
    'PaginatorBuilder',
    
    # Админские клавиатуры
    'AdminKeyboardBuilder',
    'create_admin_permissions_keyboard',
    'create_admin_management_keyboard',
    
    # Обслуживание
    'ServiceKeyboardBuilder',
    'create_service_main_keyboard',
    'create_region_keyboard',
    'create_object_panel_keyboard',
    'create_problems_keyboard',
    'create_maintenance_keyboard',
    
    # Монтаж
    'InstallationKeyboardBuilder',
    'create_installation_main_keyboard',
    'create_installation_object_panel_keyboard',
    'create_projects_keyboard',
    'create_materials_keyboard',
    'create_montage_keyboard',
    
    # Общие клавиатуры
    'CommonKeyboardBuilder',
    'create_yes_no_keyboard',
    'create_back_keyboard',
    'create_cancel_keyboard',
    'create_main_menu_keyboard',
    
    # Динамические клавиатуры
    'DynamicKeyboardBuilder',
    'create_dynamic_keyboard',
    'create_numbered_keyboard',
    'create_emoji_keyboard',
]