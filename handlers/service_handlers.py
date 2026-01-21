from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.context import get_app_context
from fsm.service_states import ServiceRegionStates, ServiceObjectStates
from modules.service.region_manager import RegionManager
from modules.service.object_manager import ObjectManager
from core.keyboards.builders.service import (
    create_service_main_keyboard,
    create_region_keyboard,
    create_object_panel_keyboard
)

router = Router(name="service_handlers")

@router.message(Command("обслуживание"))
async def service_command(message: Message, state: FSMContext):
    """Обработка команды !обслуживание"""
    context = get_app_context()
    region_manager = RegionManager(context)
    
    # Получаем все регионы
    regions = await region_manager.get_all_regions()
    
    # Создаем клавиатуру
    keyboard = await create_service_main_keyboard(regions)
    
    text = "🏢 *Обслуживание объектов!*\n\n"
    text += "Для создания нового региона обслуживания нажмите на кнопку «Создать» после Вы сможете создать новый регион и в нем создавать объекты!\n\n"
    
    if regions:
        text += "*Созданные регионы:*\n"
        for region in regions:
            text += f"• {region.short_name} - {region.full_name}\n"
    else:
        text += "Пока нет созданных регионов."
    
    await message.answer(
        text=text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await state.clear()

@router.callback_query(F.data == "service:create_region")
async def create_region_start(callback: CallbackQuery, state: FSMContext):
    """Начало создания региона"""
    await callback.message.edit_text(
        text="🏗️ *Создание нового региона обслуживания!*\n\n"
             "Напишите сокращенное наименование нового региона в чат:",
        parse_mode="Markdown"
    )
    await state.set_state(ServiceRegionStates.waiting_short_name)
    await callback.answer()

@router.message(ServiceRegionStates.waiting_short_name)
async def process_region_short_name(message: Message, state: FSMContext):
    """Обработка короткого имени региона"""
    short_name = message.text.strip()
    
    if len(short_name) > 50:
        await message.answer("❌ Сокращенное название не должно превышать 50 символов.")
        return
    
    await state.update_data(short_name=short_name)
    
    await message.answer(
        text=f"🏗️ *Создание нового региона обслуживания!*\n\n"
             f"Напишите полное наименование нового региона в чат:\n"
             f"*Сокращение:* **{short_name}**",
        parse_mode="Markdown"
    )
    await state.set_state(ServiceRegionStates.waiting_full_name)

@router.message(ServiceRegionStates.waiting_full_name)
async def process_region_full_name(message: Message, state: FSMContext):
    """Обработка полного имени региона"""
    full_name = message.text.strip()
    data = await state.get_data()
    short_name = data.get('short_name')
    
    if len(full_name) > 200:
        await message.answer("❌ Полное название не должно превышать 200 символов.")
        return
    
    context = get_app_context()
    region_manager = RegionManager(context)
    
    try:
        region = await region_manager.create_region(
            short_name=short_name,
            full_name=full_name,
            created_by=message.from_user.id
        )
        
        # Получаем обновленный список регионов
        regions = await region_manager.get_all_regions()
        keyboard = await create_service_main_keyboard(regions)
        
        text = f"✅ *Регион создан!*\n\n"
        text += f"*{region.short_name} - {region.full_name}*\n\n"
        text += "Объекты:\n(Тут будут писаться добавленные объекты)\n"
        
        await message.answer(
            text=text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
    except ValueError as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
    
    await state.clear()

@router.callback_query(F.data.startswith("service:region:"))
async def select_region(callback: CallbackQuery, state: FSMContext):
    """Выбор региона"""
    region_id = callback.data.split(":")[2]
    
    context = get_app_context()
    region_manager = RegionManager(context)
    
    region = await region_manager.get_region_by_id(region_id)
    if not region:
        await callback.answer("❌ Регион не найден")
        return
    
    # Получаем объекты региона
    objects = region.objects if hasattr(region, 'objects') else []
    
    # Создаем клавиатуру для региона
    keyboard = await create_region_keyboard(region, objects)
    
    text = f"🏢 *{region.short_name} - {region.full_name}*\n\n"
    
    if objects:
        text += "*Объекты в регионе:*\n"
        for obj in objects:
            text += f"• {obj.short_name} - {obj.full_name}\n"
    else:
        text += "Пока нет созданных объектов.\n"
    
    text += "\nНажмите 'Создать' для добавления нового объекта."
    
    await callback.message.edit_text(
        text=text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("service:create_object:"))
async def create_object_start(callback: CallbackQuery, state: FSMContext):
    """Начало создания объекта"""
    region_id = callback.data.split(":")[2]
    
    await state.update_data(region_id=region_id, step=1)
    
    await callback.message.edit_text(
        text="🏗️ *Создание нового объекта обслуживания!*\n\n"
             "1️⃣ Напишите сокращенное название объекта:",
        parse_mode="Markdown"
    )
    await state.set_state(ServiceObjectStates.waiting_short_name)
    await callback.answer()

@router.message(ServiceObjectStates.waiting_short_name)
async def process_object_short_name(message: Message, state: FSMContext):
    """Обработка короткого имени объекта"""
    short_name = message.text.strip()
    
    await state.update_data(short_name=short_name)
    
    await message.answer(
        text=f"🏗️ *Создание нового объекта обслуживания!*\n\n"
             f"2️⃣ Напишите полное название объекта:\n"
             f"*Сокращение:* **{short_name}**",
        parse_mode="Markdown"
    )
    await state.set_state(ServiceObjectStates.waiting_full_name)

# Продолжение FSM сценария будет в следующем файле...