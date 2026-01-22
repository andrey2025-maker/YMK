"""
Обработчики для работы с напоминаниями.
Реализует создание, управление и показ напоминаний.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext

from core.context import AppContext
from core.filters import HasCommandAccess
from services.reminder_service import ReminderService
from fsm.reminder_states import ReminderStates
from utils.date_utils import parse_date, format_date
from core.keyboards.inline.navigation import NavigationInlineKeyboard

router = Router()


@router.message(Command("напомнить"), HasCommandAccess())
async def remind_command(
    message: types.Message,
    command: CommandObject,
    context: AppContext,
    state: FSMContext
) -> None:
    """
    Обработчик команды !напомнить для создания напоминаний.
    
    Пошагово создает напоминание для объекта.
    """
    try:
        user_id = message.from_user.id
        
        # Получаем сервис напоминаний
        reminder_service: ReminderService = context.reminder_service
        
        # Получаем доступные объекты пользователя
        from handlers.user_handlers import my_objects_command
        from modules.service.object_manager import ServiceObjectManager
        from modules.installation.object_manager import InstallationObjectManager
        
        service_manager = ServiceObjectManager(context)
        installation_manager = InstallationObjectManager(context)
        
        service_objects = await service_manager.get_user_objects(user_id)
        installation_objects = await installation_manager.get_user_objects(user_id)
        
        if not service_objects and not installation_objects:
            await message.reply(
                "⚠️ У вас нет доступных объектов для напоминаний.\n"
                "Сначала получите доступ к объектам."
            )
            return
        
        # Сохраняем список объектов в состоянии
        await state.update_data({
            'user_id': user_id,
            'service_objects': service_objects,
            'installation_objects': installation_objects,
            'step': 'select_object_type'
        })
        
        # Создаем клавиатуру выбора типа объекта
        builder = types.InlineKeyboardBuilder()
        
        if service_objects:
            builder.button(text="🔧 Обслуживание", callback_data="remind_type:service")
        
        if installation_objects:
            builder.button(text="⚡ Монтаж", callback_data="remind_type:installation")
        
        builder.button(text="❌ Отмена", callback_data="remind_cancel")
        builder.adjust(1)
        
        await message.reply(
            "🔔 **Создание напоминания**\n\n"
            "Выберите тип объекта для напоминания:",
            reply_markup=builder.as_markup()
        )
        
        # Устанавливаем состояние
        await state.set_state(ReminderStates.selecting_object_type)
        
    except Exception as e:
        await message.reply(f"⚠️ Ошибка: {str(e)}")
        await context.log_manager.log_error(
            user_id=message.from_user.id,
            action='remind_command',
            error=str(e)
        )


@router.callback_query(F.data.startswith("remind_type:"), ReminderStates.selecting_object_type)
async def handle_object_type_selection(
    callback: types.CallbackQuery,
    state: FSMContext,
    context: AppContext
) -> None:
    """
    Обработчик выбора типа объекта для напоминания.
    """
    try:
        object_type = callback.data.split(":")[1]  # service или installation
        
        user_data = await state.get_data()
        objects = user_data.get(f'{object_type}_objects', [])
        
        if not objects:
            await callback.answer("⚠️ Нет доступных объектов этого типа", show_alert=True)
            return
        
        # Сохраняем выбранный тип
        await state.update_data({
            'object_type': object_type,
            'step': 'select_object'
        })
        
        # Создаем клавиатуру выбора объекта
        from core.keyboards.inline.navigation import NavigationInlineKeyboard
        
        items = []
        for obj in objects[:10]:  # Ограничиваем 10 объектами
            text = f"{obj.get('short_name')} - {obj.get('full_name')}"
            callback_data = f"remind_object:{object_type}:{obj.get('id')}"
            items.append((text, callback_data))
        
        keyboard = NavigationInlineKeyboard.create_numbered_list_inline(
            items=items,
            items_per_row=1,
            include_back=True,
            back_callback="remind_back_to_type"
        )
        
        await callback.message.edit_text(
            f"🔔 Выберите объект ({'обслуживания' if object_type == 'service' else 'монтажа'}):",
            reply_markup=keyboard
        )
        
        await state.set_state(ReminderStates.selecting_object)
        await callback.answer()
        
    except Exception as e:
        await callback.answer(f"⚠️ Ошибка: {str(e)}", show_alert=True)
        await context.log_manager.log_error(
            user_id=callback.from_user.id,
            action='handle_object_type_selection',
            error=str(e)
        )


@router.callback_query(F.data.startswith("remind_object:"), ReminderStates.selecting_object)
async def handle_object_selection(
    callback: types.CallbackQuery,
    state: FSMContext,
    context: AppContext
) -> None:
    """
    Обработчик выбора конкретного объекта для напоминания.
    """
    try:
        data_parts = callback.data.split(":")
        object_type = data_parts[1]
        object_id = data_parts[2]
        
        # Получаем информацию об объекте
        if object_type == 'service':
            from modules.service.object_manager import ServiceObjectManager
            manager = ServiceObjectManager(context)
        else:
            from modules.installation.object_manager import InstallationObjectManager
            manager = InstallationObjectManager(context)
        
        object_info = await manager.get_object_details(object_id)
        
        if not object_info:
            await callback.answer("⚠️ Объект не найден", show_alert=True)
            return
        
        # Сохраняем выбранный объект
        await state.update_data({
            'object_id': object_id,
            'object_name': object_info.get('short_name'),
            'step': 'enter_date'
        })
        
        await callback.message.edit_text(
            f"🔔 **Создание напоминания**\n\n"
            f"🎯 Объект: {object_info.get('short_name')}\n"
            f"📝 Название: {object_info.get('full_name')}\n\n"
            f"📅 **Введите дату напоминания:**\n"
            f"Формат: ДД.ММ.ГГГГ\n"
            f"Пример: {datetime.now().strftime('%d.%m.%Y')}\n\n"
            f"💡 Или введите `отмена` для отмены."
        )
        
        await state.set_state(ReminderStates.entering_date)
        await callback.answer()
        
    except Exception as e:
        await callback.answer(f"⚠️ Ошибка: {str(e)}", show_alert=True)
        await context.log_manager.log_error(
            user_id=callback.from_user.id,
            action='handle_object_selection',
            error=str(e)
        )


@router.message(ReminderStates.entering_date)
async def handle_date_input(
    message: types.Message,
    state: FSMContext,
    context: AppContext
) -> None:
    """
    Обработчик ввода даты напоминания.
    """
    try:
        if message.text.lower() in ['отмена', 'cancel', 'стоп', 'stop']:
            await state.clear()
            await message.reply("✅ Создание напоминания отменено.")
            return
        
        # Парсим дату
        reminder_date = parse_date(message.text)
        if not reminder_date:
            await message.reply(
                "⚠️ Неверный формат даты.\n"
                "Используйте формат: ДД.ММ.ГГГГ\n"
                f"Пример: {datetime.now().strftime('%d.%m.%Y')}\n\n"
                "Попробуйте еще раз или введите `отмена`."
            )
            return
        
        # Проверяем что дата в будущем
        if reminder_date.date() < datetime.now().date():
            await message.reply(
                "⚠️ Дата должна быть в будущем.\n"
                "Введите дату в будущем или `отмена`."
            )
            return
        
        await state.update_data({
            'reminder_date': reminder_date,
            'step': 'enter_text'
        })
        
        await message.reply(
            f"✅ Дата установлена: {format_date(reminder_date)}\n\n"
            f"📝 **Введите текст напоминания:**\n"
            f"Пример: 'Проверить оборудование' или 'Создать акт'\n\n"
            f"💡 Или введите `отмена` для отмены."
        )
        
        await state.set_state(ReminderStates.entering_text)
        
    except Exception as e:
        await message.reply(f"⚠️ Ошибка: {str(e)}")
        await context.log_manager.log_error(
            user_id=message.from_user.id,
            action='handle_date_input',
            error=str(e)
        )


@router.message(ReminderStates.entering_text)
async def handle_text_input(
    message: types.Message,
    state: FSMContext,
    context: AppContext
) -> None:
    """
    Обработчик ввода текста напоминания.
    """
    try:
        if message.text.lower() in ['отмена', 'cancel', 'стоп', 'stop']:
            await state.clear()
            await message.reply("✅ Создание напоминания отменено.")
            return
        
        reminder_text = message.text.strip()
        
        if len(reminder_text) < 3:
            await message.reply(
                "⚠️ Текст слишком короткий.\n"
                "Введите текст напоминания (минимум 3 символа) или `отмена`."
            )
            return
        
        # Получаем все данные
        user_data = await state.get_data()
        user_id = message.from_user.id
        
        # Создаем напоминание
        reminder_service: ReminderService = context.reminder_service
        
        result = await reminder_service.create_reminder(
            user_id=user_id,
            object_type=user_data.get('object_type'),
            object_id=user_data.get('object_id'),
            object_name=user_data.get('object_name'),
            reminder_date=user_data.get('reminder_date'),
            reminder_text=reminder_text,
            notify_before_days=[1]  # Напоминать за 1 день
        )
        
        if result['success']:
            # Очищаем состояние
            await state.clear()
            
            # Отправляем подтверждение
            response_text = (
                f"✅ Напоминание создано!\n\n"
                f"🔔 **Детали напоминания:**\n"
                f"🎯 Объект: {user_data.get('object_name')}\n"
                f"📅 Дата: {format_date(user_data.get('reminder_date'))}\n"
                f"📝 Текст: {reminder_text}\n"
                f"👤 Автор: {message.from_user.full_name}\n"
                f"🆔 ID: {result['reminder_id']}\n\n"
                f"💡 Вы получите уведомление за 1 день до события."
            )
            
            # Создаем клавиатуру действий
            keyboard = NavigationInlineKeyboard.create_action_buttons_inline(
                actions=[
                    ("✏️ Редактировать", f"remind_edit:{result['reminder_id']}", True),
                    ("🗑️ Удалить", f"remind_delete:{result['reminder_id']}", True),
                    ("🔔 Все напоминания", "remind_show_all", True)
                ],
                include_back=False
            )
            
            await message.reply(response_text, reply_markup=keyboard)
            
            # Логируем создание напоминания
            await context.log_manager.log_reminder_created(
                user_id=user_id,
                reminder_id=result['reminder_id'],
                details=user_data
            )
        else:
            await message.reply(f"❌ Ошибка при создании напоминания: {result.get('error')}")
        
    except Exception as e:
        await message.reply(f"⚠️ Ошибка: {str(e)}")
        await context.log_manager.log_error(
            user_id=message.from_user.id,
            action='handle_text_input',
            error=str(e)
        )


@router.message(Command("напоминания"), HasCommandAccess())
async def reminders_command(
    message: types.Message,
    command: CommandObject,
    context: AppContext
) -> None:
    """
    Обработчик команды !напоминания для показа списка напоминаний.
    
    Показывает напоминания на ближайшие 30 дней.
    """
    try:
        user_id = message.from_user.id
        
        # Получаем сервис напоминаний
        reminder_service: ReminderService = context.reminder_service
        
        # Получаем напоминания на ближайшие 30 дней
        reminders = await reminder_service.get_upcoming_reminders(
            user_id=user_id,
            days_ahead=30
        )
        
        if not reminders:
            await message.reply(
                "📭 Нет напоминаний на ближайшие 30 дней.\n\n"
                "💡 Создайте новое напоминание:\n"
                "`!напомнить` - создать напоминание"
            )
            return
        
        # Группируем напоминания по датам
        reminders_by_date = {}
        for reminder in reminders:
            reminder_date = reminder.get('reminder_date')
            if isinstance(reminder_date, str):
                reminder_date = parse_date(reminder_date)
            
            if reminder_date:
                date_key = reminder_date.strftime('%d.%m.%Y')
                if date_key not in reminders_by_date:
                    reminders_by_date[date_key] = []
                reminders_by_date[date_key].append(reminder)
        
        # Формируем ответ
        response_text = "🔔 **Ваши напоминания (ближайшие 30 дней):**\n\n"
        
        today = datetime.now().date()
        
        for date_str in sorted(reminders_by_date.keys()):
            date_reminders = reminders_by_date[date_str]
            date_obj = parse_date(date_str)
            
            # Определяем иконку для даты
            if date_obj and date_obj.date() == today:
                date_icon = "🟢"
            elif date_obj and date_obj.date() < today:
                date_icon = "🔴"
            else:
                date_icon = "🟡"
            
            response_text += f"{date_icon} **{date_str}** ({len(date_reminders)}):\n"
            
            for idx, reminder in enumerate(date_reminders, 1):
                object_icon = "🔧" if reminder.get('object_type') == 'service' else "⚡"
                response_text += f"  {idx}. {object_icon} {reminder.get('object_name')}\n"
                response_text += f"     📝 {reminder.get('reminder_text')}\n"
                
                # Добавляем информацию об авторе если не текущий пользователь
                if reminder.get('author_id') != user_id:
                    response_text += f"     👤 {reminder.get('author_name', 'Неизвестно')}\n"
                
                response_text += "\n"
        
        response_text += f"📊 Всего напоминаний: {len(reminders)}\n\n"
        
        # Создаем клавиатуру действий
        from core.keyboards.inline.navigation import NavigationInlineKeyboard
        
        actions = [
            ("➕ Создать", "remind_create_new", True),
            ("🗑️ Удалить", "remind_delete_menu", True),
            ("📊 Статистика", "remind_stats", True)
        ]
        
        keyboard = NavigationInlineKeyboard.create_action_buttons_inline(
            actions=actions,
            include_back=True,
            back_callback="main_menu"
        )
        
        await message.reply(response_text, reply_markup=keyboard)
        
    except Exception as e:
        await message.reply(f"⚠️ Ошибка: {str(e)}")
        await context.log_manager.log_error(
            user_id=message.from_user.id,
            action='reminders_command',
            error=str(e)
        )


@router.callback_query(F.data.startswith("remind_delete:"))
async def delete_reminder(
    callback: types.CallbackQuery,
    context: AppContext
) -> None:
    """
    Удаление напоминания.
    
    Callback format: remind_delete:<reminder_id>
    """
    try:
        reminder_id = callback.data.split(":")[1]
        user_id = callback.from_user.id
        
        # Получаем сервис напоминаний
        reminder_service: ReminderService = context.reminder_service
        
        # Проверяем доступ
        if not await reminder_service.check_reminder_access(user_id, reminder_id):
            await callback.answer("⛔ Нет доступа к этому напоминанию", show_alert=True)
            return
        
        # Создаем клавиатуру подтверждения
        keyboard = NavigationInlineKeyboard.create_yes_no_inline(
            yes_text="✅ Удалить",
            yes_callback=f"remind_confirm_delete:{reminder_id}",
            no_text="❌ Отмена",
            no_callback="remind_cancel_delete"
        )
        
        await callback.message.edit_text(
            "🗑️ **Удаление напоминания**\n\n"
            "Вы уверены, что хотите удалить это напоминание?\n\n"
            "Это действие нельзя отменить.",
            reply_markup=keyboard
        )
        
        await callback.answer()
        
    except Exception as e:
        await callback.answer(f"⚠️ Ошибка: {str(e)}", show_alert=True)
        await context.log_manager.log_error(
            user_id=callback.from_user.id,
            action='delete_reminder',
            error=str(e)
        )


@router.callback_query(F.data.startswith("remind_confirm_delete:"))
async def confirm_delete_reminder(
    callback: types.CallbackQuery,
    context: AppContext
) -> None:
    """
    Подтверждение удаления напоминания.
    """
    try:
        reminder_id = callback.data.split(":")[1]
        user_id = callback.from_user.id
        
        # Получаем сервис напоминаний
        reminder_service: ReminderService = context.reminder_service
        
        # Удаляем напоминание
        result = await reminder_service.delete_reminder(reminder_id, user_id)
        
        if result['success']:
            await callback.message.edit_text(
                "✅ Напоминание удалено!\n\n"
                f"🆔 ID: {reminder_id}\n"
                f"👤 Удалил: {callback.from_user.full_name}"
            )
            
            # Логируем удаление
            await context.log_manager.log_reminder_deleted(
                user_id=user_id,
                reminder_id=reminder_id
            )
        else:
            await callback.message.edit_text(
                f"❌ Ошибка при удалении: {result.get('error')}"
            )
        
        await callback.answer()
        
    except Exception as e:
        await callback.answer(f"⚠️ Ошибка: {str(e)}", show_alert=True)
        await context.log_manager.log_error(
            user_id=callback.from_user.id,
            action='confirm_delete_reminder',
            error=str(e)
        )