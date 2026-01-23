"""
Инициализатор пакета бизнес-модулей.
Экспортирует все компоненты бизнес-логики: администрирование, обслуживание, монтаж, файлы, группы.
"""
# Импорт модуля администрирования
from modules.admin import (
    AdminManager,
    PermissionManager,
    LogManager,
    ExportManager,
    AdminModule
)

# Импорт модуля обслуживания
from modules.service import (
    RegionManager,
    ObjectManager,
    ServiceModule,
    # Менеджеры подразделов обслуживания
    ProblemManager,
    MaintenanceManager,
    EquipmentManager,
    LetterManager,
    JournalManager,
    PermitManager,
    DocumentManager
)

# Импорт модуля монтажа
from modules.installation import (
    InstallationObjectManager,
    InstallationModule,
    # Менеджеры подразделов монтажа
    ProjectManager,
    MaterialManager,
    MontageManager,
    SupplyManager,
    ChangeManager,
    IDManager,
    InstallationDocumentManager
)

# Импорт модуля файлов
from modules.file import (
    ArchiveManager,
    TelegramFileManager,
    FileIdManager,
    FileModule
)

# Импорт модуля групп
from modules.group import (
    BindManager,
    AccessManager,
    GroupModule
)

# Экспорт всех менеджеров и модулей
__all__ = [
    # Администрирование
    "AdminManager",
    "PermissionManager", 
    "LogManager",
    "ExportManager",
    "AdminModule",
    
    # Обслуживание
    "RegionManager",
    "ObjectManager",
    "ServiceModule",
    "ProblemManager",
    "MaintenanceManager",
    "EquipmentManager", 
    "LetterManager",
    "JournalManager",
    "PermitManager",
    "DocumentManager",
    
    # Монтаж
    "InstallationObjectManager",
    "InstallationModule",
    "ProjectManager", 
    "MaterialManager",
    "MontageManager",
    "SupplyManager",
    "ChangeManager",
    "IDManager",
    "InstallationDocumentManager",
    
    # Файлы
    "ArchiveManager",
    "TelegramFileManager", 
    "FileIdManager",
    "FileModule",
    
    # Группы
    "BindManager",
    "AccessManager",
    "GroupModule",
]


class ModulesFactory:
    """
    Фабрика для создания всех модулей бизнес-логики.
    Управляет зависимостями и инициализацией всех модулей.
    """
    
    def __init__(self, storage_factory, config, bot):
        """
        Инициализирует фабрику модулей.
        
        Args:
            storage_factory: Фабрика хранилища (StorageFactory)
            config: Конфигурация приложения
            bot: Экземпляр Telegram бота
        """
        self.storage_factory = storage_factory
        self.config = config
        self.bot = bot
        
        # Кэш инициализированных модулей
        self._admin_module = None
        self._service_module = None
        self._installation_module = None
        self._file_module = None
        self._group_module = None
        
        # Кэш менеджеров
        self._managers_cache = {}
    
    async def init_admin_module(self) -> AdminModule:
        """
        Инициализирует и возвращает модуль администрирования.
        
        Returns:
            AdminModule объект
        """
        if not self._admin_module:
            # Создаем менеджеры
            admin_manager = AdminManager(
                await self.storage_factory.get_user_repository(),
                self.config
            )
            
            permission_manager = PermissionManager(
                await self.storage_factory.get_user_repository(),
                self.config
            )
            
            log_manager = LogManager(
                await self.storage_factory.get_log_repository(),
                await self.storage_factory.get_file_repository(),
                self.bot,
                self.config
            )
            
            export_manager = ExportManager(
                await self.storage_factory.get_service_repository(),
                await self.storage_factory.get_installation_repository(),
                self.config
            )
            
            # Создаем модуль
            self._admin_module = AdminModule(
                admin_manager=admin_manager,
                permission_manager=permission_manager,
                log_manager=log_manager,
                export_manager=export_manager,
                config=self.config
            )
            
            # Кэшируем менеджеры
            self._managers_cache['admin_manager'] = admin_manager
            self._managers_cache['permission_manager'] = permission_manager
            self._managers_cache['log_manager'] = log_manager
            self._managers_cache['export_manager'] = export_manager
        
        return self._admin_module
    
    async def init_service_module(self) -> ServiceModule:
        """
        Инициализирует и возвращает модуль обслуживания.
        
        Returns:
            ServiceModule объект
        """
        if not self._service_module:
            # Получаем репозитории
            service_repository = await self.storage_factory.get_service_repository()
            file_repository = await self.storage_factory.get_file_repository()
            reminder_repository = await self.storage_factory.get_reminder_repository()
            
            # Создаем менеджеры
            region_manager = RegionManager(service_repository, self.config)
            object_manager = ObjectManager(
                service_repository, 
                file_repository,
                reminder_repository,
                self.config
            )
            
            # Менеджеры подразделов
            problem_manager = ProblemManager(service_repository, file_repository, self.config)
            maintenance_manager = MaintenanceManager(service_repository, reminder_repository, self.config)
            equipment_manager = EquipmentManager(service_repository, self.config)
            letter_manager = LetterManager(service_repository, file_repository, self.config)
            journal_manager = JournalManager(service_repository, self.config)
            permit_manager = PermitManager(service_repository, file_repository, self.config)
            document_manager = DocumentManager(service_repository, reminder_repository, self.config)
            
            # Создаем модуль
            self._service_module = ServiceModule(
                region_manager=region_manager,
                object_manager=object_manager,
                problem_manager=problem_manager,
                maintenance_manager=maintenance_manager,
                equipment_manager=equipment_manager,
                letter_manager=letter_manager,
                journal_manager=journal_manager,
                permit_manager=permit_manager,
                document_manager=document_manager,
                config=self.config
            )
            
            # Кэшируем менеджеры
            self._managers_cache['region_manager'] = region_manager
            self._managers_cache['object_manager'] = object_manager
            self._managers_cache['problem_manager'] = problem_manager
            self._managers_cache['maintenance_manager'] = maintenance_manager
            self._managers_cache['equipment_manager'] = equipment_manager
            self._managers_cache['letter_manager'] = letter_manager
            self._managers_cache['journal_manager'] = journal_manager
            self._managers_cache['permit_manager'] = permit_manager
            self._managers_cache['document_manager'] = document_manager
        
        return self._service_module
    
    async def init_installation_module(self) -> InstallationModule:
        """
        Инициализирует и возвращает модуль монтажа.
        
        Returns:
            InstallationModule объект
        """
        if not self._installation_module:
            # Получаем репозитории
            installation_repository = await self.storage_factory.get_installation_repository()
            file_repository = await self.storage_factory.get_file_repository()
            reminder_repository = await self.storage_factory.get_reminder_repository()
            
            # Создаем менеджеры
            object_manager = InstallationObjectManager(
                installation_repository,
                file_repository,
                reminder_repository,
                self.config
            )
            
            # Менеджеры подразделов
            project_manager = ProjectManager(installation_repository, file_repository, self.config)
            material_manager = MaterialManager(installation_repository, self.config)
            montage_manager = MontageManager(installation_repository, self.config)
            supply_manager = SupplyManager(installation_repository, reminder_repository, self.config)
            change_manager = ChangeManager(installation_repository, file_repository, self.config)
            id_manager = IDManager(installation_repository, file_repository, self.config)
            document_manager = InstallationDocumentManager(installation_repository, self.config)
            
            # Создаем модуль
            self._installation_module = InstallationModule(
                object_manager=object_manager,
                project_manager=project_manager,
                material_manager=material_manager,
                montage_manager=montage_manager,
                supply_manager=supply_manager,
                change_manager=change_manager,
                id_manager=id_manager,
                document_manager=document_manager,
                config=self.config
            )
            
            # Кэшируем менеджеры
            self._managers_cache['installation_object_manager'] = object_manager
            self._managers_cache['project_manager'] = project_manager
            self._managers_cache['material_manager'] = material_manager
            self._managers_cache['montage_manager'] = montage_manager
            self._managers_cache['supply_manager'] = supply_manager
            self._managers_cache['change_manager'] = change_manager
            self._managers_cache['id_manager'] = id_manager
            self._managers_cache['installation_document_manager'] = document_manager
        
        return self._installation_module
    
    async def init_file_module(self) -> FileModule:
        """
        Инициализирует и возвращает модуль файлов.
        
        Returns:
            FileModule объект
        """
        if not self._file_module:
            # Получаем репозитории
            file_repository = await self.storage_factory.get_file_repository()
            
            # Создаем менеджеры
            archive_manager = ArchiveManager(self.bot, self.config)
            telegram_file_manager = TelegramFileManager(self.bot, self.config)
            file_id_manager = FileIdManager(file_repository, self.config)
            
            # Создаем модуль
            self._file_module = FileModule(
                archive_manager=archive_manager,
                telegram_file_manager=telegram_file_manager,
                file_id_manager=file_id_manager,
                config=self.config
            )
            
            # Кэшируем менеджеры
            self._managers_cache['archive_manager'] = archive_manager
            self._managers_cache['telegram_file_manager'] = telegram_file_manager
            self._managers_cache['file_id_manager'] = file_id_manager
        
        return self._file_module
    
    async def init_group_module(self) -> GroupModule:
        """
        Инициализирует и возвращает модуль групп.
        
        Returns:
            GroupModule объект
        """
        if not self._group_module:
            # Получаем репозитории
            # Примечание: group_repository будет добавлен позже
            # Временное решение - получаем доступ через storage_factory
            
            # Создаем менеджеры
            bind_manager = BindManager(self.config)
            access_manager = AccessManager(self.config)
            
            # Создаем модуль
            self._group_module = GroupModule(
                bind_manager=bind_manager,
                access_manager=access_manager,
                config=self.config
            )
            
            # Кэшируем менеджеры
            self._managers_cache['bind_manager'] = bind_manager
            self._managers_cache['access_manager'] = access_manager
        
        return self._group_module
    
    async def get_manager(self, manager_name: str):
        """
        Получает менеджер по имени.
        
        Args:
            manager_name: Имя менеджера
        
        Returns:
            Менеджер или None если не найден
        """
        # Если менеджер уже в кэше
        if manager_name in self._managers_cache:
            return self._managers_cache[manager_name]
        
        # Инициализируем модули если нужно
        if manager_name in ['admin_manager', 'permission_manager', 'log_manager', 'export_manager']:
            await self.init_admin_module()
        elif manager_name in ['region_manager', 'object_manager', 'problem_manager', 
                             'maintenance_manager', 'equipment_manager', 'letter_manager',
                             'journal_manager', 'permit_manager', 'document_manager']:
            await self.init_service_module()
        elif manager_name in ['installation_object_manager', 'project_manager', 'material_manager',
                             'montage_manager', 'supply_manager', 'change_manager', 
                             'id_manager', 'installation_document_manager']:
            await self.init_installation_module()
        elif manager_name in ['archive_manager', 'telegram_file_manager', 'file_id_manager']:
            await self.init_file_module()
        elif manager_name in ['bind_manager', 'access_manager']:
            await self.init_group_module()
        
        return self._managers_cache.get(manager_name)
    
    async def init_all_modules(self) -> dict:
        """
        Инициализирует все модули приложения.
        
        Returns:
            Словарь со всеми инициализированными модулями
        """
        modules = {}
        
        modules['admin'] = await self.init_admin_module()
        modules['service'] = await self.init_service_module()
        modules['installation'] = await self.init_installation_module()
        modules['file'] = await self.init_file_module()
        modules['group'] = await self.init_group_module()
        
        return modules
    
    async def close_all(self):
        """
        Закрывает все модули и освобождает ресурсы.
        """
        # Закрываем модули если они имеют метод close
        for module in [self._admin_module, self._service_module, 
                      self._installation_module, self._file_module, 
                      self._group_module]:
            if module and hasattr(module, 'close'):
                await module.close()
        
        # Очищаем кэш
        self._managers_cache.clear()
        
        # Сбрасываем ссылки на модули
        self._admin_module = None
        self._service_module = None
        self._installation_module = None
        self._file_module = None
        self._group_module = None


class ModuleRegistry:
    """
    Реестр модулей для управления зависимостями и взаимодействием.
    """
    
    MODULE_DEPENDENCIES = {
        'admin': ['storage', 'config', 'bot'],
        'service': ['storage', 'config', 'file', 'reminder'],
        'installation': ['storage', 'config', 'file', 'reminder'],
        'file': ['storage', 'config', 'bot'],
        'group': ['storage', 'config'],
    }
    
    MODULE_DESCRIPTIONS = {
        'admin': {
            'name': 'Администрирование',
            'description': 'Управление пользователями, правами, логированием и экспортом',
            'managers': [
                ('AdminManager', 'Управление администраторами разных уровней'),
                ('PermissionManager', 'Управление разрешениями команд'),
                ('LogManager', 'Логирование изменений и действий'),
                ('ExportManager', 'Экспорт данных в Excel'),
            ]
        },
        'service': {
            'name': 'Обслуживание',
            'description': 'Управление объектами обслуживания, проблемами, ТО и оборудованием',
            'managers': [
                ('RegionManager', 'Управление регионами обслуживания'),
                ('ObjectManager', 'Управление объектами обслуживания'),
                ('ProblemManager', 'Управление проблемами объектов'),
                ('MaintenanceManager', 'Управление техническим обслуживанием'),
                ('EquipmentManager', 'Управление оборудованием объектов'),
                ('LetterManager', 'Управление письмами и перепиской'),
                ('JournalManager', 'Управление журналами учета'),
                ('PermitManager', 'Управление допусками и разрешениями'),
                ('DocumentManager', 'Управление документами объектов'),
            ]
        },
        'installation': {
            'name': 'Монтаж',
            'description': 'Управление монтажными объектами, проектами, материалами и поставками',
            'managers': [
                ('InstallationObjectManager', 'Управление объектами монтажа'),
                ('ProjectManager', 'Управление проектами монтажа'),
                ('MaterialManager', 'Управление материалами монтажа'),
                ('MontageManager', 'Учет выполненных монтажных работ'),
                ('SupplyManager', 'Управление поставками материалов'),
                ('ChangeManager', 'Управление изменениями в проектах'),
                ('IDManager', 'Управление исполнительной документацией'),
                ('InstallationDocumentManager', 'Управление документами монтажа'),
            ]
        },
        'file': {
            'name': 'Файлы',
            'description': 'Управление файлами, архивацией в Telegram и прикреплением к объектам',
            'managers': [
                ('ArchiveManager', 'Архивация файлов в Telegram группы'),
                ('TelegramFileManager', 'Работа с файлами в Telegram'),
                ('FileIdManager', 'Управление идентификаторами файлов'),
            ]
        },
        'group': {
            'name': 'Группы',
            'description': 'Управление привязкой объектов к группам и доступом в группах',
            'managers': [
                ('BindManager', 'Привязка объектов обслуживания/монтажа к группам'),
                ('AccessManager', 'Управление доступом в группах'),
            ]
        }
    }
    
    @classmethod
    def get_module_info(cls, module_name: str) -> dict:
        """
        Получает информацию о модуле.
        
        Args:
            module_name: Имя модуля
        
        Returns:
            Словарь с информацией о модуле
        """
        return cls.MODULE_DESCRIPTIONS.get(module_name, {})
    
    @classmethod
    def get_all_modules_info(cls) -> dict:
        """
        Получает информацию обо всех модулях.
        
        Returns:
            Словарь с информацией о всех модулях
        """
        return cls.MODULE_DESCRIPTIONS
    
    @classmethod
    def get_module_dependencies(cls, module_name: str) -> list:
        """
        Получает зависимости модуля.
        
        Args:
            module_name: Имя модуля
        
        Returns:
            Список зависимостей модуля
        """
        return cls.MODULE_DEPENDENCIES.get(module_name, [])
    
    @classmethod
    def validate_dependencies(cls, available_modules: list) -> dict:
        """
        Проверяет доступность зависимостей для модулей.
        
        Args:
            available_modules: Список доступных модулей
        
        Returns:
            Словарь с результатами проверки
        """
        results = {}
        
        for module_name, dependencies in cls.MODULE_DEPENDENCIES.items():
            missing = []
            for dep in dependencies:
                if dep not in available_modules and dep not in ['storage', 'config', 'bot']:
                    missing.append(dep)
            
            results[module_name] = {
                'has_all_dependencies': len(missing) == 0,
                'missing_dependencies': missing,
                'total_dependencies': len(dependencies),
            }
        
        return results


# Экспортируем фабрику и реестр
__all__.extend([
    "ModulesFactory",
    "ModuleRegistry"
])


async def init_modules(storage_factory, config, bot, init_all: bool = True):
    """
    Инициализирует все модули бизнес-логики.
    
    Args:
        storage_factory: Фабрика хранилища
        config: Конфигурация приложения
        bot: Экземпляр Telegram бота
        init_all: Инициализировать ли все модули сразу
    
    Returns:
        ModulesFactory объект
    """
    factory = ModulesFactory(storage_factory, config, bot)
    
    if init_all:
        await factory.init_all_modules()
    
    return factory


async def close_modules(factory):
    """
    Закрывает все модули бизнес-логики.
    
    Args:
        factory: ModulesFactory объект
    """
    if factory:
        await factory.close_all()


# Добавляем функции инициализации и закрытия в экспорт
__all__.extend([
    "init_modules",
    "close_modules"
])


# Дополнительные утилиты для работы с модулями
class ModuleUtils:
    """
    Утилиты для работы с модулями.
    """
    
    @staticmethod
    def get_module_by_feature(feature_name: str) -> str:
        """
        Определяет к какому модулю относится фича.
        
        Args:
            feature_name: Название фичи
        
        Returns:
            Имя модуля или "unknown"
        """
        feature_to_module = {
            # Администрирование
            'админ': 'admin',
            'разрешения': 'admin',
            'логи': 'admin',
            'экспорт': 'admin',
            'кэш': 'admin',
            
            # Обслуживание
            'обслуживание': 'service',
            'регион': 'service',
            'объект': 'service',
            'проблема': 'service',
            'то': 'service',
            'оборудование': 'service',
            'письмо': 'service',
            'журнал': 'service',
            'допуск': 'service',
            'документ': 'service',
            
            # Монтаж
            'монтаж': 'installation',
            'проект': 'installation',
            'материал': 'installation',
            'поставка': 'installation',
            'изменение': 'installation',
            'ид': 'installation',
            
            # Файлы
            'файл': 'file',
            'архив': 'file',
            'загрузка': 'file',
            
            # Группы
            'группа': 'group',
            'привязка': 'group',
            'доступ': 'group',
        }
        
        feature_lower = feature_name.lower()
        for key, module in feature_to_module.items():
            if key in feature_lower:
                return module
        
        return "unknown"
    
    @staticmethod
    def check_module_access(user_role: str, module_name: str) -> bool:
        """
        Проверяет доступность модуля для роли пользователя.
        
        Args:
            user_role: Роль пользователя
            module_name: Имя модуля
        
        Returns:
            True если доступ разрешен
        """
        from utils.constants import (
            ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN, 
            ADMIN_LEVEL_SERVICE, ADMIN_LEVEL_INSTALLATION
        )
        
        module_access = {
            'admin': [ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN],
            'service': [ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN, ADMIN_LEVEL_SERVICE],
            'installation': [ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN, ADMIN_LEVEL_INSTALLATION],
            'file': [ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN, ADMIN_LEVEL_SERVICE, ADMIN_LEVEL_INSTALLATION],
            'group': [ADMIN_LEVEL_MAIN, ADMIN_LEVEL_ADMIN],
        }
        
        allowed_roles = module_access.get(module_name, [])
        return user_role in allowed_roles


# Экспортируем утилиты
__all__.append("ModuleUtils")