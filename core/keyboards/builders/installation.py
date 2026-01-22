from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Optional


def create_installation_main_keyboard(installation_objects: List = None) -> InlineKeyboardBuilder:
    """Создает основную клавиатуру монтажа"""
    builder = InlineKeyboardBuilder()
    
    # Кнопка создания нового объекта
    builder.button(text="🏗️ Создать", callback_data="create_installation")
    
    if installation_objects:
        # Кнопки существующих объектов
        for obj in installation_objects:
            builder.button(
                text=f"📁 {obj.short_name}",
                callback_data=f"installation_object_{obj.id}"
            )
    
    # Кнопка назад (если вызвано из другого меню)
    builder.button(text="◀️ Назад", callback_data="back_to_main")
    
    builder.adjust(1)  # По одной кнопке в ряд
    return builder


def create_installation_object_panel_keyboard(object_id: str) -> InlineKeyboardBuilder:
    """Создает клавиатуру панели объекта монтажа"""
    builder = InlineKeyboardBuilder()
    
    # Основные кнопки управления объектом согласно ТЗ
    builder.button(text="📁 Проекты", callback_data=f"projects_{object_id}")
    builder.button(text="📦 Поставки", callback_data=f"supplies_{object_id}")
    builder.button(text="📦 Материалы", callback_data=f"materials_{object_id}")
    builder.button(text="🔨 Монтаж", callback_data=f"montage_{object_id}")
    builder.button(text="📝 Изменения", callback_data=f"changes_{object_id}")
    builder.button(text="✉️ Письма", callback_data=f"letters_{object_id}")
    builder.button(text="🎫 Допуски", callback_data=f"permits_{object_id}")
    builder.button(text="📓 Журналы", callback_data=f"journals_{object_id}")
    builder.button(text="📄 ИД", callback_data=f"id_docs_{object_id}")
    builder.button(text="⏰ Напоминания", callback_data=f"reminders_{object_id}")
    
    # Кнопки управления (только для админов)
    builder.button(text="✏️ Изменить", callback_data=f"edit_installation_{object_id}")
    builder.button(text="🗑️ Удалить", callback_data=f"delete_installation_{object_id}")
    
    # Кнопка назад
    builder.button(text="◀️ Назад", callback_data="back_to_installation_main")
    
    builder.adjust(2, 2, 2, 2, 2, 2)  # Группируем по 2 кнопки в ряд
    return builder


def create_projects_keyboard(object_id: str, projects: List = None) -> InlineKeyboardBuilder:
    """Создает клавиатуру для управления проектами"""
    builder = InlineKeyboardBuilder()
    
    # Кнопки добавления/управления проектами
    builder.button(text="➕ Добавить", callback_data=f"add_project_{object_id}")
    
    if projects:
        # Кнопки существующих проектов
        for i, project in enumerate(projects, 1):
            builder.button(
                text=f"{i}️⃣ {project.name[:20]}",
                callback_data=f"project_{project.id}"
            )
    
    # Кнопки управления
    builder.button(text="✏️ Изменить", callback_data=f"edit_projects_{object_id}")
    builder.button(text="🗑️ Удалить", callback_data=f"delete_projects_{object_id}")
    builder.button(text="👁️ Показать", callback_data=f"show_projects_{object_id}")
    
    # Кнопка назад
    builder.button(text="◀️ Назад", callback_data=f"installation_object_{object_id}")
    
    builder.adjust(1, 2, 1)  # Настраиваем расположение
    return builder


def create_materials_keyboard(object_id: str, materials: List = None) -> InlineKeyboardBuilder:
    """Создает клавиатуру для управления материалами"""
    builder = InlineKeyboardBuilder()
    
    # Основные кнопки
    builder.button(text="📦 Общее", callback_data=f"materials_general_{object_id}")
    builder.button(text="➕ Добавить", callback_data=f"add_material_{object_id}")
    
    if materials:
        # Если есть разделы, показываем их
        sections = list(set([m.section for m in materials if m.section]))
        
        if sections:
            builder.button(text="📂 Разделы", callback_data=f"material_sections_{object_id}")
            
            for section in sections[:5]:  # Показываем до 5 разделов
                builder.button(
                    text=f"📁 {section[:15]}",
                    callback_data=f"material_section_{object_id}_{section}"
                )
    
    # Кнопки управления
    builder.button(text="✏️ Изменить", callback_data=f"edit_materials_{object_id}")
    builder.button(text="🗑️ Удалить", callback_data=f"delete_materials_{object_id}")
    
    # Кнопка назад
    builder.button(text="◀️ Назад", callback_data=f"installation_object_{object_id}")
    
    builder.adjust(2, 2, 1)  # Настраиваем расположение
    return builder


def create_montage_keyboard(object_id: str, sections: List[str] = None) -> InlineKeyboardBuilder:
    """Создает клавиатуру для учета монтажа"""
    builder = InlineKeyboardBuilder()
    
    if sections:
        # Кнопки разделов для монтажа
        for section in sections:
            builder.button(
                text=f"🔨 {section[:15]}",
                callback_data=f"montage_section_{object_id}_{section}"
            )
    else:
        builder.button(text="🔨 Общее", callback_data=f"montage_general_{object_id}")
    
    # Кнопка для команды !монтаж
    builder.button(text="⚡ Быстрый монтаж", callback_data=f"quick_montage_{object_id}")
    
    # Кнопка назад
    builder.button(text="◀️ Назад", callback_data=f"installation_object_{object_id}")
    
    builder.adjust(1)  # По одной кнопке в ряд
    return builder


def create_supplies_keyboard(object_id: str) -> InlineKeyboardBuilder:
    """Создает клавиатуру для управления поставками"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="🚚 Добавить поставку", callback_data=f"add_supply_{object_id}")
    builder.button(text="📋 Список поставок", callback_data=f"list_supplies_{object_id}")
    
    # Кнопки управления (для админов)
    builder.button(text="✏️ Изменить", callback_data=f"edit_supplies_{object_id}")
    builder.button(text="🗑️ Удалить", callback_data=f"delete_supplies_{object_id}")
    
    builder.button(text="◀️ Назад", callback_data=f"installation_object_{object_id}")
    
    builder.adjust(2, 2, 1)
    return builder


def create_changes_keyboard(object_id: str) -> InlineKeyboardBuilder:
    """Создает клавиатуру для изменений"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="📝 Добавить изменение", callback_data=f"add_change_{object_id}")
    builder.button(text="📋 Список изменений", callback_data=f"list_changes_{object_id}")
    
    # Кнопка для команды !изменения
    builder.button(text="⚡ Быстрые изменения", callback_data=f"quick_changes_{object_id}")
    
    builder.button(text="◀️ Назад", callback_data=f"installation_object_{object_id}")
    
    builder.adjust(1)  # По одной кнопке в ряд
    return builder


def create_letters_keyboard(object_id: str) -> InlineKeyboardBuilder:
    """Создает клавиатуру для писем"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="✉️ Добавить письмо", callback_data=f"add_letter_{object_id}")
    builder.button(text="📋 Список писем", callback_data=f"list_letters_{object_id}")
    
    builder.button(text="◀️ Назад", callback_data=f"installation_object_{object_id}")
    
    builder.adjust(1)  # По одной кнопке в ряд
    return builder


def create_confirmation_keyboard(action: str, item_id: str) -> InlineKeyboardBuilder:
    """Создает клавиатуру подтверждения удаления"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="✅ Да", callback_data=f"confirm_{action}_{item_id}")
    builder.button(text="❌ Нет", callback_data=f"cancel_{action}_{item_id}")
    
    builder.adjust(2)
    return builder