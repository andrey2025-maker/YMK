"""
Модуль inline-клавиатур для обслуживания.
Содержит специализированные inline-кнопки для работы с объектами обслуживания.
"""
from typing import List, Dict, Any, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


class ServiceInlineKeyboard:
    """Inline-клавиатуры для модуля обслуживания."""
    
    @staticmethod
    def create_service_main_inline() -> InlineKeyboardMarkup:
        """
        Создает inline-клавиатуру главного меню обслуживания.
        
        Returns:
            InlineKeyboardMarkup с основными командами обслуживания
        """
        builder = InlineKeyboardBuilder()
        
        main_buttons = [
            ("➕ Создать регион", "service_create_region"),
            ("📋 Мои регионы", "service_my_regions"),
            ("🔍 Поиск объектов", "service_search"),
            ("🔔 Напоминания", "service_reminders"),
            ("📊 Отчеты", "service_reports"),
            ("⚙️ Настройки", "service_settings")
        ]
        
        for text, callback in main_buttons:
            builder.button(text=text, callback_data=callback)
        
        builder.adjust(2)
        return builder.as_markup()
    
    @staticmethod
    def create_region_list_inline(
        regions: List[Dict[str, Any]],
        page: int = 0,
        total_pages: int = 1
    ) -> InlineKeyboardMarkup:
        """
        Создает inline-клавиатуру списка регионов с пагинацией.
        
        Args:
            regions: Список регионов
            page: Текущая страница
            total_pages: Всего страниц
            
        Returns:
            InlineKeyboardMarkup с регионами и пагинацией
        """
        builder = InlineKeyboardBuilder()
        
        # Кнопки регионов
        for region in regions:
            short_name = region.get('short_name', 'Неизвестно')
            region_id = region.get('id')
            callback_data = f"service_region:{region_id}"
            
            builder.button(text=short_name, callback_data=callback_data)
        
        # Пагинация
        if total_pages > 1:
            pagination_row = []
            
            if page > 0:
                pagination_row.append(InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=f"regions_page:{page - 1}"
                ))
            
            pagination_row.append(InlineKeyboardButton(
                text=f"{page + 1}/{total_pages}",
                callback_data="noop"
            ))
            
            if page < total_pages - 1:
                pagination_row.append(InlineKeyboardButton(
                    text="Далее ▶️",
                    callback_data=f"regions_page:{page + 1}"
                ))
            
            builder.row(*pagination_row)
        
        builder.button(text="➕ Создать регион", callback_data="service_create_region")
        builder.button(text="🔙 Назад", callback_data="service_back_to_main")
        
        builder.adjust(1)
        return builder.as_markup()
    
    @staticmethod
    def create_object_panel_inline(
        object_id: str,
        user_role: str,
        has_addresses: bool = False
    ) -> InlineKeyboardMarkup:
        """
        Создает inline-панель управления объектом обслуживания.
        
        Args:
            object_id: ID объекта
            user_role: Роль пользователя
            has_addresses: Есть ли несколько адресов
            
        Returns:
            InlineKeyboardMarkup с панелью объекта
        """
        builder = InlineKeyboardBuilder()
        
        # Основные разделы объекта
        sections = [
            ("⚠️ Проблемы", f"service_problems:{object_id}"),
            ("🔧 ТО", f"service_maintenance:{object_id}"),
            ("📨 Письма", f"service_letters:{object_id}"),
            ("📒 Журналы", f"service_journals:{object_id}"),
            ("✅ Допуски", f"service_permits:{object_id}"),
            ("🛠️ Оборудование", f"service_equipment:{object_id}"),
            ("🔔 Напоминания", f"service_reminders:{object_id}")
        ]
        
        for text, callback in sections:
            builder.button(text=text, callback_data=callback)
        
        # Кнопки управления (для админов)
        if user_role in ['main_admin', 'admin']:
            builder.button(text="✏️ Редактировать", callback_data=f"service_edit:{object_id}")
            builder.button(text="🗑️ Удалить", callback_data=f"service_delete:{object_id}")
        
        # Специальная кнопка если несколько адресов
        if has_addresses:
            builder.button(text="📍 Выбрать адрес", callback_data=f"service_addresses:{object_id}")
        
        builder.button(text="🔙 К регионам", callback_data="service_back_to_regions")
        
        builder.adjust(3, 3, 2, 1)
        return builder.as_markup()
    
    @staticmethod
    def create_problems_list_inline(
        problems: List[Dict[str, Any]],
        object_id: str,
        user_role: str,
        page: int = 0,
        total_pages: int = 1
    ) -> InlineKeyboardMarkup:
        """
        Создает inline-клавиатуру списка проблем с нумерацией.
        
        Args:
            problems: Список проблем
            object_id: ID объекта
            user_role: Роль пользователя
            page: Текущая страница
            total_pages: Всего страниц
            
        Returns:
            InlineKeyboardMarkup с проблемами
        """
        builder = InlineKeyboardBuilder()
        
        # Проблемы с нумерацией
        for idx, problem in enumerate(problems, start=1):
            problem_id = problem.get('id')
            problem_text = problem.get('text', 'Без описания')
            
            # Обрезаем длинный текст
            if len(problem_text) > 30:
                problem_text = problem_text[:27] + "..."
            
            text = f"{idx}. {problem_text}"
            callback_data = f"service_problem:{object_id}:{problem_id}"
            
            builder.button(text=text, callback_data=callback_data)
        
        # Пагинация
        if total_pages > 1:
            pagination_row = []
            
            if page > 0:
                pagination_row.append(InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=f"problems_page:{object_id}:{page - 1}"
                ))
            
            pagination_row.append(InlineKeyboardButton(
                text=f"Страница {page + 1}/{total_pages}",
                callback_data="noop"
            ))
            
            if page < total_pages - 1:
                pagination_row.append(InlineKeyboardButton(
                    text="Далее ▶️",
                    callback_data=f"problems_page:{object_id}:{page + 1}"
                ))
            
            builder.row(*pagination_row)
        
        # Кнопки действий
        builder.button(text="➕ Добавить", callback_data=f"service_add_problem:{object_id}")
        
        if user_role in ['main_admin', 'admin']:
            builder.button(text="🗑️ Удалить", callback_data=f"service_delete_problems:{object_id}")
        
        builder.button(text="🔙 К объекту", callback_data=f"service_back_to_object:{object_id}")
        
        builder.adjust(1)
        return builder.as_markup()
    
    @staticmethod
    def create_equipment_section_inline(
        addresses: List[Dict[str, Any]],
        object_id: str,
        user_role: str
    ) -> InlineKeyboardMarkup:
        """
        Создает inline-клавиатуру разделов оборудования по адресам.
        
        Args:
            addresses: Список адресов объекта
            object_id: ID объекта
            user_role: Роль пользователя
            
        Returns:
            InlineKeyboardMarkup с адресами для выбора
        """
        builder = InlineKeyboardBuilder()
        
        if len(addresses) > 1:
            # Если несколько адресов - показываем выбор
            for idx, address in enumerate(addresses, start=1):
                address_text = address.get('address', f'Адрес {idx}')
                callback_data = f"service_equipment_address:{object_id}:{address.get('id')}"
                
                builder.button(text=f"📍 {idx}. {address_text}", callback_data=callback_data)
        else:
            # Если один адрес - сразу к оборудованию
            address_id = addresses[0].get('id') if addresses else 'general'
            return ServiceInlineKeyboard.create_equipment_list_inline(
                equipment=[], 
                object_id=object_id, 
                address_id=address_id, 
                user_role=user_role
            )
        
        if user_role in ['main_admin', 'admin']:
            builder.button(text="➕ Добавить адрес", callback_data=f"service_add_address:{object_id}")
        
        builder.button(text="🔙 К объекту", callback_data=f"service_back_to_object:{object_id}")
        
        builder.adjust(1)
        return builder.as_markup()
    
    @staticmethod
    def create_equipment_list_inline(
        equipment: List[Dict[str, Any]],
        object_id: str,
        address_id: str,
        user_role: str,
        page: int = 0,
        total_pages: int = 1
    ) -> InlineKeyboardMarkup:
        """
        Создает inline-клавиатуру списка оборудования.
        
        Args:
            equipment: Список оборудования
            object_id: ID объекта
            address_id: ID адреса
            user_role: Роль пользователя
            page: Текущая страница
            total_pages: Всего страниц
            
        Returns:
            InlineKeyboardMarkup с оборудованием
        """
        builder = InlineKeyboardBuilder()
        
        # Оборудование с нумерацией
        for idx, item in enumerate(equipment, start=1):
            item_id = item.get('id')
            name = item.get('name', 'Без названия')
            quantity = item.get('quantity', 0)
            unit = item.get('unit', 'шт.')
            
            text = f"{idx}. {name} ({quantity} {unit})"
            callback_data = f"service_equipment_item:{object_id}:{address_id}:{item_id}"
            
            builder.button(text=text, callback_data=callback_data)
        
        # Пагинация
        if total_pages > 1:
            pagination_row = []
            
            if page > 0:
                pagination_row.append(InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=f"equipment_page:{object_id}:{address_id}:{page - 1}"
                ))
            
            pagination_row.append(InlineKeyboardButton(
                text=f"{page + 1}/{total_pages}",
                callback_data="noop"
            ))
            
            if page < total_pages - 1:
                pagination_row.append(InlineKeyboardButton(
                    text="Далее ▶️",
                    callback_data=f"equipment_page:{object_id}:{address_id}:{page + 1}"
                ))
            
            builder.row(*pagination_row)
        
        # Кнопки действий
        builder.button(text="➕ Добавить", callback_data=f"service_add_equipment:{object_id}:{address_id}")
        
        if user_role in ['main_admin', 'admin']:
            builder.button(text="✏️ Изменить", callback_data=f"service_edit_equipment:{object_id}:{address_id}")
            builder.button(text="🗑️ Удалить", callback_data=f"service_delete_equipment:{object_id}:{address_id}")
        
        builder.button(text="🔄 Обновить", callback_data=f"service_refresh_equipment:{object_id}:{address_id}")
        builder.button(text="🔙 К адресам", callback_data=f"service_equipment_back_to_addresses:{object_id}")
        
        builder.adjust(1)
        return builder.as_markup()