"""
Инициализатор пакета работы с данными.
Экспортирует все компоненты системы хранения: модели, репозитории, кэш, миграции.
"""
# Импорт моделей
from storage.models.base import Base
from storage.models.user import User, Admin, AdminPermission, UserAccess
from storage.models.service import (
    ServiceRegion,
    ServiceObject,
    ServiceAddress,
    ServiceProblem,
    ServiceMaintenance,
    ServiceEquipment,
    ServiceLetter,
    ServiceJournal,
    ServicePermit,
    ServiceDocument
)
from storage.models.installation import (
    InstallationObject,
    InstallationAddress,
    InstallationProject,
    InstallationMaterial,
    MaterialSection,
    SectionMaterial,
    InstallationMontage,
    InstallationSupply,
    InstallationChange,
    InstallationID,
    InstallationDocument
)
from storage.models.file import (
    TelegramFile,
    FileAttachment,
    FileCategory
)
from storage.models.reminder import (
    Reminder,
    ReminderRecipient,
    ReminderType,
    ReminderStatus,
    ReminderFrequency
)
from storage.models.group import (
    GroupBinding,
    GroupAdmin,
    GroupAccess
)
from storage.models.log import (
    SystemLog,
    ChangeLog,
    ErrorLog,
    LogLevel,
    ChangeType,
    ObjectType
)

# Импорт репозиториев
from storage.repositories import (
    BaseRepository,
    FileRepository,
    ReminderRepository,
    LogRepository,
    UserRepository,
    ServiceRepository,
    InstallationRepository,
    RepositoryFactory
)

# Импорт кэша
from storage.cache import (
    cache,
    cache_method,
    invalidate_cache,
    CacheGroup,
    CACHE_STRATEGY_READ,
    CACHE_STRATEGY_WRITE,
    CACHE_STRATEGY_READ_WRITE,
    CACHE_STRATEGY_WRITE_AROUND,
    generate_cache_key,
    RedisClient,
    MemoryCache,
    CacheManager,
    CacheFactory
)

# Импорт базы данных
from storage.database import Database, DatabaseSettings, init_database

# Экспорт всех моделей
__all__ = [
    # Базовые классы
    "Base",
    
    # Модели пользователей
    "User",
    "Admin", 
    "AdminPermission",
    "UserAccess",
    
    # Модели обслуживания
    "ServiceRegion",
    "ServiceObject",
    "ServiceAddress",
    "ServiceProblem",
    "ServiceMaintenance", 
    "ServiceEquipment",
    "ServiceLetter",
    "ServiceJournal",
    "ServicePermit",
    "ServiceDocument",
    
    # Модели монтажа
    "InstallationObject",
    "InstallationAddress", 
    "InstallationProject",
    "InstallationMaterial",
    "MaterialSection",
    "SectionMaterial",
    "InstallationMontage",
    "InstallationSupply",
    "InstallationChange",
    "InstallationID", 
    "InstallationDocument",
    
    # Модели файлов
    "TelegramFile",
    "FileAttachment", 
    "FileCategory",
    
    # Модели напоминаний
    "Reminder",
    "ReminderRecipient",
    "ReminderType", 
    "ReminderStatus",
    "ReminderFrequency",
    
    # Модели групп
    "GroupBinding",
    "GroupAdmin",
    "GroupAccess",
    
    # Модели логов
    "SystemLog", 
    "ChangeLog",
    "ErrorLog",
    "LogLevel",
    "ChangeType",
    "ObjectType",
    
    # Репозитории
    "BaseRepository",
    "FileRepository",
    "ReminderRepository", 
    "LogRepository",
    "UserRepository",
    "ServiceRepository",
    "InstallationRepository",
    "RepositoryFactory",
    
    # Кэш
    "cache",
    "cache_method",
    "invalidate_cache", 
    "CacheGroup",
    "CACHE_STRATEGY_READ",
    "CACHE_STRATEGY_WRITE",
    "CACHE_STRATEGY_READ_WRITE",
    "CACHE_STRATEGY_WRITE_AROUND",
    "generate_cache_key",
    "RedisClient", 
    "MemoryCache",
    "CacheManager",
    "CacheFactory",
    
    # База данных
    "Database",
    "DatabaseSettings", 
    "init_database",
]


class StorageFactory:
    """
    Фабрика для создания компонентов системы хранения данных.
    Упрощает создание и настройку всех компонентов хранилища.
    """
    
    def __init__(self, config):
        """
        Инициализирует фабрику хранилища.
        
        Args:
            config: Конфигурация приложения
        """
        self.config = config
        self._database = None
        self._cache_manager = None
        self._repository_factory = None
    
    async def init_database(self) -> Database:
        """
        Инициализирует и возвращает объект базы данных.
        
        Returns:
            Database объект
        """
        if not self._database:
            self._database = await init_database(self.config.database_settings)
        
        return self._database
    
    async def init_cache_manager(self, use_memory_cache: bool = False) -> CacheManager:
        """
        Инициализирует и возвращает менеджер кэша.
        
        Args:
            use_memory_cache: Использовать ли in-memory кэш вместо Redis
        
        Returns:
            CacheManager объект
        """
        if not self._cache_manager:
            self._cache_manager = CacheFactory.create_manager(
                self.config, 
                use_memory_cache
            )
            # Подключаемся к кэшу
            if not use_memory_cache:
                await self._cache_manager.connect()
        
        return self._cache_manager
    
    async def init_repository_factory(self) -> RepositoryFactory:
        """
        Инициализирует и возвращает фабрику репозиториев.
        
        Returns:
            RepositoryFactory объект
        """
        if not self._repository_factory:
            # Сначала инициализируем базу данных если еще не инициализирована
            database = await self.init_database()
            self._repository_factory = RepositoryFactory(database.session_factory)
        
        return self._repository_factory
    
    async def get_file_repository(self):
        """
        Получает репозиторий файлов.
        
        Returns:
            FileRepository
        """
        factory = await self.init_repository_factory()
        return await factory.get_file_repository()
    
    async def get_reminder_repository(self):
        """
        Получает репозиторий напоминаний.
        
        Returns:
            ReminderRepository
        """
        factory = await self.init_repository_factory()
        return await factory.get_reminder_repository()
    
    async def get_log_repository(self):
        """
        Получает репозиторий логов.
        
        Returns:
            LogRepository
        """
        factory = await self.init_repository_factory()
        return await factory.get_log_repository()
    
    async def get_user_repository(self):
        """
        Получает репозиторий пользователей.
        
        Returns:
            UserRepository
        """
        factory = await self.init_repository_factory()
        return await factory.get_user_repository()
    
    async def get_service_repository(self):
        """
        Получает репозиторий обслуживания.
        
        Returns:
            ServiceRepository
        """
        factory = await self.init_repository_factory()
        return await factory.get_service_repository()
    
    async def get_installation_repository(self):
        """
        Получает репозиторий монтажа.
        
        Returns:
            InstallationRepository
        """
        factory = await self.init_repository_factory()
        return await factory.get_installation_repository()
    
    async def close_all(self):
        """
        Закрывает все соединения и освобождает ресурсы.
        """
        if self._cache_manager:
            await self._cache_manager.disconnect()
        
        if self._database:
            await self._database.disconnect()
        
        if self._repository_factory:
            await self._repository_factory.close_all()
    
    def get_models_list(self) -> dict:
        """
        Возвращает список всех моделей с их описаниями.
        
        Returns:
            Словарь с моделями и описаниями
        """
        return {
            "user_models": [
                ("User", "Базовый пользователь"),
                ("Admin", "Администраторы разных уровней"),
                ("AdminPermission", "Разрешения для команд"),
                ("UserAccess", "Доступ пользователей к объектам"),
            ],
            "service_models": [
                ("ServiceRegion", "Регион обслуживания"),
                ("ServiceObject", "Объект обслуживания"),
                ("ServiceAddress", "Адрес объекта"),
                ("ServiceProblem", "Проблемы объекта"),
                ("ServiceMaintenance", "Техническое обслуживание"),
                ("ServiceEquipment", "Оборудование объекта"),
                ("ServiceLetter", "Письма и переписка"),
                ("ServiceJournal", "Журналы учета"),
                ("ServicePermit", "Допуски и разрешения"),
                ("ServiceDocument", "Документы объекта"),
            ],
            "installation_models": [
                ("InstallationObject", "Объект монтажа"),
                ("InstallationAddress", "Адрес монтажа"),
                ("InstallationProject", "Проекты монтажа"),
                ("InstallationMaterial", "Материалы монтажа"),
                ("MaterialSection", "Разделы материалов"),
                ("SectionMaterial", "Связь материалов с разделами"),
                ("InstallationMontage", "Учет монтажа"),
                ("InstallationSupply", "Поставки материалов"),
                ("InstallationChange", "Изменения в проекте"),
                ("InstallationID", "Исполнительная документация"),
                ("InstallationDocument", "Документы монтажа"),
            ],
            "file_models": [
                ("TelegramFile", "Файлы в Telegram"),
                ("FileAttachment", "Привязка файлов к объектам"),
                ("FileCategory", "Категории файлов"),
            ],
            "reminder_models": [
                ("Reminder", "Напоминания"),
                ("ReminderRecipient", "Получатели напоминаний"),
                ("ReminderType", "Типы напоминаний"),
                ("ReminderStatus", "Статусы напоминаний"),
                ("ReminderFrequency", "Частоты напоминаний"),
            ],
            "group_models": [
                ("GroupBinding", "Привязка объектов к группам"),
                ("GroupAdmin", "Администраторы групп"),
                ("GroupAccess", "Доступ в группах"),
            ],
            "log_models": [
                ("SystemLog", "Системные логи"),
                ("ChangeLog", "Логи изменений"),
                ("ErrorLog", "Логи ошибок"),
                ("LogLevel", "Уровни логирования"),
                ("ChangeType", "Типы изменений"),
                ("ObjectType", "Типы объектов"),
            ]
        }


class ModelRegistry:
    """
    Реестр моделей для автоматического обнаружения.
    Используется Alembic для миграций.
    """
    
    MODELS = [
        # Модели пользователей
        User, Admin, AdminPermission, UserAccess,
        
        # Модели обслуживания
        ServiceRegion, ServiceObject, ServiceAddress,
        ServiceProblem, ServiceMaintenance, ServiceEquipment,
        ServiceLetter, ServiceJournal, ServicePermit, ServiceDocument,
        
        # Модели монтажа
        InstallationObject, InstallationAddress, InstallationProject,
        InstallationMaterial, MaterialSection, SectionMaterial,
        InstallationMontage, InstallationSupply, InstallationChange,
        InstallationID, InstallationDocument,
        
        # Модели файлов
        TelegramFile, FileAttachment,
        
        # Модели напоминаний
        Reminder, ReminderRecipient,
        
        # Модели групп
        GroupBinding, GroupAdmin, GroupAccess,
        
        # Модели логов
        SystemLog, ChangeLog, ErrorLog,
    ]
    
    @classmethod
    def get_all_models(cls):
        """
        Возвращает список всех моделей.
        
        Returns:
            Список классов моделей
        """
        return cls.MODELS
    
    @classmethod
    def get_model_by_name(cls, model_name: str):
        """
        Получает модель по имени.
        
        Args:
            model_name: Имя модели
        
        Returns:
            Класс модели или None если не найден
        """
        for model in cls.MODELS:
            if model.__name__ == model_name:
                return model
        return None


# Экспортируем фабрику и реестр
__all__.extend([
    "StorageFactory",
    "ModelRegistry"
])


async def init_storage(config, use_memory_cache: bool = False):
    """
    Инициализирует всю систему хранения данных.
    
    Args:
        config: Конфигурация приложения
        use_memory_cache: Использовать ли in-memory кэш
    
    Returns:
        StorageFactory объект
    """
    factory = StorageFactory(config)
    
    # Инициализируем компоненты
    await factory.init_database()
    await factory.init_cache_manager(use_memory_cache)
    await factory.init_repository_factory()
    
    return factory


async def close_storage(factory):
    """
    Закрывает соединения системы хранения данных.
    
    Args:
        factory: StorageFactory объект
    """
    if factory:
        await factory.close_all()


# Добавляем функции инициализации и закрытия в экспорт
__all__.extend([
    "init_storage",
    "close_storage"
])