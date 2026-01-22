"""
Модуль inline-клавиатур для монтажа.
Содержит специализированные inline-кнопки для работы с объектами монтажа.
"""
from typing import List, Dict, Any, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


class InstallationInlineKeyboard:
    """Inline-клавиатуры для модуля монтажа."""
    
    @staticmethod
    def create_installation_main_inline() -> InlineKeyboardMarkup:
        """
        Создает inline-клавиатуру главного меню монтажа.
        
        Returns:
            InlineKeyboardMarkup с основными командами монтажа
        """
        builder = InlineKeyboardBuilder()
        
        main_buttons = [
            ("➕ Создать объект", "installation_create"),
            ("📋 Мои объекты", "installation_my_objects"),
            ("🔍 Поиск", "installation_search"),
            ("📊 Отчеты", "installation_reports"),
            ("🔔 Напоминания", "installation_reminders"),
            ("⚙️ Настройки", "installation_settings")
        ]
        
        for text, callback in main_buttons:
            builder.button(text=text, callback_data=callback)
        
        builder.adjust(2)
        return builder.as_markup()
    
    @staticmethod
    def create_projects_list_inline(
        projects: List[Dict[str, Any]],
        object_id: str,
        user_role: str,
        page: int = 0,
        total_pages: int = 1
    ) -> InlineKeyboardMarkup:
        """
        Создает inline-клавиатуру списка проектов.
        
        Args:
            projects: Список проектов
            object_id: ID объекта монтажа
            user_role: Роль пользователя
            page: Текущая страница
            total_pages: Всего страниц
            
        Returns:
            InlineKeyboardMarkup с проектами
        """
        builder = InlineKeyboardBuilder()
        
        # Проекты с нумерацией и указанием файлов
        for idx, project in enumerate(projects, start=1):
            project_id = project.get('id')
            name = project.get('name', f'Проект {idx}')
            has_file = project.get('has_file', False)
            
            file_icon = "📁" if has_file else "📄"
            text = f"{idx}. {file_icon} {name}"
            callback_data = f"installation_project:{object_id}:{project_id}"
            
            builder.button(text=text, callback_data=callback_data)
        
        # Пагинация
        if total_pages > 1:
            pagination_row = []
            
            if page > 0:
                pagination_row.append(InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=f"projects_page:{object_id}:{page - 1}"
                ))
            
            pagination_row.append(InlineKeyboardButton(
                text=f"{page + 1}/{total_pages}",
                callback_data="noop"
            ))
            
            if page < total_pages - 1:
                pagination_row.append(InlineKeyboardButton(
                    text="Далее ▶️",
                    callback_data=f"projects_page:{object_id}:{page + 1}"
                ))
            
            builder.row(*pagination_row)
        
        # Кнопки управления
        if user_role in ['main_admin', 'admin']:
            builder.button(text="➕ Добавить", callback_data=f"installation_add_project:{object_id}")
            builder.button(text="✏️ Изменить", callback_data=f"installation_edit_projects:{object_id}")
            builder.button(text="🗑️ Удалить", callback_data=f"installation_delete_projects:{object_id}")
        else:
            builder.button(text="👁️ Показать", callback_data=f"installation_show_projects:{object_id}")
        
        builder.button(text="🔙 К объекту", callback_data=f"installation_back_to_object:{object_id}")
        
        builder.adjust(1)
        return builder.as_markup()
    
    @staticmethod
    def create_materials_sections_inline(
        sections: List[Dict[str, Any]],
        object_id: str,
        user_role: str,
        has_general: bool = True
    ) -> InlineKeyboardMarkup:
        """
        Создает inline-клавиатуру разделов материалов.
        
        Args:
            sections: Список разделов материалов
            object_id: ID объекта монтажа
            user_role: Роль пользователя
            has_general: Есть ли раздел "Общее"
            
        Returns:
            InlineKeyboardMarkup с разделами материалов
        """
        builder = InlineKeyboardBuilder()
        
        # Кнопка "Общее" если есть
        if has_general:
            builder.button(text="📦 Общее", callback_data=f"installation_materials_general:{object_id}")
        
        # Разделы материалов
        for section in sections:
            section_id = section.get('id')
            name = section.get('name', 'Без названия')
            item_count = section.get('item_count', 0)
            
            text = f"📁 {name} ({item_count})"
            callback_data = f"installation_materials_section:{object_id}:{section_id}"
            
            builder.button(text=text, callback_data=callback_data)
        
        # Кнопки управления
        if user_role in ['main_admin', 'admin']:
            builder.button(text="➕ Добавить раздел", callback_data=f"installation_add_material_section:{object_id}")
            builder.button(text="⚖️ Проверить суммы", callback_data=f"installation_check_sums:{object_id}")
        
        builder.button(text="📊 Отчет по материалам", callback_data=f"installation_materials_report:{object_id}")
        builder.button(text="🔙 К объекту", callback_data=f"installation_back_to_object:{object_id}")
        
        builder.adjust(1)
        return builder.as_markup()
    
    @staticmethod
    def create_montage_tracking_inline(
        materials: List[Dict[str, Any]],
        section_id: str,
        object_id: str,
        page: int = 0,
        total_pages: int = 1
    ) -> InlineKeyboardMarkup:
        """
        Создает inline-клавиатуру учета монтажа по материалам.
        
        Args:
            materials: Список материалов для монтажа
            section_id: ID раздела (или 'general')
            object_id: ID объекта монтажа
            page: Текущая страница
            total_pages: Всего страниц
            
        Returns:
            InlineKeyboardMarkup с учетом монтажа
        """
        builder = InlineKeyboardBuilder()
        
        # Материалы с прогрессом монтажа
        for idx, material in enumerate(materials, start=1):
            material_id = material.get('id')
            name = material.get('name', f'Материал {idx}')
            planned = material.get('planned', 0)
            installed = material.get('installed', 0)
            
            # Индикатор прогресса
            if planned > 0:
                percentage = int((installed / planned) * 100)
                progress = f" {installed}/{planned} ({percentage}%)"
            else:
                progress = f" {installed}/?"
            
            text = f"{idx}. {name}{progress}"
            callback_data = f"installation_montage_material:{object_id}:{section_id}:{material_id}"
            
            builder.button(text=text, callback_data=callback_data)
        
        # Пагинация
        if total_pages > 1:
            pagination_row = []
            
            if page > 0:
                pagination_row.append(InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=f"montage_page:{object_id}:{section_id}:{page - 1}"
                ))
            
            pagination_row.append(InlineKeyboardButton(
                text=f"{page + 1}/{total_pages}",
                callback_data="noop"
            ))
            
            if page < total_pages - 1:
                pagination_row.append(InlineKeyboardButton(
                    text="Далее ▶️",
                    callback_data=f"montage_page:{object_id}:{section_id}:{page + 1}"
                ))
            
            builder.row(*pagination_row)
        
        # Кнопки управления
        builder.button(text="✅ Отметить смонтировано", callback_data=f"installation_mark_installed:{object_id}:{section_id}")
        builder.button(text="🔄 Обновить данные", callback_data=f"installation_refresh_montage:{object_id}:{section_id}")
        builder.button(text="📊 Прогресс", callback_data=f"installation_montage_progress:{object_id}:{section_id}")
        builder.button(text="🔙 К разделам", callback_data=f"installation_back_to_sections:{object_id}")
        
        builder.adjust(1)
        return builder.as_markup()
    
    @staticmethod
    def create_supplies_list_inline(
        supplies: List[Dict[str, Any]],
        object_id: str,
        user_role: str,
        page: int = 0,
        total_pages: int = 1
    ) -> InlineKeyboardMarkup:
        """
        Создает inline-клавиатуру списка поставок.
        
        Args:
            supplies: Список поставок
            object_id: ID объекта монтажа
            user_role: Роль пользователя
            page: Текущая страница
            total_pages: Всего страниц
            
        Returns:
            InlineKeyboardMarkup с поставками
        """
        builder = InlineKeyboardBuilder()
        
        # Поставки с датами
        for idx, supply in enumerate(supplies, start=1):
            supply_id = supply.get('id')
            service = supply.get('service', 'Не указано')
            date = supply.get('date', 'Без даты')
            has_reminder = supply.get('has_reminder', False)
            
            reminder_icon = "🔔" if has_reminder else ""
            text = f"{idx}. {service} - {date} {reminder_icon}"
            callback_data = f"installation_supply:{object_id}:{supply_id}"
            
            builder.button(text=text, callback_data=callback_data)
        
        # Пагинация
        if total_pages > 1:
            pagination_row = []
            
            if page > 0:
                pagination_row.append(InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=f"supplies_page:{object_id}:{page - 1}"
                ))
            
            pagination_row.append(InlineKeyboardButton(
                text=f"{page + 1}/{total_pages}",
                callback_data="noop"
            ))
            
            if page < total_pages - 1:
                pagination_row.append(InlineKeyboardButton(
                    text="Далее ▶️",
                    callback_data=f"supplies_page:{object_id}:{page + 1}"
                ))
            
            builder.row(*pagination_row)
        
        # Кнопки управления
        if user_role in ['main_admin', 'admin']:
            builder.button(text="➕ Добавить", callback_data=f"installation_add_supply:{object_id}")
            builder.button(text="✏️ Изменить", callback_data=f"installation_edit_supplies:{object_id}")
            builder.button(text="🗑️ Удалить", callback_data=f"installation_delete_supplies:{object_id}")
        
        builder.button(text="🔔 Управление напоминаниями", callback_data=f"installation_supply_reminders:{object_id}")
        builder.button(text="🔙 К объекту", callback_data=f"installation_back_to_object:{object_id}")
        
        builder.adjust(1)
        return builder.as_markup()
    
    @staticmethod
    def create_object_panel_inline(
        object_id: str,
        user_role: str,
        has_projects: bool = False,
        has_materials: bool = False
    ) -> InlineKeyboardMarkup:
        """
        Создает inline-панель управления объектом монтажа.
        
        Args:
            object_id: ID объекта монтажа
            user_role: Роль пользователя
            has_projects: Есть ли проекты
            has_materials: Есть ли материалы
            
        Returns:
            InlineKeyboardMarkup с панелью объекта монтажа
        """
        builder = InlineKeyboardBuilder()
        
        # Основные разделы объекта монтажа
        sections = [
            ("📁 Проекты", f"installation_projects:{object_id}"),
            ("📦 Материалы", f"installation_materials:{object_id}"),
            ("⚡ Монтаж", f"installation_montage:{object_id}"),
            ("🔄 Изменения", f"installation_changes:{object_id}"),
            ("📨 Письма", f"installation_letters:{object_id}"),
            ("✅ Допуски", f"installation_permits:{object_id}"),
            ("📒 Журналы", f"installation_journals:{object_id}"),
            ("📄 ИД", f"installation_id:{object_id}"),
            ("🚚 Поставки", f"installation_supplies:{object_id}"),
            ("🔔 Напоминания", f"installation_reminders:{object_id}")
        ]
        
        for text, callback in sections:
            builder.button(text=text, callback_data=callback)
        
        # Кнопки управления (для админов)
        if user_role in ['main_admin', 'admin']:
            builder.button(text="✏️ Редактировать", callback_data=f"installation_edit:{object_id}")
            builder.button(text="🗑️ Удалить", callback_data=f"installation_delete:{object_id}")
        
        # Информационные кнопки
        if has_projects:
            builder.button(text="📊 Статистика проектов", callback_data=f"installation_projects_stats:{object_id}")
        
        if has_materials:
            builder.button(text="⚖️ Баланс материалов", callback_data=f"installation_materials_balance:{object_id}")
        
        builder.button(text="🔙 К списку объектов", callback_data="installation_back_to_objects")
        
        builder.adjust(3, 3, 2, 1)
        return builder.as_markup()