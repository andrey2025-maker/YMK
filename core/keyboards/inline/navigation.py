"""
Модуль универсальных inline-клавиатур навигации.
Содержит общие кнопки для перемещения по интерфейсу.
"""
from typing import List, Optional, Tuple, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


class NavigationInlineKeyboard:
    """Универсальные inline-клавиатуры навигации."""
    
    @staticmethod
    def create_back_inline(
        back_text: str = "🔙 Назад",
        back_callback: str = "back",
        cancel_text: Optional[str] = None,
        cancel_callback: Optional[str] = None
    ) -> InlineKeyboardMarkup:
        """
        Создает inline-клавиатуру с кнопкой "Назад".
        
        Args:
            back_text: Текст кнопки "Назад"
            back_callback: Callback для кнопки "Назад"
            cancel_text: Текст кнопки "Отмена" (опционально)
            cancel_callback: Callback для кнопки "Отмена" (опционально)
            
        Returns:
            InlineKeyboardMarkup с навигационными кнопками
        """
        builder = InlineKeyboardBuilder()
        
        builder.button(text=back_text, callback_data=back_callback)
        
        if cancel_text and cancel_callback:
            builder.button(text=cancel_text, callback_data=cancel_callback)
        
        return builder.as_markup()
    
    @staticmethod
    def create_yes_no_inline(
        yes_text: str = "✅ Да",
        yes_callback: str = "yes",
        no_text: str = "❌ Нет",
        no_callback: str = "no",
        include_back: bool = False,
        back_callback: str = "back"
    ) -> InlineKeyboardMarkup:
        """
        Создает inline-клавиатуру с кнопками "Да/Нет".
        
        Args:
            yes_text: Текст кнопки "Да"
            yes_callback: Callback для кнопки "Да"
            no_text: Текст кнопки "Нет"
            no_callback: Callback для кнопки "Нет"
            include_back: Добавить ли кнопку "Назад"
            back_callback: Callback для кнопки "Назад"
            
        Returns:
            InlineKeyboardMarkup с кнопками подтверждения
        """
        builder = InlineKeyboardBuilder()
        
        builder.button(text=yes_text, callback_data=yes_callback)
        builder.button(text=no_text, callback_data=no_callback)
        
        if include_back:
            builder.button(text="🔙 Назад", callback_data=back_callback)
        
        builder.adjust(2, 1) if include_back else builder.adjust(2)
        
        return builder.as_markup()
    
    @staticmethod
    def create_numbered_list_inline(
        items: List[Tuple[str, str]],
        items_per_row: int = 2,
        include_back: bool = True,
        back_callback: str = "back",
        start_number: int = 1
    ) -> InlineKeyboardMarkup:
        """
        Создает inline-клавиатуру с пронумерованными кнопками.
        
        Args:
            items: Список кортежей (текст, callback_data)
            items_per_row: Количество кнопок в строке
            include_back: Добавить ли кнопку "Назад"
            back_callback: Callback для кнопки "Назад"
            start_number: Начальный номер для нумерации
            
        Returns:
            InlineKeyboardMarkup с пронумерованными кнопками
        """
        builder = InlineKeyboardBuilder()
        
        for idx, (text, callback) in enumerate(items, start=start_number):
            button_text = f"{idx}. {text}"
            builder.button(text=button_text, callback_data=callback)
        
        if include_back:
            builder.button(text="🔙 Назад", callback_data=back_callback)
        
        builder.adjust(items_per_row)
        return builder.as_markup()
    
    @staticmethod
    def create_pagination_inline(
        current_page: int,
        total_pages: int,
        prefix: str = "page",
        include_back: bool = True,
        back_callback: str = "back",
        items_per_page: int = 10,
        total_items: Optional[int] = None
    ) -> InlineKeyboardMarkup:
        """
        Создает inline-клавиатуру пагинации.
        
        Args:
            current_page: Текущая страница (начиная с 0)
            total_pages: Всего страниц
            prefix: Префикс для callback данных
            include_back: Добавить ли кнопку "Назад"
            back_callback: Callback для кнопки "Назад"
            items_per_page: Элементов на страницу
            total_items: Всего элементов (для отображения информации)
            
        Returns:
            InlineKeyboardMarkup с пагинацией
        """
        builder = InlineKeyboardBuilder()
        
        # Создаем строку пагинации
        pagination_buttons = []
        
        # Кнопка "Назад" если не на первой странице
        if current_page > 0:
            pagination_buttons.append(InlineKeyboardButton(
                text="◀️ Назад",
                callback_data=f"{prefix}:{current_page - 1}"
            ))
        
        # Информация о странице
        page_info = f"{current_page + 1}/{total_pages}"
        if total_items is not None:
            start_item = current_page * items_per_page + 1
            end_item = min((current_page + 1) * items_per_page, total_items)
            page_info = f"{start_item}-{end_item} из {total_items}"
        
        pagination_buttons.append(InlineKeyboardButton(
            text=page_info,
            callback_data="noop"
        ))
        
        # Кнопка "Далее" если не на последней странице
        if current_page < total_pages - 1:
            pagination_buttons.append(InlineKeyboardButton(
                text="Далее ▶️",
                callback_data=f"{prefix}:{current_page + 1}"
            ))
        
        # Добавляем строку пагинации
        builder.row(*pagination_buttons)
        
        # Добавляем кнопку "Назад" если требуется
        if include_back:
            builder.button(text="🔙 Назад", callback_data=back_callback)
        
        return builder.as_markup()
    
    @staticmethod
    def create_main_navigation_inline(
        user_role: str,
        current_module: Optional[str] = None
    ) -> InlineKeyboardMarkup:
        """
        Создает inline-клавиатуру основной навигации по модулям.
        
        Args:
            user_role: Роль пользователя
            current_module: Текущий модуль (чтобы подсветить активный)
            
        Returns:
            InlineKeyboardMarkup с основной навигацией
        """
        builder = InlineKeyboardBuilder()
        
        # Основные модули доступные всем
        modules = [
            ("🔍 Поиск", "nav_search"),
            ("🔔 Напоминания", "nav_reminders"),
            ("🏢 Мои объекты", "nav_my_objects"),
        ]
        
        # Добавляем модули в зависимости от роли
        if user_role in ["main_admin", "admin"]:
            modules.append(("👑 Админка", "nav_admin"))
        
        if user_role in ["main_admin", "admin", "service"]:
            modules.append(("🔧 Обслуживание", "nav_service"))
        
        if user_role in ["main_admin", "admin", "installation"]:
            modules.append(("⚡ Монтаж", "nav_installation"))
        
        # Добавляем служебные кнопки
        modules.extend([
            ("📋 Помощь", "nav_help"),
            ("⚙️ Настройки", "nav_settings"),
            ("🏠 Главная", "nav_main")
        ])
        
        # Создаем кнопки, подсвечивая текущий модуль
        for text, callback in modules:
            # Если это текущий модуль - добавляем индикатор
            if current_module and callback == f"nav_{current_module}":
                button_text = f"📍 {text}"
            else:
                button_text = text
            
            builder.button(text=button_text, callback_data=callback)
        
        builder.adjust(3, 2, 1)
        return builder.as_markup()
    
    @staticmethod
    def create_action_buttons_inline(
        actions: List[Tuple[str, str, bool]],
        include_back: bool = True,
        back_callback: str = "back"
    ) -> InlineKeyboardMarkup:
        """
        Создает inline-клавиатуру с кнопками действий.
        
        Args:
            actions: Список кортежей (текст, callback_data, enabled)
            include_back: Добавить ли кнопку "Назад"
            back_callback: Callback для кнопки "Назад"
            
        Returns:
            InlineKeyboardMarkup с кнопками действий
        """
        builder = InlineKeyboardBuilder()
        
        for text, callback, enabled in actions:
            if enabled:
                builder.button(text=text, callback_data=callback)
            else:
                # Неактивная кнопка (можно показать серой или с другим callback)
                builder.button(text=f"❌ {text}", callback_data="noop")
        
        if include_back:
            builder.button(text="🔙 Назад", callback_data=back_callback)
        
        builder.adjust(2)
        return builder.as_markup()
    
    @staticmethod
    def create_quick_links_inline(
        links: List[Tuple[str, str, str]],
        include_refresh: bool = True,
        refresh_callback: str = "refresh"
    ) -> InlineKeyboardMarkup:
        """
        Создает inline-клавиатуру с быстрыми ссылками.
        
        Args:
            links: Список кортежей (эмодзи, текст, callback_data)
            include_refresh: Добавить ли кнопку "Обновить"
            refresh_callback: Callback для кнопки "Обновить"
            
        Returns:
            InlineKeyboardMarkup с быстрыми ссылками
        """
        builder = InlineKeyboardBuilder()
        
        for emoji, text, callback in links:
            builder.button(text=f"{emoji} {text}", callback_data=callback)
        
        if include_refresh:
            builder.button(text="🔄 Обновить", callback_data=refresh_callback)
        
        builder.adjust(2)
        return builder.as_markup()
    
    @staticmethod
    def create_file_actions_inline(
        file_id: str,
        has_file: bool = True,
        can_edit: bool = False,
        can_delete: bool = False
    ) -> InlineKeyboardMarkup:
        """
        Создает inline-клавиатуру действий с файлом.
        
        Args:
            file_id: ID файла
            has_file: Есть ли файл
            can_edit: Можно ли редактировать
            can_delete: Можно ли удалить
            
        Returns:
            InlineKeyboardMarkup с действиями для файла
        """
        builder = InlineKeyboardBuilder()
        
        if has_file:
            builder.button(text="📥 Скачать", callback_data=f"file_download:{file_id}")
            builder.button(text="👁️ Просмотреть", callback_data=f"file_view:{file_id}")
        
        if can_edit:
            builder.button(text="✏️ Редактировать", callback_data=f"file_edit:{file_id}")
        
        if can_delete:
            builder.button(text="🗑️ Удалить", callback_data=f"file_delete:{file_id}")
        
        builder.button(text="🔙 Назад", callback_data="file_back")
        
        builder.adjust(2)
        return builder.as_markup()