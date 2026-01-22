import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.context import AppContext
from modules.file.archive_manager import ArchiveManager
from storage.models.installation import InstallationProject
from storage.repositories.installation_repository import InstallationRepository
from utils.exceptions import AccessDeniedError, NotFoundError

logger = logging.getLogger(__name__)


class ProjectManager:
    """Менеджер проектов монтажа"""
    
    def __init__(self, context: AppContext):
        self.context = context
        self.db = context.db
        self.archive_manager = context.archive_manager
        self.installation_repository = InstallationRepository(self.db)
    
    async def add_project(
        self,
        object_id: str,
        user_id: int,
        project_name: str,
        file_message_id: Optional[int] = None,
        file_data: Optional[Dict] = None
    ) -> str:
        """Добавление проекта к объекту монтажа"""
        try:
            # Проверка доступа к объекту
            has_access = await self.installation_repository.check_object_access(
                object_id, user_id
            )
            
            if not has_access:
                raise AccessDeniedError("Нет доступа к объекту")
            
            # Сохранение файла в архив если есть
            file_info = None
            if file_message_id or file_data:
                file_info = await self.archive_manager.save_project_file(
                    object_id=object_id,
                    user_id=user_id,
                    project_name=project_name,
                    message_id=file_message_id,
                    file_data=file_data
                )
            
            # Создание проекта в БД
            project = await self.installation_repository.add_project(
                object_id=object_id,
                name=project_name,
                file_info=file_info
            )
            
            # Логирование изменения
            await self._log_change(
                object_id=object_id,
                user_id=user_id,
                action="add_project",
                details={"project_name": project_name}
            )
            
            return project.id
            
        except Exception as e:
            logger.error(f"Error adding project: {e}")
            raise
    
    async def get_projects(self, object_id: str, user_id: int) -> List[Dict[str, Any]]:
        """Получение списка проектов объекта"""
        try:
            # Проверка доступа
            has_access = await self.installation_repository.check_object_access(
                object_id, user_id
            )
            
            if not has_access:
                raise AccessDeniedError("Нет доступа к объекту")
            
            # Получение проектов
            projects = await self.installation_repository.get_projects(object_id)
            
            # Форматирование результатов
            result = []
            for project in projects:
                result.append({
                    'id': str(project.id),
                    'name': project.name,
                    'created_at': project.created_at,
                    'file_info': project.file_info,
                    'order_number': project.order_number
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting projects: {e}")
            raise
    
    async def update_project(
        self,
        project_id: str,
        user_id: int,
        new_name: Optional[str] = None,
        new_file_message_id: Optional[int] = None,
        new_file_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Обновление информации о проекте"""
        try:
            # Получение проекта
            project = await self.installation_repository.get_project_by_id(project_id)
            
            if not project:
                raise NotFoundError("Проект не найден")
            
            # Проверка доступа
            has_access = await self.installation_repository.check_object_access(
                str(project.object_id), user_id
            )
            
            if not has_access:
                raise AccessDeniedError("Нет доступа к проекту")
            
            # Обновление данных
            updates = {}
            
            if new_name:
                updates['name'] = new_name
            
            # Обновление файла если есть новый
            if new_file_message_id or new_file_data:
                # Удаляем старый файл если есть
                if project.file_info:
                    await self.archive_manager.delete_file(project.file_info)
                
                # Сохраняем новый файл
                file_info = await self.archive_manager.save_project_file(
                    object_id=str(project.object_id),
                    user_id=user_id,
                    project_name=new_name or project.name,
                    message_id=new_file_message_id,
                    file_data=new_file_data
                )
                updates['file_info'] = file_info
            
            # Обновление в БД
            updated_project = await self.installation_repository.update_project(
                project_id, updates
            )
            
            # Логирование изменения
            await self._log_change(
                object_id=str(project.object_id),
                user_id=user_id,
                action="update_project",
                details={
                    "project_id": project_id,
                    "old_name": project.name,
                    "new_name": new_name
                }
            )
            
            return {
                'id': str(updated_project.id),
                'name': updated_project.name,
                'file_info': updated_project.file_info
            }
            
        except Exception as e:
            logger.error(f"Error updating project: {e}")
            raise
    
    async def delete_project(self, project_id: str, user_id: int) -> bool:
        """Удаление проекта"""
        try:
            # Получение проекта
            project = await self.installation_repository.get_project_by_id(project_id)
            
            if not project:
                raise NotFoundError("Проект не найден")
            
            # Проверка доступа
            has_access = await self.installation_repository.check_object_access(
                str(project.object_id), user_id
            )
            
            if not has_access:
                raise AccessDeniedError("Нет доступа к проекту")
            
            # Удаление файла из архива если есть
            if project.file_info:
                await self.archive_manager.delete_file(project.file_info)
            
            # Удаление проекта из БД
            deleted = await self.installation_repository.delete_project(project_id)
            
            if deleted:
                # Логирование удаления
                await self._log_change(
                    object_id=str(project.object_id),
                    user_id=user_id,
                    action="delete_project",
                    details={"project_name": project.name}
                )
                
                # Перенумерация оставшихся проектов
                await self._renumber_projects(str(project.object_id))
            
            return deleted
            
        except Exception as e:
            logger.error(f"Error deleting project: {e}")
            raise
    
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
            
            return {
                'id': str(project.id),
                'name': project.name,
                'object_id': str(project.object_id),
                'file_info': project.file_info,
                'created_at': project.created_at,
                'order_number': project.order_number
            }
            
        except Exception as e:
            logger.error(f"Error getting project by id: {e}")
            raise
    
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
    
    async def _log_change(
        self,
        object_id: str,
        user_id: int,
        action: str,
        details: Dict[str, Any]
    ) -> None:
        """Логирование изменений"""
        try:
            log_manager = self.context.log_manager
            await log_manager.log_installation_change(
                object_id=object_id,
                user_id=user_id,
                action=action,
                details=details
            )
        except Exception as e:
            logger.error(f"Error logging project change: {e}")