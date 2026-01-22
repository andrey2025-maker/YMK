"""
Пакет клавиатур бота.
Содержит все клавиатуры и построители для интерфейса.
"""

from .builders import (
    # Пагинация
    Paginator,
    paginator,
    
    # Админские
    AdminKeyboardBuilder,
    create_admin_permissions_keyboard,
    create_admin_management_keyboard,
    
    # Обслуживание
    ServiceKeyboardBuilder,
    create_service_main_keyboard,
    create_region_keyboard,
    create_object_panel_keyboard,
    create_problems_keyboard,
    create_maintenance_keyboard,
    
    # Монтаж
    InstallationKeyboardBuilder,
    create_installation_main_keyboard,
    create_installation_object_panel_keyboard,
    create_projects_keyboard,
    create_materials_keyboard,
    create_montage_keyboard,
    
    # Общие
    CommonKeyboardBuilder,
    create_yes_no_keyboard,
    create_back_keyboard,
    create_cancel_keyboard,
    create_main_menu_keyboard,
    
    # Динамические
    DynamicKeyboardBuilder,
    create_dynamic_keyboard,
    create_numbered_keyboard,
    create_emoji_keyboard,
)

# Импорты для inline клавиатур
from .inline import (
    # Импорты будут добавлены при создании inline/
    pass
)

__all__ = [
    # Builders
    'Paginator',
    'paginator',
    
    'AdminKeyboardBuilder',
    'create_admin_permissions_keyboard',
    'create_admin_management_keyboard',
    
    'ServiceKeyboardBuilder',
    'create_service_main_keyboard',
    'create_region_keyboard',
    'create_object_panel_keyboard',
    'create_problems_keyboard',
    'create_maintenance_keyboard',
    
    'InstallationKeyboardBuilder',
    'create_installation_main_keyboard',
    'create_installation_object_panel_keyboard',
    'create_projects_keyboard',
    'create_materials_keyboard',
    'create_montage_keyboard',
    
    'CommonKeyboardBuilder',
    'create_yes_no_keyboard',
    'create_back_keyboard',
    'create_cancel_keyboard',
    'create_main_menu_keyboard',
    
    'DynamicKeyboardBuilder',
    'create_dynamic_keyboard',
    'create_numbered_keyboard',
    'create_emoji_keyboard',
    
    # Inline клавиатуры (будут добавлены)
]