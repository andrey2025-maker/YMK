from typing import List, Optional
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from storage.models.service import ServiceRegion, ServiceObject


async def create_service_main_keyboard(
    regions: List[ServiceRegion],
    is_admin: bool = False
) -> InlineKeyboardMarkup:
    """
    Создание основной клавиатуры обслуживания
    
    Args:
        regions: Список регионов
        is_admin: Является ли пользователь админом
    
    Returns:
        InlineKeyboardMarkup: Клавиатура
    """
    builder = InlineKeyboardBuilder()
    
    # Кнопка создания региона (только для админов)
    if is_admin:
        builder.button(
            text="🏗️ Создать",
            callback_data="service:create_region"
        )
    
    # Кнопки существующих регионов
    for region in regions:
        builder.button(
            text=f"📍 {region.short_name}",
            callback_data=f"service:region:{region.id}"
        )
    
    # Кнопка "Назад" (если нужно вернуться к главному меню)
    builder.button(
        text="🔙 Назад",
        callback_data="main_menu"
    )
    
    # Настройка сетки (2 кнопки в ряду)
    builder.adjust(1 if is_admin else 0, 2, 1)
    
    return builder.as_markup()


async def create_region_keyboard(
    region: ServiceRegion,
    objects: List[ServiceObject],
    is_admin: bool = False
) -> InlineKeyboardMarkup:
    """
    Создание клавиатуры для региона
    
    Args:
        region: Регион
        objects: Список объектов в регионе
        is_admin: Является ли пользователь админом
    
    Returns:
        InlineKeyboardMarkup: Клавиатура
    """
    builder = InlineKeyboardBuilder()
    
    # Кнопка создания объекта (только для админов)
    if is_admin:
        builder.button(
            text="🏢 Создать объект",
            callback_data=f"service:create_object:{region.id}"
        )
    
    # Кнопки существующих объектов
    for obj in objects:
        builder.button(
            text=f"🏢 {obj.short_name}",
            callback_data=f"service:object:{obj.id}"
        )
    
    # Кнопки навигации
    builder.button(
        text="🔙 Назад к регионам",
        callback_data="service:back_to_regions"
    )
    
    builder.button(
        text="🏠 В главное меню",
        callback_data="main_menu"
    )
    
    # Настройка сетки
    builder.adjust(1 if is_admin else 0, 2, 2)
    
    return builder.as_markup()


async def create_object_panel_keyboard(
    object_id: str,
    has_problems: bool = False,
    has_maintenance: bool = False,
    has_equipment: bool = False,
    is_admin: bool = False
) -> InlineKeyboardMarkup:
    """
    Создание панели объекта обслуживания
    
    Args:
        object_id: ID объекта
        has_problems: Есть ли проблемы
        has_maintenance: Есть ли ТО
        has_equipment: Есть ли оборудование
        is_admin: Является ли пользователь админом
    
    Returns:
        InlineKeyboardMarkup: Клавиатура
    """
    builder = InlineKeyboardBuilder()
    
    # Основные кнопки
    buttons = [
        ("🔧 ТО", f"service:object:{object_id}:maintenance"),
        ("⚠️ Проблемы", f"service:object:{object_id}:problems"),
        ("🛠️ Оборудование", f"service:object:{object_id}:equipment"),
        ("📄 Письма", f"service:object:{object_id}:letters"),
        ("📋 Напоминания", f"service:object:{object_id}:reminders"),
        ("📝 Журналы", f"service:object:{object_id}:journals"),
        ("📑 Допуски", f"service:object:{object_id}:permits"),
        ("📎 Акты", f"service:object:{object_id}:acts"),
        ("✏️ Изменить", f"service:object:{object_id}:edit"),
        ("🗑️ Удалить", f"service:object:{object_id}:delete")
    ]
    
    for text, callback in buttons:
        # Для кнопок удаления/изменения проверяем права
        if callback.endswith(":edit") or callback.endswith(":delete"):
            if is_admin:
                builder.button(text=text, callback_data=callback)
        else:
            builder.button(text=text, callback_data=callback)
    
    # Кнопка "Назад"
    builder.button(text="🔙 Назад", callback_data="service:back_to_region")
    
    # Настройка сетки (3 кнопки в ряду)
    builder.adjust(3, 3, 3, 1)
    
    return builder.as_markup()


async def create_problems_keyboard(
    object_id: str,
    problems_count: int,
    is_admin: bool = False
) -> InlineKeyboardMarkup:
    """
    Создание клавиатуры для работы с проблемами
    
    Args:
        object_id: ID объекта
        problems_count: Количество проблем
        is_admin: Является ли пользователь админом
    
    Returns:
        InlineKeyboardMarkup: Клавиатура
    """
    builder = InlineKeyboardBuilder()
    
    if is_admin:
        # Кнопки управления для админа
        builder.button(
            text="➕ Добавить",
            callback_data=f"service:object:{object_id}:add_problem"
        )
        
        if problems_count > 0:
            builder.button(
                text="🗑️ Удалить",
                callback_data=f"service:object:{object_id}:delete_problem"
            )
    
    # Кнопки навигации по проблемам (если их много)
    if problems_count > 10:
        builder.button(text="◀️", callback_data=f"service:object:{object_id}:problems:prev")
        builder.button(text="▶️", callback_data=f"service:object:{object_id}:problems:next")
    
    # Кнопка назад
    builder.button(
        text="🔙 Назад к объекту",
        callback_data=f"service:object:{object_id}:back"
    )
    
    # Настройка сетки
    if problems_count > 0 and is_admin:
        builder.adjust(2, 2, 1)
    else:
        builder.adjust(1, 1)
    
    return builder.as_markup()


async def create_maintenance_keyboard(
    object_id: str,
    maintenance_count: int,
    is_admin: bool = False
) -> InlineKeyboardMarkup:
    """
    Создание клавиатуры для работы с ТО
    
    Args:
        object_id: ID объекта
        maintenance_count: Количество ТО
        is_admin: Является ли пользователь админом
    
    Returns:
        InlineKeyboardMarkup: Клавиатура
    """
    builder = InlineKeyboardBuilder()
    
    if is_admin:
        # Кнопки управления для админа
        builder.button(
            text="➕ Добавить ТО",
            callback_data=f"service:object:{object_id}:add_maintenance"
        )
        
        if maintenance_count > 0:
            builder.button(
                text="🗑️ Удалить ТО",
                callback_data=f"service:object:{object_id}:delete_maintenance"
            )
    
    # Кнопка установки ответственного
    builder.button(
        text="👤 Ответственный",
        callback_data=f"service:object:{object_id}:set_responsible"
    )
    
    # Кнопка назад
    builder.button(
        text="🔙 Назад к объекту",
        callback_data=f"service:object:{object_id}:back"
    )
    
    # Настройка сетки
    if is_admin:
        builder.adjust(2, 1, 1)
    else:
        builder.adjust(1, 1)
    
    return builder.as_markup()


async def create_equipment_keyboard(
    object_id: str,
    addresses_count: int,
    equipment_count: int,
    is_admin: bool = False
) -> InlineKeyboardMarkup:
    """
    Создание клавиатуры для работы с оборудованием
    
    Args:
        object_id: ID объекта
        addresses_count: Количество адресов
        equipment_count: Количество оборудования
        is_admin: Является ли пользователь админом
    
    Returns:
        InlineKeyboardMarkup: Клавиатура
    """
    builder = InlineKeyboardBuilder()
    
    if is_admin:
        # Кнопки управления для админа
        builder.button(
            text="➕ Добавить",
            callback_data=f"service:object:{object_id}:add_equipment"
        )
        
        if equipment_count > 0:
            builder.button(
                text="✏️ Изменить",
                callback_data=f"service:object:{object_id}:edit_equipment"
            )
            builder.button(
                text="🗑️ Удалить",
                callback_data=f"service:object:{object_id}:delete_equipment"
            )
    
    # Кнопки выбора адреса (если несколько адресов)
    if addresses_count > 1:
        for i in range(addresses_count):
            builder.button(
                text=f"📍 Адрес {i+1}",
                callback_data=f"service:object:{object_id}:equipment:address:{i}"
            )
    
    # Кнопка экспорта
    builder.button(
        text="📊 Экспорт в Excel",
        callback_data=f"service:object:{object_id}:export_equipment"
    )
    
    # Кнопка назад
    builder.button(
        text="🔙 Назад к объекту",
        callback_data=f"service:object:{object_id}:back"
    )
    
    # Настройка сетки
    rows = []
    if is_admin:
        rows.append(3 if equipment_count > 0 else 1)
    if addresses_count > 1:
        rows.append(min(addresses_count, 3))
    rows.append(1)
    rows.append(1)
    
    builder.adjust(*rows)
    
    return builder.as_markup()


async def create_pagination_keyboard(
    current_page: int,
    total_pages: int,
    prefix: str,
    object_id: Optional[str] = None
) -> InlineKeyboardMarkup:
    """
    Создание клавиатуры пагинации
    
    Args:
        current_page: Текущая страница
        total_pages: Всего страниц
        prefix: Префикс для callback_data
        object_id: ID объекта (опционально)
    
    Returns:
        InlineKeyboardMarkup: Клавиатура пагинации
    """
    builder = InlineKeyboardBuilder()
    
    # Кнопки навигации
    if current_page > 1:
        builder.button(
            text="◀️ Назад",
            callback_data=f"{prefix}:page:{current_page-1}:{object_id}" if object_id else f"{prefix}:page:{current_page-1}"
        )
    
    builder.button(
        text=f"{current_page}/{total_pages}",
        callback_data="no_action"
    )
    
    if current_page < total_pages:
        builder.button(
            text="Далее ▶️",
            callback_data=f"{prefix}:page:{current_page+1}:{object_id}" if object_id else f"{prefix}:page:{current_page+1}"
        )
    
    # Кнопка возврата
    if object_id:
        builder.button(
            text="🔙 Назад",
            callback_data=f"service:object:{object_id}:back"
        )
    else:
        builder.button(
            text="🔙 Назад",
            callback_data="service:back_to_regions"
        )
    
    # Настройка сетки
    if current_page > 1 and current_page < total_pages:
        builder.adjust(3, 1)
    else:
        builder.adjust(2, 1)
    
    return builder.as_markup()