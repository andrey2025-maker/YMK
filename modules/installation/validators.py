"""
Валидаторы для модуля монтажа.
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

class InstallationAddressValidator:
    """Валидатор адресов объектов монтажа."""
    
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


class InstallationDocumentValidator:
    """Валидатор документов монтажа."""
    
    @staticmethod
    def validate_document_number(number: str) -> Tuple[bool, str]:
        """
        Проверяет номер документа.
        
        Args:
            number: Номер документа
            
        Returns:
            Кортеж (успех, сообщение об ошибке)
        """
        if not number or len(number.strip()) == 0:
            return False, "Номер документа не может быть пустым"
        
        number = number.strip()
        
        # Длина номера
        if len(number) < 2:
            return False, "Номер документа слишком короткий"
        
        if len(number) > 100:
            return False, "Номер документа слишком длинный (макс. 100 символов)"
        
        # Разрешенные символы
        pattern = r'^[a-zA-Zа-яА-ЯёЁ0-9/\-№.,()\s]+$'
        if not re.match(pattern, number):
            return False, "Номер документа содержит недопустимые символы"
        
        return True, ""


# ========== Pydantic модели для валидации ==========

class InstallationObjectCreateData(BaseModel):
    """Данные для создания объекта монтажа."""
    
    short_name: str = Field(..., min_length=2, max_length=100, description="Сокращенное название объекта")
    full_name: str = Field(..., min_length=5, max_length=200, description="Полное название объекта")
    addresses: List[str] = Field(..., min_items=1, description="Список адресов объекта")
    contract_type: str = Field(..., description="Тип документа (контракт/гос. контракт/договор)")
    contract_number: str = Field(..., description="Номер контракта")
    contract_date: str = Field(..., description="Дата контракта в формате ДД.ММ.ГГГГ")
    start_date: str = Field(..., description="Дата начала исполнения в формате ДД.ММ.ГГГГ")
    end_date: str = Field(..., description="Дата окончания исполнения в формате ДД.ММ.ГГГГ")
    systems: str = Field(..., description="Монтируемые системы")
    notes: Optional[str] = Field(None, description="Примечания к объекту")
    additional_documents: List[Dict[str, Any]] = Field(default_factory=list, description="Дополнительные соглашения")
    
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
        """Проверяет список монтируемых систем."""
        v = v.strip()
        
        if len(v) < 3:
            raise ValueError("Укажите монтируемые системы")
        
        # Разделяем системы по разделителям
        systems = [s.strip() for s in re.split(r'[;,•]', v) if s.strip()]
        
        if len(systems) == 0:
            raise ValueError("Укажите хотя бы одну монтируемую систему")
        
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
    
    @validator('additional_documents')
    def validate_additional_documents(cls, v):
        """Проверяет дополнительные соглашения."""
        validated_docs = []
        
        for doc_data in v:
            try:
                # Валидируем каждое соглашение
                if not isinstance(doc_data, dict):
                    raise ValueError("Данные документа должны быть словарем")
                
                # Проверяем обязательные поля
                required_fields = ['document_type', 'number', 'date', 'description']
                for field in required_fields:
                    if field not in doc_data:
                        raise ValueError(f"Отсутствует обязательное поле: {field}")
                
                # Валидируем даты
                if 'date' in doc_data and not validate_date(doc_data['date']):
                    raise ValueError(f"Неверный формат даты документа: {doc_data['date']}")
                
                if 'start_date' in doc_data and doc_data['start_date']:
                    if not validate_date(doc_data['start_date']):
                        raise ValueError(f"Неверный формат даты начала: {doc_data['start_date']}")
                
                if 'end_date' in doc_data and doc_data['end_date']:
                    if not validate_date(doc_data['end_date']):
                        raise ValueError(f"Неверный формат даты окончания: {doc_data['end_date']}")
                
                validated_docs.append(doc_data)
                
            except Exception as e:
                raise ValueError(f"Ошибка в документе: {str(e)}")
        
        return validated_docs


class ProjectCreateData(BaseModel):
    """Данные для создания проекта."""
    
    name: str = Field(..., min_length=3, max_length=200, description="Наименование проекта")
    has_file: bool = Field(True, description="Проект должен иметь файл")
    
    @validator('name')
    def validate_name(cls, v):
        """Проверяет наименование проекта."""
        v = v.strip()
        
        if len(v) < 3:
            raise ValueError("Наименование проекта должно содержать минимум 3 символа")
        
        return v


class MaterialCreateData(BaseModel):
    """Данные для добавления материала."""
    
    name: str = Field(..., min_length=2, max_length=200, description="Наименование материала")
    quantity: float = Field(..., gt=0, description="Количество")
    unit: str = Field(..., description="Единица измерения (шт., м., уп., комплект)")
    description: Optional[str] = Field(None, max_length=500, description="Описание")
    
    @validator('name')
    def validate_name(cls, v):
        """Проверяет наименование материала."""
        v = v.strip()
        
        if len(v) < 2:
            raise ValueError("Наименование материала должно содержать минимум 2 символа")
        
        return v
    
    @validator('unit')
    def validate_unit(cls, v):
        """Проверяет единицу измерения."""
        v = v.strip().lower()
        
        valid_units = ['шт.', 'м.', 'уп.', 'компл.', 'кг', 'л', 'м²', 'м³', 'упак.', 'пог.м', 'кв.м']
        
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
        
        # Округляем до 3 знаков после запятой
        return round(v, 3)


class MaterialSectionCreateData(BaseModel):
    """Данные для создания раздела материалов."""
    
    name: str = Field(..., min_length=2, max_length=100, description="Название раздела")
    material_ids: List[str] = Field(default_factory=list, description="ID материалов для включения в раздел")
    
    @validator('name')
    def validate_name(cls, v):
        """Проверяет название раздела."""
        v = v.strip()
        
        if len(v) < 2:
            raise ValueError("Название раздела должно содержать минимум 2 символа")
        
        # Проверка запрещенных символов
        forbidden_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in forbidden_chars:
            if char in v:
                raise ValueError(f"Название раздела содержит запрещенный символ: {char}")
        
        return v


class MontageTrackData(BaseModel):
    """Данные для учета монтажа материала."""
    
    material_id: str = Field(..., description="ID материала")
    installed_quantity: float = Field(..., ge=0, description="Установленное количество")
    
    @validator('installed_quantity')
    def validate_quantity(cls, v):
        """Проверяет количество установленного материала."""
        if v < 0:
            raise ValueError("Количество не может быть отрицательным")
        
        # Ограничиваем слишком большие значения
        if v > 1000000:
            raise ValueError("Количество слишком велико")
        
        # Округляем до 3 знаков после запятой
        return round(v, 3)


class SupplyCreateData(BaseModel):
    """Данные для создания поставки."""
    
    delivery_service: str = Field(..., min_length=2, max_length=100, description="Сервис доставки")
    delivery_date: str = Field(..., description="Дата доставки в формате ДД.ММ.ГГГГ")
    document: Optional[str] = Field(None, max_length=100, description="Номер документа")
    description: str = Field(..., min_length=5, max_length=500, description="Описание поставки")
    
    @validator('delivery_service')
    def validate_delivery_service(cls, v):
        """Проверяет сервис доставки."""
        v = v.strip()
        
        if len(v) < 2:
            raise ValueError("Укажите сервис доставки")
        
        return v
    
    @validator('delivery_date')
    def validate_delivery_date(cls, v):
        """Проверяет дату доставки."""
        if not validate_date(v):
            raise ValueError(f"Неверный формат даты доставки: {v}. Используйте ДД.ММ.ГГГГ")
        
        return v
    
    @validator('document')
    def validate_document(cls, v):
        """Проверяет номер документа."""
        if v is None:
            return v
        
        v = v.strip()
        
        if v.lower() == 'нет':
            return None
        
        if len(v) < 2:
            raise ValueError("Номер документа должен содержать минимум 2 символа")
        
        return v
    
    @validator('description')
    def validate_description(cls, v):
        """Проверяет описание поставки."""
        v = v.strip()
        
        if len(v) < 5:
            raise ValueError("Описание поставки должно содержать минимум 5 символов")
        
        return v


class ChangeCreateData(BaseModel):
    """Данные для создания изменения в проекте."""
    
    description: str = Field(..., min_length=5, max_length=1000, description="Описание изменения")
    has_file: bool = Field(False, description="Есть ли прикрепленный файл")
    
    @validator('description')
    def validate_description(cls, v):
        """Проверяет описание изменения."""
        v = v.strip()
        
        if len(v) < 5:
            raise ValueError("Описание изменения должно содержать минимум 5 символов")
        
        return v


class InstallationDocumentCreateData(BaseModel):
    """Данные для создания документа ИД."""
    
    name: str = Field(..., min_length=3, max_length=200, description="Наименование документа")
    has_file: bool = Field(True, description="Документ должен иметь файл")
    
    @validator('name')
    def validate_name(cls, v):
        """Проверяет наименование документа."""
        v = v.strip()
        
        if len(v) < 3:
            raise ValueError("Наименование документа должно содержать минимум 3 символа")
        
        return v


# ========== Фабрика валидаторов ==========

class InstallationValidatorFactory:
    """Фабрика для создания валидаторов модуля монтажа."""
    
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
            'installation_object': InstallationObjectCreateData,
            'project': ProjectCreateData,
            'material': MaterialCreateData,
            'material_section': MaterialSectionCreateData,
            'montage_track': MontageTrackData,
            'supply': SupplyCreateData,
            'change': ChangeCreateData,
            'installation_document': InstallationDocumentCreateData,
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
            validator_class = InstallationValidatorFactory.get_validator(data_type)
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

def validate_installation_name(name: str, is_short: bool = True) -> Tuple[bool, str]:
    """
    Проверяет название объекта монтажа (сокращенное или полное).
    
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


def validate_document_count(count_str: str) -> Tuple[bool, str, int]:
    """
    Проверяет количество дополнительных документов.
    
    Args:
        count_str: Строка с количеством документов
        
    Returns:
        Кортеж (успех, сообщение об ошибке, количество)
    """
    try:
        count = int(count_str)
    except ValueError:
        return False, "Количество документов должно быть числом", 0
    
    if count < 0:
        return False, "Количество документов не может быть отрицательным", 0
    
    if count > 50:
        return False, "Слишком много документов (макс. 50)", 0
    
    return True, "", count


def validate_material_selection(selection_str: str, max_materials: int) -> Tuple[bool, List[int], str]:
    """
    Проверяет выбор материалов для раздела.
    
    Args:
        selection_str: Строка с выбранными материалами (например, "1, 2, 5, 17")
        max_materials: Максимальное количество материалов
        
    Returns:
        Кортеж (успех, список ID, сообщение об ошибке)
    """
    if not selection_str or len(selection_str.strip()) == 0:
        return False, [], "Выбор материалов не может быть пустым"
    
    selection_str = selection_str.strip()
    
    try:
        # Разделяем строку и преобразуем в числа
        numbers = [int(num.strip()) for num in selection_str.split(',') if num.strip()]
        
        if not numbers:
            return False, [], "Не выбрано ни одного материала"
        
        # Проверяем диапазон
        for num in numbers:
            if num < 1 or num > max_materials:
                return False, [], f"Номер материала {num} вне диапазона (1-{max_materials})"
        
        # Проверяем уникальность
        if len(numbers) != len(set(numbers)):
            return False, [], "Материалы не должны повторяться"
        
        return True, numbers, ""
        
    except ValueError:
        return False, [], "Неверный формат. Используйте числа, разделенные запятыми: 1, 2, 5"


# Экспорт основных классов и функций
__all__ = [
    'InstallationObjectCreateData',
    'ProjectCreateData',
    'MaterialCreateData',
    'MaterialSectionCreateData',
    'MontageTrackData',
    'SupplyCreateData',
    'ChangeCreateData',
    'InstallationDocumentCreateData',
    'InstallationValidatorFactory',
    'InstallationAddressValidator',
    'InstallationDocumentValidator',
    'validate_installation_name',
    'validate_document_count',
    'validate_material_selection',
]