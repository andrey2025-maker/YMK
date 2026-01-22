"""
Модуль inline-клавиатур для администрирования.
Содержит специализированные inline-кнопки для управления системой.
"""
from typing import Optional, List, Dict, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


class AdminInlineKeyboard:
    """Inline-клавиатуры для админ-панели."""
    
    @staticmethod
    def create_admin_add_inline() -> InlineKeyboardMarkup:
        """
        Создает inline-клавиатуру для добавления админов.
        
        Returns:
            InlineKeyboardMarkup с кнопками добавления админов
        """
        builder = InlineKeyboardBuilder()
        
        admin_types = [
            ("👑 Главный админ", "admin_add_main"),
            ("👔 Админ", "admin_add_admin"),
            ("🔧 Обслуга", "admin_add_service"),
            ("⚡ Монтаж", "admin_add_installation")
        ]
        
        for text, callback in admin_types:
            builder.button(text=text, callback_data=callback)
        
        builder.button(text="🔙 Отмена", callback_data="admin_cancel_add")
        builder.adjust(2)
        
        return builder.as_markup()
    
    @staticmethod
    def create_permissions_inline(role: str, permissions_data: List[Dict]) -> InlineKeyboardMarkup:
        """
        Создает inline-клавиатуру управления разрешениями.
        
        Args:
            role: Роль пользователя
            permissions_data: Данные о разрешениях
            
        Returns:
            InlineKeyboardMarkup с переключателями разрешений
        """
        builder = InlineKeyboardBuilder()
        
        for perm in permissions_data:
            command = perm.get('command')
            enabled = perm.get('enabled', False)
            perm_id = perm.get('id')
            
            status = "✅" if enabled else "❌"
            text = f"{status} {command}"
            callback_data = f"perm_toggle:{role}:{perm_id}"
            
            builder.button(text=text, callback_data=callback_data)
        
        # Кнопки управления
        builder.button(text="💾 Сохранить", callback_data=f"perm_save:{role}")
        builder.button(text="🔄 Сбросить", callback_data=f"perm_reset:{role}")
        builder.button(text="🔙 Назад", callback_data="perm_back")
        
        builder.adjust(2, 1)
        return builder.as_markup()
    
    @staticmethod
    def create_storage_settings_inline(current_settings: Dict[str, Any]) -> InlineKeyboardMarkup:
        """
        Создает inline-клавиатуру настроек сохранения.
        
        Args:
            current_settings: Текущие настройки сохранения
            
        Returns:
            InlineKeyboardMarkup с настройками
        """
        builder = InlineKeyboardBuilder()
        
        # Настройки архива
        archive_status = "✅" if current_settings.get('archive_enabled') else "❌"
        builder.button(
            text=f"{archive_status} Архив изменений", 
            callback_data="toggle_archive"
        )
        
        # Настройки файлов
        file_types = [
            ("📄 PDF", "file_pdf"),
            ("📊 Excel", "file_excel"),
            ("📝 Word", "file_word"),
            ("🖼️ Изображения", "file_images"),
            ("📦 Другие", "file_other")
        ]
        
        for text, callback in file_types:
            enabled = current_settings.get(f'file_{callback}', True)
            status = "✅" if enabled else "❌"
            builder.button(
                text=f"{status} {text}", 
                callback_data=f"toggle_{callback}"
            )
        
        builder.button(text="🔄 Сбросить все", callback_data="storage_reset")
        builder.button(text="💾 Применить", callback_data="storage_apply")
        builder.button(text="🔙 Назад", callback_data="storage_back")
        
        builder.adjust(2, 5, 1, 1)
        return builder.as_markup()
    
    @staticmethod
    def create_confirm_action_inline(
        action: str, 
        item_id: str, 
        confirm_text: str = "✅ Подтвердить",
        cancel_text: str = "❌ Отменить"
    ) -> InlineKeyboardMarkup:
        """
        Создает inline-клавиатуру подтверждения действия.
        
        Args:
            action: Тип действия
            item_id: ID элемента
            confirm_text: Текст кнопки подтверждения
            cancel_text: Текст кнопки отмены
            
        Returns:
            InlineKeyboardMarkup с кнопками подтверждения
        """
        builder = InlineKeyboardBuilder()
        
        builder.button(
            text=confirm_text, 
            callback_data=f"confirm_{action}:{item_id}"
        )
        builder.button(
            text=cancel_text, 
            callback_data=f"cancel_{action}:{item_id}"
        )
        
        return builder.as_markup()
    
    @staticmethod
    def create_export_inline(export_types: List[str]) -> InlineKeyboardMarkup:
        """
        Создает inline-клавиатуру выбора данных для экспорта.
        
        Args:
            export_types: Доступные типы данных для экспорта
            
        Returns:
            InlineKeyboardMarkup с опциями экспорта
        """
        builder = InlineKeyboardBuilder()
        
        type_mapping = {
            'equipment': ("📦 Оборудование", "export_equipment"),
            'materials': ("🛠️ Материалы", "export_materials"),
            'montage': ("⚡ Монтаж", "export_montage"),
            'objects': ("🏢 Объекты", "export_objects"),
            'problems': ("⚠️ Проблемы", "export_problems"),
            'reminders': ("🔔 Напоминания", "export_reminders"),
            'all': ("📊 Все данные", "export_all")
        }
        
        for exp_type in export_types:
            if exp_type in type_mapping:
                text, callback = type_mapping[exp_type]
                builder.button(text=text, callback_data=callback)
        
        builder.button(text="📅 Выбрать период", callback_data="export_period")
        builder.button(text="🔙 Отмена", callback_data="export_cancel")
        
        builder.adjust(2)
        return builder.as_markup()
    
    @staticmethod
    def create_cache_management_inline(cache_stats: Dict[str, Any]) -> InlineKeyboardMarkup:
        """
        Создает inline-клавиатуру управления кэшем.
        
        Args:
            cache_stats: Статистика кэша
            
        Returns:
            InlineKeyboardMarkup с кнопками управления кэшем
        """
        builder = InlineKeyboardBuilder()
        
        builder.button(text="🧹 Очистить кэш", callback_data="cache_clear")
        builder.button(text="📊 Статистика", callback_data="cache_stats")
        
        if cache_stats.get('has_expired'):
            builder.button(text="🗑️ Удалить истёкшие", callback_data="cache_clean_expired")
        
        builder.button(text="🔄 Обновить", callback_data="cache_refresh")
        builder.button(text="🔙 Назад", callback_data="cache_back")
        
        builder.adjust(2)
        return builder.as_markup()