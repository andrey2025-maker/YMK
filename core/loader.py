import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import List, Type, Any, Dict

from aiogram import Dispatcher, Router
from aiogram.filters import Command
import structlog

from core.context import AppContext


logger = structlog.get_logger(__name__)


class ModuleLoader:
    """Класс для динамической загрузки модулей."""
    
    def __init__(self, dp: Dispatcher, context: AppContext):
        self.dp = dp
        self.context = context
        self.loaded_modules: Dict[str, Any] = {}
    
    async def load_all_modules(self) -> None:
        """Загружает все модули приложения."""
        
        # Сначала загружаем основные обработчики в правильном порядке
        await self._load_core_handlers()
        
        # Затем загружаем остальные модули
        modules_dirs = [
            "modules",
        ]
        
        for module_dir in modules_dirs:
            await self._load_directory(module_dir)
        
        # Регистрируем команды бота
        await self._register_bot_commands()
        
        logger.info("All modules loaded", count=len(self.loaded_modules))
    
    async def _load_core_handlers(self) -> None:
        """Загружает основные обработчики в правильном порядке."""
        try:
            # Определяем порядок загрузки обработчиков
            handlers_order = [
                # 1. Админские команды (должны быть первыми для регистрации команд)
                "handlers.admin_handlers",
                
                # 2. Основные модули
                "handlers.service_handlers",
                "handlers.installation_handlers",
                
                # 3. Групповые команды
                "handlers.group_handlers",
                
                # 4. Файловые команды
                "handlers.file_handlers",
                
                # 5. Поиск
                "handlers.search_handlers",
                
                # 6. Пользовательские команды
                "handlers.user_handlers",
                
                # 7. Напоминания
                "handlers.reminder_handlers",
            ]
            
            # Загружаем каждый обработчик в порядке очереди
            for handler_module in handlers_order:
                try:
                    await self._load_module(handler_module)
                    logger.debug("Core handler loaded", module=handler_module)
                except Exception as e:
                    logger.warning("Failed to load core handler", 
                                 module=handler_module, error=str(e))
            
            # Загружаем остальные обработчики из директории handlers
            handlers_path = Path("handlers")
            if handlers_path.exists():
                for item in handlers_path.iterdir():
                    if item.is_file() and item.suffix == '.py' and item.name != '__init__.py':
                        module_name = item.stem
                        if module_name not in [h.split('.')[-1] for h in handlers_order]:
                            try:
                                full_module_name = f"handlers.{module_name}"
                                await self._load_module(full_module_name)
                            except Exception as e:
                                logger.debug("Optional handler not loaded", 
                                           module=full_module_name, error=str(e))
        
        except Exception as e:
            logger.error("Failed to load core handlers", error=str(e))
    
    async def _load_directory(self, directory: str) -> None:
        """Загружает все модули из указанной директории."""
        try:
            dir_path = Path(directory)
            
            if not dir_path.exists():
                logger.warning("Directory not found", directory=directory)
                return
            
            # Получаем все Python модули в директории
            for _, module_name, is_pkg in pkgutil.iter_modules([directory]):
                if is_pkg:
                    # Загружаем пакеты
                    full_module_name = f"{directory}.{module_name}"
                    await self._load_module(full_module_name)
                else:
                    # Загружаем отдельные модули
                    full_module_name = f"{directory}.{module_name}"
                    await self._load_module(full_module_name)
        
        except Exception as e:
            logger.error("Failed to load directory", directory=directory, error=str(e))
    
    async def _load_module(self, module_name: str) -> None:
        """Загружает конкретный модуль."""
        try:
            module = importlib.import_module(module_name)
            
            # Регистрируем роутеры, если они есть
            self._register_routers(module)
            
            # Инициализируем модуль, если есть функция initialize
            if hasattr(module, 'initialize'):
                await module.initialize(self.dp, self.context)
            
            # Для обработчиков регистрируем команды, если есть функция register_commands
            if module_name.startswith("handlers.") and hasattr(module, 'register_commands'):
                await module.register_commands(self.dp, self.context)
            
            # Сохраняем ссылку на модуль
            self.loaded_modules[module_name] = module
            
            logger.debug("Module loaded", module=module_name)
        
        except ImportError as e:
            logger.warning("Module import failed", module=module_name, error=str(e))
        except Exception as e:
            logger.error("Module loading error", module=module_name, error=str(e))
    
    def _register_routers(self, module: Any) -> None:
        """Регистрирует все роутеры из модуля."""
        for name, obj in inspect.getmembers(module):
            if isinstance(obj, Router):
                # Регистрируем роутер в диспетчере
                self.dp.include_router(obj)
                logger.debug("Router registered", router=name, module=module.__name__)
    
    async def _register_bot_commands(self) -> None:
        """Регистрирует команды бота в меню."""
        try:
            commands = []
            
            # Основные команды для всех пользователей
            commands.extend([
                {"command": "start", "description": "Начать работу с ботом"},
                {"command": "помощь", "description": "Справка по командам"},
                {"command": "мои_объекты", "description": "Мои доступные объекты"},
                {"command": "поиск", "description": "Поиск по данным"},
                {"command": "напоминания", "description": "Мои напоминания"},
                {"command": "напомнить", "description": "Создать напоминание"},
                {"command": "стоп", "description": "Отменить текущее действие"},
                {"command": "настройки", "description": "Мои настройки"},
                {"command": "профиль", "description": "Мой профиль"},
            ])
            
            # Команды обслуживания (для service и выше)
            commands.extend([
                {"command": "обслуживание", "description": "Меню обслуживания"},
                {"command": "доп", "description": "Добавить документ"},
            ])
            
            # Команды монтажа (для installation и выше)
            commands.extend([
                {"command": "монтаж", "description": "Меню монтажа"},
            ])
            
            # Админские команды (для admin и выше)
            commands.extend([
                {"command": "разрешения", "description": "Управление правами"},
                {"command": "сохранения", "description": "Настройки сохранения"},
                {"command": "файлы", "description": "Управление файлами"},
                {"command": "команды", "description": "Доступные команды"},
                {"command": "кэш", "description": "Управление кэшем"},
            ])
            
            # Команды добавления админов (только для главного админа)
            commands.extend([
                {"command": "добавить_главного_админа", "description": "Добавить главного админа"},
                {"command": "добавить_админа", "description": "Добавить админа"},
                {"command": "добавить_обслуга", "description": "Добавить обслуживающего"},
                {"command": "добавить_монтаж", "description": "Добавить монтажника"},
            ])
            
            # Групповые команды
            commands.extend([
                {"command": "группа_инфо", "description": "Информация о группе"},
                {"command": "найти_файл", "description": "Поиск файлов"},
            ])
            
            # Устанавливаем команды бота
            await self.dp.bot.set_my_commands(commands)
            logger.info("Bot commands registered", count=len(commands))
            
        except Exception as e:
            logger.error("Failed to register bot commands", error=str(e))
    
    async def reload_module(self, module_name: str) -> bool:
        """Перезагружает указанный модуль."""
        try:
            if module_name in self.loaded_modules:
                # Перезагружаем модуль
                module = importlib.reload(self.loaded_modules[module_name])
                
                # Очищаем старые роутеры
                self._unregister_module_routers(module_name)
                
                # Регистрируем новые
                self._register_routers(module)
                
                # Обновляем ссылку
                self.loaded_modules[module_name] = module
                
                logger.info("Module reloaded", module=module_name)
                return True
        
        except Exception as e:
            logger.error("Module reload failed", module=module_name, error=str(e))
        
        return False
    
    def _unregister_module_routers(self, module_name: str) -> None:
        """Удаляет роутеры указанного модуля."""
        # Эта логика требует более сложной реализации
        # В текущей версии aiogram нет простого способа удалить роутер
        # Вместо этого мы будем полагаться на перезапуск приложения в debug режиме
        pass


async def load_modules(dp: Dispatcher, context: AppContext) -> None:
    """Основная функция загрузки модулей."""
    loader = ModuleLoader(dp, context)
    await loader.load_all_modules()