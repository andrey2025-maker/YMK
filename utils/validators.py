"""
Валидаторы ввода данных.
Содержит функции для проверки корректности вводимых пользователем данных.
"""
import re
from datetime import datetime
from typing import Any, Optional, Tuple, Union
import phonenumbers

from utils.constants import (
    DATE_FORMAT, REGEX_DATE, REGEX_PHONE, REGEX_EMAIL,
    REGEX_CONTRACT_NUMBER, REGEX_USERNAME,
    MAX_NAME_LENGTH, MAX_ADDRESS_LENGTH, MAX_DESCRIPTION_LENGTH,
    MAX_CONTRACT_NUMBER_LENGTH, MAX_PHONE_LENGTH, MAX_EMAIL_LENGTH
)
from utils.exceptions import ValidationException
from utils.date_utils import parse_date, validate_date


def validate_required(value: Any, field_name: str) -> Any:
    """
    Проверяет что значение не пустое.
    
    Args:
        value: Значение для проверки
        field_name: Название поля для сообщения об ошибке
    
    Returns:
        Проверенное значение
    
    Raises:
        ValidationException: Если значение пустое
    """
    if value is None:
        raise ValidationException(f"Поле '{field_name}' обязательно для заполнения", field_name)
    
    if isinstance(value, str):
        value = value.strip()
        if not value:
            raise ValidationException(f"Поле '{field_name}' обязательно для заполнения", field_name)
    
    return value


def validate_string(value: str, field_name: str, max_length: Optional[int] = None) -> str:
    """
    Проверяет строковое значение.
    
    Args:
        value: Строка для проверки
        field_name: Название поля
        max_length: Максимальная длина (опционально)
    
    Returns:
        Очищенная строка
    
    Raises:
        ValidationException: Если строка невалидна
    """
    value = validate_required(value, field_name)
    
    if not isinstance(value, str):
        raise ValidationException(f"Поле '{field_name}' должно быть строкой", field_name, value)
    
    value = value.strip()
    
    if max_length and len(value) > max_length:
        raise ValidationException(
            f"Поле '{field_name}' не должно превышать {max_length} символов",
            field_name, value
        )
    
    return value


def validate_name(value: str, field_name: str = "название") -> str:
    """
    Проверяет название (короткое или полное).
    
    Args:
        value: Название для проверки
        field_name: Название поля
    
    Returns:
        Проверенное название
    """
    value = validate_string(value, field_name, MAX_NAME_LENGTH)
    
    # Проверяем что название не состоит только из специальных символов
    if re.match(r'^[^a-zA-Zа-яА-Я0-9]+$', value):
        raise ValidationException(
            f"Поле '{field_name}' должно содержать буквы или цифры",
            field_name, value
        )
    
    return value


def validate_date_string(value: str, field_name: str = "дата") -> str:
    """
    Проверяет дату в формате ДД.ММ.ГГГГ.
    
    Args:
        value: Строка с датой
        field_name: Название поля
    
    Returns:
        Проверенная строка даты
    
    Raises:
        ValidationException: Если дата невалидна
    """
    value = validate_required(value, field_name)
    
    if not isinstance(value, str):
        raise ValidationException(f"Поле '{field_name}' должно быть строкой", field_name, value)
    
    value = value.strip()
    
    # Проверяем формат регулярным выражением
    if not re.match(REGEX_DATE, value):
        raise ValidationException(
            f"Поле '{field_name}' должно быть в формате ДД.ММ.ГГГГ",
            field_name, value
        )
    
    # Проверяем что дата валидна (правильное количество дней в месяце и т.д.)
    if not validate_date(value):
        raise ValidationException(
            f"Некорректная дата в поле '{field_name}'",
            field_name, value
        )
    
    return value


def validate_phone(value: str, field_name: str = "телефон") -> str:
    """
    Проверяет номер телефона.
    
    Args:
        value: Номер телефона
        field_name: Название поля
    
    Returns:
        Проверенный номер телефона
    """
    value = validate_required(value, field_name)
    
    if not isinstance(value, str):
        raise ValidationException(f"Поле '{field_name}' должно быть строкой", field_name, value)
    
    value = value.strip()
    
    if len(value) > MAX_PHONE_LENGTH:
        raise ValidationException(
            f"Поле '{field_name}' не должно превышать {MAX_PHONE_LENGTH} символов",
            field_name, value
        )
    
    # Простая проверка регулярным выражением
    if not re.match(REGEX_PHONE, value):
        raise ValidationException(
            f"Некорректный формат телефона в поле '{field_name}'",
            field_name, value
        )
    
    # Дополнительная проверка с помощью phonenumbers
    try:
        parsed = phonenumbers.parse(value, None)
        if not phonenumbers.is_valid_number(parsed):
            raise ValidationException(
                f"Некорректный номер телефона в поле '{field_name}'",
                field_name, value
            )
    except phonenumbers.NumberParseException:
        # Если phonenumbers не смог распарсить, но регулярное выражение прошло,
        # все равно считаем валидным для простоты
        pass
    
    return value


def validate_email(value: str, field_name: str = "email") -> str:
    """
    Проверяет email адрес.
    
    Args:
        value: Email адрес
        field_name: Название поля
    
    Returns:
        Проверенный email
    """
    value = validate_required(value, field_name)
    
    if not isinstance(value, str):
        raise ValidationException(f"Поле '{field_name}' должно быть строкой", field_name, value)
    
    value = value.strip().lower()
    
    if len(value) > MAX_EMAIL_LENGTH:
        raise ValidationException(
            f"Поле '{field_name}' не должно превышать {MAX_EMAIL_LENGTH} символов",
            field_name, value
        )
    
    if not re.match(REGEX_EMAIL, value):
        raise ValidationException(
            f"Некорректный email в поле '{field_name}'",
            field_name, value
        )
    
    return value


def validate_contract_number(value: str, field_name: str = "номер контракта") -> str:
    """
    Проверяет номер контракта.
    
    Args:
        value: Номер контракта
        field_name: Название поля
    
    Returns:
        Проверенный номер контракта
    """
    value = validate_required(value, field_name)
    
    if not isinstance(value, str):
        raise ValidationException(f"Поле '{field_name}' должно быть строкой", field_name, value)
    
    value = value.strip()
    
    if len(value) > MAX_CONTRACT_NUMBER_LENGTH:
        raise ValidationException(
            f"Поле '{field_name}' не должно превышать {MAX_CONTRACT_NUMBER_LENGTH} символов",
            field_name, value
        )
    
    if not re.match(REGEX_CONTRACT_NUMBER, value):
        raise ValidationException(
            f"Некорректный номер контракта в поле '{field_name}'",
            field_name, value
        )
    
    return value


def validate_address(value: str, field_name: str = "адрес") -> str:
    """
    Проверяет адрес.
    
    Args:
        value: Адрес
        field_name: Название поля
    
    Returns:
        Проверенный адрес
    """
    value = validate_required(value, field_name)
    
    if not isinstance(value, str):
        raise ValidationException(f"Поле '{field_name}' должно быть строкой", field_name, value)
    
    value = value.strip()
    
    if len(value) > MAX_ADDRESS_LENGTH:
        raise ValidationException(
            f"Поле '{field_name}' не должно превышать {MAX_ADDRESS_LENGTH} символов",
            field_name, value
        )
    
    # Проверяем что адрес содержит хотя бы одну цифру (номер дома)
    if not re.search(r'\d', value):
        raise ValidationException(
            f"Адрес должен содержать номер дома",
            field_name, value
        )
    
    return value


def validate_description(value: str, field_name: str = "описание") -> str:
    """
    Проверяет описание.
    
    Args:
        value: Описание
        field_name: Название поля
    
    Returns:
        Проверенное описание
    """
    if value is None:
        return ""
    
    if not isinstance(value, str):
        raise ValidationException(f"Поле '{field_name}' должно быть строкой", field_name, value)
    
    value = value.strip()
    
    if value.lower() == "нет":
        return ""
    
    if len(value) > MAX_DESCRIPTION_LENGTH:
        raise ValidationException(
            f"Поле '{field_name}' не должно превышать {MAX_DESCRIPTION_LENGTH} символов",
            field_name, value
        )
    
    return value


def validate_username(value: str, field_name: str = "имя пользователя") -> str:
    """
    Проверяет имя пользователя Telegram.
    
    Args:
        value: Имя пользователя
        field_name: Название поля
    
    Returns:
        Проверенное имя пользователя
    """
    value = validate_required(value, field_name)
    
    if not isinstance(value, str):
        raise ValidationException(f"Поле '{field_name}' должно быть строкой", field_name, value)
    
    value = value.strip()
    
    # Убираем @ если есть
    if value.startswith('@'):
        value = value[1:]
    
    if not re.match(REGEX_USERNAME, value):
        raise ValidationException(
            f"Некорректное имя пользователя в поле '{field_name}'",
            field_name, value
        )
    
    return value


def validate_number(
    value: Union[str, int],
    field_name: str,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None
) -> int:
    """
    Проверяет числовое значение.
    
    Args:
        value: Число или строка с числом
        field_name: Название поля
        min_value: Минимальное значение (опционально)
        max_value: Максимальное значение (опционально)
    
    Returns:
        Проверенное число
    
    Raises:
        ValidationException: Если число невалидно
    """
    value = validate_required(value, field_name)
    
    try:
        if isinstance(value, str):
            num_value = int(value.strip())
        else:
            num_value = int(value)
    except (ValueError, TypeError):
        raise ValidationException(
            f"Поле '{field_name}' должно быть числом",
            field_name, value
        )
    
    if min_value is not None and num_value < min_value:
        raise ValidationException(
            f"Поле '{field_name}' должно быть не меньше {min_value}",
            field_name, value
        )
    
    if max_value is not None and num_value > max_value:
        raise ValidationException(
            f"Поле '{field_name}' должно быть не больше {max_value}",
            field_name, value
        )
    
    return num_value


def validate_boolean(value: Union[str, bool], field_name: str) -> bool:
    """
    Проверяет булево значение.
    
    Args:
        value: Булево значение или строка
        field_name: Название поля
    
    Returns:
        Проверенное булево значение
    """
    value = validate_required(value, field_name)
    
    if isinstance(value, bool):
        return value
    
    if isinstance(value, str):
        value_lower = value.strip().lower()
        if value_lower in ['да', 'yes', 'true', '1', 'есть']:
            return True
        elif value_lower in ['нет', 'no', 'false', '0', 'нету']:
            return False
    
    raise ValidationException(
        f"Поле '{field_name}' должно быть 'да' или 'нет'",
        field_name, value
    )


def validate_yes_no(value: str, field_name: str) -> Tuple[bool, str]:
    """
    Проверяет ответ да/нет и возвращает булево значение и оригинальный текст.
    
    Args:
        value: Ответ пользователя
        field_name: Название поля
    
    Returns:
        Кортеж (булево значение, оригинальный текст)
    """
    value = validate_required(value, field_name)
    
    if not isinstance(value, str):
        raise ValidationException(f"Поле '{field_name}' должно быть строкой", field_name, value)
    
    value = value.strip()
    value_lower = value.lower()
    
    if value_lower in ['да', 'yes', 'true', '1', 'есть']:
        return True, value
    elif value_lower in ['нет', 'no', 'false', '0', 'нету']:
        return False, value
    
    raise ValidationException(
        f"Поле '{field_name}' должно быть 'да' или 'нет'",
        field_name, value
    )


def validate_date_range(
    start_date_str: str,
    end_date_str: str,
    start_field: str = "дата начала",
    end_field: str = "дата окончания"
) -> Tuple[datetime, datetime]:
    """
    Проверяет диапазон дат.
    
    Args:
        start_date_str: Дата начала
        end_date_str: Дата окончания
        start_field: Название поля начала
        end_field: Название поля окончания
    
    Returns:
        Кортеж (дата начала, дата окончания)
    
    Raises:
        ValidationException: Если даты невалидны или диапазон некорректен
    """
    # Проверяем отдельно каждую дату
    validate_date_string(start_date_str, start_field)
    validate_date_string(end_date_str, end_field)
    
    # Парсим даты
    start_date = parse_date(start_date_str)
    end_date = parse_date(end_date_str)
    
    # Проверяем что дата начала не позже даты окончания
    if start_date > end_date:
        raise ValidationException(
            f"Дата начала не может быть позже даты окончания",
            start_field, start_date_str
        )
    
    return start_date, end_date


def validate_file_extension(filename: str, allowed_extensions: set) -> str:
    """
    Проверяет расширение файла.
    
    Args:
        filename: Имя файла
        allowed_extensions: Множество разрешенных расширений
    
    Returns:
        Проверенное имя файла
    
    Raises:
        ValidationException: Если расширение не разрешено
    """
    if not filename:
        raise ValidationException("Имя файла не может быть пустым", "filename")
    
    # Извлекаем расширение
    if '.' not in filename:
        raise ValidationException(f"Файл должен иметь расширение", "filename", filename)
    
    extension = filename.lower().split('.')[-1]
    if f".{extension}" not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise ValidationException(
            f"Расширение .{extension} не разрешено. Разрешены: {allowed}",
            "filename", filename
        )
    
    return filename


def validate_coordinates(value: str, field_name: str = "координаты") -> Tuple[float, float]:
    """
    Проверяет координаты в формате "широта, долгота".
    
    Args:
        value: Строка с координатами
        field_name: Название поля
    
    Returns:
        Кортеж (широта, долгота)
    
    Raises:
        ValidationException: Если координаты невалидны
    """
    value = validate_required(value, field_name)
    
    if not isinstance(value, str):
        raise ValidationException(f"Поле '{field_name}' должно быть строкой", field_name, value)
    
    value = value.strip()
    
    # Разделяем по запятой
    parts = [part.strip() for part in value.split(',')]
    if len(parts) != 2:
        raise ValidationException(
            f"Координаты должны быть в формате 'широта, долгота'",
            field_name, value
        )
    
    try:
        lat = float(parts[0])
        lon = float(parts[1])
    except ValueError:
        raise ValidationException(
            f"Координаты должны быть числами",
            field_name, value
        )
    
    # Проверяем диапазоны
    if not (-90 <= lat <= 90):
        raise ValidationException(
            f"Широта должна быть между -90 и 90",
            field_name, value
        )
    
    if not (-180 <= lon <= 180):
        raise ValidationException(
            f"Долгота должна быть между -180 и 180",
            field_name, value
        )
    
    return lat, lon


def validate_unit(value: str, field_name: str = "единица измерения") -> str:
    """
    Проверяет единицу измерения.
    
    Args:
        value: Единица измерения
        field_name: Название поля
    
    Returns:
        Проверенная единица измерения
    """
    from utils.constants import UNITS
    
    value = validate_required(value, field_name)
    
    if not isinstance(value, str):
        raise ValidationException(f"Поле '{field_name}' должно быть строкой", field_name, value)
    
    value = value.strip()
    
    if value not in UNITS:
        allowed = ", ".join(sorted(UNITS.keys()))
        raise ValidationException(
            f"Недопустимая единица измерения. Допустимые: {allowed}",
            field_name, value
        )
    
    return value


def validate_frequency(value: str, field_name: str = "частота") -> str:
    """
    Проверяет частоту напоминаний.
    
    Args:
        value: Частота
        field_name: Название поля
    
    Returns:
        Проверенная частота
    """
    from utils.constants import FREQUENCY_NAMES
    
    value = validate_required(value, field_name)
    
    if not isinstance(value, str):
        raise ValidationException(f"Поле '{field_name}' должно быть строкой", field_name, value)
    
    value = value.strip().lower()
    
    # Маппинг русских названий на коды
    russian_to_code = {
        'однократно': 'once',
        'ежедневно': 'daily',
        'еженедельно': 'weekly',
        'ежемесячно': 'monthly',
        'ежеквартально': 'quarterly',
        'ежегодно': 'yearly'
    }
    
    # Если значение на русском, конвертируем в код
    if value in russian_to_code:
        return russian_to_code[value]
    
    # Если уже код, проверяем что он валиден
    if value not in FREQUENCY_NAMES:
        allowed = ", ".join(sorted(FREQUENCY_NAMES.values()))
        raise ValidationException(
            f"Недопустимая частота. Допустимые: {allowed}",
            field_name, value
        )
    
    return value