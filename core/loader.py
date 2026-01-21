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
        
        # Список директорий для загрузки
        modules_dirs = [
            "handlers",
            "modules",
        ]
        
        for module_dir in modules_dirs:
            await self._load_directory(module_dir)
        
        logger.info("All modules loaded", count=len(self.loaded_modules))
    
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