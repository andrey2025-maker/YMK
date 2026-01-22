"""
Пользовательские обработчики команд.
Реализует команды доступные всем пользователям.
"""
from typing import List, Dict, Any, Optional
from aiogram import Router, types, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext

from core.context import AppContext
from core.filters import HasCommandAccess
from modules.admin.admin_manager import AdminManager
from modules.service.object_manager import ServiceObjectManager
from modules.installation.object_manager import InstallationObjectManager
from utils.date_utils import format_date

router = Router()


@router.message(Command("старт", "start"))
async def start_command(message: types.Message, context: AppContext) -> None:
    """
    Обработчик команды /start для начала работы с ботом.
    """
    try:
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name
        
        # Получаем информацию о пользователе
        admin_manager: AdminManager = context.admin_manager
        user_role = await admin_manager.get_user_role(user_id)
        
        if user_role:
            welcome_text = f"👋 С возвращением, {username}!\n\n"
            role_name = _get_role_name(user_role)
            welcome_text += f"🎖️ Ваша роль: {role_name}\n\n"
        else:
            welcome_text = f"👋 Добро пожаловать, {username}!\n\n"
            welcome_text += "📋 Вы зарегистрированы как обычный пользователь.\n"
            welcome_text += "Для получения прав обратитесь к администратору.\n\n"
        
        welcome_text += (
            "🤖 Я - бот для управления объектами обслуживания и монтажа.\n\n"
            "🔧 **Основные возможности:**\n"
            "• Управление объектами обслуживания\n"
            "• Учет монтажных работ\n"
            "• Отслеживание проблем и ТО\n"
            "• Управление документами и файлами\n"
            "• Умные напоминания\n\n"
            "📝 **Начните работу:**\n"
            "• `!помощь` - список всех команд\n"
            "• `!мои_объекты` - ваши доступные объекты\n"
            "• `!настройки` - ваши настройки\n\n"
            "💡 Для помощи введите `!помощь`"
        )
        
        await message.reply(welcome_text)
        
        # Логируем старт
        await context.log_manager.log_user_start(
            user_id=user_id,
            username=username,
            role=user_role
        )
        
    except Exception as e:
        await message.reply(f"⚠️ Ошибка при запуске: {str(e)}")
        await context.log_manager.log_error(
            user_id=message.from_user.id,
            action='start_command',
            error=str(e)
        )


@router.message(Command("мои_объекты"), HasCommandAccess())
async def my_objects_command(
    message: types.Message,
    command: CommandObject,
    context: AppContext
) -> None:
    """
    Обработчик команды !мои_объекты для показа доступных объектов.
    
    Показывает объекты обслуживания и монтажа, доступные пользователю.
    """
    try:
        user_id = message.from_user.id
        
        # Получаем объекты обслуживания
        service_manager = ServiceObjectManager(context)
        service_objects = await service_manager.get_user_objects(user_id)
        
        # Получаем объекты монтажа
        installation_manager = InstallationObjectManager(context)
        installation_objects = await installation_manager.get_user_objects(user_id)
        
        if not service_objects and not installation_objects:
            await message.reply(
                "📭 У вас нет доступных объектов.\n\n"
                "💡 Возможные причины:\n"
                "• Вас не добавили к объектам\n"
                "• Объекты еще не созданы\n"
                "• Обратитесь к администратору"
            )
            return
        
        response_text = "🏢 Ваши объекты:\n\n"
        
        total_objects = 0
        
        # Объекты обслуживания
        if service_objects:
            response_text += "🔧 **Обслуживание:**\n"
            for obj in service_objects[:5]:  # Показываем первые 5
                response_text += f"• {obj.get('short_name')} - {obj.get('full_name')}\n"
                if obj.get('address'):
                    response_text += f"  📍 {obj.get('address')}\n"
                response_text += "\n"
            
            if len(service_objects) > 5:
                response_text += f"📋 И еще {len(service_objects) - 5} объектов обслуживания...\n\n"
            else:
                response_text += "\n"
            
            total_objects += len(service_objects)
        
        # Объекты монтажа
        if installation_objects:
            response_text += "⚡ **Монтаж:**\n"
            for obj in installation_objects[:5]:  # Показываем первые 5
                response_text += f"• {obj.get('short_name')} - {obj.get('full_name')}\n"
                if obj.get('address'):
                    response_text += f"  📍 {obj.get('address')}\n"
                response_text += "\n"
            
            if len(installation_objects) > 5:
                response_text += f"📋 И еще {len(installation_objects) - 5} объектов монтажа...\n\n"
            else:
                response_text += "\n"
            
            total_objects += len(installation_objects)
        
        response_text += f"📊 Всего объектов: {total_objects}\n\n"
        
        # Добавляем подсказки по командам
        if service_objects:
            response_text += "💡 Для обслуживания:\n"
            response_text += "• `!обслуживание` - меню обслуживания\n"
            response_text += "• `!напомнить` - создать напоминание\n"
            response_text += "• `!доп` - добавить документ\n\n"
        
        if installation_objects:
            response_text += "💡 Для монтажа:\n"
            response_text += "• `!монтаж` - меню монтажа\n"
            response_text += "• `!проекты` - показать проекты\n"
            response_text += "• `!материалы` - показать материалы\n\n"
        
        response_text += "🔍 Используйте `!поиск` для быстрого поиска."
        
        # Создаем клавиатуру быстрого доступа
        from core.keyboards.inline.navigation import NavigationInlineKeyboard
        
        quick_links = []
        if service_objects:
            quick_links.append(("🔧", "Обслуживание", "menu_service"))
        if installation_objects:
            quick_links.append(("⚡", "Монтаж", "menu_installation"))
        
        quick_links.append(("🔍", "Поиск", "menu_search"))
        quick_links.append(("🔔", "Напоминания", "menu_reminders"))
        
        keyboard = NavigationInlineKeyboard.create_quick_links_inline(
            links=quick_links,
            include_refresh=True,
            refresh_callback="refresh_my_objects"
        )
        
        await message.reply(response_text, reply_markup=keyboard)
        
    except Exception as e:
        await message.reply(f"⚠️ Ошибка: {str(e)}")
        await context.log_manager.log_error(
            user_id=message.from_user.id,
            action='my_objects_command',
            error=str(e)
        )


@router.message(Command("помощь", "help"), HasCommandAccess())
async def help_command(
    message: types.Message,
    command: CommandObject,
    context: AppContext
) -> None:
    """
    Обработчик команды !помощь с описанием доступных команд.
    
    Показывает команды доступные пользователю в зависимости от его роли.
    """
    try:
        user_id = message.from_user.id
        
        # Получаем роль пользователя
        admin_manager: AdminManager = context.admin_manager
        user_role = await admin_manager.get_user_role(user_id)
        
        # Базовые команды для всех
        help_text = "📋 **Доступные команды:**\n\n"
        
        help_text += "👤 **Основные команды:**\n"
        help_text += "• `/start` - начало работы\n"
        help_text += "• `!помощь` - эта справка\n"
        help_text += "• `!мои_объекты` - ваши объекты\n"
        help_text += "• `!настройки` - ваши настройки\n"
        help_text += "• `!стоп` - отмена текущего действия\n\n"
        
        help_text += "🔍 **Поиск и навигация:**\n"
        help_text += "• `!поиск <текст>` - глобальный поиск\n"
        help_text += "• `!найти_файл <текст>` - поиск файлов\n"
        help_text += "• `!файлы` - управление архивами\n\n"
        
        help_text += "🔔 **Напоминания:**\n"
        help_text += "• `!напомнить` - создать напоминание\n"
        help_text += "• `!напоминания` - список напоминаний\n\n"
        
        # Команды в зависимости от роли
        if user_role in ['main_admin', 'admin']:
            help_text += "👑 **Административные команды:**\n"
            help_text += "• `!добавить_админа` - добавить админа\n"
            help_text += "• `!разрешения` - управление правами\n"
            help_text += "• `!сохранения` - настройки сохранения\n"
            help_text += "• `!кэш` - управление кэшем\n"
            help_text += "• `!команды` - список доступных команд\n\n"
        
        if user_role in ['main_admin', 'admin', 'service']:
            help_text += "🔧 **Обслуживание:**\n"
            help_text += "• `!обслуживание` - меню обслуживания\n"
            help_text += "• `!доп` - добавить документ\n\n"
        
        if user_role in ['main_admin', 'admin', 'installation']:
            help_text += "⚡ **Монтаж:**\n"
            help_text += "• `!монтаж` - меню монтажа\n\n"
        
        help_text += "👥 **Команды в группах:**\n"
        help_text += "• `!обслуживание <регион>` - привязать объект\n"
        help_text += "• `!монтаж <объект>` - привязать монтаж\n"
        help_text += "• `!-обслуживание <регион>` - отвязать\n"
        help_text += "• `!-монтаж <объект>` - отвязать\n"
        help_text += "• `!проекты` - показать проекты\n"
        help_text += "• `!изменения` - показать изменения\n"
        help_text += "• `!письма` - показать письма\n"
        help_text += "• `!допуски` - показать допуски\n"
        help_text += "• `!журналы` - показать журналы\n"
        help_text += "• `!группа_инфо` - информация о группе\n\n"
        
        help_text += "💡 **Полезные советы:**\n"
        help_text += "• Используйте `!стоп` чтобы отменить любое действие\n"
        help_text += "• Файлы автоматически архивируются\n"
        help_text += "• Все изменения логируются\n"
        help_text += "• Напоминания работают автоматически\n\n"
        
        help_text += "❓ **Нужна помощь?**\n"
        help_text += "Обратитесь к администратору системы."
        
        await message.reply(help_text)
        
    except Exception as e:
        await message.reply(f"⚠️ Ошибка: {str(e)}")
        await context.log_manager.log_error(
            user_id=message.from_user.id,
            action='help_command',
            error=str(e)
        )


@router.message(Command("стоп", "stop", "отмена", "cancel"))
async def cancel_command(
    message: types.Message,
    state: FSMContext,
    context: AppContext
) -> None:
    """
    Обработчик команды !стоп для отмены текущего действия.
    
    Прерывает FSM сценарии и очищает состояние.
    """
    try:
        current_state = await state.get_state()
        
        if current_state is None:
            await message.reply("ℹ️ Нет активных действий для отмены.")
            return
        
        # Очищаем состояние
        await state.clear()
        
        await message.reply(
            "✅ Действие отменено.\n"
            "💡 Вы можете начать новое действие."
        )
        
        # Логируем отмену
        await context.log_manager.log_action_cancel(
            user_id=message.from_user.id,
            state=current_state
        )
        
    except Exception as e:
        await message.reply(f"⚠️ Ошибка при отмене: {str(e)}")
        await context.log_manager.log_error(
            user_id=message.from_user.id,
            action='cancel_command',
            error=str(e)
        )


@router.message(Command("настройки", "settings"), HasCommandAccess())
async def settings_command(
    message: types.Message,
    command: CommandObject,
    context: AppContext
) -> None:
    """
    Обработчик команды !настройки для пользовательских настроек.
    """
    try:
        user_id = message.from_user.id
        
        # Получаем текущие настройки пользователя
        user_settings = await context.user_settings_manager.get_user_settings(user_id)
        
        if not command.args:
            # Показываем текущие настройки
            response_text = "⚙️ **Ваши настройки:**\n\n"
            
            # Основные настройки
            response_text += "🔔 **Уведомления:**\n"
            response_text += f"• Напоминания: {'✅ Вкл' if user_settings.get('notifications_enabled', True) else '❌ Выкл'}\n"
            response_text += f"• Новые объекты: {'✅ Вкл' if user_settings.get('new_objects_notify', True) else '❌ Выкл'}\n"
            response_text += f"• Изменения: {'✅ Вкл' if user_settings.get('changes_notify', True) else '❌ Выкл'}\n\n"
            
            # Настройки отображения
            response_text += "👁️ **Отображение:**\n"
            response_text += f"• Эмодзи: {'✅ Вкл' if user_settings.get('show_emojis', True) else '❌ Выкл'}\n"
            response_text += f"• Подробности: {'✅ Вкл' if user_settings.get('show_details', True) else '❌ Выкл'}\n"
            response_text += f"• Дата формат: {user_settings.get('date_format', 'ДД.ММ.ГГГГ')}\n\n"
            
            # Дополнительные настройки
            response_text += "🔧 **Дополнительно:**\n"
            response_text += f"• Автосохранение: {'✅ Вкл' if user_settings.get('auto_save', True) else '❌ Выкл'}\n"
            response_text += f"• Подтверждения: {'✅ Вкл' if user_settings.get('confirm_actions', True) else '❌ Выкл'}\n\n"
            
            response_text += "💡 **Изменить настройки:**\n"
            response_text += "`!настройки <ключ> <значение>`\n"
            response_text += "Пример: `!настройки уведомления выкл`"
            
            await message.reply(response_text)
            return
        
        # Изменение настроек
        args = command.args.strip().lower().split()
        
        if len(args) < 2:
            await message.reply(
                "⚠️ Неверный формат.\n"
                "Используйте: `!настройки <ключ> <значение>`\n"
                "Пример: `!настройки уведомления выкл`"
            )
            return
        
        setting_key = args[0]
        setting_value = args[1]
        
        # Валидация и применение настроек
        result = await context.user_settings_manager.update_user_setting(
            user_id=user_id,
            key=setting_key,
            value=setting_value
        )
        
        if result['success']:
            await message.reply(
                f"✅ Настройка обновлена!\n\n"
                f"🎯 Ключ: {setting_key}\n"
                f"📊 Значение: {setting_value}\n\n"
                f"💡 Изменения применятся сразу."
            )
            
            # Логируем изменение настроек
            await context.log_manager.log_settings_change(
                user_id=user_id,
                setting=setting_key,
                old_value=result.get('old_value'),
                new_value=setting_value
            )
        else:
            await message.reply(f"❌ Ошибка: {result.get('error', 'Неизвестная ошибка')}")
        
    except Exception as e:
        await message.reply(f"⚠️ Ошибка: {str(e)}")
        await context.log_manager.log_error(
            user_id=message.from_user.id,
            action='settings_command',
            error=str(e)
        )


@router.message(Command("профиль", "profile"), HasCommandAccess())
async def profile_command(message: types.Message, context: AppContext) -> None:
    """
    Показывает профиль пользователя и его права.
    """
    try:
        user_id = message.from_user.id
        user = message.from_user
        
        # Получаем информацию о пользователе
        admin_manager: AdminManager = context.admin_manager
        user_role = await admin_manager.get_user_role(user_id)
        
        # Получаем статистику пользователя
        user_stats = await context.user_stats_manager.get_user_stats(user_id)
        
        # Формируем профиль
        response_text = "👤 **Ваш профиль**\n\n"
        
        response_text += f"🆔 ID: `{user_id}`\n"
        response_text += f"👁️ Имя: {user.full_name}\n"
        if user.username:
            response_text += f"📱 Username: @{user.username}\n"
        
        response_text += f"\n🎖️ **Роль:** {_get_role_name(user_role)}\n"
        
        if user_role:
            response_text += f"📅 Роль назначена: {format_date(user_stats.get('role_assigned_date'))}\n"
        
        response_text += "\n📊 **Статистика:**\n"
        response_text += f"• Объектов обслуживания: {user_stats.get('service_objects_count', 0)}\n"
        response_text += f"• Объектов монтажа: {user_stats.get('installation_objects_count', 0)}\n"
        response_text += f"• Создано проблем: {user_stats.get('problems_created', 0)}\n"
        response_text += f"• Создано напоминаний: {user_stats.get('reminders_created', 0)}\n"
        response_text += f"• Загружено файлов: {user_stats.get('files_uploaded', 0)}\n"
        response_text += f"• Активность: {user_stats.get('last_active', 'Недавно')}\n"
        
        response_text += "\n🔑 **Права доступа:**\n"
        
        # Описание прав в зависимости от роли
        if user_role == 'main_admin':
            response_text += "• Полный доступ ко всем функциям\n"
            response_text += "• Управление администраторами\n"
            response_text += "• Настройка системы\n"
            response_text += "• Экспорт данных\n"
        elif user_role == 'admin':
            response_text += "• Управление объектами\n"
            response_text += "• Редактирование данных\n"
            response_text += "• Управление файлами\n"
            response_text += "• Создание отчетов\n"
        elif user_role == 'service':
            response_text += "• Работа с обслуживанием\n"
            response_text += "• Управление проблемами\n"
            response_text += "• Создание ТО\n"
            response_text += "• Работа с оборудованием\n"
        elif user_role == 'installation':
            response_text += "• Работа с монтажом\n"
            response_text += "• Управление проектами\n"
            response_text += "• Учет материалов\n"
            response_text += "• Отслеживание монтажа\n"
        else:
            response_text += "• Просмотр доступных объектов\n"
            response_text += "• Использование групповых команд\n"
            response_text += "• Поиск информации\n"
        
        await message.reply(response_text)
        
    except Exception as e:
        await message.reply(f"⚠️ Ошибка: {str(e)}")
        await context.log_manager.log_error(
            user_id=message.from_user.id,
            action='profile_command',
            error=str(e)
        )


def _get_role_name(role: Optional[str]) -> str:
    """Возвращает читаемое название роли."""
    role_names = {
        'main_admin': '👑 Главный администратор',
        'admin': '👔 Администратор',
        'service': '🔧 Обслуживающий',
        'installation': '⚡ Монтажник',
        None: '👤 Пользователь'
    }
    return role_names.get(role, '👤 Пользователь')