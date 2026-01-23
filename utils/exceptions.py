"""
Кастомные исключения приложения.
Определяет иерархию исключений для разных типов ошибок.
"""


class BotException(Exception):
    """Базовое исключение для всех ошибок бота."""
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        """
        Инициализирует исключение бота.
        
        Args:
            message: Сообщение об ошибке
            error_code: Код ошибки (опционально)
            details: Детали ошибки (опционально)
        """
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self):
        """Строковое представление исключения."""
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class PermissionException(BotException):
    """Исключение для ошибок прав доступа."""
    
    def __init__(self, message: str = "Нет прав доступа", details: dict = None):
        """
        Инициализирует исключение прав доступа.
        
        Args:
            message: Сообщение об ошибке
            details: Детали ошибки
        """
        from utils.constants import ERROR_NO_PERMISSION
        super().__init__(message, ERROR_NO_PERMISSION, details)


class ValidationException(BotException):
    """Исключение для ошибок валидации."""
    
    def __init__(self, message: str = "Ошибка валидации", field: str = None, value: any = None):
        """
        Инициализирует исключение валидации.
        
        Args:
            message: Сообщение об ошибке
            field: Поле с ошибкой (опционально)
            value: Неверное значение (опционально)
        """
        from utils.constants import ERROR_VALIDATION_FAILED
        details = {}
        if field:
            details['field'] = field
        if value:
            details['value'] = value
        
        super().__init__(message, ERROR_VALIDATION_FAILED, details)


class NotFoundException(BotException):
    """Исключение когда объект не найден."""
    
    def __init__(self, object_type: str = None, object_id: any = None):
        """
        Инициализирует исключение "не найдено".
        
        Args:
            object_type: Тип объекта (опционально)
            object_id: ID объекта (опционально)
        """
        from utils.constants import ERROR_NOT_FOUND
        message = "Объект не найден"
        details = {}
        
        if object_type:
            message = f"{object_type} не найден"
            details['object_type'] = object_type
        
        if object_id:
            details['object_id'] = object_id
        
        super().__init__(message, ERROR_NOT_FOUND, details)


class AlreadyExistsException(BotException):
    """Исключение когда объект уже существует."""
    
    def __init__(self, object_type: str = None, object_name: str = None):
        """
        Инициализирует исключение "уже существует".
        
        Args:
            object_type: Тип объекта (опционально)
            object_name: Название объекта (опционально)
        """
        from utils.constants import ERROR_ALREADY_EXISTS
        message = "Объект уже существует"
        details = {}
        
        if object_type:
            message = f"{object_type} уже существует"
            details['object_type'] = object_type
        
        if object_name:
            details['object_name'] = object_name
        
        super().__init__(message, ERROR_ALREADY_EXISTS, details)


class DatabaseException(BotException):
    """Исключение для ошибок базы данных."""
    
    def __init__(self, message: str = "Ошибка базы данных", operation: str = None):
        """
        Инициализирует исключение базы данных.
        
        Args:
            message: Сообщение об ошибке
            operation: Операция вызвавшая ошибку (опционально)
        """
        from utils.constants import ERROR_DATABASE_ERROR
        details = {}
        if operation:
            details['operation'] = operation
        
        super().__init__(message, ERROR_DATABASE_ERROR, details)


class CacheException(BotException):
    """Исключение для ошибок кэша."""
    
    def __init__(self, message: str = "Ошибка кэша", key: str = None):
        """
        Инициализирует исключение кэша.
        
        Args:
            message: Сообщение об ошибке
            key: Ключ кэша вызвавший ошибку (опционально)
        """
        from utils.constants import ERROR_CACHE_ERROR
        details = {}
        if key:
            details['key'] = key
        
        super().__init__(message, ERROR_CACHE_ERROR, details)


class FileException(BotException):
    """Исключение для ошибок работы с файлами."""
    
    def __init__(self, message: str = "Ошибка работы с файлом", filename: str = None):
        """
        Инициализирует исключение файла.
        
        Args:
            message: Сообщение об ошибке
            filename: Имя файла вызвавшего ошибку (опционально)
        """
        from utils.constants import ERROR_FILE_ERROR
        details = {}
        if filename:
            details['filename'] = filename
        
        super().__init__(message, ERROR_FILE_ERROR, details)


class NetworkException(BotException):
    """Исключение для сетевых ошибок."""
    
    def __init__(self, message: str = "Сетевая ошибка", url: str = None):
        """
        Инициализирует исключение сети.
        
        Args:
            message: Сообщение об ошибке
            url: URL вызвавший ошибку (опционально)
        """
        from utils.constants import ERROR_NETWORK_ERROR
        details = {}
        if url:
            details['url'] = url
        
        super().__init__(message, ERROR_NETWORK_ERROR, details)


class TimeoutException(BotException):
    """Исключение для таймаутов."""
    
    def __init__(self, message: str = "Таймаут операции", timeout_seconds: int = None):
        """
        Инициализирует исключение таймаута.
        
        Args:
            message: Сообщение об ошибке
            timeout_seconds: Время таймаута в секундах (опционально)
        """
        from utils.constants import ERROR_TIMEOUT
        details = {}
        if timeout_seconds:
            details['timeout_seconds'] = timeout_seconds
        
        super().__init__(message, ERROR_TIMEOUT, details)


class StateException(BotException):
    """Исключение для ошибок состояний FSM."""
    
    def __init__(self, message: str = "Ошибка состояния", state: str = None):
        """
        Инициализирует исключение состояния.
        
        Args:
            message: Сообщение об ошибке
            state: Состояние вызвавшее ошибку (опционально)
        """
        details = {}
        if state:
            details['state'] = state
        
        super().__init__(message, None, details)


class UserException(BotException):
    """Исключение для пользовательских ошибок."""
    
    def __init__(self, message: str = "Ошибка пользователя", user_id: int = None):
        """
        Инициализирует исключение пользователя.
        
        Args:
            message: Сообщение об ошибке
            user_id: ID пользователя (опционально)
        """
        details = {}
        if user_id:
            details['user_id'] = user_id
        
        super().__init__(message, None, details)


class ConfigurationException(BotException):
    """Исключение для ошибок конфигурации."""
    
    def __init__(self, message: str = "Ошибка конфигурации", config_key: str = None):
        """
        Инициализирует исключение конфигурации.
        
        Args:
            message: Сообщение об ошибке
            config_key: Ключ конфигурации (опционально)
        """
        details = {}
        if config_key:
            details['config_key'] = config_key
        
        super().__init__(message, None, details)


class BusinessLogicException(BotException):
    """Исключение для ошибок бизнес-логики."""
    
    def __init__(self, message: str = "Ошибка бизнес-логики", rule: str = None):
        """
        Инициализирует исключение бизнес-логики.
        
        Args:
            message: Сообщение об ошибке
            rule: Правило бизнес-логики (опционально)
        """
        details = {}
        if rule:
            details['rule'] = rule
        
        super().__init__(message, None, details)


class ExternalServiceException(BotException):
    """Исключение для ошибок внешних сервисов."""
    
    def __init__(self, message: str = "Ошибка внешнего сервиса", service: str = None):
        """
        Инициализирует исключение внешнего сервиса.
        
        Args:
            message: Сообщение об ошибке
            service: Название сервиса (опционально)
        """
        details = {}
        if service:
            details['service'] = service
        
        super().__init__(message, None, details)


# Алиасы для удобства
NoPermissionError = PermissionException
ValidationError = ValidationException
NotFoundError = NotFoundException
AlreadyExistsError = AlreadyExistsException
DatabaseError = DatabaseException
CacheError = CacheException
FileError = FileException
NetworkError = NetworkException
TimeoutError = TimeoutException
StateError = StateException
UserError = UserException
ConfigError = ConfigurationException
BusinessError = BusinessLogicException
ExternalServiceError = ExternalServiceException