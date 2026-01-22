from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging

from core.context import AppContext
from fsm.installation_states import (
    InstallationStates,
    CreateInstallationObjectStates,
    ProjectStates,
    MaterialStates,
    MontageStates
)
from modules.installation.object_manager import InstallationObjectManager
from modules.installation.data_managers.project_manager import ProjectManager
from modules.installation.data_managers.material_manager import MaterialManager
from core.keyboards.builders.installation import (
    create_installation_main_keyboard,
    create_installation_object_panel_keyboard,
    create_projects_keyboard,
    create_materials_keyboard
)
from utils.exceptions import AccessDeniedError, ValidationError

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("монтаж"))
async def installation_command(message: Message, context: AppContext):
    """Основная команда монтажа в личных сообщениях"""
    try:
        installation_manager = context.installation_manager
        user_id = message.from_user.id
        
        # Проверка доступа к монтажу
        if not await installation_manager.has_access(user_id):
            await message.answer("❌ Нет доступа к модулю монтажа")
            return
        
        # Получаем список объектов монтажа
        objects = await installation_manager.get_user_objects(user_id)
        
        # Создаем клавиатуру
        keyboard = create_installation_main_keyboard(objects)
        
        text = "🏗️ *Выполнение работ по монтажу!*\n\n"
        text += "Для создания нового объекта нажмите на кнопку «Создать». "
        text += "После вы сможете создать и настроить новый объект!\n\n"
        
        if objects:
            text += "*Созданные объекты:*\n"
            for obj in objects[:10]:  # Показываем первые 10 объектов
                text += f"• {obj.short_name} - {obj.full_name}\n"
            if len(objects) > 10:
                text += f"\n... и ещё {len(objects) - 10} объектов"
        else:
            text += "Пока нет созданных объектов."
        
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error in installation_command: {e}")
        await message.answer("❌ Произошла ошибка при обработке команды")


@router.callback_query(F.data == "create_installation")
async def start_create_installation_object(callback: CallbackQuery, state: FSMContext):
    """Начало создания объекта монтажа"""
    await callback.answer()
    
    await state.set_state(CreateInstallationObjectStates.SHORT_NAME)
    await callback.message.answer(
        "🏗️ *Создание нового объекта монтажа!*\n\n"
        "1️⃣ Напишите сокращенное название объекта:",
        parse_mode="Markdown"
    )


@router.message(CreateInstallationObjectStates.SHORT_NAME)
async def process_short_name(message: Message, state: FSMContext):
    """Обработка сокращенного названия"""
    short_name = message.text.strip()
    
    # Валидация
    if len(short_name) > 50:
        await message.answer("❌ Сокращенное название не должно превышать 50 символов")
        return
    
    await state.update_data(short_name=short_name)
    await state.set_state(CreateInstallationObjectStates.FULL_NAME)
    
    await message.answer(
        f"2️⃣ Напишите полное название объекта:\n"
        f"*Сокращение:* **{short_name}**",
        parse_mode="Markdown"
    )


@router.message(CreateInstallationObjectStates.FULL_NAME)
async def process_full_name(message: Message, state: FSMContext):
    """Обработка полного названия"""
    full_name = message.text.strip()
    
    # Валидация
    if len(full_name) > 200:
        await message.answer("❌ Полное название не должно превышать 200 символов")
        return
    
    await state.update_data(full_name=full_name)
    await state.set_state(CreateInstallationObjectStates.ADDRESS_COUNT)
    
    await message.answer(
        f"3️⃣ Напишите адрес объекта (если адресов несколько - напишите количество адресов):\n"
        f"*Объект:* **{full_name}**",
        parse_mode="Markdown"
    )


@router.message(CreateInstallationObjectStates.ADDRESS_COUNT)
async def process_address_count(message: Message, state: FSMContext):
    """Обработка количества адресов"""
    try:
        address_count = int(message.text.strip())
        
        if address_count < 1:
            await message.answer("❌ Количество адресов должно быть не менее 1")
            return
        
        if address_count > 10:
            await message.answer("❌ Максимальное количество адресов - 10")
            return
            
        await state.update_data(address_count=address_count, addresses=[], current_address=0)
        
        if address_count == 1:
            await state.set_state(CreateInstallationObjectStates.SINGLE_ADDRESS)
            await message.answer("📍 Напишите адрес объекта:")
        else:
            await state.set_state(CreateInstallationObjectStates.ADDRESSES)
            await message.answer(f"📍 1 адрес из {address_count}. Напишите адрес:")
            
    except ValueError:
        await message.answer("❌ Введите число от 1 до 10")


@router.message(CreateInstallationObjectStates.SINGLE_ADDRESS)
async def process_single_address(message: Message, state: FSMContext):
    """Обработка одного адреса"""
    address = message.text.strip()
    await state.update_data(addresses=[address])
    await state.set_state(CreateInstallationObjectStates.DOCUMENT_TYPE)
    
    await message.answer(
        "4️⃣ Напишите наименование документа (контракт/гос. контракт/договор):"
    )


@router.message(CreateInstallationObjectStates.ADDRESSES)
async def process_addresses(message: Message, state: FSMContext):
    """Обработка нескольких адресов"""
    address = message.text.strip()
    data = await state.get_data()
    
    addresses = data.get('addresses', [])
    addresses.append(address)
    current_address = len(addresses)
    address_count = data['address_count']
    
    await state.update_data(addresses=addresses, current_address=current_address)
    
    if current_address < address_count:
        await message.answer(f"📍 {current_address + 1} адрес из {address_count}. Напишите адрес:")
    else:
        await state.set_state(CreateInstallationObjectStates.DOCUMENT_TYPE)
        await message.answer(
            "4️⃣ Напишите наименование документа (контракт/гос. контракт/договор):"
        )


@router.message(CreateInstallationObjectStates.DOCUMENT_TYPE)
async def process_document_type(message: Message, state: FSMContext):
    """Обработка типа документа"""
    doc_type = message.text.strip()
    
    # Валидация
    valid_types = ["контракт", "гос. контракт", "договор"]
    if doc_type.lower() not in valid_types:
        await message.answer("❌ Укажите: контракт, гос. контракт или договор")
        return
    
    await state.update_data(document_type=doc_type)
    await state.set_state(CreateInstallationObjectStates.CONTRACT_NUMBER)
    
    await message.answer("5️⃣ Напишите номер контракта:")


@router.message(CreateInstallationObjectStates.CONTRACT_NUMBER)
async def process_contract_number(message: Message, state: FSMContext):
    """Обработка номера контракта"""
    contract_number = message.text.strip()
    await state.update_data(contract_number=contract_number)
    await state.set_state(CreateInstallationObjectStates.CONTRACT_DATE)
    
    await message.answer("6️⃣ Напишите дату контракта (ДД.ММ.ГГГГ):")


@router.message(CreateInstallationObjectStates.CONTRACT_DATE)
async def process_contract_date(message: Message, state: FSMContext, context: AppContext):
    """Обработка даты контракта"""
    from utils.date_utils import parse_date, validate_date
    
    date_str = message.text.strip()
    
    try:
        # Валидация формата даты
        if not validate_date(date_str):
            await message.answer("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ")
            return
        
        contract_date = parse_date(date_str)
        await state.update_data(contract_date=contract_date)
        await state.set_state(CreateInstallationObjectStates.START_DATE)
        
        await message.answer("7️⃣ Напишите дату начала исполнения контракта (ДД.ММ.ГГГГ):")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка обработки даты: {e}")


@router.message(CreateInstallationObjectStates.START_DATE)
async def process_start_date(message: Message, state: FSMContext, context: AppContext):
    """Обработка даты начала"""
    from utils.date_utils import parse_date, validate_date
    
    date_str = message.text.strip()
    
    try:
        if not validate_date(date_str):
            await message.answer("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ")
            return
        
        start_date = parse_date(date_str)
        await state.update_data(start_date=start_date)
        await state.set_state(CreateInstallationObjectStates.END_DATE)
        
        await message.answer("8️⃣ Напишите дату окончания исполнения контракта (ДД.ММ.ГГГГ):")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка обработки даты: {e}")


@router.message(CreateInstallationObjectStates.END_DATE)
async def process_end_date(message: Message, state: FSMContext, context: AppContext):
    """Обработка даты окончания"""
    from utils.date_utils import parse_date, validate_date
    
    date_str = message.text.strip()
    
    try:
        if not validate_date(date_str):
            await message.answer("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ")
            return
        
        data = await state.get_data()
        start_date = data.get('start_date')
        end_date = parse_date(date_str)
        
        # Проверка что дата окончания позже даты начала
        if start_date and end_date <= start_date:
            await message.answer("❌ Дата окончания должна быть позже даты начала")
            return
        
        await state.update_data(end_date=end_date)
        await state.set_state(CreateInstallationObjectStates.SYSTEMS)
        
        await message.answer("9️⃣ Напишите монтируемые системы (через запятую или пробел):")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка обработки даты: {e}")


@router.message(CreateInstallationObjectStates.SYSTEMS)
async def process_systems(message: Message, state: FSMContext):
    """Обработка монтируемых систем"""
    systems_text = message.text.strip()
    
    # Разделяем системы
    systems = [s.strip() for s in systems_text.replace(',', ' ').split() if s.strip()]
    
    if not systems:
        await message.answer("❌ Укажите хотя бы одну систему")
        return
    
    await state.update_data(systems=systems)
    await state.set_state(CreateInstallationObjectStates.NOTES)
    
    await message.answer("🔟 Напишите примечание к объекту (можно написать 'нет'):")


@router.message(CreateInstallationObjectStates.NOTES)
async def process_notes(message: Message, state: FSMContext):
    """Обработка примечаний"""
    notes = message.text.strip()
    
    # Если пользователь написал "нет" - очищаем примечания
    if notes.lower() == 'нет':
        notes = None
    
    await state.update_data(notes=notes)
    await state.set_state(CreateInstallationObjectStates.ADDITIONAL_AGREEMENTS_COUNT)
    
    await message.answer(
        "1️⃣1️⃣ Напишите есть ли дополнительные соглашения "
        "(можно написать 'нет' или количество доп. соглашений):"
    )


@router.message(CreateInstallationObjectStates.ADDITIONAL_AGREEMENTS_COUNT)
async def process_additional_agreements_count(
    message: Message, 
    state: FSMContext, 
    context: AppContext
):
    """Обработка количества доп. соглашений"""
    text = message.text.strip().lower()
    
    if text == 'нет':
        # Создаем объект без доп. соглашений
        await complete_installation_object_creation(message, state, context)
        return
    
    try:
        agreement_count = int(text)
        
        if agreement_count < 1:
            await message.answer("❌ Количество должно быть не менее 1")
            return
        
        if agreement_count > 20:
            await message.answer("❌ Максимальное количество доп. соглашений - 20")
            return
            
        await state.update_data(
            additional_agreements_count=agreement_count,
            additional_agreements=[],
            current_agreement=0
        )
        await state.set_state(CreateInstallationObjectStates.ADDITIONAL_AGREEMENT_NAME)
        
        await message.answer(
            "📄 Доп. соглашение 1 из {agreement_count}\n"
            "Название документа:"
        )
        
    except ValueError:
        await message.answer("❌ Введите число или 'нет'")


async def complete_installation_object_creation(
    message: Message,
    state: FSMContext,
    context: AppContext
):
    """Завершение создания объекта монтажа"""
    try:
        data = await state.get_data()
        user_id = message.from_user.id
        
        installation_manager = context.installation_manager
        
        # Создаем объект в БД
        object_id = await installation_manager.create_installation_object(
            user_id=user_id,
            short_name=data['short_name'],
            full_name=data['full_name'],
            addresses=data['addresses'],
            document_type=data['document_type'],
            contract_number=data['contract_number'],
            contract_date=data['contract_date'],
            start_date=data['start_date'],
            end_date=data['end_date'],
            systems=data['systems'],
            notes=data.get('notes'),
            additional_agreements=data.get('additional_agreements', [])
        )
        
        # Получаем созданный объект
        installation_object = await installation_manager.get_installation_object(
            object_id, 
            user_id
        )
        
        # Форматируем текст панели объекта
        text = format_installation_object_panel(installation_object)
        
        # Создаем клавиатуру
        keyboard = create_installation_object_panel_keyboard(object_id)
        
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error completing installation object creation: {e}")
        await message.answer("❌ Произошла ошибка при создании объекта")
        await state.clear()


def format_installation_object_panel(installation_object) -> str:
    """Форматирование панели объекта монтажа"""
    text = f"🏗️ *{installation_object.short_name} - {installation_object.full_name}*\n\n"
    
    text += f"📄 *Документ:* {installation_object.document_type} № {installation_object.contract_number}\n"
    text += f"📅 *Дата:* {installation_object.contract_date.strftime('%d.%m.%Y')}\n"
    
    if installation_object.start_date and installation_object.end_date:
        text += f"🗓 *Сроки:* с {installation_object.start_date.strftime('%d.%m.%Y')} "
        text += f"до {installation_object.end_date.strftime('%d.%m.%Y')}\n\n"
    
    if installation_object.addresses:
        text += "📍 *Адреса:*\n"
        for i, address in enumerate(installation_object.addresses, 1):
            text += f"{i}. {address}\n"
        text += "\n"
    
    if installation_object.systems:
        text += "🔧 *Системы:* " + " • ".join(installation_object.systems) + "\n\n"
    
    if installation_object.notes:
        text += f"📝 *Примечания:* {installation_object.notes}\n\n"
    
    if installation_object.additional_agreements:
        text += "*Дополнительные соглашения:*\n"
        for agreement in installation_object.additional_agreements:
            text += f"📄 {agreement['name']} № {agreement['number']} "
            text += f"от {agreement['date'].strftime('%d.%m.%Y')}\n"
            if agreement.get('description'):
                text += f"   {agreement['description']}\n"
    
    return text


@router.callback_query(F.data.startswith("installation_object_"))
async def show_installation_object_panel(callback: CallbackQuery, context: AppContext):
    """Показать панель объекта монтажа"""
    try:
        object_id = callback.data.split("_")[-1]
        user_id = callback.from_user.id
        
        installation_manager = context.installation_manager
        
        # Получаем объект
        installation_object = await installation_manager.get_installation_object(
            object_id, 
            user_id
        )
        
        if not installation_object:
            await callback.answer("❌ Объект не найден или нет доступа")
            return
        
        # Форматируем текст
        text = format_installation_object_panel(installation_object)
        
        # Создаем клавиатуру
        keyboard = create_installation_object_panel_keyboard(object_id)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing installation object panel: {e}")
        await callback.answer("❌ Ошибка при отображении объекта")


@router.callback_query(F.data.startswith("projects_"))
async def handle_projects(callback: CallbackQuery, context: AppContext):
    """Управление проектами объекта"""
    try:
        object_id = callback.data.split("_")[1]
        user_id = callback.from_user.id
        
        project_manager = context.project_manager
        projects = await project_manager.get_projects(object_id, user_id)
        
        keyboard = create_projects_keyboard(object_id, projects)
        
        text = "📁 *Проекты объекта*\n\n"
        if projects:
            text += "Доступные проекты:\n"
            for i, project in enumerate(projects, 1):
                text += f"{i}. {project.name}\n"
        else:
            text += "Пока нет добавленных проектов."
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error handling projects: {e}")
        await callback.answer("❌ Ошибка при отображении проектов")


@router.callback_query(F.data.startswith("materials_"))
async def handle_materials(callback: CallbackQuery, context: AppContext):
    """Управление материалами объекта"""
    try:
        object_id = callback.data.split("_")[1]
        user_id = callback.from_user.id
        
        material_manager = context.material_manager
        materials = await material_manager.get_materials(object_id, user_id)
        
        keyboard = create_materials_keyboard(object_id, materials)
        
        text = "📦 *Материалы объекта*\n\n"
        if materials:
            text += "Доступные материалы:\n"
            for i, material in enumerate(materials, 1):
                text += f"{i}. {material.name} - {material.quantity} {material.unit}\n"
        else:
            text += "Пока нет добавленных материалов."
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error handling materials: {e}")
        await callback.answer("❌ Ошибка при отображении материалов")


@router.message(Command("монтаж", prefix="!"))
async def group_installation_command(message: Message, command: CommandObject, context: AppContext):
    """Обработка команды монтажа в группах"""
    try:
        group_id = message.chat.id
        region_name = command.args
        
        if not region_name:
            await message.answer("❌ Укажите регион: !монтаж [регион]")
            return
        
        group_manager = context.group_manager
        
        # Привязка группы к региону монтажа
        await group_manager.bind_installation_group(group_id, region_name, message.from_user.id)
        
        await message.answer(f"✅ Группа привязана к монтажу региона: {region_name}")
        
    except AccessDeniedError:
        await message.answer("❌ Нет прав для привязки группы")
    except ValidationError as e:
        await message.answer(f"❌ {e}")
    except Exception as e:
        logger.error(f"Error in group installation command: {e}")
        await message.answer("❌ Ошибка при привязке группы")


@router.message(Command("-монтаж", prefix="!"))
async def remove_installation_binding(message: Message, command: CommandObject, context: AppContext):
    """Удаление привязки группы к монтажу"""
    try:
        group_id = message.chat.id
        region_name = command.args
        
        group_manager = context.group_manager
        
        if not region_name:
            # Удаляем все привязки для этой группы
            await group_manager.remove_installation_binding(group_id, None, message.from_user.id)
            await message.answer("✅ Все привязки монтажа удалены из группы")
        else:
            # Удаляем конкретную привязку
            await group_manager.remove_installation_binding(group_id, region_name, message.from_user.id)
            await message.answer(f"✅ Привязка к монтажу региона {region_name} удалена")
            
    except AccessDeniedError:
        await message.answer("❌ Нет прав для удаления привязки")
    except Exception as e:
        logger.error(f"Error removing installation binding: {e}")
        await message.answer("❌ Ошибка при удалении привязки")