"""
Модуль для динамического построения клавиатур на основе данных.
Создает клавиатуры для регионов, объектов, материалов и других сущностей.
"""
from typing import List, Dict, Any, Optional, Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from storage.cache.manager import CacheManager
from core.context import AppContext
from utils.paginator import Paginator


class DynamicKeyboardBuilder:
    """Построитель динамических клавиатур на основе данных."""
    
    def __init__(self, context: AppContext):
        self.context = context
        self.cache = context.cache
    
    async def create_service_regions_keyboard(
        self, 
        user_id: int,
        include_create: bool = True,
        page: int = 0
    ) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру регионов обслуживания.
        
        Args:
            user_id: ID пользователя
            include_create: Добавлять кнопку "Создать"
            page: Номер страницы
            
        Returns:
            InlineKeyboardMarkup с регионами
        """
        # Получаем регионы из кэша или БД
        cache_key = f"service_regions:{user_id}:{page}"
        cached = await self.cache.get(cache_key)
        
        if cached:
            return cached
        
        # Получаем регионы из БД
        from modules.service.region_manager import ServiceRegionManager
        region_manager = ServiceRegionManager(self.context)
        regions = await region_manager.get_user_regions(user_id)
        
        builder = InlineKeyboardBuilder()
        
        # Создаем кнопки для регионов (сокращенные названия)
        for region in regions:
            short_name = region.short_name
            region_id = str(region.id)
            builder.button(text=short_name, callback_data=f"service_region:{region_id}")
        
        if include_create:
            builder.button(text="➕ Создать регион", callback_data="service_create_region")
        
        builder.button(text="🔙 Назад", callback_data="service_back")
        
        # Применяем пагинацию если регионов много
        if len(regions) > 10:
            paginator = Paginator(self.cache)
            paginated_keyboard = await paginator.create_paginated_keyboard(
                items=[(r.short_name, f"service_region:{r.id}") for r in regions],
                page=page,
                page_size=10,
                prefix="service_regions"
            )
            
            # Кэшируем результат
            await self.cache.set(cache_key, paginated_keyboard, ttl=600)  # 10 минут
            return paginated_keyboard
        
        builder.adjust(1)
        keyboard = builder.as_markup()
        
        # Кэшируем результат
        await self.cache.set(cache_key, keyboard, ttl=600)  # 10 минут
        return keyboard
    
    async def create_service_objects_keyboard(
        self, 
        region_id: str,
        user_id: int,
        include_create: bool = True,
        page: int = 0
    ) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру объектов обслуживания в регионе.
        
        Args:
            region_id: ID региона
            user_id: ID пользователя
            include_create: Добавлять кнопку "Создать"
            page: Номер страницы
            
        Returns:
            InlineKeyboardMarkup с объектами
        """
        cache_key = f"service_objects:{region_id}:{user_id}:{page}"
        cached = await self.cache.get(cache_key)
        
        if cached:
            return cached
        
        # Получаем объекты из БД
        from modules.service.object_manager import ServiceObjectManager
        object_manager = ServiceObjectManager(self.context)
        objects = await object_manager.get_region_objects(region_id, user_id)
        
        builder = InlineKeyboardBuilder()
        
        # Создаем кнопки для объектов
        for obj in objects:
            short_name = obj.short_name
            obj_id = str(obj.id)
            builder.button(text=short_name, callback_data=f"service_object:{obj_id}")
        
        if include_create:
            builder.button(text="➕ Создать объект", callback_data=f"service_create_object:{region_id}")
        
        builder.button(text="🔙 К регионам", callback_data="service_back_to_regions")
        
        # Пагинация
        if len(objects) > 10:
            paginator = Paginator(self.cache)
            paginated_keyboard = await paginator.create_paginated_keyboard(
                items=[(obj.short_name, f"service_object:{obj.id}") for obj in objects],
                page=page,
                page_size=10,
                prefix=f"service_objects_{region_id}"
            )
            
            await self.cache.set(cache_key, paginated_keyboard, ttl=600)
            return paginated_keyboard
        
        builder.adjust(1)
        keyboard = builder.as_markup()
        
        await self.cache.set(cache_key, keyboard, ttl=600)
        return keyboard
    
    async def create_installation_objects_keyboard(
        self,
        user_id: int,
        include_create: bool = True,
        page: int = 0
    ) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру объектов монтажа.
        
        Args:
            user_id: ID пользователя
            include_create: Добавлять кнопку "Создать"
            page: Номер страницы
            
        Returns:
            InlineKeyboardMarkup с объектами монтажа
        """
        cache_key = f"installation_objects:{user_id}:{page}"
        cached = await self.cache.get(cache_key)
        
        if cached:
            return cached
        
        # Получаем объекты из БД
        from modules.installation.object_manager import InstallationObjectManager
        object_manager = InstallationObjectManager(self.context)
        objects = await object_manager.get_user_objects(user_id)
        
        builder = InlineKeyboardBuilder()
        
        # Кнопки для объектов
        for obj in objects:
            short_name = obj.short_name
            obj_id = str(obj.id)
            builder.button(text=short_name, callback_data=f"installation_object:{obj_id}")
        
        if include_create:
            builder.button(text="➕ Создать объект", callback_data="installation_create_object")
        
        builder.button(text="🔙 Назад", callback_data="installation_back")
        
        # Пагинация
        if len(objects) > 10:
            paginator = Paginator(self.cache)
            paginated_keyboard = await paginator.create_paginated_keyboard(
                items=[(obj.short_name, f"installation_object:{obj.id}") for obj in objects],
                page=page,
                page_size=10,
                prefix="installation_objects"
            )
            
            await self.cache.set(cache_key, paginated_keyboard, ttl=600)
            return paginated_keyboard
        
        builder.adjust(1)
        keyboard = builder.as_markup()
        
        await self.cache.set(cache_key, keyboard, ttl=600)
        return keyboard
    
    async def create_object_panel_keyboard(
        self,
        object_type: str,  # "service" или "installation"
        object_id: str,
        user_role: str,
        user_id: int
    ) -> InlineKeyboardMarkup:
        """
        Создает панель управления объектом.
        
        Args:
            object_type: Тип объекта
            object_id: ID объекта
            user_role: Роль пользователя
            user_id: ID пользователя
            
        Returns:
            InlineKeyboardMarkup с панелью объекта
        """
        cache_key = f"object_panel:{object_type}:{object_id}:{user_id}"
        cached = await self.cache.get(cache_key)
        
        if cached:
            return cached
        
        builder = InlineKeyboardBuilder()
        
        # Базовые кнопки для всех
        builder.button(text="📋 Проблемы", callback_data=f"{object_type}_problems:{object_id}")
        builder.button(text="🔧 ТО", callback_data=f"{object_type}_maintenance:{object_id}")
        builder.button(text="📨 Письма", callback_data=f"{object_type}_letters:{object_id}")
        builder.button(text="📒 Журналы", callback_data=f"{object_type}_journals:{object_id}")
        builder.button(text="✅ Допуски", callback_data=f"{object_type}_permits:{object_id}")
        
        if object_type == "service":
            builder.button(text="🛠️ Оборудование", callback_data=f"service_equipment:{object_id}")
        else:
            builder.button(text="📁 Проекты", callback_data=f"installation_projects:{object_id}")
            builder.button(text="📦 Материалы", callback_data=f"installation_materials:{object_id}")
            builder.button(text="⚡ Монтаж", callback_data=f"installation_montage:{object_id}")
            builder.button(text="🔄 Изменения", callback_data=f"installation_changes:{object_id}")
            builder.button(text="🚚 Поставки", callback_data=f"installation_supplies:{object_id}")
            builder.button(text="📄 ИД", callback_data=f"installation_id:{object_id}")
        
        builder.button(text="🔔 Напоминания", callback_data=f"{object_type}_reminders:{object_id}")
        
        # Кнопки управления для админов
        if user_role in ["main_admin", "admin"]:
            builder.button(text="✏️ Редактировать", callback_data=f"{object_type}_edit:{object_id}")
            builder.button(text="🗑️ Удалить", callback_data=f"{object_type}_delete:{object_id}")
        
        builder.button(text="🔙 Назад", callback_data=f"{object_type}_back_to_list")
        
        # Настройка расположения кнопок
        if object_type == "service":
            builder.adjust(3, 3, 2, 1)
        else:
            builder.adjust(3, 3, 3, 2, 1)
        
        keyboard = builder.as_markup()
        await self.cache.set(cache_key, keyboard, ttl=300)  # 5 минут
        
        return keyboard
    
    async def create_material_sections_keyboard(
        self,
        installation_id: str,
        include_general: bool = True
    ) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру разделов материалов объекта монтажа.
        
        Args:
            installation_id: ID объекта монтажа
            include_general: Добавлять ли кнопку "Общее"
            
        Returns:
            InlineKeyboardMarkup с разделами материалов
        """
        cache_key = f"material_sections:{installation_id}"
        cached = await self.cache.get(cache_key)
        
        if cached:
            return cached
        
        # Получаем разделы материалов из БД
        from modules.installation.data_managers.material_manager import MaterialManager
        material_manager = MaterialManager(self.context)
        sections = await material_manager.get_material_sections(installation_id)
        
        builder = InlineKeyboardBuilder()
        
        # Добавляем кнопку "Общее" если требуется
        if include_general:
            builder.button(text="📦 Общее", callback_data=f"materials_general:{installation_id}")
        
        # Кнопки для разделов
        for section in sections:
            section_name = section.name
            section_id = str(section.id)
            builder.button(text=section_name, callback_data=f"material_section:{section_id}")
        
        builder.button(text="➕ Добавить раздел", callback_data=f"material_add_section:{installation_id}")
        builder.button(text="🔙 Назад", callback_data=f"installation_materials_back:{installation_id}")
        
        builder.adjust(1)
        keyboard = builder.as_markup()
        
        await self.cache.set(cache_key, keyboard, ttl=300)
        return keyboard
    
    async def create_search_results_keyboard(
        self,
        search_results: List[Dict[str, Any]],
        search_type: str,
        page: int = 0
    ) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру с результатами поиска (не более 10 на страницу).
        
        Args:
            search_results: Результаты поиска
            search_type: Тип поиска (service, installation, etc.)
            page: Номер страницы
            
        Returns:
            InlineKeyboardMarkup с результатами поиска
        """
        builder = InlineKeyboardBuilder()
        
        # Отображаем до 10 результатов на страницу
        items_per_page = 10
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        page_results = search_results[start_idx:end_idx]
        
        for i, result in enumerate(page_results, start=1):
            text = result.get('title', f'Результат {i}')
            action = result.get('action', '')
            result_id = result.get('id', '')
            
            callback_data = f"{search_type}_search_result:{result_id}:{action}"
            builder.button(text=text, callback_data=callback_data)
        
        # Добавляем навигацию если нужно
        if len(search_results) > items_per_page:
            nav_buttons = []
            
            if page > 0:
                nav_buttons.append(InlineKeyboardButton(
                    text="◀️ Назад", 
                    callback_data=f"search_page:{search_type}:{page - 1}"
                ))
            
            total_pages = (len(search_results) + items_per_page - 1) // items_per_page
            page_info = f"{page + 1}/{total_pages}"
            nav_buttons.append(InlineKeyboardButton(text=page_info, callback_data="noop"))
            
            if page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton(
                    text="Далее ▶️", 
                    callback_data=f"search_page:{search_type}:{page + 1}"
                ))
            
            builder.row(*nav_buttons)
        
        builder.button(text="🔙 Назад к поиску", callback_data="search_back")
        
        builder.adjust(1)
        return builder.as_markup()