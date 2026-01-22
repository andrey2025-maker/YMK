"""
Сервис для валидации всех входных данных.
Реализует проверку форматов дат, текстов, контрактов и других данных согласно ТЗ.
"""

import re
import logging
from typing import Optional, Dict, Any, List, Union, Tuple
from datetime import datetime, date
from enum import Enum

import phonenumbers
from pydantic import BaseModel, ValidationError, validator, Field

from utils.date_utils import parse_date, validate_date

logger = logging.getLogger(__name__)


class ValidationResult:
    """Результат валидации."""
    
    def __init__(self, is_valid: bool, message: Optional[str] = None, errors: Optional[List[str]] = None):
        self.is_valid = is_valid
        self.message = message
        self.errors = errors or []
    
    def __bool__(self):
        return self.is_valid
    
    @classmethod
    def success(cls, message: Optional[str] = None):
        """Создание успешного результата."""
        return cls(is_valid=True, message=message)
    
    @classmethod
    def error(cls, message: str, errors: Optional[List[str]] = None):
        """Создание результата с ошибкой."""
        return cls(is_valid=False, message=message, errors=errors or [message])


class DateFormat(str, Enum):
    """Форматы дат."""
    DD_MM_YYYY = "DD.MM.YYYY"
    YYYY_MM_DD = "YYYY-MM-DD"
    ISO = "ISO"


class ContractType(str, Enum):
    """Типы контрактов."""
    CONTRACT = "контракт"
    GOVERNMENT_CONTRACT = "гос. контракт"
    AGREEMENT = "договор"
    SUPPLEMENTARY_AGREEMENT = "дополнительное соглашение"


class ValidationService:
    """Сервис для валидации данных."""
    
    # Регулярные выражения для валидации
    REGEX_CONTRACT_NUMBER = r'^[а-яА-Яa-zA-Z0-9№.\-/]+$'
    REGEX_SHORT_NAME = r'^[а-яА-Яa-zA-Z0-9\s\-_]{1,50}$'
    REGEX_FULL_NAME = r'^[а-яА-Яa-zA-Z0-9\s\-_.,()]{1,200}$'
    REGEX_ADDRESS = r'^[а-яА-Яa-zA-Z0-9\s\-_.,()№"/]{1,500}$'
    REGEX_SYSTEM_NAME = r'^[а-яА-Яa-zA-Z0-9\s\-_.,()]{1,100}$'
    
    def __init__(self):
        self.date_format = DateFormat.DD_MM_YYYY
    
    def validate_date_string(self, date_str: str) -> ValidationResult:
        """
        Валидация строки с датой в формате ДД.ММ.ГГГГ.
        
        Args:
            date_str: Строка с датой
            
        Returns:
            Результат валидации
        """
        try:
            if not date_str:
                return ValidationResult.error("Дата не может быть пустой")
            
            # Проверяем базовый формат
            if not re.match(r'^\d{2}\.\d{2}\.\d{4}$', date_str):
                return ValidationResult.error(
                    "Неверный формат даты. Используйте ДД.ММ.ГГГГ (например, 31.12.2025)"
                )
            
            # Парсим дату
            parsed_date = parse_date(date_str)
            if not parsed_date:
                return ValidationResult.error("Некорректная дата")
            
            return ValidationResult.success(f"Дата '{date_str}' корректна")
            
        except Exception as e:
            logger.error(f"Error validating date '{date_str}': {e}")
            return ValidationResult.error(f"Ошибка валидации даты: {str(e)}")
    
    def validate_date_range(
        self, 
        start_date_str: str, 
        end_date_str: str
    ) -> ValidationResult:
        """
        Валидация диапазона дат.
        
        Args:
            start_date_str: Дата начала
            end_date_str: Дата окончания
            
        Returns:
            Результат валидации
        """
        try:
            # Валидируем отдельные даты
            start_result = self.validate_date_string(start_date_str)
            if not start_result:
                return start_result
            
            end_result = self.validate_date_string(end_date_str)
            if not end_result:
                return end_result
            
            # Парсим даты
            start_date = parse_date(start_date_str)
            end_date = parse_date(end_date_str)
            
            # Проверяем что дата начала раньше даты окончания
            if start_date >= end_date:
                return ValidationResult.error(
                    "Дата начала должна быть раньше даты окончания"
                )
            
            return ValidationResult.success("Диапазон дат корректен")
            
        except Exception as e:
            logger.error(f"Error validating date range '{start_date_str}' - '{end_date_str}': {e}")
            return ValidationResult.error(f"Ошибка валидации диапазона дат: {str(e)}")
    
    def validate_contract_number(self, contract_number: str) -> ValidationResult:
        """
        Валидация номера контракта.
        
        Args:
            contract_number: Номер контракта
            
        Returns:
            Результат валидации
        """
        try:
            if not contract_number:
                return ValidationResult.error("Номер контракта не может быть пустым")
            
            if len(contract_number) > 100:
                return ValidationResult.error("Номер контракта слишком длинный (макс. 100 символов)")
            
            if not re.match(self.REGEX_CONTRACT_NUMBER, contract_number):
                return ValidationResult.error(
                    "Номер контракта содержит недопустимые символы. "
                    "Допустимы буквы, цифры, №, ., -, /"
                )
            
            return ValidationResult.success("Номер контракта корректен")
            
        except Exception as e:
            logger.error(f"Error validating contract number '{contract_number}': {e}")
            return ValidationResult.error(f"Ошибка валидации номера контракта: {str(e)}")
    
    def validate_short_name(self, name: str) -> ValidationResult:
        """
        Валидация сокращенного названия.
        
        Args:
            name: Сокращенное название
            
        Returns:
            Результат валидации
        """
        try:
            if not name:
                return ValidationResult.error("Сокращенное название не может быть пустым")
            
            if len(name) < 2:
                return ValidationResult.error("Сокращенное название слишком короткое (мин. 2 символа)")
            
            if len(name) > 50:
                return ValidationResult.error("Сокращенное название слишком длинное (макс. 50 символов)")
            
            if not re.match(self.REGEX_SHORT_NAME, name):
                return ValidationResult.error(
                    "Сокращенное название содержит недопустимые символы"
                )
            
            return ValidationResult.success("Сокращенное название корректно")
            
        except Exception as e:
            logger.error(f"Error validating short name '{name}': {e}")
            return ValidationResult.error(f"Ошибка валидации сокращенного названия: {str(e)}")
    
    def validate_full_name(self, name: str) -> ValidationResult:
        """
        Валидация полного названия.
        
        Args:
            name: Полное название
            
        Returns:
            Результат валидации
        """
        try:
            if not name:
                return ValidationResult.error("Полное название не может быть пустым")
            
            if len(name) < 5:
                return ValidationResult.error("Полное название слишком короткое (мин. 5 символов)")
            
            if len(name) > 200:
                return ValidationResult.error("Полное название слишком длинное (макс. 200 символов)")
            
            if not re.match(self.REGEX_FULL_NAME, name):
                return ValidationResult.error(
                    "Полное название содержит недопустимые символы"
                )
            
            return ValidationResult.success("Полное название корректно")
            
        except Exception as e:
            logger.error(f"Error validating full name '{name}': {e}")
            return ValidationResult.error(f"Ошибка валидации полного названия: {str(e)}")
    
    def validate_address(self, address: str) -> ValidationResult:
        """
        Валидация адреса.
        
        Args:
            address: Адрес
            
        Returns:
            Результат валидации
        """
        try:
            if not address:
                return ValidationResult.error("Адрес не может быть пустым")
            
            if len(address) < 5:
                return ValidationResult.error("Адрес слишком короткий (мин. 5 символов)")
            
            if len(address) > 500:
                return ValidationResult.error("Адрес слишком длинный (макс. 500 символов)")
            
            if not re.match(self.REGEX_ADDRESS, address):
                return ValidationResult.error(
                    "Адрес содержит недопустимые символы"
                )
            
            return ValidationResult.success("Адрес корректен")
            
        except Exception as e:
            logger.error(f"Error validating address '{address}': {e}")
            return ValidationResult.error(f"Ошибка валидации адреса: {str(e)}")
    
    def validate_system_name(self, system_name: str) -> ValidationResult:
        """
        Валидация названия системы.
        
        Args:
            system_name: Название системы
            
        Returns:
            Результат валидации
        """
        try:
            if not system_name:
                return ValidationResult.error("Название системы не может быть пустым")
            
            if len(system_name) < 2:
                return ValidationResult.error("Название системы слишком короткое (мин. 2 символа)")
            
            if len(system_name) > 100:
                return ValidationResult.error("Название системы слишком длинное (макс. 100 символов)")
            
            if not re.match(self.REGEX_SYSTEM_NAME, system_name):
                return ValidationResult.error(
                    "Название системы содержит недопустимые символы"
                )
            
            return ValidationResult.success("Название системы корректно")
            
        except Exception as e:
            logger.error(f"Error validating system name '{system_name}': {e}")
            return ValidationResult.error(f"Ошибка валидации названия системы: {str(e)}")
    
    def validate_phone_number(self, phone_number: str) -> ValidationResult:
        """
        Валидация номера телефона.
        
        Args:
            phone_number: Номер телефона
            
        Returns:
            Результат валидации
        """
        try:
            if not phone_number:
                return ValidationResult.error("Номер телефона не может быть пустым")
            
            # Удаляем все пробелы и дефисы
            clean_number = re.sub(r'[\s\-()+]', '', phone_number)
            
            # Проверяем российский формат
            try:
                parsed_number = phonenumbers.parse(clean_number, "RU")
                if not phonenumbers.is_valid_number(parsed_number):
                    return ValidationResult.error("Некорректный номер телефона")
                
                formatted = phonenumbers.format_number(
                    parsed_number, 
                    phonenumbers.PhoneNumberFormat.INTERNATIONAL
                )
                return ValidationResult.success(f"Номер телефона корректен: {formatted}")
                
            except phonenumbers.NumberParseException:
                # Проверяем простой формат
                if re.match(r'^\+?[78]\d{10}$', clean_number):
                    return ValidationResult.success("Номер телефона корректен")
                else:
                    return ValidationResult.error(
                        "Неверный формат номера телефона. "
                        "Используйте формат: +7XXXXXXXXXX или 8XXXXXXXXXX"
                    )
                
        except Exception as e:
            logger.error(f"Error validating phone number '{phone_number}': {e}")
            return ValidationResult.error(f"Ошибка валидации номера телефона: {str(e)}")
    
    def validate_email(self, email: str) -> ValidationResult:
        """
        Валидация email адреса.
        
        Args:
            email: Email адрес
            
        Returns:
            Результат валидации
        """
        try:
            if not email:
                return ValidationResult.error("Email не может быть пустым")
            
            # Простая проверка регулярным выражением
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            
            if not re.match(email_pattern, email):
                return ValidationResult.error("Неверный формат email адреса")
            
            return ValidationResult.success("Email адрес корректен")
            
        except Exception as e:
            logger.error(f"Error validating email '{email}': {e}")
            return ValidationResult.error(f"Ошибка валидации email: {str(e)}")
    
    def validate_yes_no(self, value: str) -> ValidationResult:
        """
        Валидация ответа да/нет.
        
        Args:
            value: Значение (да/нет)
            
        Returns:
            Результат валидации
        """
        try:
            if not value:
                return ValidationResult.error("Ответ не может быть пустым")
            
            value_lower = value.lower().strip()
            
            if value_lower in ['да', 'нет', 'yes', 'no']:
                return ValidationResult.success("Ответ корректен")
            else:
                return ValidationResult.error(
                    "Неверный ответ. Используйте 'да' или 'нет'"
                )
            
        except Exception as e:
            logger.error(f"Error validating yes/no '{value}': {e}")
            return ValidationResult.error(f"Ошибка валидации ответа: {str(e)}")
    
    def validate_contract_data(
        self,
        contract_type: str,
        contract_number: str,
        contract_date: str,
        start_date: str,
        end_date: str
    ) -> ValidationResult:
        """
        Комплексная валидация данных контракта.
        
        Args:
            contract_type: Тип контракта
            contract_number: Номер контракта
            contract_date: Дата контракта
            start_date: Дата начала
            end_date: Дата окончания
            
        Returns:
            Результат валидации
        """
        errors = []
        
        # Проверяем тип контракта
        if not contract_type:
            errors.append("Тип контракта не может быть пустым")
        elif contract_type.lower() not in [ct.value for ct in ContractType]:
            errors.append(f"Неверный тип контракта. Допустимые значения: {', '.join([ct.value for ct in ContractType])}")
        
        # Проверяем номер контракта
        contract_number_result = self.validate_contract_number(contract_number)
        if not contract_number_result:
            errors.extend(contract_number_result.errors)
        
        # Проверяем даты
        date_results = []
        for date_str, date_name in [
            (contract_date, "Дата контракта"),
            (start_date, "Дата начала"),
            (end_date, "Дата окончания")
        ]:
            date_result = self.validate_date_string(date_str)
            if not date_result:
                errors.append(f"{date_name}: {date_result.errors[0]}")
            else:
                date_results.append((date_str, date_name))
        
        # Если все даты корректны, проверяем их логическую последовательность
        if len(date_results) == 3:
            # Парсим даты
            try:
                contract_date_dt = parse_date(contract_date)
                start_date_dt = parse_date(start_date)
                end_date_dt = parse_date(end_date)
                
                # Контракт должен быть заключен до начала работ
                if contract_date_dt > start_date_dt:
                    errors.append("Дата контракта должна быть раньше даты начала работ")
                
                # Работы должны начинаться до их окончания
                if start_date_dt >= end_date_dt:
                    errors.append("Дата начала должна быть раньше даты окончания")
                    
            except Exception as e:
                errors.append(f"Ошибка анализа дат: {str(e)}")
        
        if errors:
            return ValidationResult.error("Ошибки валидации контракта", errors)
        else:
            return ValidationResult.success("Данные контракта корректны")
    
    def validate_object_creation_data(
        self,
        short_name: str,
        full_name: str,
        addresses: List[str],
        contract_data: Dict[str, str],
        systems: List[str],
        dispatcher: str,
        note: Optional[str] = None
    ) -> ValidationResult:
        """
        Комплексная валидация данных для создания объекта.
        
        Args:
            short_name: Сокращенное название
            full_name: Полное название
            addresses: Список адресов
            contract_data: Данные контракта
            systems: Список систем
            dispatcher: Наличие диспетчеризации (да/нет)
            note: Примечание
            
        Returns:
            Результат валидации
        """
        errors = []
        
        # Проверяем названия
        short_name_result = self.validate_short_name(short_name)
        if not short_name_result:
            errors.extend(short_name_result.errors)
        
        full_name_result = self.validate_full_name(full_name)
        if not full_name_result:
            errors.extend(full_name_result.errors)
        
        # Проверяем адреса
        if not addresses:
            errors.append("Необходимо указать хотя бы один адрес")
        else:
            for i, address in enumerate(addresses, 1):
                address_result = self.validate_address(address)
                if not address_result:
                    errors.append(f"Адрес {i}: {address_result.errors[0]}")
        
        # Проверяем данные контракта
        contract_result = self.validate_contract_data(
            contract_data.get("type", ""),
            contract_data.get("number", ""),
            contract_data.get("date", ""),
            contract_data.get("start_date", ""),
            contract_data.get("end_date", "")
        )
        if not contract_result:
            errors.extend(contract_result.errors)
        
        # Проверяем системы
        if not systems:
            errors.append("Необходимо указать хотя бы одну систему")
        else:
            for i, system in enumerate(systems, 1):
                system_result = self.validate_system_name(system)
                if not system_result:
                    errors.append(f"Система {i}: {system_result.errors[0]}")
        
        # Проверяем диспетчеризацию
        dispatcher_result = self.validate_yes_no(dispatcher)
        if not dispatcher_result:
            errors.extend(dispatcher_result.errors)
        
        # Проверяем примечание (если есть)
        if note and note.lower() != "нет":
            if len(note) > 1000:
                errors.append("Примечание слишком длинное (макс. 1000 символов)")
        
        if errors:
            return ValidationResult.error("Ошибки валидации данных объекта", errors)
        else:
            return ValidationResult.success("Данные объекта корректны")
    
    def validate_maintenance_data(
        self,
        frequency: str,
        month: Optional[str] = None,
        description: Optional[str] = None
    ) -> ValidationResult:
        """
        Валидация данных ТО.
        
        Args:
            frequency: Частота обслуживания
            month: Номер месяца (опционально)
            description: Описание (опционально)
            
        Returns:
            Результат валидации
        """
        errors = []
        
        # Проверяем частоту
        valid_frequencies = [
            "раз в день", "ежедневно",
            "раз в неделю", "еженедельно",
            "раз в месяц", "ежемесячно",
            "раз в квартал", "ежеквартально",
            "раз в полгода", "раз в год", "ежегодно"
        ]
        
        if not frequency:
            errors.append("Частота обслуживания не может быть пустой")
        elif frequency.lower() not in valid_frequencies:
            errors.append(f"Неверная частота. Допустимые значения: {', '.join(valid_frequencies)}")
        
        # Проверяем месяц (если указан)
        if month:
            try:
                month_num = int(month)
                if month_num < 1 or month_num > 12:
                    errors.append("Номер месяца должен быть от 1 до 12")
            except ValueError:
                errors.append("Номер месяца должен быть числом")
        
        # Проверяем описание (если есть)
        if description and len(description) > 500:
            errors.append("Описание слишком длинное (макс. 500 символов)")
        
        if errors:
            return ValidationResult.error("Ошибки валидации данных ТО", errors)
        else:
            return ValidationResult.success("Данные ТО корректны")
    
    def validate_problem_data(
        self,
        description: str,
        file_attached: bool = False
    ) -> ValidationResult:
        """
        Валидация данных проблемы.
        
        Args:
            description: Описание проблемы
            file_attached: Прикреплен ли файл
            
        Returns:
            Результат валидации
        """
        errors = []
        
        if not description:
            errors.append("Описание проблемы не может быть пустым")
        elif len(description) < 10:
            errors.append("Описание проблемы слишком короткое (мин. 10 символов)")
        elif len(description) > 1000:
            errors.append("Описание проблемы слишком длинное (макс. 1000 символов)")
        
        if errors:
            return ValidationResult.error("Ошибки валидации данных проблемы", errors)
        else:
            return ValidationResult.success("Данные проблемы корректны")
    
    def validate_reminder_data(
        self,
        title: str,
        date: str,
        description: Optional[str] = None
    ) -> ValidationResult:
        """
        Валидация данных напоминания.
        
        Args:
            title: Заголовок напоминания
            date: Дата напоминания
            description: Описание (опционально)
            
        Returns:
            Результат валидации
        """
        errors = []
        
        if not title:
            errors.append("Заголовок напоминания не может быть пустым")
        elif len(title) > 200:
            errors.append("Заголовок напоминания слишком длинный (макс. 200 символов)")
        
        # Проверяем дату
        date_result = self.validate_date_string(date)
        if not date_result:
            errors.extend(date_result.errors)
        
        # Проверяем описание (если есть)
        if description and len(description) > 500:
            errors.append("Описание слишком длинное (макс. 500 символов)")
        
        if errors:
            return ValidationResult.error("Ошибки валидации данных напоминания", errors)
        else:
            return ValidationResult.success("Данные напоминания корректны")
    
    def validate_material_data(
        self,
        name: str,
        quantity: str,
        unit: str,
        description: Optional[str] = None
    ) -> ValidationResult:
        """
        Валидация данных материала.
        
        Args:
            name: Наименование материала
            quantity: Количество
            unit: Единица измерения
            description: Описание (опционально)
            
        Returns:
            Результат валидации
        """
        errors = []
        
        if not name:
            errors.append("Наименование материала не может быть пустым")
        elif len(name) > 200:
            errors.append("Наименование материала слишком длинное (макс. 200 символов)")
        
        # Проверяем количество
        try:
            qty = float(quantity)
            if qty <= 0:
                errors.append("Количество должно быть положительным числом")
        except ValueError:
            errors.append("Количество должно быть числом")
        
        # Проверяем единицу измерения
        valid_units = ["м.", "шт.", "уп.", "компл.", "кг", "л"]
        if unit not in valid_units:
            errors.append(f"Неверная единица измерения. Допустимые значения: {', '.join(valid_units)}")
        
        # Проверяем описание (если есть)
        if description and len(description) > 500:
            errors.append("Описание слишком длинное (макс. 500 символов)")
        
        if errors:
            return ValidationResult.error("Ошибки валидации данных материала", errors)
        else:
            return ValidationResult.success("Данные материала корректны")
    
    def validate_user_input(
        self,
        input_type: str,
        value: str,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Универсальная валидация пользовательского ввода.
        
        Args:
            input_type: Тип ввода (date, name, address и т.д.)
            value: Значение
            additional_data: Дополнительные данные для контекста
            
        Returns:
            Результат валидации
        """
        validators = {
            "date": self.validate_date_string,
            "short_name": self.validate_short_name,
            "full_name": self.validate_full_name,
            "address": self.validate_address,
            "contract_number": self.validate_contract_number,
            "system_name": self.validate_system_name,
            "phone": self.validate_phone_number,
            "email": self.validate_email,
            "yes_no": self.validate_yes_no,
            "problem": lambda v: self.validate_problem_data(v),
            "material_name": lambda v: self.validate_material_data(v, "1", "шт."),
        }
        
        validator_func = validators.get(input_type)
        if validator_func:
            return validator_func(value)
        else:
            return ValidationResult.error(f"Неизвестный тип валидации: {input_type}")