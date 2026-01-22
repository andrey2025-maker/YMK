"""
Обработчики для работы с группами.
Реализует привязку объектов к группам и групповые команды.
"""
import re
from typing import Optional, List, Dict, Any
from aiogram import Router, types, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext

from core.context import AppContext
from core.filters import IsGroupOrSuperGroup, HasCommandAccess
from modules.group.bind_manager import BindManager
from modules.group.access_manager import AccessManager
from handlers.service_handlers import ServiceHandlers
from handlers.installation_handlers import InstallationHandlers

router = Router()
router.message.filter(IsGroupOrSuperGroup())


@router.message(Command("обслуживание"))
async def bind_service_to_group(
    message: types.Message,
    command: CommandObject,
    context: AppContext
) -> None:
    """
    Обработчик команды !обслуживание ХМАО для привязки обслуживания к группе.
    
    Формат: !обслуживание <регион> или !обслуживание <регион> <объект>
    """
    try:
        if not command.args:
            await message.reply(
                "⚠️ Укажите регион обслуживания:\n"
                "Пример: `!обслуживание ХМАО`\n"
                "Или: `!обслуживание ХМАО ТЦ_Мегаполис`"
            )
            return
        
        args = command.args.strip().split()
        region_name = args[0]
        object_name = args[1] if len(args) > 1 else None
        
        bind_manager: BindManager = context.bind_manager
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # Проверяем права пользователя
        access_manager: AccessManager = context.access_manager
        if not await access_manager.check_group_admin(user_id, chat_id):
            await message.reply("⛔ Только администраторы группы могут привязывать объекты.")
            return
        
        # Привязываем объект к группе
        result = await bind_manager.bind_service_to_group(
            chat_id=chat_id,
            region_name=region_name,
            object_name=object_name,
            user_id=user_id
        )
        
        if result['success']:
            response_text = f"✅ Объект обслуживания привязан к группе!\n\n"
            
            if result.get('region'):
                response_text += f"🏙️ Регион: {result['region']['short_name']} - {result['region']['full_name']}\n"
            
            if result.get('object'):
                response_text += f"🏢 Объект: {result['object']['short_name']} - {result['object']['full_name']}\n"
            
            response_text += f"👤 Привязал: @{message.from_user.username or message.from_user.first_name}\n"
            response_text += f"📅 Дата: {result['bind_date']}"
            
            # Сохраняем в архив изменений
            await context.log_manager.log_group_binding(
                chat_id=chat_id,
                user_id=user_id,
                action='bind_service',
                details=result
            )
        else:
            response_text = f"❌ Ошибка: {result.get('error', 'Неизвестная ошибка')}"
        
        await message.reply(response_text)
        
    except Exception as e:
        await message.reply(f"⚠️ Ошибка при привязке: {str(e)}")
        await context.log_manager.log_error(
            user_id=message.from_user.id,
            action='bind_service_to_group',
            error=str(e),
            details={'command': command.args}
        )


@router.message(Command("монтаж"))
async def bind_installation_to_group(
    message: types.Message,
    command: CommandObject,
    context: AppContext
) -> None:
    """
    Обработчик команды !монтаж Сочи для привязки монтажа к группе.
    
    Формат: !монтаж <название объекта>
    """
    try:
        if not command.args:
            await message.reply(
                "⚠️ Укажите объект монтажа:\n"
                "Пример: `!монтаж Сочи`\n"
                "Или: `!монтаж ТРЦ_Галактика`"
            )
            return
        
        object_name = command.args.strip()
        
        bind_manager: BindManager = context.bind_manager
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # Проверяем права пользователя
        access_manager: AccessManager = context.access_manager
        if not await access_manager.check_group_admin(user_id, chat_id):
            await message.reply("⛔ Только администраторы группы могут привязывать объекты.")
            return
        
        # Привязываем объект монтажа к группе
        result = await bind_manager.bind_installation_to_group(
            chat_id=chat_id,
            object_name=object_name,
            user_id=user_id
        )
        
        if result['success']:
            response_text = f"✅ Объект монтажа привязан к группе!\n\n"
            
            if result.get('object'):
                response_text += f"🏗️ Объект: {result['object']['short_name']} - {result['object']['full_name']}\n"
            
            response_text += f"👤 Привязал: @{message.from_user.username or message.from_user.first_name}\n"
            response_text += f"📅 Дата: {result['bind_date']}"
            
            # Сохраняем в архив изменений
            await context.log_manager.log_group_binding(
                chat_id=chat_id,
                user_id=user_id,
                action='bind_installation',
                details=result
            )
        else:
            response_text = f"❌ Ошибка: {result.get('error', 'Неизвестная ошибка')}"
        
        await message.reply(response_text)
        
    except Exception as e:
        await message.reply(f"⚠️ Ошибка при привязке: {str(e)}")
        await context.log_manager.log_error(
            user_id=message.from_user.id,
            action='bind_installation_to_group',
            error=str(e),
            details={'command': command.args}
        )


@router.message(Command(commands=["-обслуживание", "-монтаж"], prefix="!"))
async def remove_binding(
    message: types.Message,
    command: CommandObject,
    context: AppContext
) -> None:
    """
    Обработчик команд !-обслуживание и !-монтаж для удаления привязки.
    
    Формат: !-обслуживание <регион> или !-монтаж <объект>
    """
    try:
        command_name = message.text.split()[0].lower()
        is_service = command_name == "!-обслуживание"
        
        if not command.args:
            binding_type = "обслуживания" if is_service else "монтажа"
            await message.reply(
                f"⚠️ Укажите объект {binding_type} для отвязки:\n"
                f"Пример: `!-обслуживание ХМАО`\n"
                f"Или: `!-монтаж Сочи`"
            )
            return
        
        target_name = command.args.strip()
        
        bind_manager: BindManager = context.bind_manager
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # Проверяем права пользователя
        access_manager: AccessManager = context.access_manager
        if not await access_manager.check_group_admin(user_id, chat_id):
            await message.reply("⛔ Только администраторы группы могут отвязывать объекты.")
            return
        
        # Удаляем привязку
        if is_service:
            result = await bind_manager.unbind_service_from_group(
                chat_id=chat_id,
                region_name=target_name,
                user_id=user_id
            )
            binding_type = "обслуживания"
        else:
            result = await bind_manager.unbind_installation_from_group(
                chat_id=chat_id,
                object_name=target_name,
                user_id=user_id
            )
            binding_type = "монтажа"
        
        if result['success']:
            response_text = f"✅ Объект {binding_type} отвязан от группы!\n\n"
            response_text += f"🎯 Объект: {target_name}\n"
            response_text += f"👤 Отвязал: @{message.from_user.username or message.from_user.first_name}\n"
            response_text += f"📅 Дата: {result['unbind_date']}"
            
            # Сохраняем в архив изменений
            await context.log_manager.log_group_binding(
                chat_id=chat_id,
                user_id=user_id,
                action=f'unbind_{binding_type}',
                details=result
            )
        else:
            response_text = f"❌ Ошибка: {result.get('error', 'Неизвестная ошибка')}"
        
        await message.reply(response_text)
        
    except Exception as e:
        await message.reply(f"⚠️ Ошибка при отвязке: {str(e)}")
        await context.log_manager.log_error(
            user_id=message.from_user.id,
            action='remove_binding',
            error=str(e),
            details={'command': message.text}
        )


@router.message(Command("проекты"))
@router.message(Command("изменения"))
@router.message(Command("письма"))
@router.message(Command("допуски"))
@router.message(Command("журналы"))
async def group_commands(
    message: types.Message,
    command: CommandObject,
    context: AppContext
) -> None:
    """
    Обработчик групповых команд для работы с объектами.
    
    Поддерживает: !проекты, !изменения, !письма, !допуски, !журналы
    """
    try:
        command_name = command.command.lower()
        
        bind_manager: BindManager = context.bind_manager
        chat_id = message.chat.id
        
        # Получаем привязанные объекты для этой группы
        bindings = await bind_manager.get_group_bindings(chat_id)
        
        if not bindings:
            await message.reply(
                "ℹ️ В этой группе нет привязанных объектов.\n"
                "Используйте команды:\n"
                "• `!обслуживание ХМАО` - для обслуживания\n"
                "• `!монтаж Сочи` - для монтажа"
            )
            return
        
        # Если несколько объектов - предлагаем выбор
        if len(bindings) > 1:
            from core.keyboards.inline.navigation import NavigationInlineKeyboard
            
            # Создаем клавиатуру выбора объекта
            items = []
            for binding in bindings:
                if binding['type'] == 'service':
                    text = f"🔧 {binding.get('region_name', 'Обслуживание')}"
                    if binding.get('object_name'):
                        text += f" / {binding['object_name']}"
                    callback = f"group_select_service:{binding['id']}:{command_name}"
                else:
                    text = f"⚡ {binding.get('object_name', 'Монтаж')}"
                    callback = f"group_select_installation:{binding['id']}:{command_name}"
                
                items.append((text, callback))
            
            keyboard = NavigationInlineKeyboard.create_numbered_list_inline(
                items=items,
                items_per_row=1,
                include_back=False
            )
            
            await message.reply(
                f"🔍 Выберите объект для команды `!{command_name}`:",
                reply_markup=keyboard
            )
            return
        
        # Если один объект - сразу выполняем команду
        binding = bindings[0]
        
        if binding['type'] == 'service':
            # Для обслуживания вызываем соответствующий обработчик
            handler = ServiceHandlers(context)
            if command_name == "письма":
                await handler.show_letters(message, binding['object_id'])
            elif command_name == "допуски":
                await handler.show_permits(message, binding['object_id'])
            elif command_name == "журналы":
                await handler.show_journals(message, binding['object_id'])
            else:
                await message.reply(f"⚠️ Команда `!{command_name}` недоступна для объектов обслуживания.")
        else:
            # Для монтажа вызываем соответствующий обработчик
            handler = InstallationHandlers(context)
            if command_name == "проекты":
                await handler.show_projects(message, binding['object_id'])
            elif command_name == "изменения":
                await handler.show_changes(message, binding['object_id'])
            elif command_name == "письма":
                await handler.show_letters(message, binding['object_id'])
            elif command_name == "допуски":
                await handler.show_permits(message, binding['object_id'])
            elif command_name == "журналы":
                await handler.show_journals(message, binding['object_id'])
            else:
                await message.reply(f"⚠️ Команда `!{command_name}` недоступна для объектов монтажа.")
                
    except Exception as e:
        await message.reply(f"⚠️ Ошибка при выполнении команды: {str(e)}")
        await context.log_manager.log_error(
            user_id=message.from_user.id,
            action=f'group_command_{command.command}',
            error=str(e),
            details={'chat_id': message.chat.id}
        )


@router.message(Command("группа_инфо"))
async def group_info(message: types.Message, context: AppContext) -> None:
    """
    Показывает информацию о привязанных объектах в группе.
    """
    try:
        bind_manager: BindManager = context.bind_manager
        chat_id = message.chat.id
        
        bindings = await bind_manager.get_group_bindings(chat_id)
        
        if not bindings:
            await message.reply(
                "📋 Информация о группе:\n"
                "├── Привязанные объекты: нет\n"
                "├── Администраторов: все участники\n"
                "└── Команды: доступны базовые"
            )
            return
        
        response_text = "📋 Информация о привязанных объектах:\n\n"
        
        service_count = 0
        installation_count = 0
        
        for binding in bindings:
            if binding['type'] == 'service':
                service_count += 1
                response_text += f"🔧 Обслуживание:\n"
                response_text += f"  ├── Регион: {binding.get('region_name', 'Не указан')}\n"
                if binding.get('object_name'):
                    response_text += f"  ├── Объект: {binding['object_name']}\n"
                response_text += f"  └── Привязан: {binding.get('bind_date', 'Неизвестно')}\n\n"
            else:
                installation_count += 1
                response_text += f"⚡ Монтаж:\n"
                response_text += f"  ├── Объект: {binding.get('object_name', 'Не указан')}\n"
                response_text += f"  └── Привязан: {binding.get('bind_date', 'Неизвестно')}\n\n"
        
        response_text += f"📊 Итого:\n"
        response_text += f"• Обслуживание: {service_count} объектов\n"
        response_text += f"• Монтаж: {installation_count} объектов\n"
        response_text += f"• Всего: {len(bindings)} объектов"
        
        await message.reply(response_text)
        
    except Exception as e:
        await message.reply(f"⚠️ Ошибка при получении информации: {str(e)}")


@router.message(Command("мои_объекты"))
async def my_objects_in_group(message: types.Message, context: AppContext) -> None:
    """
    Показывает объекты доступные пользователю в этой группе.
    """
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        bind_manager: BindManager = context.bind_manager
        access_manager: AccessManager = context.access_manager
        
        # Получаем все привязки группы
        bindings = await bind_manager.get_group_bindings(chat_id)
        
        if not bindings:
            await message.reply("ℹ️ В этой группе нет привязанных объектов.")
            return
        
        # Фильтруем объекты доступные пользователю
        accessible_objects = []
        
        for binding in bindings:
            if binding['type'] == 'service':
                # Проверяем доступ к объекту обслуживания
                if await access_manager.check_service_access(
                    user_id=user_id,
                    object_id=binding.get('object_id')
                ):
                    accessible_objects.append({
                        'type': 'service',
                        'name': f"{binding.get('region_name', 'Обслуживание')} / {binding.get('object_name', 'Объект')}",
                        'id': binding.get('object_id')
                    })
            else:
                # Проверяем доступ к объекту монтажа
                if await access_manager.check_installation_access(
                    user_id=user_id,
                    object_id=binding.get('object_id')
                ):
                    accessible_objects.append({
                        'type': 'installation',
                        'name': binding.get('object_name', 'Монтаж'),
                        'id': binding.get('object_id')
                    })
        
        if not accessible_objects:
            await message.reply(
                "⛔ У вас нет доступа к объектам в этой группе.\n"
                "Обратитесь к администратору для получения доступа."
            )
            return
        
        # Формируем ответ
        response_text = "🏢 Ваши объекты в этой группе:\n\n"
        
        for idx, obj in enumerate(accessible_objects, 1):
            icon = "🔧" if obj['type'] == 'service' else "⚡"
            response_text += f"{idx}. {icon} {obj['name']}\n"
        
        response_text += f"\n📊 Всего объектов: {len(accessible_objects)}"
        
        # Добавляем подсказки по командам
        response_text += "\n\n💡 Доступные команды:\n"
        response_text += "• `!проекты` - показать проекты\n"
        response_text += "• `!изменения` - показать изменения\n"
        response_text += "• `!письма` - показать переписку\n"
        response_text += "• И другие команды из меню объекта"
        
        await message.reply(response_text)
        
    except Exception as e:
        await message.reply(f"⚠️ Ошибка: {str(e)}")
        await context.log_manager.log_error(
            user_id=message.from_user.id,
            action='my_objects_in_group',
            error=str(e)
        )