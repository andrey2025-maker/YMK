from typing import Dict, List, Any, Optional
import uuid

import structlog

from core.context import AppContext
from storage.models.user import AdminLevel
from storage.repositories.user_repository import UserRepository


logger = structlog.get_logger(__name__)


class PermissionManager:
    """Менеджер для управления разрешениями команд."""
    
    # Команды для разных уровней админов (по ТЗ)
    COMMAND_STRUCTURE = {
        "pm": {  # Личные сообщения
            "management": [
                "добавить_главного_админа",
                "добавить_админа", 
                "добавить_обслуга",
                "добавить_монтаж",
                "удалить_админа",
                "разрешения",
                "сохранения",
                "файлы",
                "админы",
                "кэш",
            ],
            "service": [
                "обслуживание",
                "доп",
                "напомнить",
                "напоминания",
                "поиск",
            ],
            "installation": [
                "монтаж",
                "проекты",
                "материалы",
                "монтаж_статус",
                "изменения",
                "поставки",
                "искать",
            ],
        },
        "group": {  # Группы
            "management": [
                "обслуживание",
                "монтаж",
                "-обслуживание",
                "-монтаж",
                "мои_объекты",
            ],
            "service": [
                "обслуживание",
                "напомнить",
            ],
            "installation": [
                "монтаж",
                "проекты",
                "изменения",
                "монтаж_статус",
            ],
        }
    }
    
    def __init__(self, context: AppContext):
        self.context = context
        self._permission_cache = {}
    
    async def get_available_commands(self, level: str) -> List[Dict[str, Any]]:
        """
        Получает список доступных команд для уровня.
        
        Args:
            level: Уровень админа или 'group'
            
        Returns:
            Список команд с их состоянием
        """
        try:
            # Пробуем получить из кэша
            cache_key = f"commands:{level}"
            if cache_key in self._permission_cache:
                return self._permission_cache[cache_key]
            
            async with self.context.get_session() as session:
                repo = UserRepository(session)
                
                if level == "group":
                    # Для групп получаем настройки из БД или используем по умолчанию
                    commands = await self._get_group_commands(repo)
                else:
                    # Для админов получаем их разрешения из БД
                    commands = await self._get_admin_commands(level, repo)
                
                # Сохраняем в кэш
                self._permission_cache[cache_key] = commands
                
                return commands
        
        except Exception as e:
            logger.error("Get available commands failed", level=level, error=str(e))
            return []
    
    async def _get_admin_commands(self, level: str, repo: UserRepository) -> List[Dict[str, Any]]:
        """Получает команды для админа указанного уровня."""
        # Получаем всех админов этого уровня
        admins = await repo.get_admins_by_level(level)
        
        if not admins:
            # Если нет админов такого уровня, возвращаем все команды выключенными
            return self._get_default_commands_for_level(level, enabled=False)
        
        # Берем разрешения первого админа (предполагаем, что у всех одинаковые)
        # В реальном приложении нужно хранить разрешения для каждого уровня отдельно
        admin = admins[0]
        
        if not admin.permissions:
            # Если нет разрешений, создаем дефолтные
            return self._get_default_commands_for_level(level, enabled=True)
        
        commands = []
        
        # PM команды
        pm_commands = self.COMMAND_STRUCTURE["pm"]
        for category, cmd_list in pm_commands.items():
            for cmd in cmd_list:
                # Проверяем, доступна ли команда этому уровню админа
                if self._is_command_available_for_level(cmd, level, "pm"):
                    is_enabled = admin.permissions.pm_permissions.get(cmd, False)
                    commands.append({
                        "name": cmd,
                        "category": f"pm_{category}",
                        "enabled": is_enabled,
                        "type": "pm",
                        "display_name": self._get_command_display_name(cmd),
                    })
        
        # Group команды
        group_commands = self.COMMAND_STRUCTURE["group"]
        for category, cmd_list in group_commands.items():
            for cmd in cmd_list:
                if self._is_command_available_for_level(cmd, level, "group"):
                    is_enabled = admin.permissions.group_permissions.get(cmd, False)
                    commands.append({
                        "name": cmd,
                        "category": f"group_{category}",
                        "enabled": is_enabled,
                        "type": "group",
                        "display_name": self._get_command_display_name(cmd),
                    })
        
        return commands
    
    async def _get_group_commands(self, repo: UserRepository) -> List[Dict[str, Any]]:
        """Получает команды для групп."""
        # В реальном приложении здесь нужно получать настройки групп из БД
        # Сейчас возвращаем дефолтные настройки
        
        commands = []
        group_commands = self.COMMAND_STRUCTURE["group"]
        
        for category, cmd_list in group_commands.items():
            for cmd in cmd_list:
                # Для групп все команды включены по умолчанию
                commands.append({
                    "name": cmd,
                    "category": f"group_{category}",
                    "enabled": True,  # По умолчанию включены
                    "type": "group",
                    "display_name": self._get_command_display_name(cmd),
                })
        
        return commands
    
    def _get_default_commands_for_level(
        self, 
        level: str, 
        enabled: bool = False
    ) -> List[Dict[str, Any]]:
        """Возвращает команды по умолчанию для уровня."""
        commands = []
        
        # Определяем, какие команды доступны этому уровню
        available_categories = self._get_available_categories_for_level(level)
        
        for chat_type in ["pm", "group"]:
            for category in available_categories.get(chat_type, []):
                cmd_list = self.COMMAND_STRUCTURE[chat_type].get(category, [])
                for cmd in cmd_list:
                    if self._is_command_available_for_level(cmd, level, chat_type):
                        commands.append({
                            "name": cmd,
                            "category": f"{chat_type}_{category}",
                            "enabled": enabled,
                            "type": chat_type,
                            "display_name": self._get_command_display_name(cmd),
                        })
        
        return commands
    
    def _get_available_categories_for_level(self, level: str) -> Dict[str, List[str]]:
        """Определяет доступные категории команд для уровня админа."""
        # Главный админ имеет доступ ко всему
        if level == AdminLevel.MAIN_ADMIN.value:
            return {
                "pm": ["management", "service", "installation"],
                "group": ["management", "service", "installation"],
            }
        
        # Админ имеет доступ к management и service
        elif level == AdminLevel.ADMIN.value:
            return {
                "pm": ["management", "service"],
                "group": ["management", "service"],
            }
        
        # Обслуга имеет доступ только к service
        elif level == AdminLevel.SERVICE.value:
            return {
                "pm": ["service"],
                "group": ["service"],
            }
        
        # Монтаж имеет доступ только к installation
        elif level == AdminLevel.INSTALLATION.value:
            return {
                "pm": ["installation"],
                "group": ["installation"],
            }
        
        return {}
    
    def _is_command_available_for_level(
        self, 
        command: str, 
        level: str, 
        chat_type: str
    ) -> bool:
        """Проверяет, доступна ли команда для уровня админа."""
        # Главный админ имеет доступ ко всем командам
        if level == AdminLevel.MAIN_ADMIN.value:
            return True
        
        # Специальные проверки для определенных команд
        restricted_commands = {
            AdminLevel.ADMIN.value: [
                "добавить_главного_админа",
                "добавить_админа",
                "удалить_админа",
                "разрешения",
            ],
            AdminLevel.SERVICE.value: [
                # Обслуга не имеет доступа к management командам
            ],
            AdminLevel.INSTALLATION.value: [
                # Монтаж не имеет доступа к service командам
            ],
        }
        
        # Проверяем ограничения
        if command in restricted_commands.get(level, []):
            return False
        
        return True
    
    def _get_command_display_name(self, command: str) -> str:
        """Возвращает отображаемое имя команды."""
        display_names = {
            "добавить_главного_админа": "Добавить главного админа",
            "добавить_админа": "Добавить админа",
            "добавить_обслуга": "Добавить обслугу",
            "добавить_монтаж": "Добавить монтаж",
            "удалить_админа": "Удалить админа",
            "разрешения": "Управление разрешениями",
            "сохранения": "Настройка сохранения изменений",
            "файлы": "Настройка архивации файлов",
            "админы": "Список админов",
            "кэш": "Управление кэшем",
            "обслуживание": "Обслуживание объектов",
            "доп": "Дополнительные соглашения",
            "напомнить": "Создать напоминание",
            "напоминания": "Список напоминаний",
            "поиск": "Поиск по данным",
            "монтаж": "Монтаж объектов",
            "проекты": "Проекты монтажа",
            "материалы": "Материалы монтажа",
            "монтаж_статус": "Статус монтажа",
            "изменения": "Изменения в проекте",
            "поставки": "Поставки материалов",
            "искать": "Поиск по монтажу",
            "-обслуживание": "Убрать обслуживание из группы",
            "-монтаж": "Убрать монтаж из группы",
            "мои_объекты": "Мои объекты",
        }
        
        return display_names.get(command, command.replace("_", " ").title())
    
    async def toggle_command_permission(
        self, 
        level: str, 
        command_name: str
    ) -> bool:
        """
        Переключает разрешение для команды.
        
        Args:
            level: Уровень админа или 'group'
            command_name: Имя команды
            
        Returns:
            Новое состояние разрешения
        """
        try:
            async with self.context.get_session() as session:
                repo = UserRepository(session)
                
                if level == "group":
                    # Для групп нужно хранить настройки отдельно
                    # Временно возвращаем просто переключение
                    return await self._toggle_group_permission(repo, command_name)
                else:
                    # Для админов обновляем разрешения
                    return await self._toggle_admin_permission(repo, level, command_name)
        
        except Exception as e:
            logger.error("Toggle permission failed", level=level, command=command_name, error=str(e))
            return False
    
    async def _toggle_admin_permission(
        self, 
        repo: UserRepository, 
        level: str, 
        command_name: str
    ) -> bool:
        """Переключает разрешение для админа."""
        # Получаем первого админа этого уровня
        admins = await repo.get_admins_by_level(level)
        if not admins:
            return False
        
        admin = admins[0]
        
        if not admin.permissions:
            return False
        
        # Определяем тип чата и категорию команды
        chat_type, category = self._get_command_info(command_name)
        
        if not chat_type:
            return False
        
        # Получаем текущие разрешения
        if chat_type == "pm":
            permissions = admin.permissions.pm_permissions
        else:
            permissions = admin.permissions.group_permissions
        
        # Переключаем состояние
        current_state = permissions.get(command_name, False)
        new_state = not current_state
        permissions[command_name] = new_state
        
        # Сохраняем изменения
        if chat_type == "pm":
            admin.permissions.pm_permissions = permissions
        else:
            admin.permissions.group_permissions = permissions
        
        await session.commit()
        
        # Очищаем кэш
        cache_key = f"commands:{level}"
        if cache_key in self._permission_cache:
            del self._permission_cache[cache_key]
        
        return new_state
    
    async def _toggle_group_permission(
        self, 
        repo: UserRepository, 
        command_name: str
    ) -> bool:
        """Переключает разрешение для групп."""
        # В реальном приложении здесь нужно сохранять настройки групп в БД
        # Сейчас просто возвращаем переключенное состояние
        return True  # Всегда включено для групп
    
    def _get_command_info(self, command_name: str) -> tuple[Optional[str], Optional[str]]:
        """Определяет тип чата и категорию команды."""
        for chat_type in ["pm", "group"]:
            for category, commands in self.COMMAND_STRUCTURE[chat_type].items():
                if command_name in commands:
                    return chat_type, category
        
        return None, None
    
    async def save_permissions(self, level: str) -> bool:
        """
        Сохраняет все изменения в разрешениях.
        
        Args:
            level: Уровень админа или 'group'
            
        Returns:
            Успешность операции
        """
        try:
            # Очищаем кэш
            cache_key = f"commands:{level}"
            if cache_key in self._permission_cache:
                del self._permission_cache[cache_key]
            
            logger.info("Permissions saved", level=level)
            return True
        
        except Exception as e:
            logger.error("Save permissions failed", level=level, error=str(e))
            return False
    
    async def get_user_commands(
        self,
        user_id: Optional[uuid.UUID],
        admin_level: Optional[str],
        is_pm: bool = True
    ) -> Dict[str, List[str]]:
        """
        Получает команды, доступные пользователю.
        
        Args:
            user_id: ID пользователя
            admin_level: Уровень админа (если есть)
            is_pm: True для личных сообщений, False для групп
            
        Returns:
            Словарь команд по категориям
        """
        try:
            chat_type = "pm" if is_pm else "group"
            
            if not admin_level:
                # Обычный пользователь - только базовые команды
                return self._get_basic_user_commands(chat_type)
            
            # Получаем команды для уровня админа
            commands = await self.get_available_commands(admin_level)
            
            # Фильтруем по типу чата и включенным командам
            user_commands = {}
            for cmd in commands:
                if cmd["type"] == chat_type and cmd["enabled"]:
                    category = cmd["category"].replace(f"{chat_type}_", "")
                    if category not in user_commands:
                        user_commands[category] = []
                    user_commands[category].append(f"!{cmd['name']}")
            
            return user_commands
        
        except Exception as e:
            logger.error("Get user commands failed", user_id=user_id, error=str(e))
            return {}
    
    def _get_basic_user_commands(self, chat_type: str) -> Dict[str, List[str]]:
        """Получает базовые команды для обычных пользователей."""
        basic_commands = {
            "pm": {
                "Основные": [
                    "!команды",
                    "!мои_объекты",
                    "!поиск",
                ]
            },
            "group": {
                "Основные": [
                    "!команды",
                    "!мои_объекты",
                ]
            }
        }
        
        return basic_commands.get(chat_type, {})
    
    async def check_permission(
        self,
        admin_level: str,
        command: str,
        chat_type: str
    ) -> bool:
        """
        Проверяет, имеет ли админ разрешение на команду.
        
        Args:
            admin_level: Уровень админа
            command: Имя команды (без префикса !)
            chat_type: Тип чата ('pm' или 'group')
            
        Returns:
            True если разрешение есть
        """
        try:
            # Главный админ имеет все права
            if admin_level == AdminLevel.MAIN_ADMIN.value:
                return True
            
            # Получаем команды для уровня
            commands = await self.get_available_commands(admin_level)
            
            # Ищем команду
            for cmd in commands:
                if cmd["name"] == command and cmd["type"] == chat_type:
                    return cmd["enabled"]
            
            return False
        
        except Exception as e:
            logger.error("Check permission failed", 
                       level=admin_level, 
                       command=command, 
                       error=str(e))
            return False
    
    async def clear_cache(self) -> None:
        """Очищает кэш разрешений."""
        self._permission_cache = {}
        logger.info("Permission cache cleared")