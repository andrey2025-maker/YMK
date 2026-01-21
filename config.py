from pydantic_settings import BaseSettings
from pydantic import Field, PostgresDsn, RedisDsn
from typing import Optional, Dict, Any


class DatabaseSettings(BaseSettings):
    """Настройки базы данных PostgreSQL."""
    
    host: str = Field(default="localhost", description="Хост PostgreSQL")
    port: int = Field(default=5432, description="Порт PostgreSQL")
    name: str = Field(default="electric_bot", description="Имя базы данных")
    user: str = Field(default="postgres", description="Пользователь БД")
    password: str = Field(default="postgres", description="Пароль БД")
    
    @property
    def dsn(self) -> str:
        """Возвращает DSN строку для подключения."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
    
    @property
    def alembic_dsn(self) -> str:
        """Возвращает DSN для Alembic (без asyncpg)."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class RedisSettings(BaseSettings):
    """Настройки Redis для кэширования."""
    
    host: str = Field(default="localhost", description="Хост Redis")
    port: int = Field(default=6379, description="Порт Redis")
    db: int = Field(default=0, description="Номер базы Redis")
    password: Optional[str] = Field(default=None, description="Пароль Redis (опционально)")
    
    @property
    def dsn(self) -> str:
        """Возвращает DSN строку для Redis."""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class TelegramArchiveSettings(BaseSettings):
    """Настройки Telegram архивов."""
    
    # ID группы/канала для логов изменений
    changes_chat_id: Optional[str] = Field(default=None, description="ID чата для логов изменений")
    changes_topic_id: Optional[int] = Field(default=None, description="ID темы для логов изменений")
    
    # ID группы/канала для архивов файлов по типам
    files_chat_id: Optional[str] = Field(default=None, description="Базовый ID чата для файлов")
    
    # ID тем для разных типов файлов (будут использоваться как смещения от files_chat_id)
    pdf_topic_id: Optional[int] = Field(default=1, description="ID темы для PDF файлов")
    excel_topic_id: Optional[int] = Field(default=2, description="ID темы для Excel файлов")
    word_topic_id: Optional[int] = Field(default=3, description="ID темы для Word файлов")
    images_topic_id: Optional[int] = Field(default=4, description="ID темы для изображений")
    other_topic_id: Optional[int] = Field(default=5, description="ID темы для других файлов")
    archives_topic_id: Optional[int] = Field(default=6, description="ID темы для архивов удаленных объектов")
    
    # ID группы/канала для логов приложения
    logs_chat_id: Optional[str] = Field(default=None, description="ID чата для логов приложения")
    logs_topic_id: Optional[int] = Field(default=1, description="ID темы для логов")
    
    # Формат именования файлов
    file_name_template: str = Field(
        default="{date} {object} {type} {description}",
        description="Шаблон для именования файлов"
    )


class BotSettings(BaseSettings):
    """Настройки бота."""
    
    token: str = Field(..., description="Токен Telegram бота")
    main_admin_id: int = Field(..., description="ID главного администратора")
    
    debug: bool = Field(default=False, description="Режим отладки")
    log_level: str = Field(default="INFO", description="Уровень логирования")
    timezone: str = Field(default="Europe/Moscow", description="Часовой пояс")
    
    # Таймауты и лимиты
    dialog_timeout: int = Field(default=7200, description="Таймаут диалога в секундах (120 минут)")
    pagination_ttl: int = Field(default=600, description="TTL пагинации в секундах (10 минут)")
    cache_cleanup_interval: int = Field(default=3600, description="Интервал очистки кэша в секундах")
    
    # Напоминания
    reminder_check_interval: int = Field(default=300, description="Интервал проверки напоминаний в секундах")
    contract_warning_days: list[int] = Field(default=[7, 1], description="За сколько дней напоминать о контракте")
    
    # Лимиты файлов
    max_file_size: int = Field(default=50 * 1024 * 1024, description="Максимальный размер файла (50 MB)")
    allowed_file_types: Dict[str, list] = Field(
        default={
            "pdf": [".pdf"],
            "excel": [".xlsx", ".xls", ".xlsm", ".xlsb", ".csv"],
            "word": [".docx", ".doc", ".docm", ".dotx"],
            "images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],
            "other": [".txt", ".zip", ".rar", ".7z", ".tar", ".gz"],
        },
        description="Разрешенные типы файлов"
    )


class Config(BaseSettings):
    """Основной класс конфигурации."""
    
    bot: BotSettings = BotSettings()
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    archive: TelegramArchiveSettings = TelegramArchiveSettings()
    
    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"
        env_prefix = "ELECTRIC_BOT_"
        case_sensitive = False


# Создаем глобальный экземпляр конфигурации
config = Config()