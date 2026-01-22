"""
Менеджер доступа в группах.
Управление правами пользователей и проверка доступа к командам в группах.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime

from aiogram import Bot
from aiogram.types import ChatMember

from core.context import AppContext
from storage.models.group import GroupPermission, GroupAdmin
from storage.models.user import User
from storage.repositories.group_repository import GroupRepository
from storage.repositories.user_repository import UserRepository
from modules.admin.log_manager import LogManager
from utils.exceptions import AccessDeniedError

logger = logging.getLogger(__name__)


class GroupAccessManager:
    """Менеджер доступа в группах."""
    
    def __init__(self, context: AppContext):
        self.context = context
        self.bot: Bot = context.bot
        self.db = context.db
        
        self.group_repository = GroupRepository(self.db)
        self.user_repository = UserRepository(self.db)
        self.log_manager: LogManager = context.log_manager
    
    async def initialize_user_access(
        self,
        chat_id: int,
        user_id: int,
        user_name: Optional[str] = None
    ) -> bool:
        """
        Инициализация доступа пользователя в группе.
        
        Args:
            chat_id: ID чата/группы
            user_id: ID пользователя
            user_name: Имя пользователя
            
        Returns:
            Успех инициализации
        """
        try:
            # Проверяем, существует ли уже запись о доступе
            existing_permission = await self.group_repository.get_user_permission(chat_id, user_id)
            if existing_permission:
                return True
            
            # Получаем информацию о пользователе в чате
            try:
                chat_member = await self.bot.get_chat_member(chat_id, user_id)
                user_role = self._get_role_from_chat_member(chat_member)
            except Exception as e:
                logger.warning(f"Cannot get chat member info: {e}")
                user_role = 'member'
            
            # Определяем базовые права по роли
            base_permissions = self._get_base_permissions_by_role(user_role)
            
            # Создаем или получаем пользователя
            user = await self.user_repository.get_user_by_id(user_id)
            if not user:
                user = User(
                    id=user_id,
                    username=user_name,
                    created_at=datetime.now()
                )
                await self.user_repository.save_user(user)
            
            # Создаем запись о правах
            permission = GroupPermission(
                chat_id=chat_id,
                user_id=user_id,
                role=user_role,
                permissions=base_permissions,
                is_active=True,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            await self.group_repository.save_permission(permission)
            
            logger.info(f"Initialized access for user {user_id} in chat {chat_id} with role {user_role}")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing user access: {e}", exc_info=True)
            return False
    
    async def check_command_access(
        self,
        chat_id: int,
        user_id: int,
        command: str,
        is_admin_command: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Проверка доступа пользователя к команде в группе.
        
        Args:
            chat_id: ID чата/группы
            user_id: ID пользователя
            command: Команда для проверки
            is_admin_command: Является ли команда административной
            
        Returns:
            Кортеж (доступ разрешен, причина отказа)
        """
        try:
            # Инициализируем доступ пользователя если нужно
            await self.initialize_user_access(chat_id, user_id)
            
            # Получаем права пользователя
            permissions = await self.group_repository.get_user_permissions(chat_id, user_id)
            
            # Проверяем базовый доступ
            if not permissions.get('view', False):
                return False, "Нет доступа к просмотру в этой группе"
            
            # Админские команды требуют прав администратора
            if is_admin_command and not permissions.get('admin', False):
                return False, "Требуются права администратора группы"
            
            # Определяем требуемые права для команды
            required_permission = self._get_required_permission_for_command(command)
            
            # Проверяем наличие требуемого права
            if required_permission and not permissions.get(required_permission, False):
                permission_names = {
                    'view': 'просмотр',
                    'edit': 'редактирование',
                    'add': 'добавление',
                    'delete': 'удаление',
                    'admin': 'администрирование'
                }
                return False, f"Требуется право '{permission_names.get(required_permission, required_permission)}'"
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error checking command access: {e}", exc_info=True)
            return False, f"Ошибка проверки доступа: {str(e)}"
    
    async def get_user_permissions(
        self,
        chat_id: int,
        user_id: int
    ) -> Dict[str, bool]:
        """
        Получение прав пользователя в группе.
        
        Args:
            chat_id: ID чата/группы
            user_id: ID пользователя
            
        Returns:
            Словарь прав пользователя
        """
        try:
            return await self.group_repository.get_user_permissions(chat_id, user_id)
        except Exception as e:
            logger.error(f"Error getting user permissions: {e}")
            return {}
    
    async def update_user_permissions(
        self,
        chat_id: int,
        target_user_id: int,
        updater_user_id: int,
        permissions: Dict[str, bool]
    ) -> Tuple[bool, str]:
        """
        Обновление прав пользователя в группе.
        
        Args:
            chat_id: ID чата/группы
            target_user_id: ID пользователя, чьи права обновляются
            updater_user_id: ID пользователя, обновляющего права
            permissions: Новые права
            
        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            # Проверяем, что обновляющий имеет права администратора
            updater_permissions = await self.get_user_permissions(chat_id, updater_user_id)
            if not updater_permissions.get('admin', False):
                return False, "Требуются права администратора группы"
            
            # Получаем текущие права
            existing_permission = await self.group_repository.get_user_permission(chat_id, target_user_id)
            
            if not existing_permission:
                return False, "Пользователь не найден в группе"
            
            # Обновляем права
            old_permissions = existing_permission.permissions.copy()
            
            # Обновляем только существующие ключи прав
            valid_permissions = {'view', 'edit', 'add', 'delete', 'admin'}
            for perm_key, perm_value in permissions.items():
                if perm_key in valid_permissions:
                    existing_permission.permissions[perm_key] = perm_value
            
            existing_permission.updated_at = datetime.now()
            
            await self.group_repository.save_permission(existing_permission)
            
            # Логирование
            await self.log_manager.log_group_permission_change(
                chat_id=chat_id,
                admin_user_id=updater_user_id,
                target_user_id=target_user_id,
                old_permissions=old_permissions,
                new_permissions=existing_permission.permissions
            )
            
            return True, "Права пользователя успешно обновлены"
            
        except Exception as e:
            logger.error(f"Error updating user permissions: {e}", exc_info=True)
            return False, f"Ошибка обновления прав: {str(e)}"
    
    async def set_user_role(
        self,
        chat_id: int,
        target_user_id: int,
        updater_user_id: int,
        role: str
    ) -> Tuple[bool, str]:
        """
        Установка роли пользователя в группе.
        
        Args:
            chat_id: ID чата/группы
            target_user_id: ID пользователя
            updater_user_id: ID пользователя, устанавливающего роль
            role: Новая роль
            
        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            # Проверяем, что обновляющий имеет права администратора
            updater_permissions = await self.get_user_permissions(chat_id, updater_user_id)
            if not updater_permissions.get('admin', False):
                return False, "Требуются права администратора группы"
            
            # Проверяем валидность роли
            valid_roles = {'owner', 'administrator', 'member', 'restricted', 'left', 'kicked'}
            if role not in valid_roles:
                return False, f"Недопустимая роль: {role}"
            
            # Получаем текущую запись
            existing_permission = await self.group_repository.get_user_permission(chat_id, target_user_id)
            
            if not existing_permission:
                return False, "Пользователь не найден в группе"
            
            old_role = existing_permission.role
            
            # Обновляем роль и соответствующие права
            existing_permission.role = role
            
            # Обновляем права согласно роли
            base_permissions = self._get_base_permissions_by_role(role)
            existing_permission.permissions.update(base_permissions)
            
            existing_permission.updated_at = datetime.now()
            
            await self.group_repository.save_permission(existing_permission)
            
            # Логирование
            await self.log_manager.log_group_role_change(
                chat_id=chat_id,
                admin_user_id=updater_user_id,
                target_user_id=target_user_id,
                old_role=old_role,
                new_role=role
            )
            
            return True, f"Роль пользователя успешно изменена на '{role}'"
            
        except Exception as e:
            logger.error(f"Error setting user role: {e}", exc_info=True)
            return False, f"Ошибка установки роли: {str(e)}"
    
    async def add_group_admin(
        self,
        chat_id: int,
        admin_user_id: int,
        added_by_user_id: int,
        admin_type: str = 'group_admin'
    ) -> Tuple[bool, str]:
        """
        Добавление администратора группы.
        
        Args:
            chat_id: ID чата/группы
            admin_user_id: ID пользователя-администратора
            added_by_user_id: ID пользователя, добавляющего администратора
            admin_type: Тип администратора ('group_admin', 'main_admin')
            
        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            # Проверяем, что добавляющий имеет права главного администратора
            adder_permissions = await self.get_user_permissions(chat_id, added_by_user_id)
            if not adder_permissions.get('admin', False):
                return False, "Требуются права администратора группы"
            
            # Проверяем, не является ли пользователь уже администратором
            existing_admin = await self.group_repository.get_group_admin(chat_id, admin_user_id)
            if existing_admin:
                return False, "Пользователь уже является администратором группы"
            
            # Создаем запись администратора
            admin = GroupAdmin(
                chat_id=chat_id,
                user_id=admin_user_id,
                admin_type=admin_type,
                is_active=True,
                created_by=added_by_user_id,
                created_at=datetime.now()
            )
            
            await self.group_repository.save_group_admin(admin)
            
            # Обновляем права пользователя
            await self.update_user_permissions(
                chat_id=chat_id,
                target_user_id=admin_user_id,
                updater_user_id=added_by_user_id,
                permissions={'admin': True, 'edit': True, 'add': True, 'delete': True, 'view': True}
            )
            
            # Логирование
            await self.log_manager.log_group_admin_action(
                chat_id=chat_id,
                action='add_admin',
                admin_user_id=added_by_user_id,
                target_user_id=admin_user_id,
                details={'admin_type': admin_type}
            )
            
            return True, "Администратор группы успешно добавлен"
            
        except Exception as e:
            logger.error(f"Error adding group admin: {e}", exc_info=True)
            return False, f"Ошибка добавления администратора: {str(e)}"
    
    async def remove_group_admin(
        self,
        chat_id: int,
        admin_user_id: int,
        removed_by_user_id: int
    ) -> Tuple[bool, str]:
        """
        Удаление администратора группы.
        
        Args:
            chat_id: ID чата/группы
            admin_user_id: ID пользователя-администратора
            removed_by_user_id: ID пользователя, удаляющего администратора
            
        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            # Проверяем, что удаляющий имеет права главного администратора
            remover_permissions = await self.get_user_permissions(chat_id, removed_by_user_id)
            if not remover_permissions.get('admin', False):
                return False, "Требуются права администратора группы"
            
            # Находим администратора
            admin = await self.group_repository.get_group_admin(chat_id, admin_user_id)
            if not admin:
                return False, "Пользователь не является администратором группы"
            
            # Удаляем запись администратора
            deleted = await self.group_repository.delete_group_admin(str(admin.id))
            
            if deleted:
                # Сбрасываем права пользователя к базовым
                try:
                    chat_member = await self.bot.get_chat_member(chat_id, admin_user_id)
                    user_role = self._get_role_from_chat_member(chat_member)
                    base_permissions = self._get_base_permissions_by_role(user_role)
                    
                    await self.update_user_permissions(
                        chat_id=chat_id,
                        target_user_id=admin_user_id,
                        updater_user_id=removed_by_user_id,
                        permissions=base_permissions
                    )
                except Exception as e:
                    logger.warning(f"Cannot reset permissions for user {admin_user_id}: {e}")
                
                # Логирование
                await self.log_manager.log_group_admin_action(
                    chat_id=chat_id,
                    action='remove_admin',
                    admin_user_id=removed_by_user_id,
                    target_user_id=admin_user_id,
                    details={'admin_type': admin.admin_type}
                )
                
                return True, "Администратор группы успешно удален"
            else:
                return False, "Не удалось удалить администратора"
            
        except Exception as e:
            logger.error(f"Error removing group admin: {e}", exc_info=True)
            return False, f"Ошибка удаления администратора: {str(e)}"
    
    async def get_group_admins(
        self,
        chat_id: int,
        user_id: int
    ) -> List[Dict[str, Any]]:
        """
        Получение списка администраторов группы.
        
        Args:
            chat_id: ID чата/группы
            user_id: ID пользователя, запрашивающего список
            
        Returns:
            Список администраторов
        """
        try:
            # Проверяем права пользователя
            permissions = await self.get_user_permissions(chat_id, user_id)
            if not permissions.get('admin', False) and not permissions.get('view', False):
                raise AccessDeniedError("Нет доступа к списку администраторов")
            
            admins = await self.group_repository.get_group_admins(chat_id)
            
            result = []
            for admin in admins:
                # Получаем информацию о пользователе
                user = await self.user_repository.get_user_by_id(admin.user_id)
                
                admin_info = {
                    'user_id': admin.user_id,
                    'username': user.username if user else f"user_{admin.user_id}",
                    'admin_type': admin.admin_type,
                    'created_at': admin.created_at.isoformat() if admin.created_at else None,
                    'created_by': admin.created_by,
                    'is_active': admin.is_active
                }
                
                result.append(admin_info)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting group admins: {e}")
            return []
    
    async def sync_group_permissions(
        self,
        chat_id: int
    ) -> Tuple[bool, str, Dict[str, int]]:
        """
        Синхронизация прав пользователей с реальным статусом в чате.
        
        Args:
            chat_id: ID чата/группы
            
        Returns:
            Кортеж (успех, сообщение, статистика)
        """
        try:
            stats = {
                'total_members': 0,
                'synced': 0,
                'errors': 0
            }
            
            # Получаем всех участников чата
            try:
                # Внимание: Этот метод может быть ограничен правами бота
                # В реальном приложении нужно использовать события обновления участников
                members_count = await self.bot.get_chat_member_count(chat_id)
                stats['total_members'] = members_count
                
                # Получаем администраторов чата
                admins = await self.bot.get_chat_administrators(chat_id)
                
                # Синхронизируем администраторов
                for admin_member in admins:
                    try:
                        user_id = admin_member.user.id
                        user_role = self._get_role_from_chat_member(admin_member)
                        
                        # Инициализируем доступ
                        await self.initialize_user_access(
                            chat_id=chat_id,
                            user_id=user_id,
                            user_name=admin_member.user.username
                        )
                        
                        # Устанавливаем роль и права
                        await self.set_user_role(
                            chat_id=chat_id,
                            target_user_id=user_id,
                            updater_user_id=self.bot.id,  # Бот как инициатор
                            role=user_role
                        )
                        
                        # Если это создатель или администратор, добавляем как администратора бота
                        if user_role in ['owner', 'administrator']:
                            await self.add_group_admin(
                                chat_id=chat_id,
                                admin_user_id=user_id,
                                added_by_user_id=self.bot.id,
                                admin_type='group_admin'
                            )
                        
                        stats['synced'] += 1
                        
                    except Exception as e:
                        logger.error(f"Error syncing member {admin_member.user.id}: {e}")
                        stats['errors'] += 1
                
                return True, f"Синхронизировано {stats['synced']} пользователей", stats
                
            except Exception as e:
                logger.error(f"Error getting chat members: {e}")
                return False, f"Ошибка синхронизации: {str(e)}", stats
            
        except Exception as e:
            logger.error(f"Error syncing group permissions: {e}", exc_info=True)
            return False, f"Ошибка синхронизации: {str(e)}", {'total_members': 0, 'synced': 0, 'errors': 1}
    
    async def can_user_access_object(
        self,
        chat_id: int,
        user_id: int,
        object_type: str,
        object_id: str,
        required_permission: str = 'view'
    ) -> Tuple[bool, Optional[str]]:
        """
        Проверка доступа пользователя к объекту в группе.
        
        Args:
            chat_id: ID чата/группы
            user_id: ID пользователя
            object_type: Тип объекта
            object_id: ID объекта
            required_permission: Требуемое право
            
        Returns:
            Кортеж (доступ разрешен, причина отказа)
        """
        try:
            # Проверяем общий доступ к группе
            has_group_access, reason = await self.check_command_access(
                chat_id=chat_id,
                user_id=user_id,
                command=f"access_{object_type}",
                is_admin_command=False
            )
            
            if not has_group_access:
                return False, reason
            
            # Проверяем, привязан ли объект к группе
            bind_manager = self.context.group_bind_manager
            if hasattr(bind_manager, 'check_object_in_group'):
                is_bound = await bind_manager.check_object_in_group(chat_id, object_type, object_id)
                if not is_bound:
                    return False, "Объект не привязан к этой группе"
            
            # Проверяем права на объект
            permissions = await self.get_user_permissions(chat_id, user_id)
            
            # Проверяем требуемое право
            if required_permission == 'view':
                if not permissions.get('view', False):
                    return False, "Нет права на просмотр"
            elif required_permission == 'edit':
                if not permissions.get('edit', False):
                    return False, "Нет права на редактирование"
            elif required_permission == 'add':
                if not permissions.get('add', False):
                    return False, "Нет права на добавление"
            elif required_permission == 'delete':
                if not permissions.get('delete', False):
                    return False, "Нет права на удаление"
            elif required_permission == 'admin':
                if not permissions.get('admin', False):
                    return False, "Требуются права администратора"
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error checking object access: {e}")
            return False, f"Ошибка проверки доступа: {str(e)}"
    
    # ========== Внутренние методы ==========
    
    def _get_role_from_chat_member(self, chat_member: ChatMember) -> str:
        """
        Определение роли пользователя из информации о участнике чата.
        
        Args:
            chat_member: Информация об участнике чата
            
        Returns:
            Роль пользователя
        """
        if chat_member.status == 'creator':
            return 'owner'
        elif chat_member.status == 'administrator':
            return 'administrator'
        elif chat_member.status == 'member':
            return 'member'
        elif chat_member.status == 'restricted':
            return 'restricted'
        elif chat_member.status == 'left':
            return 'left'
        elif chat_member.status == 'kicked':
            return 'kicked'
        else:
            return 'member'
    
    def _get_base_permissions_by_role(self, role: str) -> Dict[str, bool]:
        """
        Получение базовых прав по роли.
        
        Args:
            role: Роль пользователя
            
        Returns:
            Базовые права
        """
        # Базовые права для разных ролей
        base_permissions = {
            'owner': {
                'view': True,
                'edit': True,
                'add': True,
                'delete': True,
                'admin': True
            },
            'administrator': {
                'view': True,
                'edit': True,
                'add': True,
                'delete': True,
                'admin': True
            },
            'member': {
                'view': True,
                'edit': False,
                'add': False,
                'delete': False,
                'admin': False
            },
            'restricted': {
                'view': False,
                'edit': False,
                'add': False,
                'delete': False,
                'admin': False
            },
            'left': {
                'view': False,
                'edit': False,
                'add': False,
                'delete': False,
                'admin': False
            },
            'kicked': {
                'view': False,
                'edit': False,
                'add': False,
                'delete': False,
                'admin': False
            }
        }
        
        return base_permissions.get(role, base_permissions['member'])
    
    def _get_required_permission_for_command(self, command: str) -> Optional[str]:
        """
        Определение требуемого права для команды.
        
        Args:
            command: Команда
            
        Returns:
            Требуемое право или None
        """
        # Маппинг команд к требуемым правам
        command_permissions = {
            # Команды просмотра
            'мои_объекты': 'view',
            'проекты': 'view',
            'изменения': 'view',
            'письма': 'view',
            'допуски': 'view',
            'журналы': 'view',
            'напоминания': 'view',
            'поиск': 'view',
            
            # Команды добавления
            'добавить': 'add',
            'создать': 'add',
            'новый': 'add',
            
            # Команды редактирования
            'изменить': 'edit',
            'обновить': 'edit',
            'редактировать': 'edit',
            
            # Команды удаления
            'удалить': 'delete',
            'стереть': 'delete',
            'очистить': 'delete',
            
            # Админские команды
            'разрешения': 'admin',
            'админы': 'admin',
            'права': 'admin',
            'настройки': 'admin'
        }
        
        # Ищем команду в маппинге
        command_lower = command.lower().strip('!/')
        for cmd_key, perm in command_permissions.items():
            if cmd_key in command_lower:
                return perm
        
        return None
    
    async def _get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получение информации о пользователе.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Информация о пользователе
        """
        try:
            user = await self.user_repository.get_user_by_id(user_id)
            if user:
                return {
                    'id': user.id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'created_at': user.created_at.isoformat() if user.created_at else None
                }
            return None
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return None
    
    async def cleanup_inactive_users(self, days_inactive: int = 30) -> int:
        """
        Очистка записей о неактивных пользователях.
        
        Args:
            days_inactive: Дней неактивности
            
        Returns:
            Количество очищенных записей
        """
        try:
            cleaned_count = await self.group_repository.deactivate_inactive_users(days_inactive)
            logger.info(f"Cleaned up {cleaned_count} inactive user records")
            return cleaned_count
        except Exception as e:
            logger.error(f"Error cleaning up inactive users: {e}")
            return 0