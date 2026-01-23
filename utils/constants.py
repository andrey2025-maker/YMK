"""
Константы приложения.
Содержит все строковые константы, коды ошибок, лимиты и другие фиксированные значения.
"""

# ==================== КОМАНДЫ БОТА ====================
COMMAND_PREFIX = "!"

# Админские команды
CMD_ADD_MAIN_ADMIN = "!добавить главного админа"
CMD_ADD_ADMIN = "!добавить админа"
CMD_ADD_SERVICE = "!добавить обслуга"
CMD_ADD_INSTALLATION = "!добавить монтаж"
CMD_PERMISSIONS = "!разрешения"
CMD_COMMANDS = "!команды"
CMD_SAVE_SETTINGS = "!сохранения"
CMD_FILE_SETTINGS = "!файлы"
CMD_CACHE = "!кэш"

# Команды обслуживания
CMD_SERVICE = "!обслуживание"
CMD_SERVICE_STOP = "!стоп"
CMD_SERVICE_SEARCH = "!поиск"
CMD_ADDITIONAL_DOC = "!доп"
CMD_REMIND = "!напомнить"
CMD_REMINDERS = "!напоминания"
CMD_MY_OBJECTS = "!мои объекты"

# Команды монтажа
CMD_INSTALLATION = "!монтаж"
CMD_PROJECTS = "!проекты"
CMD_CHANGES = "!изменения"

# Групповые команды
CMD_BIND_SERVICE = "!обслуживание"  # с параметром региона
CMD_UNBIND_SERVICE = "!-обслуживание"
CMD_BIND_INSTALLATION = "!монтаж"  # с параметром объекта
CMD_UNBIND_INSTALLATION = "!-монтаж"

# ==================== УРОВНИ ДОСТУПА ====================
ADMIN_LEVEL_MAIN = "main_admin"
ADMIN_LEVEL_ADMIN = "admin"
ADMIN_LEVEL_SERVICE = "service"
ADMIN_LEVEL_INSTALLATION = "installation"
ADMIN_LEVEL_NAMES = {
    ADMIN_LEVEL_MAIN: "Главный админ",
    ADMIN_LEVEL_ADMIN: "Админ",
    ADMIN_LEVEL_SERVICE: "Обслуга",
    ADMIN_LEVEL_INSTALLATION: "Монтаж"
}

# ==================== ФОРМАТЫ ====================
DATE_FORMAT = "%d.%m.%Y"
DATETIME_FORMAT = "%d.%m.%Y %H:%M"
TIME_FORMAT = "%H:%M"

# Регулярные выражения
REGEX_DATE = r"^(0[1-9]|[12][0-9]|3[01])\.(0[1-9]|1[0-2])\.\d{4}$"
REGEX_PHONE = r"^\+?[1-9]\d{1,14}$"
REGEX_EMAIL = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
REGEX_CONTRACT_NUMBER = r"^[A-Za-z0-9\-/]+$"
REGEX_USERNAME = r"^@?[a-zA-Z0-9_]{5,32}$"

# ==================== ЛИМИТЫ И ОГРАНИЧЕНИЯ ====================
# Пагинация
PAGE_SIZE = 10
MAX_PAGES = 100
PAGINATION_TTL = 600  # 10 минут в секундах

# Таймауты
DIALOG_TIMEOUT = 7200  # 120 минут в секундах
CACHE_TTL = 300  # 5 минут по умолчанию
FSM_TIMEOUT = 1800  # 30 минут для FSM состояний

# Ограничения ввода
MAX_NAME_LENGTH = 100
MAX_ADDRESS_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 1000
MAX_CONTRACT_NUMBER_LENGTH = 50
MAX_PHONE_LENGTH = 20
MAX_EMAIL_LENGTH = 100

# Файлы
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt"}
ALLOWED_ALL_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS.union(ALLOWED_DOCUMENT_EXTENSIONS)

# ==================== ТИПЫ ОБЪЕКТОВ ====================
OBJECT_TYPE_SERVICE_REGION = "service_region"
OBJECT_TYPE_SERVICE_OBJECT = "service_object"
OBJECT_TYPE_INSTALLATION_OBJECT = "installation_object"
OBJECT_TYPE_PROJECT = "project"
OBJECT_TYPE_PROBLEM = "problem"
OBJECT_TYPE_MAINTENANCE = "maintenance"
OBJECT_TYPE_EQUIPMENT = "equipment"
OBJECT_TYPE_LETTER = "letter"
OBJECT_TYPE_PERMIT = "permit"
OBJECT_TYPE_JOURNAL = "journal"
OBJECT_TYPE_DOCUMENT = "document"

# ==================== ТИПЫ ФАЙЛОВ ====================
FILE_CATEGORY_PDF = "pdf"
FILE_CATEGORY_EXCEL = "excel"
FILE_CATEGORY_WORD = "word"
FILE_CATEGORY_IMAGE = "image"
FILE_CATEGORY_OTHER = "other"

FILE_CATEGORIES = {
    FILE_CATEGORY_PDF: "PDF документы",
    FILE_CATEGORY_EXCEL: "Excel файлы",
    FILE_CATEGORY_WORD: "Word документы",
    FILE_CATEGORY_IMAGE: "Изображения",
    FILE_CATEGORY_OTHER: "Другие файлы"
}

# ==================== СТАТУСЫ ====================
STATUS_ACTIVE = "active"
STATUS_INACTIVE = "inactive"
STATUS_PENDING = "pending"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"
STATUS_EXPIRED = "expired"

# ==================== КОДЫ ОШИБОК ====================
ERROR_NO_PERMISSION = "NO_PERMISSION"
ERROR_INVALID_FORMAT = "INVALID_FORMAT"
ERROR_NOT_FOUND = "NOT_FOUND"
ERROR_ALREADY_EXISTS = "ALREADY_EXISTS"
ERROR_VALIDATION_FAILED = "VALIDATION_FAILED"
ERROR_DATABASE_ERROR = "DATABASE_ERROR"
ERROR_CACHE_ERROR = "CACHE_ERROR"
ERROR_FILE_ERROR = "FILE_ERROR"
ERROR_NETWORK_ERROR = "NETWORK_ERROR"
ERROR_TIMEOUT = "TIMEOUT"

# ==================== ЭМОДЗИ ДЛЯ ФОРМАТИРОВАНИЯ ====================
EMOJI_REGION = "🏙"
EMOJI_OBJECT = "🏢"
EMOJI_CONTRACT = "📄"
EMOJI_DATE = "📅"
EMOJI_ADDRESS = "📍"
EMOJI_SYSTEMS = "🔥"
EMOJI_ZIP = "🛠"
EMOJI_DISPATCH = "📞"
EMOJI_NOTE = "📝"
EMOJI_PROBLEM = "⚠️"
EMOJI_MAINTENANCE = "🔧"
EMOJI_EQUIPMENT = "⚙️"
EMOJI_LETTER = "✉️"
EMOJI_PERMIT = "📋"
EMOJI_JOURNAL = "📓"
EMOJI_DOCUMENT = "📑"
EMOJI_PROJECT = "📐"
EMOJI_MATERIAL = "📦"
EMOJI_INSTALLATION = "⚡"
EMOJI_SUPPLY = "🚚"
EMOJI_CHANGE = "🔄"
EMOJI_ID = "🆔"
EMOJI_REMINDER = "⏰"
EMOJI_USER = "👤"
EMOJI_FILE = "📁"
EMOJI_SEARCH = "🔍"
EMOJI_BACK = "◀️"
EMOJI_NEXT = "▶️"
EMOJI_OK = "✅"
EMOJI_CANCEL = "❌"
EMOJI_EDIT = "✏️"
EMOJI_DELETE = "🗑️"
EMOJI_ADD = "➕"
EMOJI_INFO = "ℹ️"
EMOJI_WARNING = "⚠️"
EMOJI_ERROR = "❌"
EMOJI_SUCCESS = "✅"
EMOJI_LOADING = "⏳"

# ==================== ТЕКСТОВЫЕ ШАБЛОНЫ ====================
# Используются как ключи для templates.py
TEMPLATE_NO_PERMISSION = "no_permission"
TEMPLATE_INVALID_FORMAT = "invalid_format"
TEMPLATE_NOT_FOUND = "not_found"
TEMPLATE_ALREADY_EXISTS = "already_exists"
TEMPLATE_VALIDATION_FAILED = "validation_failed"
TEMPLATE_OPERATION_SUCCESS = "operation_success"
TEMPLATE_OPERATION_FAILED = "operation_failed"
TEMPLATE_CONFIRM_DELETE = "confirm_delete"
TEMPLATE_CONFIRM_ACTION = "confirm_action"
TEMPLATE_WELCOME = "welcome"
TEMPLATE_HELP = "help"
TEMPLATE_COMMANDS_LIST = "commands_list"

# ==================== НАСТРОЙКИ БОТА ====================
BOT_NAME = "Бот электрики"
BOT_VERSION = "1.0.0"
BOT_DESCRIPTION = "Бот для управления объектами обслуживания и монтажа электрических систем"

# ==================== БАЗА ДАННЫХ ====================
DB_SCHEMA = "ymk"
DB_ENCODING = "UTF8"
DB_TIMEZONE = "UTC"

# ==================== РЕДИС ====================
REDIS_DEFAULT_DB = 0
REDIS_MAX_CONNECTIONS = 10
REDIS_SOCKET_TIMEOUT = 5
REDIS_SOCKET_CONNECT_TIMEOUT = 5

# ==================== API И ВЕБ ====================
API_VERSION = "v1"
API_PREFIX = "/api/v1"
API_DOCS_URL = "/docs"
API_REDOC_URL = "/redoc"
API_TITLE = "YMK Bot API"
API_DESCRIPTION = "API для бота управления электриками"

# ==================== ДРУГИЕ КОНСТАНТЫ ====================
DEFAULT_TIMEZONE = "Europe/Moscow"
DEFAULT_LANGUAGE = "ru"
SUPPORTED_LANGUAGES = ["ru", "en"]

# Единицы измерения
UNIT_PIECES = "шт."
UNIT_METERS = "м."
UNIT_PACKAGES = "уп."
UNIT_SETS = "компл."
UNIT_LITERS = "л."
UNIT_KILOGRAMS = "кг."

UNITS = {
    "шт.": "штуки",
    "м.": "метры",
    "уп.": "упаковки",
    "компл.": "комплекты",
    "л.": "литры",
    "кг.": "килограммы"
}

# Частоты напоминаний
FREQUENCY_ONCE = "once"
FREQUENCY_DAILY = "daily"
FREQUENCY_WEEKLY = "weekly"
FREQUENCY_MONTHLY = "monthly"
FREQUENCY_QUARTERLY = "quarterly"
FREQUENCY_YEARLY = "yearly"

FREQUENCY_NAMES = {
    FREQUENCY_ONCE: "Однократно",
    FREQUENCY_DAILY: "Ежедневно",
    FREQUENCY_WEEKLY: "Еженедельно",
    FREQUENCY_MONTHLY: "Ежемесячно",
    FREQUENCY_QUARTERLY: "Ежеквартально",
    FREQUENCY_YEARLY: "Ежегодно"
}

# Типы документов
DOCUMENT_TYPE_CONTRACT = "contract"
DOCUMENT_TYPE_GOV_CONTRACT = "gov_contract"
DOCUMENT_TYPE_AGREEMENT = "agreement"
DOCUMENT_TYPE_SUPPLEMENT = "supplement"
DOCUMENT_TYPE_OTHER = "other"

DOCUMENT_TYPE_NAMES = {
    DOCUMENT_TYPE_CONTRACT: "Контракт",
    DOCUMENT_TYPE_GOV_CONTRACT: "Гос. контракт",
    DOCUMENT_TYPE_AGREEMENT: "Договор",
    DOCUMENT_TYPE_SUPPLEMENT: "Доп. соглашение",
    DOCUMENT_TYPE_OTHER: "Другой документ"
}