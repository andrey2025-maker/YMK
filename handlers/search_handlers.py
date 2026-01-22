"""
Обработчики поиска по данным.
Реализует глобальный поиск по всем доступным данным с пагинацией.
"""
from typing import List, Dict, Any, Optional
from aiogram import Router, types, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext

from core.context import AppContext
from core.filters import HasCommandAccess
from services.search_service import SearchService
from utils.paginator import Paginator
from core.keyboards.inline.navigation import NavigationInlineKeyboard
from utils.date_utils import format_date

router = Router()


@router.message(Command("поиск"), HasCommandAccess())
async def search_command(
    message: types.Message,
    command: CommandObject,
    context: AppContext
) -> None:
    """
    Обработчик команды !поиск для глобального поиска по данным.
    
    Формат: !поиск <запрос>
    Поиск по: объектам обслуживания, монтажа, проблемам, письмам, ТО и т.д.
    """
    try:
        if not command.args:
            await message.reply(
                "🔍 Глобальный поиск\n\n"
                "Ищет по всем доступным вам данным:\n"
                "• Объекты обслуживания и монтажа\n"
                "• Проблемы и ТО\n"
                "• Письма и документы\n"
                "• Оборудование и материалы\n\n"
                "Формат: `!поиск <запрос>`\n"
                "Пример: `!поиск извещатели`\n"
                "        `!поиск ХМАО`\n"
                "        `!поиск контракт 45-23`"
            )
            return
        
        search_query = command.args.strip()
        user_id = message.from_user.id
        
        # Получаем сервис поиска
        search_service: SearchService = context.search_service
        
        # Выполняем поиск
        results = await search_service.global_search(
            query=search_query,
            user_id=user_id,
            limit=50  # Ограничиваем для пагинации
        )
        
        if not results:
            await message.reply(
                f"🔍 По запросу '{search_query}' ничего не найдено.\n\n"
                f"💡 Попробуйте:\n"
                f"• Изменить запрос\n"
                "• Использовать часть слова\n"
                "• Поискать в конкретном разделе"
            )
            return
        
        # Группируем результаты по типам
        results_by_type = {}
        for result in results:
            result_type = result.get('type', 'other')
            if result_type not in results_by_type:
                results_by_type[result_type] = []
            results_by_type[result_type].append(result)
        
        # Формируем сводную информацию
        total_results = len(results)
        type_summary = []
        
        for result_type, type_results in results_by_type.items():
            type_count = len(type_results)
            type_name = self._get_type_name(result_type)
            type_summary.append(f"{type_name}: {type_count}")
        
        # Отправляем первую страницу результатов
        await send_search_results_page(
            message=message,
            results=results[:10],  # Первые 10 результатов
            page=0,
            total_pages=(total_results + 9) // 10,
            search_query=search_query,
            total_results=total_results,
            type_summary=type_summary
        )
        
        # Сохраняем результаты в кэш для пагинации
        cache_key = f"search:{user_id}:{message.message_id}"
        await context.cache.set(
            key=cache_key,
            value={
                'results': results,
                'query': search_query,
                'timestamp': message.date.timestamp()
            },
            ttl=600  # 10 минут как в ТЗ
        )
        
        # Логируем поиск
        await context.log_manager.log_search(
            user_id=user_id,
            query=search_query,
            results_count=total_results
        )
        
    except Exception as e:
        await message.reply(f"⚠️ Ошибка при поиске: {str(e)}")
        await context.log_manager.log_error(
            user_id=message.from_user.id,
            action='search_command',
            error=str(e)
        )


async def send_search_results_page(
    message: types.Message,
    results: List[Dict[str, Any]],
    page: int,
    total_pages: int,
    search_query: str,
    total_results: int,
    type_summary: List[str]
) -> None:
    """
    Отправляет страницу результатов поиска.
    """
    response_text = (
        f"🔍 Результаты поиска: '{search_query}'\n"
        f"📊 Найдено: {total_results} результатов\n"
        f"📑 По типам: {', '.join(type_summary)}\n\n"
    )
    
    # Отображаем результаты текущей страницы
    start_num = page * 10 + 1
    for idx, result in enumerate(results, start=start_num):
        result_type = result.get('type', 'other')
        result_title = result.get('title', 'Без названия')
        result_subtitle = result.get('subtitle', '')
        result_date = result.get('date')
        
        type_icon = _get_type_icon(result_type)
        
        response_text += f"{idx}. {type_icon} {result_title}\n"
        if result_subtitle:
            response_text += f"   {result_subtitle}\n"
        if result_date:
            response_text += f"   📅 {format_date(result_date)}\n"
        response_text += "\n"
    
    response_text += f"📄 Страница {page + 1}/{total_pages}\n"
    
    # Создаем клавиатуру пагинации
    keyboard = NavigationInlineKeyboard.create_pagination_inline(
        current_page=page,
        total_pages=total_pages,
        prefix=f"search_page:{search_query}",
        include_back=False,
        total_items=total_results
    )
    
    # Добавляем кнопки фильтрации по типам
    if len(type_summary) > 1:
        from core.keyboards.inline.navigation import NavigationInlineKeyboard
        builder = types.InlineKeyboardBuilder()
        
        # Добавляем существующую пагинацию
        if keyboard.inline_keyboard:
            for row in keyboard.inline_keyboard:
                builder.row(*row)
        
        # Добавляем кнопки фильтрации
        builder.button(text="🎯 Фильтровать по типу", callback_data=f"search_filter:{search_query}")
        
        keyboard = builder.as_markup()
    
    await message.reply(response_text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("search_page:"))
async def handle_search_results(
    callback: types.CallbackQuery,
    context: AppContext
) -> None:
    """
    Обработчик пагинации результатов поиска.
    
    Callback format: search_page:<query>:<page>
    """
    try:
        data_parts = callback.data.split(":")
        if len(data_parts) < 3:
            await callback.answer("⚠️ Неверный формат")
            return
        
        search_query = data_parts[1]
        page = int(data_parts[2])
        user_id = callback.from_user.id
        
        # Получаем результаты из кэша
        cache_key = f"search:{user_id}:{callback.message.message_id}"
        cached_data = await context.cache.get(cache_key)
        
        if not cached_data or cached_data.get('query') != search_query:
            await callback.answer("⚠️ Результаты поиска устарели", show_alert=True)
            return
        
        results = cached_data.get('results', [])
        total_results = len(results)
        
        if total_results == 0:
            await callback.answer("⚠️ Нет результатов")
            return
        
        # Вычисляем диапазон для текущей страницы
        start_idx = page * 10
        end_idx = min(start_idx + 10, total_results)
        page_results = results[start_idx:end_idx]
        
        # Группируем результаты по типам для сводки
        results_by_type = {}
        for result in results:
            result_type = result.get('type', 'other')
            if result_type not in results_by_type:
                results_by_type[result_type] = []
            results_by_type[result_type].append(result)
        
        type_summary = []
        for result_type, type_results in results_by_type.items():
            type_name = _get_type_name(result_type)
            type_summary.append(f"{type_name}: {len(type_results)}")
        
        # Обновляем сообщение с новой страницей
        await update_search_results_page(
            callback=callback,
            results=page_results,
            page=page,
            total_pages=(total_results + 9) // 10,
            search_query=search_query,
            total_results=total_results,
            type_summary=type_summary
        )
        
        await callback.answer()
        
    except Exception as e:
        await callback.answer(f"⚠️ Ошибка: {str(e)}", show_alert=True)
        await context.log_manager.log_error(
            user_id=callback.from_user.id,
            action='handle_search_results',
            error=str(e)
        )


async def update_search_results_page(
    callback: types.CallbackQuery,
    results: List[Dict[str, Any]],
    page: int,
    total_pages: int,
    search_query: str,
    total_results: int,
    type_summary: List[str]
) -> None:
    """
    Обновляет страницу результатов поиска.
    """
    response_text = (
        f"🔍 Результаты поиска: '{search_query}'\n"
        f"📊 Найдено: {total_results} результатов\n"
        f"📑 По типам: {', '.join(type_summary)}\n\n"
    )
    
    # Отображаем результаты текущей страницы
    start_num = page * 10 + 1
    for idx, result in enumerate(results, start=start_num):
        result_type = result.get('type', 'other')
        result_title = result.get('title', 'Без названия')
        result_subtitle = result.get('subtitle', '')
        result_date = result.get('date')
        
        type_icon = _get_type_icon(result_type)
        
        response_text += f"{idx}. {type_icon} {result_title}\n"
        if result_subtitle:
            response_text += f"   {result_subtitle}\n"
        if result_date:
            response_text += f"   📅 {format_date(result_date)}\n"
        response_text += "\n"
    
    response_text += f"📄 Страница {page + 1}/{total_pages}\n"
    
    # Создаем клавиатуру пагинации
    keyboard = NavigationInlineKeyboard.create_pagination_inline(
        current_page=page,
        total_pages=total_pages,
        prefix=f"search_page:{search_query}",
        include_back=False,
        total_items=total_results
    )
    
    await callback.message.edit_text(
        response_text,
        reply_markup=keyboard
    )


@router.callback_query(F.data.startswith("search_result:"))
async def handle_search_result_select(
    callback: types.CallbackQuery,
    context: AppContext
) -> None:
    """
    Обработчик выбора конкретного результата поиска.
    
    Callback format: search_result:<type>:<id>:<action>
    """
    try:
        data_parts = callback.data.split(":")
        if len(data_parts) < 4:
            await callback.answer("⚠️ Неверный формат")
            return
        
        result_type = data_parts[1]
        result_id = data_parts[2]
        action = data_parts[3]
        
        # В зависимости от типа результата выполняем разные действия
        if result_type == 'service_object':
            # Открываем объект обслуживания
            from handlers.service_handlers import ServiceHandlers
            handler = ServiceHandlers(context)
            await handler.show_object_panel_by_id(callback, result_id)
            
        elif result_type == 'installation_object':
            # Открываем объект монтажа
            from handlers.installation_handlers import InstallationHandlers
            handler = InstallationHandlers(context)
            await handler.show_object_panel_by_id(callback, result_id)
            
        elif result_type == 'problem':
            # Показываем проблему
            await show_problem_details(callback, result_id, context)
            
        elif result_type == 'document':
            # Показываем документ
            await show_document_details(callback, result_id, context)
            
        else:
            await callback.answer(f"⚠️ Тип результата '{result_type}' не поддерживается", show_alert=True)
        
        await callback.answer()
        
    except Exception as e:
        await callback.answer(f"⚠️ Ошибка: {str(e)}", show_alert=True)
        await context.log_manager.log_error(
            user_id=callback.from_user.id,
            action='handle_search_result_select',
            error=str(e)
        )


async def show_problem_details(
    callback: types.CallbackQuery,
    problem_id: str,
    context: AppContext
) -> None:
    """Показывает детали проблемы."""
    try:
        from modules.service.data_managers.problem_manager import ProblemManager
        problem_manager = ProblemManager(context)
        
        problem = await problem_manager.get_problem(problem_id)
        if not problem:
            await callback.answer("⚠️ Проблема не найдена", show_alert=True)
            return
        
        # Проверяем доступ
        user_id = callback.from_user.id
        if not await problem_manager.check_access(user_id, problem_id):
            await callback.answer("⛔ Нет доступа к этой проблеме", show_alert=True)
            return
        
        response_text = (
            f"⚠️ Проблема\n\n"
            f"🏷️ Название: {problem.get('title', 'Без названия')}\n"
            f"📅 Дата: {format_date(problem.get('created_at'))}\n"
            f"🏢 Объект: {problem.get('object_name', 'Неизвестно')}\n"
            f"👤 Автор: {problem.get('author_name', 'Неизвестно')}\n\n"
            f"📝 Описание:\n{problem.get('description', 'Нет описания')}\n\n"
        )
        
        if problem.get('status') == 'resolved':
            response_text += f"✅ Решено: {format_date(problem.get('resolved_at'))}\n"
            if problem.get('solution'):
                response_text += f"💡 Решение: {problem.get('solution')}\n"
        
        # Проверяем наличие файлов
        if problem.get('has_files'):
            response_text += "\n📁 Прикрепленные файлы: есть\n"
        
        await callback.message.edit_text(response_text)
        
    except Exception as e:
        await callback.answer(f"⚠️ Ошибка: {str(e)}", show_alert=True)


def _get_type_icon(result_type: str) -> str:
    """Возвращает иконку для типа результата."""
    icons = {
        'service_object': '🔧',
        'installation_object': '⚡',
        'problem': '⚠️',
        'maintenance': '🔧',
        'letter': '📨',
        'document': '📄',
        'equipment': '🛠️',
        'material': '📦',
        'project': '📁',
        'reminder': '🔔',
        'other': '📝'
    }
    return icons.get(result_type, '📝')


def _get_type_name(result_type: str) -> str:
    """Возвращает читаемое название типа результата."""
    names = {
        'service_object': 'Обслуживание',
        'installation_object': 'Монтаж',
        'problem': 'Проблемы',
        'maintenance': 'ТО',
        'letter': 'Письма',
        'document': 'Документы',
        'equipment': 'Оборудование',
        'material': 'Материалы',
        'project': 'Проекты',
        'reminder': 'Напоминания',
        'other': 'Другое'
    }
    return names.get(result_type, 'Другое')