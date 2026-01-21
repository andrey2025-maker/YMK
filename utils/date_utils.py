import re
from datetime import datetime, timedelta
from typing import Optional, Tuple, Union
from dateutil import parser
import pytz

from config import config


class DateUtils:
    """Утилиты для работы с датами в формате ДД.ММ.ГГГГ."""
    
    DATE_PATTERN = re.compile(r'^(\d{2})\.(\d{2})\.(\d{4})$')
    
    @staticmethod
    def parse_date(date_str: str, raise_error: bool = True) -> Optional[datetime]:
        """
        Парсит дату из строки в формате ДД.ММ.ГГГГ.
        
        Args:
            date_str: Строка с датой
            raise_error: Вызывать исключение при ошибке
            
        Returns:
            Объект datetime или None
        """
        if not date_str or not isinstance(date_str, str):
            if raise_error:
                raise ValueError("Date string cannot be empty")
            return None
        
        try:
            # Пробуем несколько форматов
            try:
                # Основной формат ДД.ММ.ГГГГ
                match = DateUtils.DATE_PATTERN.match(date_str.strip())
                if match:
                    day, month, year = map(int, match.groups())
                    return datetime(year, month, day).replace(
                        tzinfo=pytz.timezone(config.bot.timezone)
                    )
            except ValueError:
                pass
            
            # Пробуем dateutil.parser для других форматов
            parsed_date = parser.parse(date_str, dayfirst=True)
            if parsed_date:
                return parsed_date.replace(tzinfo=pytz.timezone(config.bot.timezone))
            
            if raise_error:
                raise ValueError(f"Cannot parse date: {date_str}")
            return None
        
        except Exception as e:
            if raise_error:
                raise ValueError(f"Invalid date format: {date_str}. Expected: ДД.ММ.ГГГГ") from e
            return None
    
    @staticmethod
    def format_date(date_obj: Union[datetime, date], include_time: bool = False) -> str:
        """
        Форматирует дату в строку ДД.ММ.ГГГГ.
        
        Args:
            date_obj: Объект datetime или date
            include_time: Включать ли время в формате ЧЧ:ММ
            
        Returns:
            Отформатированная строка
        """
        if not date_obj:
            return ""
        
        if isinstance(date_obj, datetime):
            if date_obj.tzinfo is None:
                # Добавляем часовой пояс, если его нет
                date_obj = date_obj.replace(tzinfo=pytz.timezone(config.bot.timezone))
            
            if include_time:
                return date_obj.strftime("%d.%m.%Y %H:%M")
            return date_obj.strftime("%d.%m.%Y")
        
        elif isinstance(date_obj, date):
            return date_obj.strftime("%d.%m.%Y")
        
        else:
            raise TypeError(f"Unsupported date type: {type(date_obj)}")
    
    @staticmethod
    def validate_date(date_str: str) -> Tuple[bool, Optional[str]]:
        """
        Проверяет корректность даты в формате ДД.ММ.ГГГГ.
        
        Args:
            date_str: Строка с датой
            
        Returns:
            Кортеж (валидна ли дата, сообщение об ошибке)
        """
        try:
            parsed = DateUtils.parse_date(date_str)
            if not parsed:
                return False, "Неверный формат даты"
            
            # Проверяем, что дата не в далеком прошлом или будущем
            current_year = datetime.now().year
            if parsed.year < 2000 or parsed.year > current_year + 10:
                return False, f"Год должен быть между 2000 и {current_year + 10}"
            
            return True, None
        
        except ValueError as e:
            return False, str(e)
    
    @staticmethod
    def calculate_difference(start_date: Union[str, datetime], 
                           end_date: Union[str, datetime]) -> timedelta:
        """
        Вычисляет разницу между датами.
        
        Args:
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            Разница как timedelta
        """
        if isinstance(start_date, str):
            start_date = DateUtils.parse_date(start_date)
        if isinstance(end_date, str):
            end_date = DateUtils.parse_date(end_date)
        
        if not start_date or not end_date:
            raise ValueError("Invalid dates provided")
        
        return end_date - start_date
    
    @staticmethod
    def add_days(date_obj: Union[str, datetime], days: int) -> datetime:
        """
        Добавляет дни к дате.
        
        Args:
            date_obj: Исходная дата
            days: Количество дней для добавления (может быть отрицательным)
            
        Returns:
            Новая дата
        """
        if isinstance(date_obj, str):
            date_obj = DateUtils.parse_date(date_obj)
        
        if not date_obj:
            raise ValueError("Invalid date provided")
        
        return date_obj + timedelta(days=days)
    
    @staticmethod
    def is_future_date(date_obj: Union[str, datetime]) -> bool:
        """Проверяет, является ли дата будущей."""
        if isinstance(date_obj, str):
            date_obj = DateUtils.parse_date(date_obj)
        
        if not date_obj:
            return False
        
        now = datetime.now(pytz.timezone(config.bot.timezone))
        return date_obj > now
    
    @staticmethod
    def is_past_date(date_obj: Union[str, datetime]) -> bool:
        """Проверяет, является ли дата прошедшей."""
        if isinstance(date_obj, str):
            date_obj = DateUtils.parse_date(date_obj)
        
        if not date_obj:
            return False
        
        now = datetime.now(pytz.timezone(config.bot.timezone))
        return date_obj < now
    
    @staticmethod
    def get_current_date() -> datetime:
        """Возвращает текущую дату с часовым поясом."""
        return datetime.now(pytz.timezone(config.bot.timezone))
    
    @staticmethod
    def days_until(date_obj: Union[str, datetime]) -> int:
        """
        Вычисляет количество дней до даты.
        
        Args:
            date_obj: Целевая дата
            
        Returns:
            Количество дней (отрицательное если дата в прошлом)
        """
        if isinstance(date_obj, str):
            date_obj = DateUtils.parse_date(date_obj)
        
        if not date_obj:
            return 0
        
        now = DateUtils.get_current_date()
        difference = date_obj - now
        return difference.days
    
    @staticmethod
    def get_date_ranges() -> Dict[str, Tuple[datetime, datetime]]:
        """Возвращает стандартные диапазоны дат."""
        now = DateUtils.get_current_date()
        
        return {
            "today": (now.replace(hour=0, minute=0, second=0, microsecond=0),
                     now.replace(hour=23, minute=59, second=59, microsecond=999999)),
            "week": (now - timedelta(days=now.weekday()),
                    now + timedelta(days=6 - now.weekday())),
            "month": (now.replace(day=1),
                     (now.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)),
            "year": (now.replace(month=1, day=1),
                    now.replace(month=12, day=31)),
        }