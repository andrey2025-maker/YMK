"""
Модуль общих клавиатур для всего приложения.
Содержит часто используемые элементы интерфейса.
"""
from typing import Optional, List, Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


class CommonKeyboardBuilder:
    """Построитель общих клавиатур."""
    
    @staticmethod
    def create_back_keyboard(back_callback: str = "back") -> InlineKeyboardMarkup:
        """
        Создает простую клавиатуру с кнопкой "Назад".
        
        Args:
            back_callback: Callback data для кнопки назад
            
        Returns:
            InlineKeyboardMarkup с кнопкой "Назад"
        """
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад", callback_data=back_callback)
        return builder.as_markup()
    
    @staticmethod
    def create_yes_no_keyboard(
        yes_callback: str = "yes", 
        no_callback: str = "no"
    ) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру с кнопками "Да"/"Нет".
        
        Args:
            yes_callback: Callback data для "Да"
            no_callback: Callback data для "Нет"
            
        Returns:
            InlineKeyboardMarkup с кнопками подтверждения
        """
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Да", callback_data=yes_callback)
        builder.button(text="❌ Нет", callback_data=no_callback)
        return builder.as_markup()
    
    @staticmethod
    def create_cancel_keyboard(cancel_callback: str = "cancel") -> InlineKeyboardMarkup:
        """
        Создает клавиатуру с кнопкой "Отмена".
        
        Args:
            cancel_callback: Callback data для отмены
            
        Returns:
            InlineKeyboardMarkup с кнопкой "Отмена"
        """
        builder = InlineKeyboardBuilder()
        builder.button(text="❌ Отмена", callback_data=cancel_callback)
        return builder.as_markup()
    
    @staticmethod
    def create_navigation_keyboard(
        back_callback: Optional[str] = None,
        next_callback: Optional[str] = None,
        page_info: Optional[str] = None
    ) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру навигации "Назад/Далее".
        
        Args:
            back_callback: Callback data для "Назад"
            next_callback: Callback data для "Далее"
            page_info: Информация о странице (например, "1/3")
            
        Returns:
            InlineKeyboardMarkup с навигационными кнопками
        """
        builder = InlineKeyboardBuilder()
        
        buttons = []
        
        if back_callback:
            buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=back_callback))
        
        if page_info:
            buttons.append(InlineKeyboardButton(text=page_info, callback_data="noop"))
        
        if next_callback:
            buttons.append(InlineKeyboardButton(text="Далее ▶️", callback_data=next_callback))
        
        if buttons:
            builder.row(*buttons)
        
        return builder.as_markup()
    
    @staticmethod
    def create_main_menu_keyboard(user_role: str) -> InlineKeyboardMarkup:
        """
        Создает главное меню в зависимости от роли пользователя.
        
        Args:
            user_role: Роль пользователя
            
        Returns:
            InlineKeyboardMarkup с доступными командами
        """
        builder = InlineKeyboardBuilder()
        
        # Основные команды доступные всем
        builder.button(text="🔍 Поиск", callback_data="menu_search")
        builder.button(text="🔔 Мои напоминания", callback_data="menu_reminders")
        builder.button(text="🏢 Мои объекты", callback_data="menu_my_objects")
        
        # Команды в зависимости от роли
        if user_role in ["main_admin", "admin"]:
            builder.button(text="👑 Админ-панель", callback_data="menu_admin")
        
        if user_role in ["main_admin", "admin", "service"]:
            builder.button(text="🔧 Обслуживание", callback_data="menu_service")
        
        if user_role in ["main_admin", "admin", "installation"]:
            builder.button(text="⚡ Монтаж", callback_data="menu_installation")
        
        # Дополнительные команды
        builder.button(text="📋 Помощь", callback_data="menu_help")
        builder.button(text="⚙️ Настройки", callback_data="menu_settings")
        
        builder.adjust(2)
        return builder.as_markup()
    
    @staticmethod
    def create_item_list_keyboard(
        items: List[Tuple[str, str]], 
        page: int = 0,
        items_per_page: int = 10,
        include_back: bool = True
    ) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру со списком элементов (до 10 на страницу).
        
        Args:
            items: Список кортежей (текст, callback_data)
            page: Номер страницы
            items_per_page: Количество элементов на страницу
            include_back: Добавлять ли кнопку "Назад"
            
        Returns:
            InlineKeyboardMarkup со списком элементов
        """
        builder = InlineKeyboardBuilder()
        
        # Пагинация
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        page_items = items[start_idx:end_idx]
        
        # Добавляем элементы
        for text, callback_data in page_items:
            builder.button(text=text, callback_data=callback_data)
        
        # Добавляем навигацию если нужно
        if len(items) > items_per_page:
            nav_buttons = []
            
            if page > 0:
                nav_buttons.append(InlineKeyboardButton(
                    text="◀️ Назад", 
                    callback_data=f"page_{page - 1}"
                ))
            
            total_pages = (len(items) + items_per_page - 1) // items_per_page
            page_info = f"Страница {page + 1}/{total_pages}"
            nav_buttons.append(InlineKeyboardButton(text=page_info, callback_data="noop"))
            
            if page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton(
                    text="Далее ▶️", 
                    callback_data=f"page_{page + 1}"
                ))
            
            builder.row(*nav_buttons)
        
        # Добавляем кнопку "Назад" если требуется
        if include_back:
            builder.button(text="🔙 Назад", callback_data="back")
        
        builder.adjust(1)
        return builder.as_markup()
    
    @staticmethod
    def create_quick_actions_keyboard() -> InlineKeyboardMarkup:
        """
        Создает клавиатуру быстрых действий.
        
        Returns:
            InlineKeyboardMarkup с часто используемыми командами
        """
        builder = InlineKeyboardBuilder()
        
        quick_actions = [
            ("➕ Добавить", "quick_add"),
            ("✏️ Редактировать", "quick_edit"),
            ("🗑️ Удалить", "quick_delete"),
            ("📁 Прикрепить файл", "quick_attach_file"),
            ("🔍 Поиск", "quick_search"),
            ("📊 Отчет", "quick_report")
        ]
        
        for text, callback_data in quick_actions:
            builder.button(text=text, callback_data=callback_data)
        
        builder.adjust(2)
        return builder.as_markup()
    
    @staticmethod
    def create_reply_keyboard(buttons: List[str]) -> ReplyKeyboardMarkup:
        """
        Создает Reply клавиатуру из списка текстовых кнопок.
        
        Args:
            buttons: Список текстов для кнопок
            
        Returns:
            ReplyKeyboardMarkup
        """
        builder = ReplyKeyboardBuilder()
        
        for button_text in buttons:
            builder.button(text=button_text)
        
        builder.adjust(2)
        return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)