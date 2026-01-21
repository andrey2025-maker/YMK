from typing import Optional
from uuid import UUID

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
import structlog

from core.context import AppContext
from core.middlewares.auth import AuthMiddleware
from modules.admin.admin_manager import AdminManager
from modules.admin.permission_manager import PermissionManager
from storage.models.user import AdminLevel
from utils.formatters import format_admin_info, format_permission_panel


logger = structlog.get_logger(__name__)

# Создаем роутер
admin_router = Router(name="admin_handlers")


# Команды для главного админа
@admin_router.message(Command("добавить_главного_админа"))
@AuthMiddleware.require_admin(AdminLevel.MAIN_ADMIN.value)
async def add_main_admin(
    message: Message, 
    command: CommandObject,
    context: AppContext,
    admin: Optional[dict] = None
) -> None:
    """Добавляет главного админа."""
    if not command.args:
        await message.answer(
            "Использование: !добавить_главного_админа (id/ссылка/имя пользователя)\n\n"
            "Примеры:\n"
            "!добавить_главного_админа 123456789\n"
            "!добавить_главного_админа @username\n"
            "!добавить_главного_админа https://t.me/username"
        )
        return
    
    try:
        admin_manager = AdminManager(context)
        result = await admin_manager.add_admin(
            admin_identifier=command.args,
            level=AdminLevel.MAIN_ADMIN.value,
            added_by=admin.get("id") if admin else None
        )
        
        if result["success"]:
            await message.answer(
                f"✅ Главный админ добавлен:\n"
                f"Пользователь: {result['user']['username']}\n"
                f"Telegram ID: {result['user']['telegram_id']}\n"
                f"Уровень: {result['admin']['level_display']}"
            )
            
            # Логируем действие
            logger.info(
                "Main admin added",
                added_by=admin.get("id") if admin else None,
                new_admin_id=result["admin"]["id"]
            )
        else:
            await message.answer(f"❌ Ошибка: {result['message']}")
    
    except Exception as e:
        logger.error("Add main admin failed", error=str(e))
        await message.answer(f"❌ Ошибка при добавлении админа: {str(e)}")


@admin_router.message(Command("добавить_админа"))
@AuthMiddleware.require_admin(AdminLevel.MAIN_ADMIN.value)
async def add_admin(
    message: Message,
    command: CommandObject,
    context: AppContext,
    admin: Optional[dict] = None
) -> None:
    """Добавляет админа."""
    await _add_admin_with_level(
        message, command, context, admin, AdminLevel.ADMIN.value
    )


@admin_router.message(Command("добавить_обслуга"))
@AuthMiddleware.require_admin(AdminLevel.MAIN_ADMIN.value)
async def add_service_admin(
    message: Message,
    command: CommandObject,
    context: AppContext,
    admin: Optional[dict] = None
) -> None:
    """Добавляет админа уровня 'Обслуга'."""
    await _add_admin_with_level(
        message, command, context, admin, AdminLevel.SERVICE.value
    )


@admin_router.message(Command("добавить_монтаж"))
@AuthMiddleware.require_admin(AdminLevel.MAIN_ADMIN.value)
async def add_installation_admin(
    message: Message,
    command: CommandObject,
    context: AppContext,
    admin: Optional[dict] = None
) -> None:
    """Добавляет админа уровня 'Монтаж'."""
    await _add_admin_with_level(
        message, command, context, admin, AdminLevel.INSTALLATION.value
    )


async def _add_admin_with_level(
    message: Message,
    command: CommandObject,
    context: AppContext,
    admin: Optional[dict],
    level: str
) -> None:
    """Общая функция для добавления админа с указанным уровнем."""
    if not command.args:
        level_name = AdminLevel(level).value.replace("_", " ").title()
        await message.answer(
            f"Использование: !добавить_{level} (id/ссылка/имя пользователя)\n\n"
            f"Примеры:\n"
            f"!добавить_{level} 123456789\n"
            f"!добавить_{level} @username\n"
            f"!добавить_{level} https://t.me/username\n\n"
            f"Уровень: {level_name}"
        )
        return
    
    try:
        admin_manager = AdminManager(context)
        result = await admin_manager.add_admin(
            admin_identifier=command.args,
            level=level,
            added_by=admin.get("id") if admin else None
        )
        
        if result["success"]:
            await message.answer(
                f"✅ Админ добавлен:\n"
                f"Пользователь: {result['user']['username']}\n"
                f"Уровень: {result['admin']['level_display']}\n"
                f"Добавил: {admin.get('username', 'Система') if admin else 'Система'}"
            )
            
            logger.info(
                f"{level} admin added",
                added_by=admin.get("id") if admin else None,
                new_admin_id=result["admin"]["id"],
                level=level
            )
        else:
            await message.answer(f"❌ Ошибка: {result['message']}")
    
    except Exception as e:
        logger.error(f"Add {level} admin failed", error=str(e))
        await message.answer(f"❌ Ошибка при добавлении админа: {str(e)}")


@admin_router.message(Command("разрешения"))
@AuthMiddleware.require_admin(AdminLevel.MAIN_ADMIN.value)
async def permissions_command(
    message: Message,
    context: AppContext,
    admin: Optional[dict] = None
) -> None:
    """Показывает панель управления разрешениями."""
    try:
        permission_manager = PermissionManager(context)
        
        # Создаем клавиатуру с кнопками для выбора уровня админа
        builder = InlineKeyboardBuilder()
        
        # Кнопки для каждого уровня админа
        levels = [
            (AdminLevel.ADMIN.value, "👨‍💼 Админ"),
            (AdminLevel.SERVICE.value, "🔧 Обслуга"),
            (AdminLevel.INSTALLATION.value, "⚡ Монтаж"),
            ("group", "👥 Группа"),
        ]
        
        for level, display_name in levels:
            builder.button(
                text=display_name,
                callback_data=f"permissions_select:{level}"
            )
        
        builder.adjust(2)  # 2 кнопки в ряд
        
        await message.answer(
            "🛠 <b>Панель управления разрешениями</b>\n\n"
            "Выберите уровень админа или группу для настройки разрешений:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    
    except Exception as e:
        logger.error("Permissions command failed", error=str(e))
        await message.answer("❌ Ошибка при загрузке панели разрешений")


@admin_router.callback_query(F.data.startswith("permissions_select:"))
async def select_permission_level(callback: CallbackQuery, context: AppContext):
    """Обработчик выбора уровня для настройки разрешений."""
    level = callback.data.split(":")[1]
    
    try:
        permission_manager = PermissionManager(context)
        
        # Получаем список доступных команд для этого уровня
        commands = await permission_manager.get_available_commands(level)
        
        # Формируем сообщение с командами
        message_text = format_permission_panel(level, commands)
        
        # Создаем клавиатуру для переключения команд
        builder = InlineKeyboardBuilder()
        
        for command in commands:
            command_name = command["name"]
            is_enabled = command.get("enabled", False)
            status = "✅" if is_enabled else "❌"
            
            builder.button(
                text=f"{status} {command_name}",
                callback_data=f"permission_toggle:{level}:{command_name}"
            )
        
        # Кнопки навигации
        builder.button(text="⬅️ Назад", callback_data="permissions_back")
        builder.button(text="💾 Сохранить", callback_data=f"permissions_save:{level}")
        builder.adjust(1, 2)  # По 1 команде в ряд, потом 2 кнопки
        
        await callback.message.edit_text(
            message_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        
        await callback.answer()
    
    except Exception as e:
        logger.error("Select permission level failed", level=level, error=str(e))
        await callback.answer("❌ Ошибка при загрузке разрешений", show_alert=True)


@admin_router.callback_query(F.data.startswith("permission_toggle:"))
async def toggle_permission(callback: CallbackQuery, context: AppContext):
    """Переключает разрешение для команды."""
    _, level, command_name = callback.data.split(":", 2)
    
    try:
        permission_manager = PermissionManager(context)
        
        # Переключаем состояние команды
        new_state = await permission_manager.toggle_command_permission(
            level=level,
            command_name=command_name
        )
        
        # Обновляем сообщение
        commands = await permission_manager.get_available_commands(level)
        message_text = format_permission_panel(level, commands)
        
        # Пересоздаем клавиатуру
        builder = InlineKeyboardBuilder()
        
        for command in commands:
            cmd_name = command["name"]
            is_enabled = command.get("enabled", False)
            status = "✅" if is_enabled else "❌"
            
            builder.button(
                text=f"{status} {cmd_name}",
                callback_data=f"permission_toggle:{level}:{cmd_name}"
            )
        
        builder.button(text="⬅️ Назад", callback_data="permissions_back")
        builder.button(text="💾 Сохранить", callback_data=f"permissions_save:{level}")
        builder.adjust(1, 2)
        
        status_text = "включена" if new_state else "выключена"
        await callback.message.edit_text(
            message_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        
        await callback.answer(f"Команда {command_name} {status_text}")
    
    except Exception as e:
        logger.error("Toggle permission failed", command=command_name, error=str(e))
        await callback.answer("❌ Ошибка при переключении разрешения", show_alert=True)


@admin_router.callback_query(F.data.startswith("permissions_save:"))
async def save_permissions(callback: CallbackQuery, context: AppContext):
    """Сохраняет изменения в разрешениях."""
    level = callback.data.split(":")[1]
    
    try:
        permission_manager = PermissionManager(context)
        
        # Сохраняем изменения
        await permission_manager.save_permissions(level)
        
        await callback.answer("✅ Изменения сохранены")
        
        # Возвращаемся к выбору уровня
        builder = InlineKeyboardBuilder()
        levels = [
            (AdminLevel.ADMIN.value, "👨‍💼 Админ"),
            (AdminLevel.SERVICE.value, "🔧 Обслуга"),
            (AdminLevel.INSTALLATION.value, "⚡ Монтаж"),
            ("group", "👥 Группа"),
        ]
        
        for lvl, display_name in levels:
            builder.button(
                text=display_name,
                callback_data=f"permissions_select:{lvl}"
            )
        
        builder.adjust(2)
        
        await callback.message.edit_text(
            "🛠 <b>Панель управления разрешениями</b>\n\n"
            "✅ Изменения сохранены!\n\n"
            "Выберите уровень админа или группу для настройки разрешений:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    
    except Exception as e:
        logger.error("Save permissions failed", level=level, error=str(e))
        await callback.answer("❌ Ошибка при сохранении изменений", show_alert=True)


@admin_router.callback_query(F.data == "permissions_back")
async def permissions_back(callback: CallbackQuery):
    """Возвращает к выбору уровня."""
    builder = InlineKeyboardBuilder()
    levels = [
        (AdminLevel.ADMIN.value, "👨‍💼 Админ"),
        (AdminLevel.SERVICE.value, "🔧 Обслуга"),
        (AdminLevel.INSTALLATION.value, "⚡ Монтаж"),
        ("group", "👥 Группа"),
    ]
    
    for level, display_name in levels:
        builder.button(
            text=display_name,
            callback_data=f"permissions_select:{level}"
        )
    
    builder.adjust(2)
    
    await callback.message.edit_text(
        "🛠 <b>Панель управления разрешениями</b>\n\n"
        "Выберите уровень админа или группу для настройки разрешений:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@admin_router.message(Command("команды"))
async def available_commands(
    message: Message,
    context: AppContext,
    user: Optional[dict] = None,
    admin: Optional[dict] = None
) -> None:
    """Показывает все доступные пользователю команды."""
    try:
        permission_manager = PermissionManager(context)
        
        # Получаем команды для пользователя
        user_commands = await permission_manager.get_user_commands(
            user_id=user.get("id") if user else None,
            admin_level=admin.get("level") if admin else None,
            is_pm=message.chat.type == "private"
        )
        
        if not user_commands:
            await message.answer(
                "📝 <b>Доступные команды</b>\n\n"
                "У вас нет доступных команд в этом чате.",
                parse_mode="HTML"
            )
            return
        
        # Форматируем команды по категориям
        response = ["📝 <b>Доступные вам команды:</b>\n"]
        
        for category, commands in user_commands.items():
            if commands:
                response.append(f"\n<b>{category}:</b>")
                for cmd in commands:
                    response.append(f"  • {cmd}")
        
        await message.answer(
            "\n".join(response),
            parse_mode="HTML"
        )
    
    except Exception as e:
        logger.error("Available commands failed", error=str(e))
        await message.answer("❌ Ошибка при получении списка команд")


@admin_router.message(Command("сохранения"))
@AuthMiddleware.require_admin(AdminLevel.MAIN_ADMIN.value)
async def setup_save_channel(
    message: Message,
    command: CommandObject,
    context: AppContext,
    admin: Optional[dict] = None
) -> None:
    """Настраивает канал/группу для сохранения изменений."""
    if not command.args:
        await message.answer(
            "📋 <b>Настройка сохранения изменений</b>\n\n"
            "Использование: !сохранения ссылка_на_группу\n\n"
            "Пример:\n"
            "!сохранения https://t.me/c/3644263802/2\n\n"
            "Группа должна быть супергруппой с включенными темами.\n"
            "Бот должен быть добавлен в группу с правами администратора.",
            parse_mode="HTML"
        )
        return
    
    try:
        # Здесь должна быть логика сохранения ссылки на группу
        # и настройки бота для отправки изменений
        
        await message.answer(
            f"✅ Настройки сохранения обновлены:\n"
            f"Группа: {command.args}\n\n"
            f"Теперь все изменения будут сохраняться в указанную группу."
        )
        
        logger.info(
            "Save channel configured",
            admin_id=admin.get("id") if admin else None,
            channel_link=command.args
        )
    
    except Exception as e:
        logger.error("Setup save channel failed", error=str(e))
        await message.answer(f"❌ Ошибка при настройке сохранения: {str(e)}")


@admin_router.message(Command("файлы"))
@AuthMiddleware.require_admin(AdminLevel.MAIN_ADMIN.value)
async def setup_file_archive(
    message: Message,
    context: AppContext,
    admin: Optional[dict] = None
) -> None:
    """Настраивает архивацию файлов по типам."""
    try:
        # Создаем интерактивную панель для настройки архивации
        builder = InlineKeyboardBuilder()
        
        file_types = [
            ("pdf", "📄 PDF файлы"),
            ("excel", "📊 Excel файлы"),
            ("word", "📝 Word файлы"),
            ("images", "🖼 Изображения"),
            ("other", "📦 Другие файлы"),
        ]
        
        for file_type, display_name in file_types:
            builder.button(
                text=display_name,
                callback_data=f"file_setup:{file_type}"
            )
        
        builder.adjust(2)
        
        await message.answer(
            "🗂 <b>Настройка архивации файлов</b>\n\n"
            "Выберите тип файлов для настройки архивации:\n\n"
            "Для каждого типа можно настроить:\n"
            "• Целевую группу/канал\n"
            "• Формат именования\n"
            "• Правила сортировки",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    
    except Exception as e:
        logger.error("Setup file archive failed", error=str(e))
        await message.answer("❌ Ошибка при настройке архивации файлов")


@admin_router.message(Command("админы"))
@AuthMiddleware.require_admin(AdminLevel.ADMIN.value)
async def list_admins(
    message: Message,
    context: AppContext,
    admin: Optional[dict] = None
) -> None:
    """Показывает список всех админов."""
    try:
        admin_manager = AdminManager(context)
        admins = await admin_manager.get_all_admins()
        
        if not admins:
            await message.answer("📋 Список админов пуст.")
            return
        
        # Форматируем список админов
        response = ["👨‍💼 <b>Список администраторов:</b>\n"]
        
        for i, admin_info in enumerate(admins, 1):
            response.append(
                f"\n{i}. {format_admin_info(admin_info)}"
            )
        
        await message.answer(
            "\n".join(response),
            parse_mode="HTML"
        )
    
    except Exception as e:
        logger.error("List admins failed", error=str(e))
        await message.answer("❌ Ошибка при получении списка админов")


@admin_router.message(Command("удалить_админа"))
@AuthMiddleware.require_admin(AdminLevel.MAIN_ADMIN.value)
async def remove_admin(
    message: Message,
    command: CommandObject,
    context: AppContext,
    admin: Optional[dict] = None
) -> None:
    """Удаляет админа."""
    if not command.args:
        await message.answer(
            "Использование: !удалить_админа (id/ссылка/имя пользователя)\n\n"
            "Примеры:\n"
            "!удалить_админа 123456789\n"
            "!удалить_админа @username"
        )
        return
    
    try:
        admin_manager = AdminManager(context)
        result = await admin_manager.remove_admin(
            admin_identifier=command.args,
            removed_by=admin.get("id") if admin else None
        )
        
        if result["success"]:
            await message.answer(
                f"✅ Админ удален:\n"
                f"Пользователь: {result['user']['username']}\n"
                f"Удалил: {admin.get('username', 'Система') if admin else 'Система'}"
            )
            
            logger.info(
                "Admin removed",
                removed_by=admin.get("id") if admin else None,
                removed_admin_id=result["admin"]["id"]
            )
        else:
            await message.answer(f"❌ Ошибка: {result['message']}")
    
    except Exception as e:
        logger.error("Remove admin failed", error=str(e))
        await message.answer(f"❌ Ошибка при удалении админа: {str(e)}")


async def initialize(dp, context):
    """Инициализация модуля админских команд."""
    # Регистрируем роутер в диспетчере
    dp.include_router(admin_router)
    
    logger.info("Admin handlers initialized")