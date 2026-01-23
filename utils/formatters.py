"""
Форматтеры сообщений.
Содержит функции для форматирования данных в читаемые сообщения.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from utils.constants import (
    EMOJI_REGION, EMOJI_OBJECT, EMOJI_CONTRACT, EMOJI_DATE, EMOJI_ADDRESS,
    EMOJI_SYSTEMS, EMOJI_ZIP, EMOJI_DISPATCH, EMOJI_NOTE, EMOJI_PROBLEM,
    EMOJI_MAINTENANCE, EMOJI_EQUIPMENT, EMOJI_LETTER, EMOJI_PERMIT,
    EMOJI_JOURNAL, EMOJI_DOCUMENT, EMOJI_PROJECT, EMOJI_MATERIAL,
    EMOJI_INSTALLATION, EMOJI_SUPPLY, EMOJI_CHANGE, EMOJI_ID, EMOJI_REMINDER,
    EMOJI_USER, EMOJI_FILE, EMOJI_SEARCH, EMOJI_BACK, EMOJI_NEXT,
    EMOJI_OK, EMOJI_CANCEL, EMOJI_EDIT, EMOJI_DELETE, EMOJI_ADD,
    EMOJI_INFO, EMOJI_WARNING, EMOJI_ERROR, EMOJI_SUCCESS, EMOJI_LOADING,
    DATE_FORMAT, DATETIME_FORMAT
)
from utils.date_utils import format_date


def format_bold(text: str) -> str:
    """
    Форматирует текст как жирный (для Markdown).
    
    Args:
        text: Текст для форматирования
    
    Returns:
        Жирный текст
    """
    return f"**{text}**"


def format_italic(text: str) -> str:
    """
    Форматирует текст как курсив (для Markdown).
    
    Args:
        text: Текст для форматирования
    
    Returns:
        Курсивный текст
    """
    return f"_{text}_"


def format_code(text: str) -> str:
    """
    Форматирует текст как код (для Markdown).
    
    Args:
        text: Текст для форматирования
    
    Returns:
        Текст в коде
    """
    return f"`{text}`"


def format_header(text: str, level: int = 1) -> str:
    """
    Форматирует текст как заголовок (для Markdown).
    
    Args:
        text: Текст заголовка
        level: Уровень заголовка (1-3)
    
    Returns:
        Форматированный заголовок
    """
    hashes = "#" * min(max(level, 1), 3)
    return f"{hashes} {text}"


def format_list(items: List[str], numbered: bool = False) -> str:
    """
    Форматирует список элементов.
    
    Args:
        items: Список элементов
        numbered: Нумерованный ли список
    
    Returns:
        Форматированный список
    """
    if not items:
        return ""
    
    result = []
    for i, item in enumerate(items, 1):
        prefix = f"{i}." if numbered else "•"
        result.append(f"{prefix} {item}")
    
    return "\n".join(result)


def format_key_value(key: str, value: Any, emoji: Optional[str] = None) -> str:
    """
    Форматирует пару ключ-значение.
    
    Args:
        key: Ключ
        value: Значение
        emoji: Эмодзи для ключа (опционально)
    
    Returns:
        Форматированная строка
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return ""
    
    prefix = f"{emoji} " if emoji else ""
    return f"{prefix}{key}: {value}"


def format_date_display(date_value: Union[str, datetime]) -> str:
    """
    Форматирует дату для отображения.
    
    Args:
        date_value: Дата как строка или объект datetime
    
    Returns:
        Отформатированная дата
    """
    if isinstance(date_value, datetime):
        return date_value.strftime(DATE_FORMAT)
    elif isinstance(date_value, str):
        try:
            # Пытаемся распарсить и отформатировать
            from utils.date_utils import parse_date
            date_obj = parse_date(date_value)
            return date_obj.strftime(DATE_FORMAT)
        except:
            return date_value
    else:
        return str(date_value)


def format_datetime_display(datetime_value: Union[str, datetime]) -> str:
    """
    Форматирует дату и время для отображения.
    
    Args:
        datetime_value: Дата и время как строка или объект datetime
    
    Returns:
        Отформатированные дата и время
    """
    if isinstance(datetime_value, datetime):
        return datetime_value.strftime(DATETIME_FORMAT)
    elif isinstance(datetime_value, str):
        try:
            from utils.date_utils import parse_datetime
            dt_obj = parse_datetime(datetime_value)
            return dt_obj.strftime(DATETIME_FORMAT)
        except:
            return datetime_value
    else:
        return str(datetime_value)


def format_service_object(obj_data: Dict[str, Any]) -> str:
    """
    Форматирует объект обслуживания для отображения.
    
    Args:
        obj_data: Данные объекта
    
    Returns:
        Отформатированное описание объекта
    """
    lines = []
    
    # Заголовок
    if obj_data.get('short_name') and obj_data.get('full_name'):
        title = f"{obj_data['short_name']} - {obj_data['full_name']}"
        lines.append(format_bold(title))
    
    # Контракт
    contract_lines = []
    if obj_data.get('document_type') and obj_data.get('contract_number'):
        contract_text = f"{obj_data['document_type']} № {obj_data['contract_number']}"
        contract_lines.append(format_key_value("Документ", contract_text, EMOJI_CONTRACT))
    
    if obj_data.get('contract_date'):
        contract_lines.append(format_key_value("Дата", format_date_display(obj_data['contract_date']), EMOJI_DATE))
    
    if obj_data.get('start_date') and obj_data.get('end_date'):
        dates_text = f"с {format_date_display(obj_data['start_date'])} до {format_date_display(obj_data['end_date'])}"
        contract_lines.append(format_key_value("Сроки", dates_text, EMOJI_DATE))
    
    if contract_lines:
        lines.extend(contract_lines)
    
    # Адреса
    addresses = obj_data.get('addresses', [])
    if addresses:
        lines.append(f"{EMOJI_ADDRESS} Адреса:")
        for i, address in enumerate(addresses, 1):
            lines.append(f"  {i}. {address}")
    
    # Системы
    systems = obj_data.get('systems', [])
    if systems:
        systems_text = " • ".join(systems)
        lines.append(format_key_value("Системы", systems_text, EMOJI_SYSTEMS))
    
    # ЗИП
    if obj_data.get('zip_info'):
        lines.append(format_key_value("ЗИП", obj_data['zip_info'], EMOJI_ZIP))
    
    # Диспетчеризация
    if obj_data.get('has_dispatch') is not None:
        dispatch_text = "есть" if obj_data['has_dispatch'] else "нет"
        lines.append(format_key_value("Диспетчеризация", dispatch_text, EMOJI_DISPATCH))
    
    # Примечания
    if obj_data.get('notes'):
        lines.append(format_key_value("Примечания", obj_data['notes'], EMOJI_NOTE))
    
    return "\n".join(filter(None, lines))


def format_problem(problem_data: Dict[str, Any], index: Optional[int] = None) -> str:
    """
    Форматирует проблему для отображения.
    
    Args:
        problem_data: Данные проблемы
        index: Номер проблемы (опционально)
    
    Returns:
        Отформатированное описание проблемы
    """
    prefix = f"{index}. " if index is not None else ""
    
    lines = []
    lines.append(f"{prefix}{EMOJI_PROBLEM} {problem_data.get('description', '')}")
    
    if problem_data.get('file_info'):
        lines.append(f"   {EMOJI_FILE} {problem_data['file_info']}")
    
    if problem_data.get('created_at'):
        date_text = format_date_display(problem_data['created_at'])
        lines.append(f"   📅 {date_text}")
    
    if problem_data.get('status'):
        status_emoji = EMOJI_SUCCESS if problem_data['status'] == 'resolved' else EMOJI_WARNING
        lines.append(f"   {status_emoji} {problem_data['status']}")
    
    return "\n".join(lines)


def format_maintenance(maintenance_data: Dict[str, Any], index: Optional[int] = None) -> str:
    """
    Форматирует ТО для отображения.
    
    Args:
        maintenance_data: Данные ТО
        index: Номер ТО (опционально)
    
    Returns:
        Отформатированное описание ТО
    """
    prefix = f"{index}. " if index is not None else ""
    
    lines = []
    lines.append(f"{prefix}{EMOJI_MAINTENANCE} {maintenance_data.get('description', '')}")
    
    if maintenance_data.get('frequency'):
        lines.append(f"   🔄 Частота: {maintenance_data['frequency']}")
    
    if maintenance_data.get('months'):
        months_text = ", ".join(str(m) for m in maintenance_data['months'])
        lines.append(f"   📅 Месяцы: {months_text}")
    
    if maintenance_data.get('last_performed'):
        last_text = format_date_display(maintenance_data['last_performed'])
        lines.append(f"   ⏱ Последнее: {last_text}")
    
    if maintenance_data.get('next_due'):
        next_text = format_date_display(maintenance_data['next_due'])
        lines.append(f"   ⏰ Следующее: {next_text}")
    
    return "\n".join(lines)


def format_equipment(equipment_data: Dict[str, Any], index: Optional[int] = None) -> str:
    """
    Форматирует оборудование для отображения.
    
    Args:
        equipment_data: Данные оборудования
        index: Номер оборудования (опционально)
    
    Returns:
        Отформатированное описание оборудования
    """
    prefix = f"{index}. " if index is not None else ""
    
    name = equipment_data.get('name', '')
    quantity = equipment_data.get('quantity', 0)
    unit = equipment_data.get('unit', 'шт.')
    
    line = f"{prefix}{EMOJI_EQUIPMENT} {name}: {quantity} {unit}"
    
    if equipment_data.get('description'):
        line += f" ({equipment_data['description']})"
    
    return line


def format_reminder(reminder_data: Dict[str, Any], index: Optional[int] = None) -> str:
    """
    Форматирует напоминание для отображения.
    
    Args:
        reminder_data: Данные напоминания
        index: Номер напоминания (опционально)
    
    Returns:
        Отформатированное описание напоминания
    """
    prefix = f"{index}. " if index is not None else ""
    
    lines = []
    
    # Дата и заголовок
    if reminder_data.get('due_date'):
        date_text = format_datetime_display(reminder_data['due_date'])
        title = reminder_data.get('title', 'Напоминание')
        lines.append(f"{prefix}{EMOJI_REMINDER} {date_text} - {title}")
    else:
        lines.append(f"{prefix}{EMOJI_REMINDER} {reminder_data.get('title', 'Напоминание')}")
    
    # Описание
    if reminder_data.get('description'):
        lines.append(f"   📝 {reminder_data['description']}")
    
    # Объект
    if reminder_data.get('object_type') and reminder_data.get('object_name'):
        obj_type = reminder_data['object_type'].replace('_', ' ').title()
        lines.append(f"   {EMOJI_OBJECT} {obj_type}: {reminder_data['object_name']}")
    
    # Частота
    if reminder_data.get('frequency') and reminder_data['frequency'] != 'once':
        lines.append(f"   🔄 Повтор: {reminder_data['frequency']}")
    
    # Уведомления
    if reminder_data.get('days_before'):
        days_text = ", ".join(str(d) for d in reminder_data['days_before'])
        lines.append(f"   🔔 Уведомление за: {days_text} д.")
    
    return "\n".join(lines)


def format_pagination_info(page: int, total_pages: int, total_items: int, page_size: int) -> str:
    """
    Форматирует информацию о пагинации.
    
    Args:
        page: Текущая страница
        total_pages: Всего страниц
        total_items: Всего элементов
        page_size: Размер страницы
    
    Returns:
        Информация о пагинации
    """
    start_item = (page - 1) * page_size + 1
    end_item = min(page * page_size, total_items)
    
    return f"📄 Страница {page}/{total_pages} (элементы {start_item}-{end_item} из {total_items})"


def format_search_results(results: List[Dict[str, Any]], query: str) -> str:
    """
    Форматирует результаты поиска.
    
    Args:
        results: Список результатов
        query: Поисковый запрос
    
    Returns:
        Отформатированные результаты поиска
    """
    if not results:
        return f"{EMOJI_SEARCH} По запросу '{query}' ничего не найдено."
    
    lines = [f"{EMOJI_SEARCH} Результаты поиска по запросу '{query}':"]
    
    for i, result in enumerate(results, 1):
        result_type = result.get('type', 'Объект').replace('_', ' ').title()
        result_name = result.get('name', 'Без названия')
        result_desc = result.get('description', '')[:100]
        
        line = f"{i}. **{result_type}**: {result_name}"
        if result_desc:
            line += f"\n   {result_desc}"
        
        lines.append(line)
    
    return "\n\n".join(lines)


def format_file_info(file_data: Dict[str, Any]) -> str:
    """
    Форматирует информацию о файле.
    
    Args:
        file_data: Данные файла
    
    Returns:
        Отформатированная информация о файле
    """
    lines = []
    
    # Название
    if file_data.get('file_name'):
        lines.append(f"{EMOJI_FILE} {format_bold(file_data['file_name'])}")
    
    # Размер
    if file_data.get('file_size'):
        size_mb = file_data['file_size'] / (1024 * 1024)
        lines.append(f"   📏 Размер: {size_mb:.2f} MB")
    
    # Тип
    if file_data.get('file_type'):
        lines.append(f"   📋 Тип: {file_data['file_type']}")
    
    # Дата загрузки
    if file_data.get('upload_date'):
        date_text = format_datetime_display(file_data['upload_date'])
        lines.append(f"   📅 Загружен: {date_text}")
    
    # Загрузил
    if file_data.get('uploader_name'):
        lines.append(f"   {EMOJI_USER} Загрузил: {file_data['uploader_name']}")
    
    # Описание
    if file_data.get('description'):
        lines.append(f"   📝 Описание: {file_data['description']}")
    
    return "\n".join(lines)


def format_user_info(user_data: Dict[str, Any]) -> str:
    """
    Форматирует информацию о пользователе.
    
    Args:
        user_data: Данные пользователя
    
    Returns:
        Отформатированная информация о пользователе
    """
    lines = []
    
    # Имя
    if user_data.get('full_name'):
        lines.append(f"{EMOJI_USER} {format_bold(user_data['full_name'])}")
    elif user_data.get('username'):
        lines.append(f"{EMOJI_USER} @{user_data['username']}")
    
    # Роль
    if user_data.get('role'):
        role_emoji = {
            'main_admin': '👑',
            'admin': '⚡',
            'service': '🔧',
            'installation': '⚙️'
        }.get(user_data['role'], '👤')
        lines.append(f"   {role_emoji} Роль: {user_data['role_name']}")
    
    # Контакты
    if user_data.get('phone'):
        lines.append(f"   📞 Телефон: {user_data['phone']}")
    
    if user_data.get('email'):
        lines.append(f"   📧 Email: {user_data['email']}")
    
    # Статистика
    if user_data.get('object_count') is not None:
        lines.append(f"   📊 Объектов: {user_data['object_count']}")
    
    if user_data.get('last_active'):
        last_active = format_datetime_display(user_data['last_active'])
        lines.append(f"   ⏰ Последняя активность: {last_active}")
    
    return "\n".join(lines)


def format_confirmation_message(
    action: str,
    object_type: str,
    object_name: str,
    details: Optional[str] = None
) -> str:
    """
    Форматирует сообщение подтверждения действия.
    
    Args:
        action: Действие (удалить, изменить и т.д.)
        object_type: Тип объекта
        object_name: Название объекта
        details: Детали действия (опционально)
    
    Returns:
        Сообщение подтверждения
    """
    action_names = {
        'delete': 'удалить',
        'edit': 'изменить',
        'add': 'добавить',
        'cancel': 'отменить',
        'confirm': 'подтвердить'
    }
    
    action_text = action_names.get(action, action)
    object_type_text = object_type.replace('_', ' ').title()
    
    lines = [f"⚠️ **Подтверждение действия**"]
    lines.append(f"Вы действительно хотите {action_text} {object_type_text.lower()}?")
    lines.append(f"")
    lines.append(f"**{object_type_text}:** {object_name}")
    
    if details:
        lines.append(f"")
        lines.append(f"**Детали:**")
        lines.append(details)
    
    return "\n".join(lines)


def format_error_message(error: Exception, user_friendly: bool = True) -> str:
    """
    Форматирует сообщение об ошибке.
    
    Args:
        error: Исключение
        user_friendly: Пользовательский ли формат (без технических деталей)
    
    Returns:
        Отформатированное сообщение об ошибке
    """
    from utils.exceptions import BotException
    
    if user_friendly:
        # Пользовательские сообщения
        if isinstance(error, BotException):
            return f"{EMOJI_ERROR} {error.message}"
        
        # Общие ошибки
        error_messages = {
            'Permission denied': 'Нет прав доступа',
            'Invalid format': 'Неверный формат данных',
            'Not found': 'Объект не найден',
            'Already exists': 'Объект уже существует',
            'Validation failed': 'Ошибка валидации данных',
            'Database error': 'Ошибка базы данных',
            'Network error': 'Сетевая ошибка',
            'Timeout': 'Таймаут операции'
        }
        
        error_str = str(error)
        for eng, rus in error_messages.items():
            if eng.lower() in error_str.lower():
                return f"{EMOJI_ERROR} {rus}"
        
        return f"{EMOJI_ERROR} Произошла ошибка. Пожалуйста, попробуйте позже."
    else:
        # Техническое сообщение для логирования
        error_type = type(error).__name__
        error_msg = str(error)
        return f"[{error_type}] {error_msg}"


def format_success_message(message: str, details: Optional[str] = None) -> str:
    """
    Форматирует сообщение об успешном выполнении.
    
    Args:
        message: Основное сообщение
        details: Детали (опционально)
    
    Returns:
        Отформатированное сообщение об успехе
    """
    lines = [f"{EMOJI_SUCCESS} {message}"]
    
    if details:
        lines.append(f"")
        lines.append(details)
    
    return "\n".join(lines)


def format_warning_message(message: str, details: Optional[str] = None) -> str:
    """
    Форматирует предупреждающее сообщение.
    
    Args:
        message: Основное сообщение
        details: Детали (опционально)
    
    Returns:
        Отформатированное предупреждение
    """
    lines = [f"{EMOJI_WARNING} {message}"]
    
    if details:
        lines.append(f"")
        lines.append(details)
    
    return "\n".join(lines)


def format_info_message(message: str, details: Optional[str] = None) -> str:
    """
    Форматирует информационное сообщение.
    
    Args:
        message: Основное сообщение
        details: Детали (опционально)
    
    Returns:
        Отформатированное информационное сообщение
    """
    lines = [f"{EMOJI_INFO} {message}"]
    
    if details:
        lines.append(f"")
        lines.append(details)
    
    return "\n".join(lines)


def format_loading_message(message: str = "Загрузка...") -> str:
    """
    Форматирует сообщение о загрузке.
    
    Args:
        message: Сообщение о загрузке
    
    Returns:
        Отформатированное сообщение о загрузке
    """
    return f"{EMOJI_LOADING} {message}"