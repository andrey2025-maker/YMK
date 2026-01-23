"""
Инициализатор пакета утилит.
Экспортирует все вспомогательные функции и классы.
"""
from utils.constants import *
from utils.exceptions import *
from utils.validators import *
from utils.formatters import *
from utils.paginator import *
from utils.templates import TemplateStore
from utils.helpers import (
    CryptoHelper,
    StringHelper,
    FileHelper,
    DataHelper,
    ValidationHelper
)
from utils.date_utils import (
    parse_date,
    parse_datetime,
    format_date,
    format_datetime,
    validate_date,
    get_date_difference,
    add_days_to_date,
    is_date_in_range,
    get_current_date,
    get_current_datetime
)

__all__ = [
    # Константы
    *[name for name in dir() if name.isupper()],
    
    # Исключения
    "BotException",
    "PermissionException",
    "ValidationException",
    "NotFoundException",
    "AlreadyExistsException",
    "DatabaseException",
    "CacheException",
    "FileException",
    "NetworkException",
    "TimeoutException",
    "StateException",
    "UserException",
    "ConfigurationException",
    "BusinessLogicException",
    "ExternalServiceException",
    
    # Алиасы исключений
    "NoPermissionError",
    "ValidationError",
    "NotFoundError",
    "AlreadyExistsError",
    "DatabaseError",
    "CacheError",
    "FileError",
    "NetworkError",
    "TimeoutError",
    "StateError",
    "UserError",
    "ConfigError",
    "BusinessError",
    "ExternalServiceError",
    
    # Валидаторы
    "validate_required",
    "validate_string",
    "validate_name",
    "validate_date_string",
    "validate_phone",
    "validate_email",
    "validate_contract_number",
    "validate_address",
    "validate_description",
    "validate_username",
    "validate_number",
    "validate_boolean",
    "validate_yes_no",
    "validate_date_range",
    "validate_file_extension",
    "validate_coordinates",
    "validate_unit",
    "validate_frequency",
    
    # Форматтеры
    "format_bold",
    "format_italic",
    "format_code",
    "format_header",
    "format_list",
    "format_key_value",
    "format_date_display",
    "format_datetime_display",
    "format_service_object",
    "format_problem",
    "format_maintenance",
    "format_equipment",
    "format_reminder",
    "format_pagination_info",
    "format_search_results",
    "format_file_info",
    "format_user_info",
    "format_confirmation_message",
    "format_error_message",
    "format_success_message",
    "format_warning_message",
    "format_info_message",
    "format_loading_message",
    
    # Пагинация
    "PageInfo",
    "paginate_list",
    "calculate_page_info",
    "create_pagination_buttons",
    "validate_page_number",
    "split_into_chunks",
    "get_page_from_chunks",
    "create_numbered_buttons",
    
    # Шаблоны
    "TemplateStore",
    
    # Хелперы
    "CryptoHelper",
    "StringHelper",
    "FileHelper",
    "DataHelper",
    "ValidationHelper",
    
    # Дата/время утилиты
    "parse_date",
    "parse_datetime",
    "format_date",
    "format_datetime",
    "validate_date",
    "get_date_difference",
    "add_days_to_date",
    "is_date_in_range",
    "get_current_date",
    "get_current_datetime",
]


class UtilsFactory:
    """
    Фабрика для создания экземпляров утилит.
    """
    
    @staticmethod
    def create_crypto_helper() -> CryptoHelper:
        """
        Создает экземпляр CryptoHelper.
        
        Returns:
            CryptoHelper
        """
        return CryptoHelper()
    
    @staticmethod
    def create_string_helper() -> StringHelper:
        """
        Создает экземпляр StringHelper.
        
        Returns:
            StringHelper
        """
        return StringHelper()
    
    @staticmethod
    def create_file_helper() -> FileHelper:
        """
        Создает экземпляр FileHelper.
        
        Returns:
            FileHelper
        """
        return FileHelper()
    
    @staticmethod
    def create_data_helper() -> DataHelper:
        """
        Создает экземпляр DataHelper.
        
        Returns:
            DataHelper
        """
        return DataHelper()
    
    @staticmethod
    def create_validation_helper() -> ValidationHelper:
        """
        Создает экземпляр ValidationHelper.
        
        Returns:
            ValidationHelper
        """
        return ValidationHelper()


# Экспортируем фабрику
__all__.append("UtilsFactory")