"""
Модуль для построения клавиатур админ-панели.
Реализует интерфейсы для управления админами, разрешениями и настройками.
"""
from typing import Dict, List, Optional, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from models.user import Admin, AdminPermission


class AdminKeyboardBuilder:
    """Построитель клавиатур для админ-панели."""
    
    @staticmethod
    def create_admin_main_keyboard(user_id: int, is_main_admin: bool = False) -> InlineKeyboardMarkup:
        """
        Создает главную клавиатуру админа.
        
        Args:
            user_id: ID пользователя
            is_main_admin: Является ли главным админом
            
        Returns:
            InlineKeyboardMarkup с основными командами админа
        """
        builder = InlineKeyboardBuilder()
        
        if is_main_admin:
            builder.button(text="👑 Добавить главного админа", callback_data="admin_add_main")
        
        builder.button(text="👔 Добавить админа", callback_data="admin_add_admin")
        builder.button(text="🔧 Добавить обслугу", callback_data="admin_add_service")
        builder.button(text="⚡ Добавить монтаж", callback_data="admin_add_installation")
        
        builder.button(text="⚙️ Управление разрешениями", callback_data="admin_permissions")
        builder.button(text="💾 Настройки сохранения", callback_data="admin_storage_settings")
        builder.button(text="📁 Управление файлами", callback_data="admin_files")
        
        builder.button(text="🗂️ Доступные команды", callback_data="admin_available_commands")
        builder.button(text="🧹 Очистка кэша", callback_data="admin_clear_cache")
        builder.button(text="📊 Экспорт в Excel", callback_data="admin_export_excel")
        
        builder.adjust(2)
        return builder.as_markup()
    
    @staticmethod
    def create_permissions_panel_keyboard() -> InlineKeyboardMarkup:
        """
        Создает панель управления разрешениями (команда !разрешения).
        
        Returns:
            InlineKeyboardMarkup с 5 кнопками: 4 уровня админов + группа
        """
        builder = InlineKeyboardBuilder()
        
        builder.button(text="👑 Главный админ", callback_data="permissions_main_admin")
        builder.button(text="👔 Админ", callback_data="permissions_admin")
        builder.button(text="🔧 Обслуга", callback_data="permissions_service")
        builder.button(text="⚡ Монтаж", callback_data="permissions_installation")
        builder.button(text="👥 Группа", callback_data="permissions_group")
        
        builder.adjust(1)
        return builder.as_markup()
    
    @staticmethod
    def create_admin_type_selection_keyboard() -> InlineKeyboardMarkup:
        """
        Создает клавиатуру выбора типа админа для добавления.
        
        Returns:
            InlineKeyboardMarkup с кнопками типов админов
        """
        builder = InlineKeyboardBuilder()
        
        builder.button(text="👑 Главный админ", callback_data="add_admin_type_main")
        builder.button(text="👔 Админ", callback_data="add_admin_type_admin")
        builder.button(text="🔧 Обслуга", callback_data="add_admin_type_service")
        builder.button(text="⚡ Монтаж", callback_data="add_admin_type_installation")
        builder.button(text="🔙 Назад", callback_data="admin_back_to_main")
        
        builder.adjust(2)
        return builder.as_markup()
    
    @staticmethod
    def create_command_permissions_keyboard(
        role: str, 
        permissions: List[AdminPermission],
        current_page: int = 0
    ) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру настройки разрешений для конкретной роли.
        
        Args:
            role: Роль (main_admin, admin, service, installation, group)
            permissions: Список доступных разрешений
            current_page: Текущая страница (для пагинации)
            
        Returns:
            InlineKeyboardMarkup с переключателями разрешений
        """
        builder = InlineKeyboardBuilder()
        
        # Отображаем до 10 команд на страницу согласно ТЗ
        page_size = 10
        start_idx = current_page * page_size
        end_idx = start_idx + page_size
        
        visible_permissions = permissions[start_idx:end_idx]
        
        for perm in visible_permissions:
            command_name = perm.command_name
            is_enabled = perm.is_enabled
            
            # Эмодзи статуса согласно ТЗ
            status_emoji = "✅" if is_enabled else "❌"
            button_text = f"{status_emoji} {command_name}"
            callback_data = f"permission_toggle:{role}:{perm.id}:{current_page}"
            
            builder.button(text=button_text, callback_data=callback_data)
        
        # Кнопки навигации
        if len(permissions) > page_size:
            nav_buttons = []
            
            if current_page > 0:
                nav_buttons.append(InlineKeyboardButton(
                    text="◀️ Назад", 
                    callback_data=f"permissions_page:{role}:{current_page - 1}"
                ))
            
            total_pages = (len(permissions) + page_size - 1) // page_size
            page_info = f"{current_page + 1}/{total_pages}"
            nav_buttons.append(InlineKeyboardButton(text=page_info, callback_data="noop"))
            
            if current_page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton(
                    text="Далее ▶️", 
                    callback_data=f"permissions_page:{role}:{current_page + 1}"
                ))
            
            builder.row(*nav_buttons)
        
        # Кнопки управления
        builder.button(text="💾 Сохранить", callback_data=f"permissions_save:{role}")
        builder.button(text="📄 Показать все", callback_data=f"permissions_show_all:{role}")
        builder.button(text="🔙 Назад к ролям", callback_data="permissions_back_to_roles")
        
        builder.adjust(2, 1)
        return builder.as_markup()
    
    @staticmethod
    def create_storage_settings_keyboard(archive_group_id: Optional[str] = None) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру настроек сохранения (команда !сохранения).
        
        Args:
            archive_group_id: ID группы для архива (если настроена)
            
        Returns:
            InlineKeyboardMarkup с настройками сохранения
        """
        builder = InlineKeyboardBuilder()
        
        if archive_group_id:
            builder.button(text=f"📊 Архив: настроен", callback_data="storage_archive_info")
            builder.button(text="✏️ Изменить архив", callback_data="storage_change_archive")
        else:
            builder.button(text="➕ Настроить архив", callback_data="storage_setup_archive")
        
        builder.button(text="📁 Настройка файлов", callback_data="storage_file_settings")
        builder.button(text="🔄 Настройка логов", callback_data="storage_log_settings")
        builder.button(text="🔙 Назад", callback_data="admin_back_to_main")
        
        builder.adjust(1)
        return builder.as_markup()
    
    @staticmethod
    def create_file_types_keyboard() -> InlineKeyboardMarkup:
        """
        Создает клавиатуру выбора типа файлов для загрузки (команда !файлы).
        
        Returns:
            InlineKeyboardMarkup с 5 темами из ТЗ
        """
        builder = InlineKeyboardBuilder()
        
        file_types = [
            ("📄 PDF", "file_type_pdf"),
            ("📊 Excel", "file_type_excel"),
            ("📝 Word", "file_type_word"),
            ("🖼️ Изображения", "file_type_images"),
            ("📦 Другие файлы", "file_type_other")
        ]
        
        for text, callback_data in file_types:
            builder.button(text=text, callback_data=callback_data)
        
        builder.button(text="⚙️ Настройки по умолчанию", callback_data="file_default_settings")
        builder.button(text="🔙 Назад", callback_data="storage_back_to_main")
        
        builder.adjust(1)
        return builder.as_markup()
    
    @staticmethod
    def create_confirmation_keyboard(
        action: str, 
        item_id: str, 
        item_name: str = ""
    ) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру подтверждения действия (✅/❌).
        
        Args:
            action: Тип действия (delete, clear_cache, etc.)
            item_id: ID элемента
            item_name: Название элемента для отображения
            
        Returns:
            InlineKeyboardMarkup с кнопками подтверждения
        """
        builder = InlineKeyboardBuilder()
        
        builder.button(text="✅ Да", callback_data=f"confirm_{action}:{item_id}")
        builder.button(text="❌ Нет", callback_data=f"cancel_{action}:{item_id}")
        
        return builder.as_markup()
    
    @staticmethod
    def create_export_options_keyboard() -> InlineKeyboardMarkup:
        """
        Создает клавиатуру выбора данных для экспорта в Excel.
        
        Returns:
            InlineKeyboardMarkup с типами данных для экспорта
        """
        builder = InlineKeyboardBuilder()
        
        export_options = [
            ("📦 Оборудование", "export_equipment"),
            ("🛠️ Материалы", "export_materials"),
            ("⚡ Монтаж", "export_installation"),
            ("📊 Все данные", "export_all"),
            ("🔙 Назад", "admin_back_to_main")
        ]
        
        for text, callback_data in export_options:
            builder.button(text=text, callback_data=callback_data)
        
        builder.adjust(2)
        return builder.as_markup()