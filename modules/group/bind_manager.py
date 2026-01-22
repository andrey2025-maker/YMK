"""
Менеджер привязки объектов к группам.
Реализует привязку объектов обслуживания и монтажа к Telegram группам.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime

from aiogram import Bot
from aiogram.types import Chat

from core.context import AppContext
from storage.models.group import GroupBinding, GroupPermission
from storage.models.service import ServiceObject, ServiceRegion
from storage.models.installation import InstallationObject
from storage.repositories.group_repository import GroupRepository
from storage.repositories.service_repository import ServiceRepository
from storage.repositories.installation_repository import InstallationRepository
from modules.admin.log_manager import LogManager
from utils.exceptions import NotFoundError, ValidationError, AccessDeniedError

logger = logging.getLogger(__name__)


class GroupBindManager:
    """Менеджер привязки объектов к группам."""
    
    def __init__(self, context: AppContext):
        self.context = context
        self.bot: Bot = context.bot
        self.db = context.db
        
        self.group_repository = GroupRepository(self.db)
        self.service_repository = ServiceRepository(self.db)
        self.installation_repository = InstallationRepository(self.db)
        self.log_manager: LogManager = context.log_manager
    
    async def bind_service_to_group(
        self,
        chat_id: int,
        user_id: int,
        region_identifier: str,
        object_identifier: Optional[str] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Привязка объекта обслуживания к группе.
        
        Args:
            chat_id: ID чата/группы
            user_id: ID пользователя
            region_identifier: Идентификатор региона (название или ID)
            object_identifier: Идентификатор объекта (опционально)
            
        Returns:
            Кортеж (успех, сообщение, информация о привязке)
        """
        try:
            # Проверяем, что пользователь имеет права в группе
            has_permission = await self._check_group_permission(chat_id, user_id, 'bind_service')
            if not has_permission:
                return False, "У вас нет прав для привязки объектов к этой группе", None
            
            # Находим регион обслуживания
            region = await self._find_service_region(region_identifier, user_id)
            if not region:
                return False, f"Регион обслуживания '{region_identifier}' не найден", None
            
            # Если указан объект, находим конкретный объект
            if object_identifier:
                # Находим объект в регионе
                service_object = await self._find_service_object_in_region(
                    region.id, object_identifier, user_id
                )
                if not service_object:
                    return False, f"Объект '{object_identifier}' не найден в регионе '{region.short_name}'", None
                
                # Привязываем конкретный объект
                return await self._bind_specific_service_object(
                    chat_id, user_id, service_object
                )
            else:
                # Привязываем весь регион
                return await self._bind_service_region(
                    chat_id, user_id, region
                )
            
        except Exception as e:
            logger.error(f"Error binding service to group {chat_id}: {e}", exc_info=True)
            return False, f"Ошибка привязки: {str(e)}", None
    
    async def bind_installation_to_group(
        self,
        chat_id: int,
        user_id: int,
        installation_identifier: str
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Привязка объекта монтажа к группе.
        
        Args:
            chat_id: ID чата/группы
            user_id: ID пользователя
            installation_identifier: Идентификатор объекта монтажа
            
        Returns:
            Кортеж (успех, сообщение, информация о привязке)
        """
        try:
            # Проверяем, что пользователь имеет права в группе
            has_permission = await self._check_group_permission(chat_id, user_id, 'bind_installation')
            if not has_permission:
                return False, "У вас нет прав для привязки объектов монтажа к этой группе", None
            
            # Находим объект монтажа
            installation_object = await self._find_installation_object(installation_identifier, user_id)
            if not installation_object:
                return False, f"Объект монтажа '{installation_identifier}' не найден", None
            
            # Проверяем, не привязан ли уже объект к этой группе
            existing_binding = await self.group_repository.get_binding(
                object_type='installation',
                object_id=str(installation_object.id),
                chat_id=chat_id
            )
            
            if existing_binding:
                return False, f"Объект монтажа '{installation_object.short_name}' уже привязан к этой группе", None
            
            # Создаем привязку
            binding = GroupBinding(
                chat_id=chat_id,
                object_type='installation',
                object_id=str(installation_object.id),
                object_name=installation_object.short_name,
                full_object_name=installation_object.full_name,
                created_by=user_id,
                created_at=datetime.now()
            )
            
            await self.group_repository.save_binding(binding)
            
            # Логирование
            await self.log_manager.log_group_binding(
                user_id=user_id,
                chat_id=chat_id,
                object_type='installation',
                object_id=str(installation_object.id),
                object_name=installation_object.full_name,
                action='bind'
            )
            
            binding_info = {
                'id': str(binding.id),
                'object_type': 'installation',
                'object_id': str(installation_object.id),
                'object_name': installation_object.short_name,
                'full_name': installation_object.full_name,
                'created_at': binding.created_at.isoformat() if binding.created_at else None
            }
            
            return True, f"Объект монтажа '{installation_object.short_name}' успешно привязан к группе", binding_info
            
        except Exception as e:
            logger.error(f"Error binding installation to group {chat_id}: {e}", exc_info=True)
            return False, f"Ошибка привязки: {str(e)}", None
    
    async def remove_binding(
        self,
        chat_id: int,
        user_id: int,
        binding_identifier: str
    ) -> Tuple[bool, str]:
        """
        Удаление привязки объекта к группе.
        
        Args:
            chat_id: ID чата/группы
            user_id: ID пользователя
            binding_identifier: Идентификатор привязки (регион/объект)
            
        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            # Проверяем, что пользователь имеет права в группе
            has_permission = await self._check_group_permission(chat_id, user_id, 'remove_binding')
            if not has_permission:
                return False, "У вас нет прав для удаления привязок в этой группе"
            
            # Ищем привязку
            binding = await self._find_binding(chat_id, binding_identifier)
            if not binding:
                return False, f"Привязка '{binding_identifier}' не найдена в этой группе"
            
            # Получаем информацию об объекте для логирования
            object_info = await self._get_object_info(binding.object_type, binding.object_id)
            
            # Удаляем привязку
            deleted = await self.group_repository.delete_binding(str(binding.id))
            
            if deleted:
                # Логирование
                await self.log_manager.log_group_binding(
                    user_id=user_id,
                    chat_id=chat_id,
                    object_type=binding.object_type,
                    object_id=binding.object_id,
                    object_name=object_info.get('name', binding.object_name),
                    action='unbind'
                )
                
                return True, f"Привязка '{binding.object_name}' успешно удалена из группы"
            else:
                return False, "Не удалось удалить привязку"
            
        except Exception as e:
            logger.error(f"Error removing binding from group {chat_id}: {e}", exc_info=True)
            return False, f"Ошибка удаления привязки: {str(e)}"
    
    async def get_group_bindings(
        self,
        chat_id: int,
        user_id: int,
        object_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Получение списка привязок группы.
        
        Args:
            chat_id: ID чата/группы
            user_id: ID пользователя
            object_type: Тип объекта для фильтрации ('service', 'installation')
            
        Returns:
            Список привязок с дополнительной информацией
        """
        try:
            # Проверяем, что пользователь имеет доступ к группе
            has_access = await self._check_group_access(chat_id, user_id)
            if not has_access:
                raise AccessDeniedError("Нет доступа к этой группе")
            
            # Получаем привязки
            bindings = await self.group_repository.get_chat_bindings(
                chat_id=chat_id,
                object_type=object_type
            )
            
            # Форматируем результат
            result = []
            for binding in bindings:
                # Получаем дополнительную информацию об объекте
                object_info = await self._get_object_info(binding.object_type, binding.object_id)
                
                binding_data = {
                    'id': str(binding.id),
                    'object_type': binding.object_type,
                    'object_id': binding.object_id,
                    'object_name': binding.object_name,
                    'full_object_name': binding.full_object_name or binding.object_name,
                    'created_at': binding.created_at.isoformat() if binding.created_at else None,
                    'created_by': binding.created_by,
                    'is_active': binding.is_active
                }
                
                # Добавляем информацию об объекте
                if object_info:
                    binding_data.update(object_info)
                
                result.append(binding_data)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting group bindings {chat_id}: {e}", exc_info=True)
            return []
    
    async def get_user_groups_with_bindings(
        self,
        user_id: int
    ) -> Dict[int, Dict[str, Any]]:
        """
        Получение групп пользователя с их привязками.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Словарь {chat_id: информация_о_группе_с_привязками}
        """
        try:
            # Получаем группы, где пользователь имеет доступ
            user_groups = await self.group_repository.get_user_groups(user_id)
            
            result = {}
            for chat_id in user_groups:
                # Получаем информацию о группе
                try:
                    chat = await self.bot.get_chat(chat_id)
                    group_info = {
                        'chat_id': chat_id,
                        'title': chat.title,
                        'type': chat.type,
                        'bindings': await self.get_group_bindings(chat_id, user_id)
                    }
                    result[chat_id] = group_info
                except Exception as e:
                    logger.warning(f"Cannot get chat info {chat_id}: {e}")
                    # Используем базовую информацию
                    group_info = {
                        'chat_id': chat_id,
                        'title': f"Группа {chat_id}",
                        'type': 'group',
                        'bindings': await self.get_group_bindings(chat_id, user_id)
                    }
                    result[chat_id] = group_info
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting user groups with bindings: {e}", exc_info=True)
            return {}
    
    async def parse_binding_command(
        self,
        command_text: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Парсинг команды привязки/отвязки.
        
        Args:
            command_text: Текст команды (например: "!обслуживание ХМАО" или "!-обслуживание ХМАО")
            
        Returns:
            Кортеж (действие, тип_объекта, идентификатор)
        """
        try:
            # Регулярные выражения для команд
            service_pattern = r'^!(-?)(обслуживание|service)\s+(.+)$'
            installation_pattern = r'^!(-?)(монтаж|installation|install)\s+(.+)$'
            
            command_text = command_text.strip()
            
            # Проверяем команду обслуживания
            service_match = re.match(service_pattern, command_text, re.IGNORECASE)
            if service_match:
                action = 'remove' if service_match.group(1) == '-' else 'bind'
                object_type = 'service'
                identifier = service_match.group(3).strip()
                return action, object_type, identifier
            
            # Проверяем команду монтажа
            installation_match = re.match(installation_pattern, command_text, re.IGNORECASE)
            if installation_match:
                action = 'remove' if installation_match.group(1) == '-' else 'bind'
                object_type = 'installation'
                identifier = installation_match.group(3).strip()
                return action, object_type, identifier
            
            return None, None, None
            
        except Exception as e:
            logger.error(f"Error parsing binding command: {e}")
            return None, None, None
    
    async def check_object_in_group(
        self,
        chat_id: int,
        object_type: str,
        object_id: str
    ) -> bool:
        """
        Проверка, привязан ли объект к группе.
        
        Args:
            chat_id: ID чата/группы
            object_type: Тип объекта ('service', 'installation')
            object_id: ID объекта
            
        Returns:
            True если объект привязан к группе
        """
        try:
            binding = await self.group_repository.get_binding(
                object_type=object_type,
                object_id=object_id,
                chat_id=chat_id
            )
            return binding is not None
        except Exception as e:
            logger.error(f"Error checking object in group: {e}")
            return False
    
    async def get_group_object_permissions(
        self,
        chat_id: int,
        user_id: int,
        object_type: str,
        object_id: str
    ) -> Dict[str, bool]:
        """
        Получение прав пользователя на объект в группе.
        
        Args:
            chat_id: ID чата/группы
            user_id: ID пользователя
            object_type: Тип объекта
            object_id: ID объекта
            
        Returns:
            Словарь прав пользователя
        """
        try:
            # Проверяем, привязан ли объект к группе
            is_bound = await self.check_object_in_group(chat_id, object_type, object_id)
            if not is_bound:
                return {'access': False, 'reason': 'object_not_bound'}
            
            # Получаем права пользователя в группе
            permissions = await self.group_repository.get_user_permissions(chat_id, user_id)
            
            # Базовая проверка доступа
            has_access = permissions.get('view', False)
            
            result = {
                'access': has_access,
                'view': permissions.get('view', False),
                'edit': permissions.get('edit', False),
                'add': permissions.get('add', False),
                'delete': permissions.get('delete', False),
                'admin': permissions.get('admin', False)
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting group object permissions: {e}")
            return {'access': False, 'reason': 'error'}
    
    # ========== Внутренние методы ==========
    
    async def _check_group_permission(
        self,
        chat_id: int,
        user_id: int,
        permission: str
    ) -> bool:
        """
        Проверка права пользователя в группе.
        
        Args:
            chat_id: ID чата/группы
            user_id: ID пользователя
            permission: Требуемое право
            
        Returns:
            True если пользователь имеет право
        """
        try:
            # Для админов бота всегда разрешено
            admin_manager = self.context.admin_manager
            if hasattr(admin_manager, 'is_admin'):
                is_admin = await admin_manager.is_admin(user_id)
                if is_admin:
                    return True
            
            # Получаем права пользователя в группе
            permissions = await self.group_repository.get_user_permissions(chat_id, user_id)
            
            # Проверяем конкретное право
            if permission == 'bind_service':
                return permissions.get('admin', False) or permissions.get('edit', False)
            elif permission == 'bind_installation':
                return permissions.get('admin', False) or permissions.get('edit', False)
            elif permission == 'remove_binding':
                return permissions.get('admin', False) or permissions.get('edit', False)
            else:
                return permissions.get('admin', False)
                
        except Exception as e:
            logger.error(f"Error checking group permission: {e}")
            return False
    
    async def _check_group_access(self, chat_id: int, user_id: int) -> bool:
        """
        Проверка доступа пользователя к группе.
        
        Args:
            chat_id: ID чата/группы
            user_id: ID пользователя
            
        Returns:
            True если пользователь имеет доступ к группе
        """
        try:
            # Для админов бота всегда разрешено
            admin_manager = self.context.admin_manager
            if hasattr(admin_manager, 'is_admin'):
                is_admin = await admin_manager.is_admin(user_id)
                if is_admin:
                    return True
            
            # Проверяем, есть ли у пользователя права в группе
            permissions = await self.group_repository.get_user_permissions(chat_id, user_id)
            return permissions.get('view', False) or permissions.get('admin', False)
            
        except Exception as e:
            logger.error(f"Error checking group access: {e}")
            return False
    
    async def _find_service_region(
        self,
        identifier: str,
        user_id: int
    ) -> Optional[ServiceRegion]:
        """
        Поиск региона обслуживания по идентификатору.
        
        Args:
            identifier: Идентификатор региона (название или ID)
            user_id: ID пользователя
            
        Returns:
            Объект региона или None
        """
        try:
            # Пробуем найти по ID
            try:
                region = await self.service_repository.get_region_by_id(identifier)
                if region:
                    return region
            except:
                pass
            
            # Ищем по короткому названию
            regions = await self.service_repository.get_user_regions(user_id)
            for region in regions:
                if (region.short_name.lower() == identifier.lower() or 
                    region.full_name.lower() == identifier.lower()):
                    return region
            
            # Ищем по части названия
            for region in regions:
                if (identifier.lower() in region.short_name.lower() or 
                    identifier.lower() in region.full_name.lower()):
                    return region
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding service region: {e}")
            return None
    
    async def _find_service_object_in_region(
        self,
        region_id: str,
        identifier: str,
        user_id: int
    ) -> Optional[ServiceObject]:
        """
        Поиск объекта обслуживания в регионе.
        
        Args:
            region_id: ID региона
            identifier: Идентификатор объекта
            user_id: ID пользователя
            
        Returns:
            Объект обслуживания или None
        """
        try:
            # Получаем объекты региона
            objects = await self.service_repository.get_region_objects(region_id, user_id)
            
            for obj in objects:
                if (obj.short_name.lower() == identifier.lower() or 
                    obj.full_name.lower() == identifier.lower() or
                    str(obj.id) == identifier):
                    return obj
            
            # Ищем по части названия
            for obj in objects:
                if (identifier.lower() in obj.short_name.lower() or 
                    identifier.lower() in obj.full_name.lower()):
                    return obj
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding service object: {e}")
            return None
    
    async def _find_installation_object(
        self,
        identifier: str,
        user_id: int
    ) -> Optional[InstallationObject]:
        """
        Поиск объекта монтажа.
        
        Args:
            identifier: Идентификатор объекта
            user_id: ID пользователя
            
        Returns:
            Объект монтажа или None
        """
        try:
            # Пробуем найти по ID
            try:
                obj = await self.installation_repository.get_installation_object_by_id(identifier)
                if obj:
                    return obj
            except:
                pass
            
            # Ищем по названию среди объектов пользователя
            objects = await self.installation_repository.get_installation_objects_by_user(user_id)
            
            for obj in objects:
                if (obj.short_name.lower() == identifier.lower() or 
                    obj.full_name.lower() == identifier.lower()):
                    return obj
            
            # Ищем по части названия
            for obj in objects:
                if (identifier.lower() in obj.short_name.lower() or 
                    identifier.lower() in obj.full_name.lower()):
                    return obj
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding installation object: {e}")
            return None
    
    async def _bind_specific_service_object(
        self,
        chat_id: int,
        user_id: int,
        service_object: ServiceObject
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Привязка конкретного объекта обслуживания к группе.
        """
        try:
            # Проверяем, не привязан ли уже объект к этой группе
            existing_binding = await self.group_repository.get_binding(
                object_type='service',
                object_id=str(service_object.id),
                chat_id=chat_id
            )
            
            if existing_binding:
                return False, f"Объект '{service_object.short_name}' уже привязан к этой группе", None
            
            # Создаем привязку
            binding = GroupBinding(
                chat_id=chat_id,
                object_type='service',
                object_id=str(service_object.id),
                object_name=service_object.short_name,
                full_object_name=service_object.full_name,
                created_by=user_id,
                created_at=datetime.now()
            )
            
            await self.group_repository.save_binding(binding)
            
            # Логирование
            await self.log_manager.log_group_binding(
                user_id=user_id,
                chat_id=chat_id,
                object_type='service',
                object_id=str(service_object.id),
                object_name=service_object.full_name,
                action='bind'
            )
            
            binding_info = {
                'id': str(binding.id),
                'object_type': 'service',
                'object_id': str(service_object.id),
                'object_name': service_object.short_name,
                'full_name': service_object.full_name,
                'created_at': binding.created_at.isoformat() if binding.created_at else None
            }
            
            return True, f"Объект обслуживания '{service_object.short_name}' успешно привязан к группе", binding_info
            
        except Exception as e:
            logger.error(f"Error binding specific service object: {e}", exc_info=True)
            raise
    
    async def _bind_service_region(
        self,
        chat_id: int,
        user_id: int,
        region: ServiceRegion
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Привязка всего региона обслуживания к группе.
        """
        try:
            # Проверяем, не привязан ли уже регион к этой группе
            existing_binding = await self.group_repository.get_binding(
                object_type='service_region',
                object_id=str(region.id),
                chat_id=chat_id
            )
            
            if existing_binding:
                return False, f"Регион '{region.short_name}' уже привязан к этой группе", None
            
            # Создаем привязку региона
            binding = GroupBinding(
                chat_id=chat_id,
                object_type='service_region',
                object_id=str(region.id),
                object_name=region.short_name,
                full_object_name=region.full_name,
                created_by=user_id,
                created_at=datetime.now()
            )
            
            await self.group_repository.save_binding(binding)
            
            # Логирование
            await self.log_manager.log_group_binding(
                user_id=user_id,
                chat_id=chat_id,
                object_type='service_region',
                object_id=str(region.id),
                object_name=region.full_name,
                action='bind'
            )
            
            binding_info = {
                'id': str(binding.id),
                'object_type': 'service_region',
                'object_id': str(region.id),
                'object_name': region.short_name,
                'full_name': region.full_name,
                'created_at': binding.created_at.isoformat() if binding.created_at else None
            }
            
            return True, f"Регион обслуживания '{region.short_name}' успешно привязан к группе", binding_info
            
        except Exception as e:
            logger.error(f"Error binding service region: {e}", exc_info=True)
            raise
    
    async def _find_binding(
        self,
        chat_id: int,
        identifier: str
    ) -> Optional[GroupBinding]:
        """
        Поиск привязки в группе по идентификатору.
        
        Args:
            chat_id: ID чата/группы
            identifier: Идентификатор привязки
            
        Returns:
            Объект привязки или None
        """
        try:
            # Получаем все привязки группы
            bindings = await self.group_repository.get_chat_bindings(chat_id)
            
            for binding in bindings:
                if (binding.object_name.lower() == identifier.lower() or
                    (binding.full_object_name and binding.full_object_name.lower() == identifier.lower()) or
                    str(binding.id) == identifier):
                    return binding
            
            # Ищем по части названия
            for binding in bindings:
                if (identifier.lower() in binding.object_name.lower() or
                    (binding.full_object_name and identifier.lower() in binding.full_object_name.lower())):
                    return binding
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding binding: {e}")
            return None
    
    async def _get_object_info(
        self,
        object_type: str,
        object_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Получение дополнительной информации об объекте.
        
        Args:
            object_type: Тип объекта
            object_id: ID объекта
            
        Returns:
            Информация об объекте или None
        """
        try:
            if object_type == 'service':
                obj = await self.service_repository.get_service_object_by_id(object_id)
                if obj:
                    return {
                        'contract_number': obj.contract_number,
                        'end_date': obj.end_date.isoformat() if obj.end_date else None,
                        'addresses': [addr.address for addr in obj.addresses]
                    }
            
            elif object_type == 'installation':
                obj = await self.installation_repository.get_installation_object_by_id(object_id)
                if obj:
                    return {
                        'contract_number': obj.contract_number,
                        'end_date': obj.end_date.isoformat() if obj.end_date else None,
                        'addresses': [addr.address for addr in obj.addresses]
                    }
            
            elif object_type == 'service_region':
                region = await self.service_repository.get_region_by_id(object_id)
                if region:
                    # Получаем количество объектов в регионе
                    objects_count = await self.service_repository.get_region_objects_count(object_id)
                    return {
                        'objects_count': objects_count,
                        'region_type': 'service'
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting object info: {e}")
            return None
    
    async def cleanup_old_bindings(self, days_inactive: int = 90) -> int:
        """
        Очистка старых неактивных привязок.
        
        Args:
            days_inactive: Дней неактивности
            
        Returns:
            Количество удаленных привязок
        """
        try:
            deleted_count = await self.group_repository.delete_old_inactive_bindings(days_inactive)
            logger.info(f"Cleaned up {deleted_count} old inactive bindings")
            return deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up old bindings: {e}")
            return 0