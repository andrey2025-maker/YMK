"""
Модуль для создания клавиатур пагинации.
Пагинация с TTL для Redis кэша и поддержкой навигации.
"""

from typing import List, Any, Dict, Optional
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from structlog import get_logger

logger = get_logger(__name__)


class Paginator:
    """Класс для управления пагинацией с кэшированием в Redis"""
    
    def __init__(self, cache_manager=None):
        """
        Инициализирует пагинатор.
        
        Args:
            cache_manager: Менеджер кэша Redis (опционально)
        """
        self.cache = cache_manager
        self.default_page_size = 10  # По ТЗ: не больше 10 на страницу
    
    async def create_paginated_keyboard(
        self,
        items: List[Any],
        page: int = 1,
        page_size: int = None,
        callback_prefix: str = "page",
        item_callback_prefix: str = "item",
        include_navigation: bool = True,
        custom_buttons: List[InlineKeyboardButton] = None,
        cache_key: str = None,
        cache_ttl: int = 300  # 5 минут по ТЗ
    ) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру с пагинацией.
        
        Args:
            items: Список элементов для отображения
            page: Текущая страница
            page_size: Количество элементов на странице
            callback_prefix: Префикс для callback кнопок пагинации
            item_callback_prefix: Префикс для callback кнопок элементов
            include_navigation: Включать ли кнопки навигации
            custom_buttons: Дополнительные кнопки
            cache_key: Ключ для кэширования (если нужен)
            cache_ttl: Время жизни кэша в секундах
            
        Returns:
            InlineKeyboardMarkup с пагинацией
        """
        builder = InlineKeyboardBuilder()
        
        # Используем дефолтный размер страницы если не указан
        if page_size is None:
            page_size = self.default_page_size
        
        # Рассчитываем общее количество страниц
        total_items = len(items)
        total_pages = (total_items + page_size - 1) // page_size
        
        # Корректируем номер страницы
        if page < 1:
            page = 1
        elif page > total_pages and total_pages > 0:
            page = total_pages
        
        # Получаем элементы для текущей страницы
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_items = items[start_idx:end_idx]
        
        # Создаем кнопки для элементов
        for idx, item in enumerate(page_items, start=1):
            item_number = start_idx + idx
            button_text = self._format_item_button(item, item_number)
            callback_data = f"{item_callback_prefix}:{self._get_item_id(item)}"
            
            builder.button(
                text=button_text,
                callback_data=callback_data
            )
        
        builder.adjust(1)  # По одной кнопке в строке
        
        # Добавляем кнопки навигации если нужно
        if include_navigation and total_pages > 1:
            await self._add_navigation_buttons(
                builder=builder,
                page=page,
                total_pages=total_pages,
                callback_prefix=callback_prefix,
                cache_key=cache_key
            )
        
        # Добавляем пользовательские кнопки
        if custom_buttons:
            for button in custom_buttons:
                builder.add(button)
        
        # Кэшируем данные если указан ключ
        if cache_key and self.cache:
            await self._cache_pagination_data(
                cache_key=cache_key,
                items=items,
                page=page,
                ttl=cache_ttl
            )
        
        return builder.as_markup()
    
    async def _add_navigation_buttons(
        self,
        builder: InlineKeyboardBuilder,
        page: int,
        total_pages: int,
        callback_prefix: str,
        cache_key: str = None
    ) -> None:
        """
        Добавляет кнопки навигации пагинации.
        
        Args:
            builder: InlineKeyboardBuilder
            page: Текущая страница
            total_pages: Всего страниц
            callback_prefix: Префикс callback
            cache_key: Ключ кэша для передачи в callback
        """
        navigation_buttons = []
        
        # Кнопка "Назад" (только если не на первой странице)
        if page > 1:
            nav_data = f"{callback_prefix}:{page-1}"
            if cache_key:
                nav_data = f"{nav_data}:{cache_key}"
            navigation_buttons.append(
                InlineKeyboardButton(text="◀ Назад", callback_data=nav_data)
            )
        
        # Текст с номером страницы
        navigation_buttons.append(
            InlineKeyboardButton(
                text=f"📄 {page}/{total_pages}",
                callback_data="noop"  # Не делает ничего
            )
        )
        
        # Кнопка "Далее" (только если не на последней странице)
        if page < total_pages:
            nav_data = f"{callback_prefix}:{page+1}"
            if cache_key:
                nav_data = f"{nav_data}:{cache_key}"
            navigation_buttons.append(
                InlineKeyboardButton(text="Далее ▶", callback_data=nav_data)
            )
        
        # Добавляем кнопки навигации
        for button in navigation_buttons:
            builder.add(button)
        
        builder.adjust(3)  # 3 кнопки в строке для навигации
    
    def _format_item_button(self, item: Any, number: int) -> str:
        """
        Форматирует текст кнопки элемента.
        
        Args:
            item: Элемент для отображения
            number: Порядковый номер
            
        Returns:
            Форматированный текст кнопки
        """
        # Базовый формат
        if isinstance(item, dict):
            if 'name' in item:
                return f"{number}. {item['name']}"
            elif 'title' in item:
                return f"{number}. {item['title']}"
        
        elif hasattr(item, 'name'):
            return f"{number}. {item.name}"
        elif hasattr(item, 'title'):
            return f"{number}. {item.title}"
        
        return f"{number}. {str(item)[:30]}"
    
    def _get_item_id(self, item: Any) -> str:
        """
        Извлекает ID из элемента.
        
        Args:
            item: Элемент
            
        Returns:
            ID элемента в виде строки
        """
        if isinstance(item, dict):
            return str(item.get('id', id(item)))
        elif hasattr(item, 'id'):
            return str(item.id)
        else:
            return str(id(item))
    
    async def _cache_pagination_data(
        self,
        cache_key: str,
        items: List[Any],
        page: int,
        ttl: int
    ) -> None:
        """
        Кэширует данные пагинации.
        
        Args:
            cache_key: Ключ кэша
            items: Список элементов
            page: Текущая страница
            ttl: Время жизни кэша
        """
        try:
            if self.cache:
                cache_data = {
                    'items': items,
                    'page': page,
                    'timestamp': self._get_timestamp()
                }
                await self.cache.set(cache_key, cache_data, ex=ttl)
        except Exception as e:
            logger.error("pagination_cache_failed", error=str(e))
    
    async def get_cached_page(
        self,
        cache_key: str,
        new_page: int
    ) -> Optional[Dict]:
        """
        Получает кэшированные данные пагинации.
        
        Args:
            cache_key: Ключ кэша
            new_page: Новая страница
            
        Returns:
            Кэшированные данные или None
        """
        try:
            if self.cache:
                cached = await self.cache.get(cache_key)
                if cached:
                    cached['page'] = new_page
                    return cached
        except Exception as e:
            logger.error("get_cached_page_failed", error=str(e))
        
        return None
    
    def _get_timestamp(self) -> str:
        """Возвращает текущую метку времени."""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def create_simple_pagination(
        self,
        current_page: int,
        total_pages: int,
        callback_prefix: str = "paginate"
    ) -> InlineKeyboardMarkup:
        """
        Создает простую клавиатуру пагинации.
        
        Args:
            current_page: Текущая страница
            total_pages: Всего страниц
            callback_prefix: Префикс callback
            
        Returns:
            InlineKeyboardMarkup
        """
        builder = InlineKeyboardBuilder()
        
        if current_page > 1:
            builder.button(
                text="◀ Предыдущая",
                callback_data=f"{callback_prefix}:{current_page-1}"
            )
        
        builder.button(
            text=f"{current_page}/{total_pages}",
            callback_data="noop"
        )
        
        if current_page < total_pages:
            builder.button(
                text="Следующая ▶",
                callback_data=f"{callback_prefix}:{current_page+1}"
            )
        
        builder.adjust(3)
        return builder.as_markup()
    
    async def create_search_results_keyboard(
        self,
        results: List[Dict],
        search_query: str,
        page: int = 1,
        cache_key: str = None
    ) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру для результатов поиска (по ТЗ).
        
        Args:
            results: Результаты поиска
            search_query: Поисковый запрос
            page: Текущая страница
            cache_key: Ключ для кэширования
            
        Returns:
            InlineKeyboardMarkup
        """
        # По ТЗ: не больше 10 на страницу
        keyboard = await self.create_paginated_keyboard(
            items=results,
            page=page,
            page_size=10,
            callback_prefix="search_page",
            item_callback_prefix="search_result",
            include_navigation=True,
            cache_key=cache_key or f"search:{search_query}",
            cache_ttl=600  # 10 минут для поиска
        )
        
        return keyboard


# Создаем экземпляр пагинатора для использования в других модулях
paginator = Paginator()