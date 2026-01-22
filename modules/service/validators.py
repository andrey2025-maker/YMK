"""
Валидаторы для модуля обслуживания.
Реализует проверку всех входных данных согласно требованиям ТЗ.
"""

import re
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, validator, root_validator
from pydantic.error_wrappers import ValidationError

from utils.date_utils import parse_date, validate_date
from utils.exceptions import ValidationException


# ========== Базовые валидаторы ==========

class AddressValidator:
    """Валидатор адресов объектов."""
    
    @staticmethod
    def validate_address(address: str) -> Tuple[bool, str]:
        """
        Проверяет корректность адреса.
        
        Args:
            address: Адрес для проверки
            
        Returns:
            Кортеж (успех, сообщение об ошибке)
        """
        if not address or len(address.strip()) == 0:
            return False, "Адрес не может быть пустым"
        
        address = address.strip()
        
        # Минимальная длина адреса
        if len(address) < 5:
            return False, "Адрес слишком короткий"
        
        # Максимальная длина
        if len(address) > 500:
            return False, "Адрес слишком длинный (макс. 500 символов)"
        
        return True, ""

    @staticmethod
    def validate_address_count(count_str: str) -> Tuple[bool, str, int]:
        """
        Проверяет количество адресов.
        
        Args:
            count_str: Строка с количеством адресов
            
        Returns:
            Кортеж (успех, сообщение об ошибке, количество)
        """
        try:
            count = int(count_str)
        except ValueError:
            return False, "Количество адресов должно быть числом", 0
        
        if count < 1:
            return False, "Количество адресов должно быть положительным числом", 0
        
        if count > 50:
            return False, "Слишком много адресов (макс. 50)", 0
        
        return True, "", count


class ContractValidator:
    """Валидатор данных контрактов."""
    
    @staticmethod
    def validate_contract_number(number: str) -> Tuple[bool, str]:
        """
        Проверяет номер контракта.
        
        Args:
            number: Номер контракта
            
        Returns:
            Кортеж (успех, сообщение об ошибке)
        """
        if not number or len(number.strip()) == 0:
            return False, "Номер контракта не может быть пустым"
        
        number = number.strip()
        
        # Длина номера
        if len(number) < 2:
            return False, "Номер контракта слишком короткий"
        
        if len(number) > 100:
            return False, "Номер контракта слишком длинный (макс. 100 символов)"
        
        # Разрешенные символы
        pattern = r'^[a-zA-Zа-яА-ЯёЁ0-9/\-№.,()\s]+$'
        if not re.match(pattern, number):
            return False, "Номер контракта содержит недопустимые символы"
        
        return True, ""
    
    @staticmethod
    def validate_contract_type(contract_type: str) -> Tuple[bool, str]:
        """
        Проверяет тип документа контракта.
        
        Args:
            contract_type: Тип документа
            
        Returns:
            Кортеж (успех, сообщение об ошибке)
        """
        if not contract_type or len(contract_type.strip()) == 0:
            return False, "Тип документа не может быть пустым"
        
        contract_type = contract_type.strip()
        
        # Проверяем, что тип содержит одно из ожидаемых значений
        valid_types = ['контракт', 'гос. контракт', 'договор', 'государственный контракт']
        
        if contract_type.lower() not in valid_types:
            # Но разрешаем любой текст, если пользователь хочет уточнить
            if len(contract_type) < 3:
                return False, "Тип документа слишком короткий"
            
            if len(contract_type) > 100:
                return False, "Тип документа слишком длинный (макс. 100 символов)"
        
        return True, ""


class DateRangeValidator:
    """Валидатор диапазонов дат."""
    
    @staticmethod
    def validate_date_range(start_date_str: str, end_date_str: str) -> Tuple[bool, str]:
        """
        Проверяет корректность диапазона дат.
        
        Args:
            start_date_str: Дата начала в формате ДД.ММ.ГГГГ
            end_date_str: Дата окончания в формате ДД.ММ.ГГГГ
            
        Returns:
            Кортеж (успех, сообщение об ошибке)
        """
        # Валидация формата дат
        if not validate_date(start_date_str):
            return False, f"Неверный формат даты начала: {start_date_str}. Используйте ДД.ММ.ГГГГ"
        
        if not validate_date(end_date_str):
            return False, f"Неверный формат даты окончания: {end_date_str}. Используйте ДД.ММ.ГГГГ"
        
        try:
            start_date = parse_date(start_date_str)
            end_date = parse_date(end_date_str)
            
            # Проверяем, что дата начала раньше даты окончания
            if start_date > end_date:
                return False, "Дата начала не может быть позже даты окончания"
            
            # Проверяем разумные пределы (не более 50 лет)
            if (end_date - start_date).days > 365 * 50:
                return False, "Срок контракта не может превышать 50 лет"
            
            return True, ""
            
        except Exception as e:
            return False, f"Ошибка при обработке дат: {str(e)}"


# ========== Pydantic модели для валидации ==========

class RegionCreateData(BaseModel):
    """Данные для создания региона обслуживания."""
    
    short_name: str = Field(..., min_length=2, max_length=50, description="Сокращенное наименование региона")
    full_name: str = Field(..., min_length=5, max_length=200, description="Полное наименование региона")
    
    @validator('short_name')
    def validate_short_name(cls, v):
        """Проверяет сокращенное название региона."""
        v = v.strip()
        
        # Запрещенные символы
        forbidden_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in forbidden_chars:
            if char in v:
                raise ValueError(f"Сокращенное название содержит запрещенный символ: {char}")
        
        return v
    
    @validator('full_name')
    def validate_full_name(cls, v):
        """Проверяет полное название региона."""
        v = v.strip()
        
        if len(v) < 5:
            raise ValueError("Полное название региона должно содержать минимум 5 символов")
        
        return v


class ServiceObjectCreateData(BaseModel):
    """Данные для создания объекта обслуживания."""
    
    short_name: str = Field(..., min_length=2, max_length=100, description="Сокращенное название объекта")
    full_name: str = Field(..., min_length=5, max_length=200, description="Полное название объекта")
    addresses: List[str] = Field(..., min_items=1, description="Список адресов объекта")
    contract_type: str = Field(..., description="Тип документа (контракт/гос. контракт/договор)")
    contract_number: str = Field(..., description="Номер контракта")
    contract_date: str = Field(..., description="Дата контракта в формате ДД.ММ.ГГГГ")
    start_date: str = Field(..., description="Дата начала исполнения в формате ДД.ММ.ГГГГ")
    end_date: str = Field(..., description="Дата окончания исполнения в формате ДД.ММ.ГГГГ")
    systems: str = Field(..., description="Обслуживаемые системы")
    zip_payment: str = Field(..., description="За чей счет покупается ЗИП")
    has_dispatching: bool = Field(..., description="Наличие диспетчеризации")
    notes: Optional[str] = Field(None, description="Примечания к объекту")
    
    @validator('short_name')
    def validate_short_name(cls, v):
        """Проверяет сокращенное название объекта."""
        v = v.strip()
        
        if len(v) < 2:
            raise ValueError("Сокращенное название должно содержать минимум 2 символа")
        
        # Проверка запрещенных символов
        forbidden_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '!']
        for char in forbidden_chars:
            if char in v:
                raise ValueError(f"Сокращенное название содержит запрещенный символ: {char}")
        
        return v
    
    @validator('full_name')
    def validate_full_name(cls, v):
        """Проверяет полное название объекта."""
        v = v.strip()
        
        if len(v) < 5:
            raise ValueError("Полное название должно содержать минимум 5 символов")
        
        return v
    
    @validator('addresses', each_item=True)
    def validate_addresses(cls, v):
        """Проверяет каждый адрес в списке."""
        v = v.strip()
        
        if len(v) < 5:
            raise ValueError("Адрес должен содержать минимум 5 символов")
        
        if len(v) > 500:
            raise ValueError("Адрес слишком длинный (макс. 500 символов)")
        
        return v
    
    @validator('contract_date', 'start_date', 'end_date')
    def validate_date_format(cls, v):
        """Проверяет формат даты."""
        if not validate_date(v):
            raise ValueError(f"Неверный формат даты: {v}. Используйте ДД.ММ.ГГГГ")
        return v
    
    @validator('contract_number')
    def validate_contract_number(cls, v):
        """Проверяет номер контракта."""
        v = v.strip()
        
        if len(v) < 2:
            raise ValueError("Номер контракта должен содержать минимум 2 символа")
        
        if len(v) > 100:
            raise ValueError("Номер контракта слишком длинный (макс. 100 символов)")
        
        return v
    
    @validator('systems')
    def validate_systems(cls, v):
        """Проверяет список обслуживаемых систем."""
        v = v.strip()
        
        if len(v) < 3:
            raise ValueError("Укажите обслуживаемые системы")
        
        # Разделяем системы по разделителям
        systems = [s.strip() for s in re.split(r'[;,•]', v) if s.strip()]
        
        if len(systems) == 0:
            raise ValueError("Укажите хотя бы одну обслуживаемую систему")
        
        # Объединяем обратно для хранения
        return " • ".join(systems)
    
    @root_validator
    def validate_date_ranges(cls, values):
        """Проверяет корректность диапазонов дат."""
        start_date = values.get('start_date')
        end_date = values.get('end_date')
        contract_date = values.get('contract_date')
        
        if not all([start_date, end_date, contract_date]):
            return values
        
        try:
            # Парсим даты
            start = parse_date(start_date)
            end = parse_date(end_date)
            contract = parse_date(contract_date)
            
            # Контракт не должен быть позже начала исполнения
            if contract > start:
                raise ValueError("Дата контракта не может быть позже даты начала исполнения")
            
            # Начало не должно быть позже окончания
            if start > end:
                raise ValueError("Дата начала не может быть позже даты окончания")
            
            # Контракт не должен быть в будущем (допускается +/- 1 день)
            now = datetime.now()
            if (contract - now).days > 1:
                raise ValueError("Дата контракта не может быть в будущем")
            
        except ValueError as e:
            raise ValueError(f"Ошибка в датах: {str(e)}")
        
        return values


class ProblemCreateData(BaseModel):
    """Данные для создания проблемы."""
    
    description: str = Field(..., min_length=5, max_length=1000, description="Описание проблемы")
    has_file: bool = Field(False, description="Есть ли прикрепленный файл")
    
    @validator('description')
    def validate_description(cls, v):
        """Проверяет описание проблемы."""
        v = v.strip()
        
        if len(v) < 5:
            raise ValueError("Описание проблемы должно содержать минимум 5 символов")
        
        # Проверяем на явно неинформативные описания
        uninformative = ['нет', 'без описания', 'пусто', '...', '---']
        if v.lower() in uninformative:
            raise ValueError("Пожалуйста, укажите содержательное описание проблемы")
        
        return v


class MaintenanceCreateData(BaseModel):
    """Данные для создания ТО (технического обслуживания)."""
    
    frequency: str = Field(..., description="Частота обслуживания")
    month: Optional[int] = Field(None, ge=1, le=12, description="Месяц выполнения (1-12)")
    description: str = Field(..., min_length=3, max_length=500, description="Описание ТО")
    
    @validator('frequency')
    def validate_frequency(cls, v):
        """Проверяет частоту обслуживания."""
        v = v.strip()
        
        valid_frequencies = ['раз в неделю', 'раз в месяц', 'раз в квартал', 
                            'раз в полгода', 'раз в год', 'ежедневно', 'по требованию']
        
        if v.lower() not in valid_frequencies:
            # Разрешаем пользовательские частоты, но проверяем длину
            if len(v) < 3:
                raise ValueError("Укажите частоту обслуживания")
        
        return v
    
    @validator('description')
    def validate_description(cls, v):
        """Проверяет описание ТО."""
        v = v.strip()
        
        if len(v) < 3:
            raise ValueError("Описание ТО должно содержать минимум 3 символа")
        
        return v


class EquipmentCreateData(BaseModel):
    """Данные для добавления оборудования."""
    
    name: str = Field(..., min_length=2, max_length=200, description="Наименование оборудования")
    quantity: float = Field(..., gt=0, description="Количество")
    unit: str = Field(..., description="Единица измерения (шт., м., уп., комплект)")
    description: Optional[str] = Field(None, max_length=500, description="Описание")
    
    @validator('name')
    def validate_name(cls, v):
        """Проверяет наименование оборудования."""
        v = v.strip()
        
        if len(v) < 2:
            raise ValueError("Наименование оборудования должно содержать минимум 2 символа")
        
        return v
    
    @validator('unit')
    def validate_unit(cls, v):
        """Проверяет единицу измерения."""
        v = v.strip().lower()
        
        valid_units = ['шт.', 'м.', 'уп.', 'компл.', 'кг', 'л', 'м²', 'м³', 'упак.']
        
        # Проверяем, что единица измерения корректна или заканчивается на точку
        if v not in valid_units and not v.endswith('.'):
            # Позволяем пользовательские единицы, но добавляем точку если нужно
            if not v.endswith('.'):
                v = v + '.'
        
        return v
    
    @validator('quantity')
    def validate_quantity(cls, v):
        """Проверяет количество."""
        if v <= 0:
            raise ValueError("Количество должно быть положительным числом")
        
        # Ограничиваем слишком большие значения
        if v > 1000000:
            raise ValueError("Количество слишком велико")
        
        # Округляем до 2 знаков после запятой
        return round(v, 2)


class LetterCreateData(BaseModel):
    """Данные для создания письма."""
    
    number: str = Field(..., min_length=2, max_length=50, description="Номер письма")
    date: str = Field(..., description="Дата письма в формате ДД.ММ.ГГГГ")
    description: str = Field(..., min_length=5, max_length=500, description="Описание письма")
    has_file: bool = Field(False, description="Есть ли прикрепленный файл")
    
    @validator('number')
    def validate_number(cls, v):
        """Проверяет номер письма."""
        v = v.strip()
        
        # Проверяем формат номера (обычно содержит цифры и слэши)
        if len(v) < 2:
            raise ValueError("Номер письма должен содержать минимум 2 символа")
        
        return v
    
    @validator('date')
    def validate_date(cls, v):
        """Проверяет дату письма."""
        if not validate_date(v):
            raise ValueError(f"Неверный формат даты: {v}. Используйте ДД.ММ.ГГГГ")
        
        # Проверяем, что дата не в будущем
        try:
            date_obj = parse_date(v)
            now = datetime.now()
            
            # Допускаем даты на 1 день вперед (на случай разных часовых поясов)
            if (date_obj - now).days > 1:
                raise ValueError("Дата письма не может быть в будущем")
            
        except Exception:
            # Если не удалось распарсить, дата уже проверена validate_date
            pass
        
        return v
    
    @validator('description')
    def validate_description(cls, v):
        """Проверяет описание письма."""
        v = v.strip()
        
        if len(v) < 5:
            raise ValueError("Описание письма должно содержать минимум 5 символов")
        
        return v


class AdditionalDocumentData(BaseModel):
    """Данные для дополнительного соглашения."""
    
    document_type: str = Field(..., description="Тип документа")
    number: str = Field(..., min_length=2, max_length=50, description="Номер документа")
    date: str = Field(..., description="Дата документа в формате ДД.ММ.ГГГГ")
    start_date: Optional[str] = Field(None, description="Дата начала в формате ДД.ММ.ГГГГ")
    end_date: Optional[str] = Field(None, description="Дата окончания в формате ДД.ММ.ГГГГ")
    description: str = Field(..., min_length=5, max_length=500, description="Описание документа")
    
    @validator('date', 'start_date', 'end_date')
    def validate_document_dates(cls, v, field):
        """Проверяет даты документа."""
        if v is None:
            return v
            
        if not validate_date(v):
            raise ValueError(f"Неверный формат даты {field.name}: {v}. Используйте ДД.ММ.ГГГГ")
        return v
    
    @validator('number')
    def validate_document_number(cls, v):
        """Проверяет номер документа."""
        v = v.strip()
        
        if len(v) < 2:
            raise ValueError("Номер документа должен содержать минимум 2 символа")
        
        return v
    
    @root_validator
    def validate_document_date_ranges(cls, values):
        """Проверяет корректность диапазонов дат для документа."""
        start_date = values.get('start_date')
        end_date = values.get('end_date')
        
        if start_date and end_date:
            try:
                start = parse_date(start_date)
                end = parse_date(end_date)
                
                if start > end:
                    raise ValueError("Дата начала не может быть позже даты окончания")
                
            except Exception as e:
                raise ValueError(f"Ошибка в датах документа: {str(e)}")
        
        return values


# ========== Фабрика валидаторов ==========

class ServiceValidatorFactory:
    """Фабрика для создания валидаторов модуля обслуживания."""
    
    @staticmethod
    def get_validator(data_type: str) -> Any:
        """
        Возвращает класс валидатора для указанного типа данных.
        
        Args:
            data_type: Тип данных для валидации
            
        Returns:
            Класс валидатора (Pydantic модель)
            
        Raises:
            ValueError: Если тип данных не поддерживается
        """
        validators = {
            'region': RegionCreateData,
            'object': ServiceObjectCreateData,
            'problem': ProblemCreateData,
            'maintenance': MaintenanceCreateData,
            'equipment': EquipmentCreateData,
            'letter': LetterCreateData,
            'additional_document': AdditionalDocumentData,
        }
        
        if data_type not in validators:
            raise ValueError(f"Неизвестный тип данных для валидации: {data_type}")
        
        return validators[data_type]
    
    @staticmethod
    def validate(data_type: str, data: Dict[str, Any]) -> Tuple[bool, Optional[BaseModel], str]:
        """
        Валидирует данные для указанного типа.
        
        Args:
            data_type: Тип данных для валидации
            data: Словарь с данными для проверки
            
        Returns:
            Кортеж (успех, валидированные данные, сообщение об ошибке)
        """
        try:
            validator_class = ServiceValidatorFactory.get_validator(data_type)
            validated_data = validator_class(**data)
            return True, validated_data, ""
        except ValidationError as e:
            # Извлекаем первую ошибку для пользователя
            errors = e.errors()
            if errors:
                first_error = errors[0]
                field = first_error.get('loc', [''])[0]
                msg = first_error.get('msg', 'Неизвестная ошибка валидации')
                error_message = f"Ошибка в поле '{field}': {msg}"
            else:
                error_message = "Ошибка валидации данных"
            return False, None, error_message
        except Exception as e:
            return False, None, f"Ошибка при валидации: {str(e)}"


# ========== Утилитные функции валидации ==========

def validate_object_name(name: str, is_short: bool = True) -> Tuple[bool, str]:
    """
    Проверяет название объекта (сокращенное или полное).
    
    Args:
        name: Название для проверки
        is_short: True для сокращенного названия, False для полного
        
    Returns:
        Кортеж (успех, сообщение об ошибке)
    """
    if not name or len(name.strip()) == 0:
        return False, "Название не может быть пустым"
    
    name = name.strip()
    
    if is_short:
        if len(name) < 2:
            return False, "Сокращенное название должно содержать минимум 2 символа"
        if len(name) > 100:
            return False, "Сокращенное название слишком длинное (макс. 100 символов)"
    else:
        if len(name) < 5:
            return False, "Полное название должно содержать минимум 5 символов"
        if len(name) > 200:
            return False, "Полное название слишком длинное (макс. 200 символов)"
    
    # Проверка запрещенных символов для сокращенного названия
    if is_short:
        forbidden_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '!']
        for char in forbidden_chars:
            if char in name:
                return False, f"Название содержит запрещенный символ: {char}"
    
    return True, ""


def validate_yes_no_answer(answer: str) -> Tuple[bool, Optional[bool], str]:
    """
    Проверяет ответ да/нет и преобразует в булево значение.
    
    Args:
        answer: Ответ пользователя
        
    Returns:
        Кортеж (успех, булево значение, сообщение об ошибке)
    """
    if not answer:
        return False, None, "Ответ не может быть пустым"
    
    answer = answer.strip().lower()
    
    yes_answers = ['да', 'yes', 'y', 'д', '+', 'есть', 'имеется']
    no_answers = ['нет', 'no', 'n', 'н', '-', 'отсутствует', 'не имеется']
    
    if answer in yes_answers:
        return True, True, ""
    elif answer in no_answers:
        return True, False, ""
    else:
        return False, None, "Пожалуйста, ответьте 'да' или 'нет'"


def validate_note_text(note: str) -> Tuple[bool, Optional[str], str]:
    """
    Проверяет текст примечания.
    
    Args:
        note: Текст примечания
        
    Returns:
        Кортеж (успех, текст примечания или None, сообщение об ошибке)
    """
    if not note:
        return True, None, ""
    
    note = note.strip()
    
    # Если пользователь написал "нет", то примечания нет
    if note.lower() == 'нет':
        return True, None, ""
    
    # Проверяем минимальную длину для реального примечания
    if len(note) < 3:
        return False, None, "Примечание должно содержать минимум 3 символа или быть 'нет'"
    
    # Максимальная длина
    if len(note) > 1000:
        return False, None, "Примечание слишком длинное (макс. 1000 символов)"
    
    return True, note, ""


# Экспорт основных классов и функций
__all__ = [
    'RegionCreateData',
    'ServiceObjectCreateData',
    'ProblemCreateData',
    'MaintenanceCreateData',
    'EquipmentCreateData',
    'LetterCreateData',
    'AdditionalDocumentData',
    'ServiceValidatorFactory',
    'AddressValidator',
    'ContractValidator',
    'DateRangeValidator',
    'validate_object_name',
    'validate_yes_no_answer',
    'validate_note_text',
]