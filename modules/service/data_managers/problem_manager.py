"""
Менеджер для управления проблемами объектов обслуживания.
Реализует добавление, удаление, редактирование проблем с прикреплением файлов.
"""
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import structlog

from core.context import AppContext
from storage.models.service import Problem, ServiceObject
from storage.repositories.service_repository import ServiceRepository
from utils.date_utils import format_date
from modules.file.archive_manager import ArchiveManager


logger = structlog.get_logger(__name__)


class ProblemManager:
    """Менеджер для управления проблемами объектов обслуживания."""
    
    def __init__(self, context: AppContext):
        self.context = context
        self.service_repository: Optional[ServiceRepository] = None
        self.archive_manager: Optional[ArchiveManager] = None
    
    async def initialize(self) -> None:
        """Инициализирует менеджер проблем."""
        self.service_repository = ServiceRepository(self.context.db_session)
        self.archive_manager = ArchiveManager(self.context)
        logger.info("ProblemManager initialized")
    
    async def add_problem(
        self,
        object_id: str,
        user_id: int,
        user_name: str,
        problem_text: str,
        file_id: Optional[str] = None,
        file_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Добавляет проблему к объекту обслуживания.
        
        Args:
            object_id: ID объекта обслуживания
            user_id: ID пользователя
            user_name: Имя пользователя
            problem_text: Текст проблемы
            file_id: ID файла в Telegram (опционально)
            file_name: Имя файла (опционально)
            
        Returns:
            Dict с информацией о созданной проблеме
        """
        try:
            # Проверяем существование объекта
            object_info = await self.service_repository.get_object_by_id(object_id)
            if not object_info:
                return {
                    'success': False,
                    'error': 'Объект не найден'
                }
            
            # Получаем следующий номер проблемы для этого объекта
            problem_number = await self._get_next_problem_number(object_id)
            
            # Создаем запись проблемы
            problem = Problem(
                object_id=object_id,
                problem_number=problem_number,
                description=problem_text,
                status='open',
                reported_by_id=user_id,
                reported_by_name=user_name,
                reported_at=datetime.now(),
                has_file=file_id is not None,
                file_id=file_id,
                file_name=file_name
            )
            
            # Сохраняем в БД
            saved_problem = await self.service_repository.create_problem(problem)
            
            # Если есть файл, сохраняем его в архив
            if file_id and self.archive_manager:
                await self.archive_manager.save_file_to_archive(
                    file_id=file_id,
                    file_name=file_name or f"problem_{saved_problem.id}.file",
                    file_type='other',
                    user_id=user_id,
                    metadata={
                        'problem_id': str(saved_problem.id),
                        'object_id': object_id,
                        'object_name': object_info.short_name,
                        'problem_number': problem_number
                    }
                )
            
            # Логируем создание проблемы
            await self.context.log_manager.log_change(
                user_id=user_id,
                user_name=user_name,
                entity_type='problem',
                entity_id=str(saved_problem.id),
                entity_name=f"Проблема {problem_number}",
                action='create',
                changes={
                    'description': {'new': problem_text},
                    'status': {'new': 'open'}
                }
            )
            
            return {
                'success': True,
                'problem_id': str(saved_problem.id),
                'problem_number': problem_number,
                'object_name': object_info.short_name,
                'timestamp': saved_problem.reported_at
            }
            
        except Exception as e:
            logger.error("Failed to add problem", error=str(e), object_id=object_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_problems(
        self,
        object_id: str,
        page: int = 0,
        limit: int = 10,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Получает список проблем объекта с пагинацией.
        
        Args:
            object_id: ID объекта обслуживания
            page: Номер страницы (начиная с 0)
            limit: Количество записей на страницу
            status: Фильтр по статусу (open, resolved, all)
            
        Returns:
            Dict с проблемами и информацией о пагинации
        """
        try:
            # Получаем проблемы из БД
            problems = await self.service_repository.get_problems(
                object_id=object_id,
                skip=page * limit,
                limit=limit,
                status=status
            )
            
            # Получаем общее количество
            total = await self.service_repository.count_problems(object_id, status)
            
            # Форматируем проблемы для отображения
            formatted_problems = []
            for problem in problems:
                formatted_problems.append({
                    'id': str(problem.id),
                    'number': problem.problem_number,
                    'description': problem.description,
                    'status': problem.status,
                    'reported_by': problem.reported_by_name,
                    'reported_at': problem.reported_at,
                    'resolved_at': problem.resolved_at,
                    'resolved_by': problem.resolved_by_name,
                    'has_file': problem.has_file,
                    'file_name': problem.file_name
                })
            
            return {
                'success': True,
                'problems': formatted_problems,
                'total': total,
                'page': page,
                'limit': limit,
                'total_pages': (total + limit - 1) // limit
            }
            
        except Exception as e:
            logger.error("Failed to get problems", error=str(e), object_id=object_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def update_problem(
        self,
        problem_id: str,
        user_id: int,
        user_name: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Редактирует проблему.
        
        Args:
            problem_id: ID проблемы
            user_id: ID пользователя
            user_name: Имя пользователя
            updates: Словарь обновлений
            
        Returns:
            Dict с результатом обновления
        """
        try:
            # Получаем текущую проблему
            problem = await self.service_repository.get_problem_by_id(problem_id)
            if not problem:
                return {
                    'success': False,
                    'error': 'Проблема не найдена'
                }
            
            # Проверяем права доступа (только автор или админ)
            if problem.reported_by_id != user_id:
                from modules.admin.admin_manager import AdminManager
                admin_manager = AdminManager(self.context)
                user_role = await admin_manager.get_user_role(user_id)
                if user_role not in ['main_admin', 'admin']:
                    return {
                        'success': False,
                        'error': 'Нет прав для редактирования этой проблемы'
                    }
            
            # Подготавливаем изменения для логирования
            changes = {}
            old_values = {}
            
            # Проверяем каждое обновляемое поле
            if 'description' in updates and updates['description'] != problem.description:
                changes['description'] = {
                    'old': problem.description,
                    'new': updates['description']
                }
                old_values['description'] = problem.description
                problem.description = updates['description']
            
            if 'status' in updates and updates['status'] != problem.status:
                changes['status'] = {
                    'old': problem.status,
                    'new': updates['status']
                }
                old_values['status'] = problem.status
                problem.status = updates['status']
                
                # Если статус изменен на resolved, обновляем дату решения
                if updates['status'] == 'resolved' and not problem.resolved_at:
                    problem.resolved_at = datetime.now()
                    problem.resolved_by_id = user_id
                    problem.resolved_by_name = user_name
            
            # Сохраняем изменения
            updated_problem = await self.service_repository.update_problem(problem)
            
            # Логируем изменения если они были
            if changes:
                await self.context.log_manager.log_change(
                    user_id=user_id,
                    user_name=user_name,
                    entity_type='problem',
                    entity_id=problem_id,
                    entity_name=f"Проблема {problem.problem_number}",
                    action='update',
                    changes=changes
                )
            
            return {
                'success': True,
                'problem_id': problem_id,
                'updated_fields': list(changes.keys())
            }
            
        except Exception as e:
            logger.error("Failed to update problem", error=str(e), problem_id=problem_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def delete_problem(
        self,
        problem_id: str,
        user_id: int,
        user_name: str
    ) -> Dict[str, Any]:
        """
        Удаляет проблему.
        
        Args:
            problem_id: ID проблемы
            user_id: ID пользователя
            user_name: Имя пользователя
            
        Returns:
            Dict с результатом удаления
        """
        try:
            # Получаем проблему
            problem = await self.service_repository.get_problem_by_id(problem_id)
            if not problem:
                return {
                    'success': False,
                    'error': 'Проблема не найдена'
                }
            
            # Проверяем права доступа (только автор или админ)
            if problem.reported_by_id != user_id:
                from modules.admin.admin_manager import AdminManager
                admin_manager = AdminManager(self.context)
                user_role = await admin_manager.get_user_role(user_id)
                if user_role not in ['main_admin', 'admin']:
                    return {
                        'success': False,
                        'error': 'Нет прав для удаления этой проблемы'
                    }
            
            # Сохраняем информацию для архива
            problem_info = {
                'id': str(problem.id),
                'number': problem.problem_number,
                'description': problem.description,
                'object_id': problem.object_id,
                'reported_by': problem.reported_by_name,
                'reported_at': problem.reported_at,
                'deleted_by': user_name,
                'deleted_at': datetime.now()
            }
            
            # Удаляем проблему
            deleted = await self.service_repository.delete_problem(problem_id)
            
            if deleted:
                # Логируем удаление
                await self.context.log_manager.log_change(
                    user_id=user_id,
                    user_name=user_name,
                    entity_type='problem',
                    entity_id=problem_id,
                    entity_name=f"Проблема {problem.problem_number}",
                    action='delete',
                    changes={'problem': {'old': problem_info, 'new': None}}
                )
                
                return {
                    'success': True,
                    'problem_id': problem_id,
                    'problem_number': problem.problem_number
                }
            else:
                return {
                    'success': False,
                    'error': 'Не удалось удалить проблему'
                }
            
        except Exception as e:
            logger.error("Failed to delete problem", error=str(e), problem_id=problem_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def mark_as_resolved(
        self,
        problem_id: str,
        user_id: int,
        user_name: str,
        solution_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Отмечает проблему как решенную.
        
        Args:
            problem_id: ID проблемы
            user_id: ID пользователя
            user_name: Имя пользователя
            solution_text: Текст решения (опционально)
            
        Returns:
            Dict с результатом
        """
        try:
            # Получаем проблему
            problem = await self.service_repository.get_problem_by_id(problem_id)
            if not problem:
                return {
                    'success': False,
                    'error': 'Проблема не найдена'
                }
            
            # Проверяем что проблема еще не решена
            if problem.status == 'resolved':
                return {
                    'success': False,
                    'error': 'Проблема уже решена'
                }
            
            # Обновляем статус
            problem.status = 'resolved'
            problem.resolved_at = datetime.now()
            problem.resolved_by_id = user_id
            problem.resolved_by_name = user_name
            
            if solution_text:
                problem.solution = solution_text
            
            # Сохраняем изменения
            updated_problem = await self.service_repository.update_problem(problem)
            
            # Логируем изменение
            changes = {
                'status': {
                    'old': 'open',
                    'new': 'resolved'
                }
            }
            
            if solution_text:
                changes['solution'] = {
                    'old': None,
                    'new': solution_text
                }
            
            await self.context.log_manager.log_change(
                user_id=user_id,
                user_name=user_name,
                entity_type='problem',
                entity_id=problem_id,
                entity_name=f"Проблема {problem.problem_number}",
                action='update',
                changes=changes
            )
            
            return {
                'success': True,
                'problem_id': problem_id,
                'resolved_at': updated_problem.resolved_at,
                'resolved_by': user_name
            }
            
        except Exception as e:
            logger.error("Failed to mark problem as resolved", error=str(e), problem_id=problem_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def attach_file_to_problem(
        self,
        problem_id: str,
        user_id: int,
        user_name: str,
        file_id: str,
        file_name: str
    ) -> Dict[str, Any]:
        """
        Прикрепляет файл к проблеме.
        
        Args:
            problem_id: ID проблемы
            user_id: ID пользователя
            user_name: Имя пользователя
            file_id: ID файла в Telegram
            file_name: Имя файла
            
        Returns:
            Dict с результатом
        """
        try:
            # Получаем проблему
            problem = await self.service_repository.get_problem_by_id(problem_id)
            if not problem:
                return {
                    'success': False,
                    'error': 'Проблема не найдена'
                }
            
            # Проверяем права доступа
            if problem.reported_by_id != user_id:
                from modules.admin.admin_manager import AdminManager
                admin_manager = AdminManager(self.context)
                user_role = await admin_manager.get_user_role(user_id)
                if user_role not in ['main_admin', 'admin']:
                    return {
                        'success': False,
                        'error': 'Нет прав для изменения этой проблемы'
                    }
            
            # Сохраняем файл в архив
            if self.archive_manager:
                await self.archive_manager.save_file_to_archive(
                    file_id=file_id,
                    file_name=file_name,
                    file_type='other',
                    user_id=user_id,
                    metadata={
                        'problem_id': problem_id,
                        'problem_number': problem.problem_number,
                        'object_id': problem.object_id
                    }
                )
            
            # Обновляем проблему
            problem.has_file = True
            problem.file_id = file_id
            problem.file_name = file_name
            
            updated_problem = await self.service_repository.update_problem(problem)
            
            # Логируем прикрепление файла
            await self.context.log_manager.log_change(
                user_id=user_id,
                user_name=user_name,
                entity_type='problem',
                entity_id=problem_id,
                entity_name=f"Проблема {problem.problem_number}",
                action='update',
                changes={
                    'file': {
                        'old': None,
                        'new': file_name
                    }
                }
            )
            
            return {
                'success': True,
                'problem_id': problem_id,
                'file_name': file_name
            }
            
        except Exception as e:
            logger.error("Failed to attach file to problem", error=str(e), problem_id=problem_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_problem_details(self, problem_id: str) -> Dict[str, Any]:
        """
        Получает детальную информацию о проблеме.
        
        Args:
            problem_id: ID проблемы
            
        Returns:
            Dict с детальной информацией о проблеме
        """
        try:
            problem = await self.service_repository.get_problem_by_id(problem_id)
            if not problem:
                return {
                    'success': False,
                    'error': 'Проблема не найдена'
                }
            
            # Получаем информацию об объекте
            object_info = await self.service_repository.get_object_by_id(problem.object_id)
            
            problem_details = {
                'id': str(problem.id),
                'number': problem.problem_number,
                'description': problem.description,
                'status': problem.status,
                'solution': problem.solution,
                'reported_by': problem.reported_by_name,
                'reported_at': problem.reported_at,
                'resolved_by': problem.resolved_by_name,
                'resolved_at': problem.resolved_at,
                'has_file': problem.has_file,
                'file_name': problem.file_name,
                'file_id': problem.file_id,
                'object_id': problem.object_id,
                'object_name': object_info.short_name if object_info else 'Неизвестно',
                'object_full_name': object_info.full_name if object_info else 'Неизвестно'
            }
            
            return {
                'success': True,
                'problem': problem_details
            }
            
        except Exception as e:
            logger.error("Failed to get problem details", error=str(e), problem_id=problem_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _get_next_problem_number(self, object_id: str) -> int:
        """Получает следующий номер проблемы для объекта."""
        try:
            last_problem = await self.service_repository.get_last_problem_number(object_id)
            return (last_problem or 0) + 1
        except Exception as e:
            logger.error("Failed to get next problem number", error=str(e), object_id=object_id)
            return 1
    
    async def check_access(self, user_id: int, problem_id: str) -> bool:
        """
        Проверяет доступ пользователя к проблеме.
        
        Args:
            user_id: ID пользователя
            problem_id: ID проблемы
            
        Returns:
            bool: True если есть доступ
        """
        try:
            problem = await self.service_repository.get_problem_by_id(problem_id)
            if not problem:
                return False
            
            # Автор проблемы имеет доступ
            if problem.reported_by_id == user_id:
                return True
            
            # Проверяем права администратора
            from modules.admin.admin_manager import AdminManager
            admin_manager = AdminManager(self.context)
            user_role = await admin_manager.get_user_role(user_id)
            
            return user_role in ['main_admin', 'admin']
            
        except Exception as e:
            logger.error("Failed to check problem access", error=str(e))
            return False