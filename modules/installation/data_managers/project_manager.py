import logging
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from core.context import AppContext
from modules.file.archive_manager import ArchiveManager
from storage.models.installation import InstallationProject
from storage.repositories.installation_repository import InstallationRepository
from utils.exceptions import AccessDeniedError, NotFoundError
from modules.admin.log_manager import LogManager

logger = logging.getLogger(__name__)


class ProjectManager:
    """Менеджер проектов монтажа"""
    
    def __init__(self, context: AppContext):
        self.context = context
        self.db = context.db
        self.archive_manager: ArchiveManager = context.archive_manager
        self.installation_repository = InstallationRepository(self.db)
        self.log_manager: LogManager = context.log_manager
    
    async def add_project(
        self,
        object_id: str,
        user_id: int,
        project_name: str,
        file_message_id: Optional[int] = None,
        file_data: Optional[Dict] = None
    ) -> Tuple[bool, str, str]:
        """
        Добавление проекта к объекту монтажа
        
        Returns:
            Tuple[успех, ID проекта, сообщение]
        """
        try:
            # Проверка доступа к объекту
            has_access = await self.installation_repository.check_object_access(
                object_id, user_id
            )
            
            if not has_access:
                return False, "", "Нет доступа к объекту"
            
            # Проверка имени проекта
            if not project_name or len(project_name.strip()) < 3:
                return False, "", "Название проекта должно содержать минимум 3 символа"
            
            # Сохранение файла в архив если есть
            file_info = None
            if file_message_id or file_data:
                try:
                    file_info = await self.archive_manager.save_project_file(
                        object_id=object_id,
                        user_id=user_id,
                        project_name=project_name,
                        message_id=file_message_id,
                        file_data=file_data
                    )
                except Exception as e:
                    logger.error(f"Error saving project file: {e}")
                    return False, "", f"Ошибка сохранения файла: {str(e)}"
            
            # Создание проекта в БД
            project = await self.installation_repository.add_project(
                object_id=object_id,
                name=project_name,
                file_info=file_info
            )
            
            # Логирование изменения
            await self._log_project_action(
                object_id=object_id,
                user_id=user_id,
                project_id=project.id,
                project_name=project_name,
                action='add',
                details={
                    'file_info': file_info,
                    'has_file': file_info is not None
                }
            )
            
            return True, str(project.id), "Проект успешно добавлен"
            
        except Exception as e:
            logger.error(f"Error adding project: {e}", exc_info=True)
            return False, "", f"Ошибка добавления проекта: {str(e)}"
    
    async def get_projects(self, object_id: str, user_id: int, user_level: str = 'viewer') -> List[Dict[str, Any]]:
        """
        Получение списка проектов объекта с учетом уровня доступа
        
        Args:
            user_level: 'admin', 'editor', 'viewer'
        """
        try:
            # Проверка доступа
            has_access = await self.installation_repository.check_object_access(
                object_id, user_id
            )
            
            if not has_access:
                raise AccessDeniedError("Нет доступа к объекту")
            
            # Получение проектов
            projects = await self.installation_repository.get_projects(object_id)
            
            # Определяем доступные действия
            can_edit = user_level in ['admin', 'editor']
            can_delete = user_level in ['admin']
            
            # Форматирование результатов
            result = []
            for project in projects:
                project_data = {
                    'id': str(project.id),
                    'name': project.name,
                    'created_at': project.created_at.isoformat() if project.created_at else None,
                    'file_info': project.file_info,
                    'order_number': project.order_number,
                    'has_file': project.file_info is not None,
                    'can_edit': can_edit,
                    'can_delete': can_delete,
                    'created_by': project.created_by
                }
                
                # Добавляем информацию о файле если есть
                if project.file_info and hasattr(self.archive_manager, 'get_file_info'):
                    try:
                        file_info = await self.archive_manager.get_file_info(project.file_info)
                        if file_info:
                            project_data['file_details'] = file_info
                    except Exception as e:
                        logger.debug(f"Could not get file info: {e}")
                
                result.append(project_data)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting projects: {e}", exc_info=True)
            raise
    
    async def update_project(
        self,
        project_id: str,
        user_id: int,
        new_name: Optional[str] = None,
        new_file_message_id: Optional[int] = None,
        new_file_data: Optional[Dict] = None
    ) -> Tuple[bool, str]:
        """
        Обновление информации о проекте
        
        Returns:
            Tuple[успех, сообщение]
        """
        try:
            # Получение проекта
            project = await self.installation_repository.get_project_by_id(project_id)
            
            if not project:
                return False, "Проект не найден"
            
            # Проверка доступа
            has_access = await self.installation_repository.check_object_access(
                str(project.object_id), user_id
            )
            
            if not has_access:
                return False, "Нет доступа к проекту"
            
            old_data = {
                'name': project.name,
                'file_info': project.file_info
            }
            
            # Обновление данных
            updates = {}
            
            if new_name:
                if len(new_name.strip()) < 3:
                    return False, "Название проекта должно содержать минимум 3 символа"
                updates['name'] = new_name
            
            # Обновление файла если есть новый
            new_file_info = None
            if new_file_message_id or new_file_data:
                try:
                    # Удаляем старый файл если есть
                    if project.file_info:
                        await self.archive_manager.delete_file(project.file_info)
                    
                    # Сохраняем новый файл
                    new_file_info = await self.archive_manager.save_project_file(
                        object_id=str(project.object_id),
                        user_id=user_id,
                        project_name=new_name or project.name,
                        message_id=new_file_message_id,
                        file_data=new_file_data
                    )
                    updates['file_info'] = new_file_info
                except Exception as e:
                    logger.error(f"Error updating project file: {e}")
                    return False, f"Ошибка обновления файла: {str(e)}"
            
            # Обновление в БД
            updated_project = await self.installation_repository.update_project(
                project_id, updates
            )
            
            # Логирование изменения
            new_data = {}
            if new_name:
                new_data['name'] = new_name
            if new_file_info:
                new_data['file_info'] = new_file_info
            
            await self._log_project_action(
                object_id=str(project.object_id),
                user_id=user_id,
                project_id=project_id,
                project_name=updated_project.name,
                action='update',
                old_data=old_data,
                new_data=new_data
            )
            
            return True, "Проект успешно обновлен"
            
        except Exception as e:
            logger.error(f"Error updating project: {e}", exc_info=True)
            return False, f"Ошибка обновления проекта: {str(e)}"
    
    async def delete_project(self, project_id: str, user_id: int) -> Tuple[bool, str]:
        """
        Удаление проекта
        
        Returns:
            Tuple[успех, сообщение]
        """
        try:
            # Получение проекта
            project = await self.installation_repository.get_project_by_id(project_id)
            
            if not project:
                return False, "Проект не найден"
            
            # Проверка доступа
            has_access = await self.installation_repository.check_object_access(
                str(project.object_id), user_id
            )
            
            if not has_access:
                return False, "Нет доступа к проекту"
            
            # Удаление файла из архива если есть
            if project.file_info:
                try:
                    await self.archive_manager.delete_file(project.file_info)
                except Exception as e:
                    logger.error(f"Error deleting project file: {e}")
                    # Продолжаем удаление проекта даже если файл не удалось удалить
            
            # Удаление проекта из БД
            deleted = await self.installation_repository.delete_project(project_id)
            
            if deleted:
                # Логирование удаления
                await self._log_project_action(
                    object_id=str(project.object_id),
                    user_id=user_id,
                    project_id=project_id,
                    project_name=project.name,
                    action='delete',
                    details={
                        'had_file': project.file_info is not None
                    }
                )
                
                # Перенумерация оставшихся проектов
                await self._renumber_projects(str(project.object_id))
                
                return True, "Проект успешно удален"
            else:
                return False, "Не удалось удалить проект"
            
        except Exception as e:
            logger.error(f"Error deleting project: {e}", exc_info=True)
            return False, f"Ошибка удаления проекта: {str(e)}"
    
    async def get_project_by_id(self, project_id: str, user_id: int) -> Optional[Dict[str, Any]]:
        """Получение проекта по ID"""
        try:
            project = await self.installation_repository.get_project_by_id(project_id)
            
            if not project:
                return None
            
            # Проверка доступа
            has_access = await self.installation_repository.check_object_access(
                str(project.object_id), user_id
            )
            
            if not has_access:
                raise AccessDeniedError("Нет доступа к проекту")
            
            result = {
                'id': str(project.id),
                'name': project.name,
                'object_id': str(project.object_id),
                'file_info': project.file_info,
                'has_file': project.file_info is not None,
                'created_at': project.created_at.isoformat() if project.created_at else None,
                'order_number': project.order_number,
                'created_by': project.created_by
            }
            
            # Получаем детальную информацию о файле если есть
            if project.file_info and hasattr(self.archive_manager, 'get_file_info'):
                try:
                    file_info = await self.archive_manager.get_file_info(project.file_info)
                    if file_info:
                        result['file_details'] = file_info
                        
                        # Получаем URL для скачивания если доступно
                        if hasattr(self.archive_manager, 'get_file_download_url'):
                            download_url = await self.archive_manager.get_file_download_url(project.file_info)
                            if download_url:
                                result['download_url'] = download_url
                except Exception as e:
                    logger.debug(f"Could not get file details: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting project by id: {e}", exc_info=True)
            raise
    
    async def search_projects(self, object_id: str, user_id: int, search_text: str) -> List[Dict[str, Any]]:
        """
        Поиск проектов по названию
        
        Returns:
            Список найденных проектов
        """
        try:
            if not search_text or len(search_text.strip()) < 2:
                return []
            
            search_text = search_text.strip().lower()
            
            # Проверка доступа
            has_access = await self.installation_repository.check_object_access(
                object_id, user_id
            )
            
            if not has_access:
                raise AccessDeniedError("Нет доступа к объекту")
            
            # Получаем все проекты и фильтруем локально
            # В будущем можно добавить поиск в репозитории
            projects = await self.installation_repository.get_projects(object_id)
            
            result = []
            for project in projects:
                if search_text in project.name.lower():
                    result.append({
                        'id': str(project.id),
                        'name': project.name,
                        'has_file': project.file_info is not None,
                        'created_at': project.created_at.isoformat() if project.created_at else None,
                        'created_by': project.created_by
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"Error searching projects: {e}", exc_info=True)
            return []
    
    async def batch_add_projects(
        self,
        object_id: str,
        user_id: int,
        projects_data: List[Dict[str, Any]]
    ) -> Tuple[bool, List[str], str]:
        """
        Пакетное добавление проектов
        
        Args:
            projects_data: [{'name': '...', 'file_data': {...}}]
            
        Returns:
            Tuple[успех, список ID добавленных проектов, сообщение]
        """
        try:
            # Проверка доступа
            has_access = await self.installation_repository.check_object_access(
                object_id, user_id
            )
            
            if not has_access:
                return False, [], "Нет доступа к объекту"
            
            added_project_ids = []
            errors = []
            
            for i, project_data in enumerate(projects_data):
                try:
                    success, project_id, error = await self.add_project(
                        object_id,
                        user_id,
                        project_data['name'],
                        file_data=project_data.get('file_data')
                    )
                    
                    if success:
                        added_project_ids.append(project_id)
                    else:
                        errors.append(f"Проект {i+1}: {error}")
                        
                except Exception as e:
                    errors.append(f"Проект {i+1}: {str(e)}")
            
            if errors:
                error_message = f"Добавлено {len(added_project_ids)} из {len(projects_data)} проектов. Ошибки: " + "; ".join(errors[:3])
                if len(errors) > 3:
                    error_message += f" ... и ещё {len(errors) - 3} ошибок"
                return len(added_project_ids) > 0, added_project_ids, error_message
            else:
                return True, added_project_ids, f"Успешно добавлено {len(added_project_ids)} проектов"
            
        except Exception as e:
            logger.error(f"Error batch adding projects: {e}", exc_info=True)
            return False, [], f"Ошибка пакетного добавления: {str(e)}"
    
    async def _renumber_projects(self, object_id: str) -> None:
        """Перенумерация проектов после удаления"""
        try:
            projects = await self.installation_repository.get_projects(object_id)
            
            for index, project in enumerate(projects, 1):
                await self.installation_repository.update_project(
                    str(project.id),
                    {'order_number': index}
                )
                
        except Exception as e:
            logger.error(f"Error renumbering projects: {e}")
    
    async def _log_project_action(
        self,
        object_id: str,
        user_id: int,
        project_id: str,
        project_name: str,
        action: str,
        details: Optional[Dict] = None,
        old_data: Optional[Dict] = None,
        new_data: Optional[Dict] = None
    ) -> None:
        """Логирование действий с проектами"""
        try:
            if hasattr(self.log_manager, 'log_project_action'):
                await self.log_manager.log_project_action(
                    user_id=user_id,
                    object_id=object_id,
                    object_name=await self._get_object_name(object_id),
                    project_id=project_id,
                    project_name=project_name,
                    action=action,
                    details=details,
                    old_data=old_data,
                    new_data=new_data
                )
            else:
                # Fallback к старому методу логирования
                await self._log_change(
                    object_id=object_id,
                    user_id=user_id,
                    action=f"{action}_project",
                    details={
                        'project_id': project_id,
                        'project_name': project_name,
                        **(details or {})
                    }
                )
                
        except Exception as e:
            logger.error(f"Error logging project action: {e}")
    
    async def _log_change(
        self,
        object_id: str,
        user_id: int,
        action: str,
        details: Dict[str, Any]
    ) -> None:
        """Логирование изменений (совместимость со старым кодом)"""
        try:
            if hasattr(self.log_manager, 'log_installation_change'):
                await self.log_manager.log_installation_change(
                    object_id=object_id,
                    user_id=user_id,
                    action=action,
                    details=details
                )
        except Exception as e:
            logger.error(f"Error logging project change: {e}")
    
    async def _get_object_name(self, object_id: str) -> str:
        """Получение названия объекта"""
        try:
            # Метод должен быть в installation_repository
            if hasattr(self.installation_repository, 'get_object_name'):
                return await self.installation_repository.get_object_name(object_id)
            return ""
        except Exception:
            return ""