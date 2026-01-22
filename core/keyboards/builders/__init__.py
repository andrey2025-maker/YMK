"""
Пакет построителей клавиатур.
Экспортирует все builder'ы для использования в обработчиках.
"""

from .paginator import Paginator, paginator
from .admin import (
    AdminKeyboardBuilder,
    create_admin_permissions_keyboard,
    create_admin_management_keyboard
)
from .service import (
    ServiceKeyboardBuilder,
    create_service_main_keyboard,
    create_region_keyboard,
    create_object_panel_keyboard,
    create_problems_keyboard,
    create_maintenance_keyboard
)
from .installation import (
    InstallationKeyboardBuilder,
    create_installation_main_keyboard,
    create_installation_object_panel_keyboard,
    create_projects_keyboard,
    create_materials_keyboard,
    create_montage_keyboard
)
from .common import (
    CommonKeyboardBuilder,
    create_yes_no_keyboard,
    create_back_keyboard,
    create_cancel_keyboard,
    create_main_menu_keyboard
)
from .dynamic import (
    DynamicKeyboardBuilder,
    create_dynamic_keyboard,
    create_numbered_keyboard,
    create_emoji_keyboard
)

__all__ = [
    # Пагинация
    'Paginator',
    'paginator',
    
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