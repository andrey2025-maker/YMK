"""
Менеджер для управления допусками объектов обслуживания.
Реализует учет разрешительной документации с номерами, датами и файлами.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
import structlog

from core.context import AppContext
from storage.models.service import Permit, ServiceObject
from storage.repositories.service_repository import ServiceRepository
from utils.date_utils import parse_date, format_date
from modules.file.archive_manager import ArchiveManager


logger = structlog.get_logger(__name__)


class PermitManager:
    """Менеджер для управления допусками объектов обслуживания."""
    
    def __init__(self, context: AppContext):
        self.context = context
        self.service_repository: Optional[ServiceRepository] = None
        self.archive_manager: Optional[ArchiveManager] = None
    
    async def initialize(self) -> None:
        """Инициализирует менеджер допусков."""
        self.service_repository = ServiceRepository(self.context.db_session)
        self.archive_manager = ArchiveManager(self.context)
        logger.info("PermitManager initialized")
    
    async def add_permit(
        self,
        object_id: str,
        user_id: int,
        user_name: str,
        permit_number: str,
        permit_date: str,
        description: str,
        expiry_date: Optional[str] = None,
        file_id: Optional[str] = None,
        file_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Добавляет допуск к объекту обслуживания.
        
        Args:
            object_id: ID объекта обслуживания
            user_id: ID пользователя
            user_name: Имя пользователя
            permit_number: Номер допуска
            permit_date: Дата допуска (формат: ДД.ММ.ГГГГ)
            description: Описание допуска
            expiry_date: Дата окончания действия (формат: ДД.ММ.ГГГГ, опционально)
            file_id: ID файла в Telegram (опционально)
            file_name: Имя файла (опционально)
            
        Returns:
            Dict с информацией о созданном допуске
        """
        try:
            # Проверяем существование объекта
            object_info = await self.service_repository.get_object_by_id(object_id)
            if not object_info:
                return {
                    'success': False,
                    'error': 'Объект не найден'
                }
            
            # Парсим дату допуска
            parsed_date = parse_date(permit_date)
            if not parsed_date:
                return {
                    'success': False,
                    'error': 'Неверный формат даты допуска. Используйте ДД.ММ.ГГГГ'
                }
            
            # Парсим дату окончания если указана
            parsed_expiry_date = None
            if expiry_date:
                parsed_expiry_date = parse_date(expiry_date)
                if not parsed_expiry_date:
                    return {
                        'success': False,
                        'error': 'Неверный формат даты окончания. Используйте ДД.ММ.ГГГГ'
                    }
            
            # Проверяем уникальность номера допуска для объекта
            existing_permit = await self.service_repository.get_permit_by_number(object_id, permit_number)
            if existing_permit:
                return {
                    'success': False,
                    'error': f'Допуск с номером {permit_number} уже существует для этого объекта'
                }
            
            # Создаем запись допуска
            permit = Permit(
                object_id=object_id,
                permit_number=permit_number,
                permit_date=parsed_date,
                expiry_date=parsed_expiry_date,
                description=description,
                status='active',
                has_file=file_id is not None,
                file_id=file_id,
                file_name=file_name,
                added_by_id=user_id,
                added_by_name=user_name,
                added_at=datetime.now()
            )
            
            # Сохраняем в БД
            saved_permit = await self.service_repository.create_permit(permit)
            
            # Если есть файл, сохраняем его в архив
            if file_id and self.archive_manager:
                await self.archive_manager.save_file_to_archive(
                    file_id=file_id,
                    file_name=file_name or f"permit_{saved_permit.id}.file",
                    file_type='other',
                    user_id=user_id,
                    metadata={
                        'permit_id': str(saved_permit.id),
                        'object_id': object_id,
                        'object_name': object_info.short_name,
                        'permit_number': permit_number,
                        'permit_date': permit_date,
                        'expiry_date': expiry_date
                    }
                )
            
            # Создаем напоминание об истечении срока если указана дата окончания
            if parsed_expiry_date:
                await self._create_expiry_reminder(saved_permit, object_info, user_id)
            
            # Логируем создание допуска
            await self.context.log_manager.log_change(
                user_id=user_id,
                user_name=user_name,
                entity_type='permit',
                entity_id=str(saved_permit.id),
                entity_name=f"Допуск {permit_number}",
                action='create',
                changes={
                    'permit_number': {'new': permit_number},
                    'permit_date': {'new': permit_date},
                    'expiry_date': {'new': expiry_date} if expiry_date else {'new': 'Не указана'},
                    'description': {'new': description}
                }
            )
            
            return {
                'success': True,
                'permit_id': str(saved_permit.id),
                'permit_number': permit_number,
                'permit_date': permit_date,
                'expiry_date': expiry_date,
                'object_name': object_info.short_name,
                'timestamp': saved_permit.added_at
            }
            
        except Exception as e:
            logger.error("Failed to add permit", error=str(e), object_id=object_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_permits(
        self,
        object_id: str,
        page: int = 0,
        limit: int = 10,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Получает список допусков объекта с пагинацией.
        
        Args:
            object_id: ID объекта обслуживания
            page: Номер страницы (начиная с 0)
            limit: Количество записей на страницу
            status: Фильтр по статусу (active, expired, all)
            
        Returns:
            Dict с допусками и информацией о пагинации
        """
        try:
            # Получаем допуски из БД
            permits = await self.service_repository.get_permits(
                object_id=object_id,
                skip=page * limit,
                limit=limit,
                status=status
            )
            
            # Получаем общее количество
            total = await self.service_repository.count_permits(object_id, status)
            
            # Форматируем допуски для отображения
            formatted_permits = []
            for permit in permits:
                # Определяем статус
                current_status = permit.status
                if current_status == 'active' and permit.expiry_date:
                    if permit.expiry_date < datetime.now().date():
                        current_status = 'expired'
                    elif (permit.expiry_date - datetime.now().date()).days <= 30:
                        current_status = 'expiring_soon'
                
                formatted_permits.append({
                    'id': str(permit.id),
                    'permit_number': permit.permit_number,
                    'permit_date': permit.permit_date,
                    'formatted_date': format_date(permit.permit_date),
                    'expiry_date': permit.expiry_date,
                    'formatted_expiry_date': format_date(permit.expiry_date) if permit.expiry_date else 'Бессрочно',
                    'description': permit.description,
                    'status': current_status,
                    'has_file': permit.has_file,
                    'file_name': permit.file_name,
                    'added_by': permit.added_by_name,
                    'added_at': permit.added_at
                })
            
            return {
                'success': True,
                'permits': formatted_permits,
                'total': total,
                'page': page,
                'limit': limit,
                'total_pages': (total + limit - 1) // limit,
                'status': status
            }
            
        except Exception as e:
            logger.error("Failed to get permits", error=str(e), object_id=object_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def update_permit(
        self,
        permit_id: str,
        user_id: int,
        user_name: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Редактирует допуск.
        
        Args:
            permit_id: ID допуска
            user_id: ID пользователя
            user_name: Имя пользователя
            updates: Словарь обновлений
            
        Returns:
            Dict с результатом обновления
        """
        try:
            # Получаем текущий допуск
            permit = await self.service_repository.get_permit_by_id(permit_id)
            if not permit:
                return {
                    'success': False,
                    'error': 'Допуск не найдено'
                }
            
            # Проверяем права доступа
            from modules.admin.admin_manager import AdminManager
            admin_manager = AdminManager(self.context)
            user_role = await admin_manager.get_user_role(user_id)
            if user_role not in ['main_admin', 'admin']:
                return {
                    'success': False,
                    'error': 'Нет прав для редактирования допуска'
                }
            
            # Получаем информацию об объекте
            object_info = await self.service_repository.get_object_by_id(permit.object_id)
            
            # Подготавливаем изменения для логирования
            changes = {}
            
            # Проверяем каждое обновляемое поле
            if 'permit_number' in updates and updates['permit_number'] != permit.permit_number:
                # Проверяем уникальность нового номера
                existing_permit = await self.service_repository.get_permit_by_number(
                    permit.object_id, 
                    updates['permit_number']
                )
                if existing_permit and str(existing_permit.id) != permit_id:
                    return {
                        'success': False,
                        'error': f'Допуск с номером {updates["permit_number"]} уже существует для этого объекта'
                    }
                
                changes['permit_number'] = {
                    'old': permit.permit_number,
                    'new': updates['permit_number']
                }
                permit.permit_number = updates['permit_number']
            
            if 'permit_date' in updates:
                parsed_date = parse_date(updates['permit_date'])
                if not parsed_date:
                    return {
                        'success': False,
                        'error': 'Неверный формат даты допуска. Используйте ДД.ММ.ГГГГ'
                    }
                
                if parsed_date != permit.permit_date:
                    changes['permit_date'] = {
                        'old': format_date(permit.permit_date),
                        'new': updates['permit_date']
                    }
                    permit.permit_date = parsed_date
            
            if 'expiry_date' in updates:
                if updates['expiry_date']:
                    parsed_expiry_date = parse_date(updates['expiry_date'])
                    if not parsed_expiry_date:
                        return {
                            'success': False,
                            'error': 'Неверный формат даты окончания. Используйте ДД.ММ.ГГГГ'
                        }
                    
                    if parsed_expiry_date != permit.expiry_date:
                        changes['expiry_date'] = {
                            'old': format_date(permit.expiry_date) if permit.expiry_date else 'Не указана',
                            'new': updates['expiry_date']
                        }
                        permit.expiry_date = parsed_expiry_date
                else:
                    changes['expiry_date'] = {
                        'old': format_date(permit.expiry_date) if permit.expiry_date else 'Не указана',
                        'new': 'Не указана'
                    }
                    permit.expiry_date = None
            
            if 'description' in updates and updates['description'] != permit.description:
                changes['description'] = {
                    'old': permit.description,
                    'new': updates['description']
                }
                permit.description = updates['description']
            
            if 'status' in updates and updates['status'] != permit.status:
                changes['status'] = {
                    'old': permit.status,
                    'new': updates['status']
                }
                permit.status = updates['status']
            
            # Сохраняем изменения
            updated_permit = await self.service_repository.update_permit(permit)
            
            # Обновляем напоминание об истечении срока если изменилась дата окончания
            if 'expiry_date' in changes and permit.expiry_date:
                await self._update_expiry_reminder(permit, object_info, user_id)
            
            # Логируем изменения если они были
            if changes:
                await self.context.log_manager.log_change(
                    user_id=user_id,
                    user_name=user_name,
                    entity_type='permit',
                    entity_id=permit_id,
                    entity_name=f"Допуск {permit.permit_number}",
                    action='update',
                    changes=changes
                )
            
            return {
                'success': True,
                'permit_id': permit_id,
                'updated_fields': list(changes.keys())
            }
            
        except Exception as e:
            logger.error("Failed to update permit", error=str(e), permit_id=permit_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def delete_permit(
        self,
        permit_id: str,
        user_id: int,
        user_name: str
    ) -> Dict[str, Any]:
        """
        Удаляет допуск.
        
        Args:
            permit_id: ID допуска
            user_id: ID пользователя
            user_name: Имя пользователя
            
        Returns:
            Dict с результатом удаления
        """
        try:
            # Получаем допуск
            permit = await self.service_repository.get_permit_by_id(permit_id)
            if not permit:
                return {
                    'success': False,
                    'error': 'Допуск не найден'
                }
            
            # Проверяем права доступа
            from modules.admin.admin_manager import AdminManager
            admin_manager = AdminManager(self.context)
            user_role = await admin_manager.get_user_role(user_id)
            if user_role not in ['main_admin', 'admin']:
                return {
                    'success': False,
                    'error': 'Нет прав для удаления допуска'
                }
            
            # Сохраняем информацию для архива
            permit_info = {
                'id': str(permit.id),
                'permit_number': permit.permit_number,
                'permit_date': format_date(permit.permit_date),
                'expiry_date': format_date(permit.expiry_date) if permit.expiry_date else None,
                'description': permit.description,
                'object_id': permit.object_id,
                'added_by': permit.added_by_name,
                'added_at': permit.added_at,
                'deleted_by': user_name,
                'deleted_at': datetime.now()
            }
            
            # Удаляем допуск
            deleted = await self.service_repository.delete_permit(permit_id)
            
            if deleted:
                # Удаляем связанное напоминание
                await self._delete_expiry_reminder(permit_id)
                
                # Логируем удаление
                await self.context.log_manager.log_change(
                    user_id=user_id,
                    user_name=user_name,
                    entity_type='permit',
                    entity_id=permit_id,
                    entity_name=f"Допуск {permit.permit_number}",
                    action='delete',
                    changes={'permit': {'old': permit_info, 'new': None}}
                )
                
                return {
                    'success': True,
                    'permit_id': permit_id,
                    'permit_number': permit.permit_number
                }
            else:
                return {
                    'success': False,
                    'error': 'Не удалось удалить допуск'
                }
            
        except Exception as e:
            logger.error("Failed to delete permit", error=str(e), permit_id=permit_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def check_permit_expiry(self, permit_id: str) -> Dict[str, Any]:
        """
        Проверяет срок действия допуска.
        
        Args:
            permit_id: ID допуска
            
        Returns:
            Dict с информацией о сроке действия
        """
        try:
            permit = await self.service_repository.get_permit_by_id(permit_id)
            if not permit:
                return {
                    'success': False,
                    'error': 'Допуск не найден'
                }
            
            if not permit.expiry_date:
                return {
                    'success': True,
                    'permit_number': permit.permit_number,
                    'expiry_date': None,
                    'status': 'active',
                    'days_until_expiry': None,
                    'is_expired': False,
                    'is_expiring_soon': False
                }
            
            today = datetime.now().date()
            expiry_date = permit.expiry_date
            days_until_expiry = (expiry_date - today).days
            
            is_expired = days_until_expiry < 0
            is_expiring_soon = 0 <= days_until_expiry <= 30
            
            status = 'expired' if is_expired else 'expiring_soon' if is_expiring_soon else 'active'
            
            # Обновляем статус в БД если изменился
            if permit.status != status:
                permit.status = status
                await self.service_repository.update_permit(permit)
            
            return {
                'success': True,
                'permit_number': permit.permit_number,
                'expiry_date': format_date(expiry_date),
                'status': status,
                'days_until_expiry': days_until_expiry,
                'is_expired': is_expired,
                'is_expiring_soon': is_expiring_soon
            }
            
        except Exception as e:
            logger.error("Failed to check permit expiry", error=str(e), permit_id=permit_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_expiring_permits(
        self,
        object_id: Optional[str] = None,
        days_threshold: int = 30
    ) -> Dict[str, Any]:
        """
        Получает истекающие допуски.
        
        Args:
            object_id: ID объекта (опционально)
            days_threshold: Порог дней до истечения
            
        Returns:
            Dict с истекающими допусками
        """
        try:
            # Получаем истекающие допуски
            expiring_permits = await self.service_repository.get_expiring_permits(
                object_id=object_id,
                days_threshold=days_threshold
            )
            
            # Форматируем результат
            formatted_permits = []
            for permit in expiring_permits:
                # Получаем информацию об объекте
                object_info = await self.service_repository.get_object_by_id(permit.object_id)
                
                today = datetime.now().date()
                days_until_expiry = (permit.expiry_date - today).days if permit.expiry_date else None
                
                formatted_permits.append({
                    'id': str(permit.id),
                    'permit_number': permit.permit_number,
                    'permit_date': format_date(permit.permit_date),
                    'expiry_date': format_date(permit.expiry_date) if permit.expiry_date else 'Бессрочно',
                    'description': permit.description,
                    'object_id': permit.object_id,
                    'object_name': object_info.short_name if object_info else 'Неизвестно',
                    'days_until_expiry': days_until_expiry,
                    'is_expired': days_until_expiry is not None and days_until_expiry < 0,
                    'is_expiring_soon': days_until_expiry is not None and 0 <= days_until_expiry <= days_threshold
                })
            
            # Группируем по статусу
            expired = [p for p in formatted_permits if p['is_expired']]
            expiring_soon = [p for p in formatted_permits if p['is_expiring_soon'] and not p['is_expired']]
            
            return {
                'success': True,
                'permits': formatted_permits,
                'expired': expired,
                'expiring_soon': expiring_soon,
                'total_expired': len(expired),
                'total_expiring_soon': len(expiring_soon),
                'total': len(formatted_permits),
                'days_threshold': days_threshold
            }
            
        except Exception as e:
            logger.error("Failed to get expiring permits", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    async def attach_file_to_permit(
        self,
        permit_id: str,
        user_id: int,
        user_name: str,
        file_id: str,
        file_name: str
    ) -> Dict[str, Any]:
        """
        Прикрепляет файл к допуску.
        
        Args:
            permit_id: ID допуска
            user_id: ID пользователя
            user_name: Имя пользователя
            file_id: ID файла в Telegram
            file_name: Имя файла
            
        Returns:
            Dict с результатом
        """
        try:
            # Получаем допуск
            permit = await self.service_repository.get_permit_by_id(permit_id)
            if not permit:
                return {
                    'success': False,
                    'error': 'Допуск не найден'
                }
            
            # Проверяем права доступа
            from modules.admin.admin_manager import AdminManager
            admin_manager = AdminManager(self.context)
            user_role = await admin_manager.get_user_role(user_id)
            if user_role not in ['main_admin', 'admin']:
                return {
                    'success': False,
                    'error': 'Нет прав для изменения допуска'
                }
            
            # Сохраняем файл в архив
            if self.archive_manager:
                # Получаем информацию об объекте
                object_info = await self.service_repository.get_object_by_id(permit.object_id)
                
                await self.archive_manager.save_file_to_archive(
                    file_id=file_id,
                    file_name=file_name,
                    file_type='other',
                    user_id=user_id,
                    metadata={
                        'permit_id': permit_id,
                        'permit_number': permit.permit_number,
                        'object_id': permit.object_id,
                        'object_name': object_info.short_name if object_info else 'Неизвестно'
                    }
                )
            
            # Обновляем допуск
            permit.has_file = True
            permit.file_id = file_id
            permit.file_name = file_name
            
            updated_permit = await self.service_repository.update_permit(permit)
            
            # Логируем прикрепление файла
            await self.context.log_manager.log_change(
                user_id=user_id,
                user_name=user_name,
                entity_type='permit',
                entity_id=permit_id,
                entity_name=f"Допуск {permit.permit_number}",
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
                'permit_id': permit_id,
                'file_name': file_name
            }
            
        except Exception as e:
            logger.error("Failed to attach file to permit", error=str(e), permit_id=permit_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _create_expiry_reminder(
        self,
        permit: Permit,
        object_info: ServiceObject,
        user_id: int
    ) -> None:
        """Создает напоминание об истечении срока допуска."""
        try:
            if not permit.expiry_date:
                return
            
            from services.reminder_service import ReminderService
            reminder_service = ReminderService(self.context)
            
            # Создаем напоминание за 7 дней и за 1 день до истечения
            reminder_text = f"Истекает срок допуска: {permit.permit_number} ({object_info.short_name})"
            
            # Напоминание за 7 дней
            reminder_date_7 = permit.expiry_date - timedelta(days=7)
            if reminder_date_7 > datetime.now().date():
                await reminder_service.create_reminder(
                    user_id=user_id,
                    object_type='service',
                    object_id=permit.object_id,
                    object_name=object_info.short_name,
                    reminder_date=reminder_date_7,
                    reminder_text=f"Через 7 дней: {reminder_text}",
                    notify_before_days=[1]
                )
            
            # Напоминание за 1 день
            reminder_date_1 = permit.expiry_date - timedelta(days=1)
            if reminder_date_1 > datetime.now().date():
                await reminder_service.create_reminder(
                    user_id=user_id,
                    object_type='service',
                    object_id=permit.object_id,
                    object_name=object_info.short_name,
                    reminder_date=reminder_date_1,
                    reminder_text=f"Завтра: {reminder_text}",
                    notify_before_days=[0]
                )
            
        except Exception as e:
            logger.error("Failed to create expiry reminder", error=str(e))
    
    async def _update_expiry_reminder(
        self,
        permit: Permit,
        object_info: ServiceObject,
        user_id: int
    ) -> None:
        """Обновляет напоминание об истечении срока допуска."""
        try:
            # Удаляем старые напоминания
            await self._delete_expiry_reminder(str(permit.id))
            
            # Создаем новые напоминания
            await self._create_expiry_reminder(permit, object_info, user_id)
            
        except Exception as e:
            logger.error("Failed to update expiry reminder", error=str(e))
    
    async def _delete_expiry_reminder(self, permit_id: str) -> None:
        """Удаляет напоминание об истечении срока допуска."""
        try:
            from services.reminder_service import ReminderService
            reminder_service = ReminderService(self.context)
            
            # Здесь нужно реализовать поиск и удаление напоминаний для этого допуска
            # В реальной реализации нужно хранить связь между допуском и напоминанием
            pass
            
        except Exception as e:
            logger.error("Failed to delete expiry reminder", error=str(e))