"""
Вспомогательные утилиты.
Содержит различные хелперы для работы с данными, криптографией и строками.
"""
import hashlib
import json
import os
import random
import re
import string
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

import bcrypt
from cryptography.fernet import Fernet


class CryptoHelper:
    """
    Хелпер для криптографических операций.
    """
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Хэширует пароль с помощью bcrypt.
        
        Args:
            password: Пароль для хэширования
        
        Returns:
            Хэшированный пароль
        """
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """
        Проверяет пароль.
        
        Args:
            password: Пароль для проверки
            hashed_password: Хэшированный пароль
        
        Returns:
            True если пароль верный
        """
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                hashed_password.encode('utf-8')
            )
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def generate_token(length: int = 32) -> str:
        """
        Генерирует случайный токен.
        
        Args:
            length: Длина токена
        
        Returns:
            Случайный токен
        """
        characters = string.ascii_letters + string.digits
        return ''.join(random.choice(characters) for _ in range(length))
    
    @staticmethod
    def generate_secure_random_string(length: int = 16) -> str:
        """
        Генерирует криптографически безопасную случайную строку.
        
        Args:
            length: Длина строки
        
        Returns:
            Случайная строка
        """
        return ''.join(
            random.SystemRandom().choice(string.ascii_letters + string.digits)
            for _ in range(length)
        )
    
    @staticmethod
    def md5_hash(data: str) -> str:
        """
        Создает MD5 хэш строки.
        
        Args:
            data: Данные для хэширования
        
        Returns:
            MD5 хэш
        """
        return hashlib.md5(data.encode('utf-8')).hexdigest()
    
    @staticmethod
    def sha256_hash(data: str) -> str:
        """
        Создает SHA256 хэш строки.
        
        Args:
            data: Данные для хэширования
        
        Returns:
            SHA256 хэш
        """
        return hashlib.sha256(data.encode('utf-8')).hexdigest()


class StringHelper:
    """
    Хелпер для работы со строками.
    """
    
    @staticmethod
    def truncate(text: str, max_length: int, suffix: str = "...") -> str:
        """
        Обрезает строку до указанной длины.
        
        Args:
            text: Текст для обрезки
            max_length: Максимальная длина
            suffix: Суффикс для обрезанной строки
        
        Returns:
            Обрезанная строка
        """
        if len(text) <= max_length:
            return text
        
        return text[:max_length - len(suffix)] + suffix
    
    @staticmethod
    def slugify(text: str) -> str:
        """
        Преобразует строку в slug (для URL и идентификаторов).
        
        Args:
            text: Текст для преобразования
        
        Returns:
            Slug строка
        """
        # Приводим к нижнему регистру
        text = text.lower()
        
        # Заменяем кириллические символы
        cyrillic_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd',
            'е': 'e', 'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i',
            'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n',
            'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't',
            'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch',
            'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '',
            'э': 'e', 'ю': 'yu', 'я': 'ya'
        }
        
        result = []
        for char in text:
            if char in cyrillic_map:
                result.append(cyrillic_map[char])
            elif char.isalnum():
                result.append(char)
            elif char in ' -_':
                result.append('-')
        
        slug = ''.join(result)
        
        # Убираем множественные дефисы
        slug = re.sub(r'-+', '-', slug)
        
        # Убираем дефисы в начале и конце
        slug = slug.strip('-')
        
        return slug
    
    @staticmethod
    def extract_hashtags(text: str) -> List[str]:
        """
        Извлекает хэштеги из текста.
        
        Args:
            text: Текст для анализа
        
        Returns:
            Список хэштегов
        """
        hashtags = re.findall(r'#(\w+)', text)
        return [tag.lower() for tag in hashtags]
    
    @staticmethod
    def extract_mentions(text: str) -> List[str]:
        """
        Извлекает упоминания пользователей из текста.
        
        Args:
            text: Текст для анализа
        
        Returns:
            Список упоминаний
        """
        mentions = re.findall(r'@(\w+)', text)
        return mentions
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Очищает имя файла от опасных символов.
        
        Args:
            filename: Имя файла
        
        Returns:
            Очищенное имя файла
        """
        # Убираем опасные символы
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # Убираем начальные и конечные точки и пробелы
        filename = filename.strip('. ')
        
        # Ограничиваем длину
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            name = name[:255 - len(ext)]
            filename = name + ext
        
        return filename
    
    @staticmethod
    def camel_to_snake(text: str) -> str:
        """
        Преобразует CamelCase в snake_case.
        
        Args:
            text: Текст в CamelCase
        
        Returns:
            Текст в snake_case
        """
        # Вставляем подчеркивания перед заглавными буквами
        text = re.sub(r'(?<!^)(?=[A-Z])', '_', text)
        
        # Приводим к нижнему регистру
        return text.lower()
    
    @staticmethod
    def snake_to_camel(text: str) -> str:
        """
        Преобразует snake_case в CamelCase.
        
        Args:
            text: Текст в snake_case
        
        Returns:
            Текст в CamelCase
        """
        parts = text.split('_')
        return ''.join(part.capitalize() for part in parts if part)


class FileHelper:
    """
    Хелпер для работы с файлами.
    """
    
    @staticmethod
    def get_file_extension(filename: str) -> str:
        """
        Получает расширение файла.
        
        Args:
            filename: Имя файла
        
        Returns:
            Расширение файла (с точкой)
        """
        _, ext = os.path.splitext(filename)
        return ext.lower()
    
    @staticmethod
    def get_file_size_kb(file_path: str) -> float:
        """
        Получает размер файла в килобайтах.
        
        Args:
            file_path: Путь к файлу
        
        Returns:
            Размер в KB
        """
        try:
            size_bytes = os.path.getsize(file_path)
            return size_bytes / 1024
        except OSError:
            return 0
    
    @staticmethod
    def get_file_size_mb(file_path: str) -> float:
        """
        Получает размер файла в мегабайтах.
        
        Args:
            file_path: Путь к файлу
        
        Returns:
            Размер в MB
        """
        try:
            size_bytes = os.path.getsize(file_path)
            return size_bytes / (1024 * 1024)
        except OSError:
            return 0
    
    @staticmethod
    def create_directory(dir_path: str) -> bool:
        """
        Создает директорию если ее нет.
        
        Args:
            dir_path: Путь к директории
        
        Returns:
            True если директория создана или уже существует
        """
        try:
            os.makedirs(dir_path, exist_ok=True)
            return True
        except OSError:
            return False
    
    @staticmethod
    def generate_unique_filename(
        original_filename: str,
        prefix: Optional[str] = None,
        suffix: Optional[str] = None
    ) -> str:
        """
        Генерирует уникальное имя файла.
        
        Args:
            original_filename: Оригинальное имя файла
            prefix: Префикс (опционально)
            suffix: Суффикс (опционально)
        
        Returns:
            Уникальное имя файла
        """
        # Извлекаем имя и расширение
        name, ext = os.path.splitext(original_filename)
        
        # Добавляем временную метку
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Добавляем случайную строку
        random_str = CryptoHelper.generate_secure_random_string(8)
        
        # Формируем новое имя
        parts = []
        if prefix:
            parts.append(prefix)
        
        parts.append(name)
        parts.append(timestamp)
        parts.append(random_str)
        
        if suffix:
            parts.append(suffix)
        
        new_name = "_".join(parts)
        
        # Возвращаем с расширением
        return f"{new_name}{ext}"
    
    @staticmethod
    def is_safe_path(base_path: str, target_path: str) -> bool:
        """
        Проверяет что путь безопасен (не выходит за пределы базовой директории).
        
        Args:
            base_path: Базовая директория
            target_path: Целевой путь
        
        Returns:
            True если путь безопасен
        """
        try:
            base = Path(base_path).resolve()
            target = Path(target_path).resolve()
            
            # Проверяем что целевой путь находится внутри базового
            return target.is_relative_to(base)
        except (ValueError, OSError):
            return False


class DataHelper:
    """
    Хелпер для работы с данными.
    """
    
    @staticmethod
    def deep_merge(base_dict: Dict, update_dict: Dict) -> Dict:
        """
        Рекурсивно объединяет два словаря.
        
        Args:
            base_dict: Базовый словарь
            update_dict: Словарь с обновлениями
        
        Returns:
            Объединенный словарь
        """
        result = base_dict.copy()
        
        for key, value in update_dict.items():
            if (key in result and isinstance(result[key], dict) and 
                isinstance(value, dict)):
                result[key] = DataHelper.deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    @staticmethod
    def filter_dict(data: Dict, keys: List[str]) -> Dict:
        """
        Фильтрует словарь, оставляя только указанные ключи.
        
        Args:
            data: Исходный словарь
            keys: Список ключей для сохранения
        
        Returns:
            Отфильтрованный словарь
        """
        return {key: data[key] for key in keys if key in data}
    
    @staticmethod
    def exclude_dict(data: Dict, keys: List[str]) -> Dict:
        """
        Фильтрует словарь, исключая указанные ключи.
        
        Args:
            data: Исходный словарь
            keys: Список ключей для исключения
        
        Returns:
            Отфильтрованный словарь
        """
        return {key: value for key, value in data.items() if key not in keys}
    
    @staticmethod
    def safe_json_loads(data: str, default: Any = None) -> Any:
        """
        Безопасно загружает JSON.
        
        Args:
            data: JSON строка
            default: Значение по умолчанию при ошибке
        
        Returns:
            Распарсенные данные или default
        """
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return default
    
    @staticmethod
    def safe_json_dumps(data: Any, default: Any = None) -> str:
        """
        Безопасно сохраняет в JSON.
        
        Args:
            data: Данные для сериализации
            default: Значение при ошибке сериализации
        
        Returns:
            JSON строка или default
        """
        try:
            return json.dumps(data, default=str)
        except (TypeError, ValueError):
            return default
    
    @staticmethod
    def generate_uuid() -> str:
        """
        Генерирует UUID строку.
        
        Returns:
            UUID строка
        """
        return str(uuid.uuid4())
    
    @staticmethod
    def is_valid_uuid(uuid_string: str) -> bool:
        """
        Проверяет валидность UUID.
        
        Args:
            uuid_string: Строка UUID
        
        Returns:
            True если UUID валиден
        """
        try:
            uuid.UUID(uuid_string)
            return True
        except (ValueError, AttributeError):
            return False
    
    @staticmethod
    def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
        """
        Разбивает список на чанки.
        
        Args:
            lst: Исходный список
            chunk_size: Размер чанка
        
        Returns:
            Список чанков
        """
        return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]
    
    @staticmethod
    def flatten_list(nested_list: List[Any]) -> List[Any]:
        """
        Преобразует вложенный список в плоский.
        
        Args:
            nested_list: Вложенный список
        
        Returns:
            Плоский список
        """
        result = []
        for item in nested_list:
            if isinstance(item, list):
                result.extend(DataHelper.flatten_list(item))
            else:
                result.append(item)
        return result
    
    @staticmethod
    def remove_duplicates_preserve_order(lst: List[Any]) -> List[Any]:
        """
        Удаляет дубликаты из списка, сохраняя порядок.
        
        Args:
            lst: Исходный список
        
        Returns:
            Список без дубликатов
        """
        seen = set()
        result = []
        for item in lst:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result


class ValidationHelper:
    """
    Хелпер для валидации данных.
    """
    
    @staticmethod
    def validate_russian_phone(phone: str) -> bool:
        """
        Проверяет российский номер телефона.
        
        Args:
            phone: Номер телефона
        
        Returns:
            True если номер валиден
        """
        # Убираем все нецифровые символы
        digits = re.sub(r'\D', '', phone)
        
        # Российские номера: +7 или 8, затем 10 цифр
        if digits.startswith('7') and len(digits) == 11:
            return True
        elif digits.startswith('8') and len(digits) == 11:
            return True
        
        return False
    
    @staticmethod
    def validate_inn(inn: str) -> bool:
        """
        Проверяет ИНН (индивидуальный номер налогоплательщика).
        
        Args:
            inn: ИНН
        
        Returns:
            True если ИНН валиден
        """
        # Убираем все нецифровые символы
        inn = re.sub(r'\D', '', inn)
        
        # Проверяем длину
        if len(inn) not in [10, 12]:
            return False
        
        # Проверяем контрольные суммы
        if len(inn) == 10:
            # 10-значный ИНН
            coefficients = [2, 4, 10, 3, 5, 9, 4, 6, 8]
            checksum = sum(int(inn[i]) * coefficients[i] for i in range(9)) % 11 % 10
            return checksum == int(inn[9])
        else:
            # 12-значный ИНН
            # Первая контрольная сумма
            coefficients1 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
            checksum1 = sum(int(inn[i]) * coefficients1[i] for i in range(10)) % 11 % 10
            
            # Вторая контрольная сумма
            coefficients2 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
            checksum2 = sum(int(inn[i]) * coefficients2[i] for i in range(11)) % 11 % 10
            
            return checksum1 == int(inn[10]) and checksum2 == int(inn[11])
    
    @staticmethod
    def validate_kpp(kpp: str) -> bool:
        """
        Проверяет КПП (код причины постановки на учет).
        
        Args:
            kpp: КПП
        
        Returns:
            True если КПП валиден
        """
        # КПП: 9 символов, первые 4 - цифры, 5 и 6 - 2 цифры, остальные - буквы или цифры
        pattern = r'^\d{4}[\dA-Z]{2}[\dA-Z]{3}$'
        return bool(re.match(pattern, kpp))
    
    @staticmethod
    def validate_ogrn(ogrn: str) -> bool:
        """
        Проверяет ОГРН (основной государственный регистрационный номер).
        
        Args:
            ogrn: ОГРН
        
        Returns:
            True если ОГРН валиден
        """
        # Убираем все нецифровые символы
        ogrn = re.sub(r'\D', '', ogrn)
        
        # Проверяем длину
        if len(ogrn) not in [13, 15]:
            return False
        
        # Проверяем контрольную сумму
        if len(ogrn) == 13:
            # ОГРН (13 цифр)
            checksum = int(ogrn[:-1]) % 11 % 10
            return checksum == int(ogrn[-1])
        else:
            # ОГРНИП (15 цифр)
            checksum = int(ogrn[:-1]) % 13 % 10
            return checksum == int(ogrn[-1])