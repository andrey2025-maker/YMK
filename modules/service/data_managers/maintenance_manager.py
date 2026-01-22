"""
Менеджер для управления техническим обслуживанием (ТО).
Реализует добавление, удаление ТО с настройкой частоты и месяцев выполнения.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, date
import structlog

from core.context import AppContext
from storage.models.service import Maintenance, ServiceObject
from storage.repositories.service_repository import ServiceRepository
from utils.date_utils import format_date
from services.reminder_service import ReminderService


logger = structlog.get_logger(__name__)


class MaintenanceManager:
    """Менеджер для управления техническим обслуживанием."""
    
    def __init__(self, context: AppContext):
        self.context = context
        self.service_repository: Optional[ServiceRepository] = None
        self.reminder_service: Optional[ReminderService] = None
    
    async def initialize(self) -> None:
        """Инициализирует менеджер ТО."""
        self.service_repository = ServiceRepository(self.context.db_session)
        self.reminder_service = ReminderService(self.context)
        logger.info("MaintenanceManager initialized")
    
    async def add_maintenance(
        self,
        object_id: str,
        user_id: int,
        user_name: str,
        description: str,
        frequency: str,
        months: List[int],
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Добавляет ТО к объекту обслуживания.
        
        Args:
            object_id: ID объекта обслуживания
            user_id: ID пользователя
            user_name: Имя пользователя
            description: Описание ТО
            frequency: Частота выполнения (weekly, monthly, quarterly, yearly, custom)
            months: Список месяцев выполнения (1-12)
            notes: Дополнительные примечания
            
        Returns:
            Dict с информацией о созданном ТО
        """
        try:
            # Проверяем существование объекта
            object_info = await self.service_repository.get_object_by_id(object_id)
            if not object_info:
                return {
                    'success': False,
                    'error': 'Объект не найден'
                }
            
            # Валидируем частоту
            valid_frequencies = ['weekly', 'monthly', 'quarterly', 'yearly', 'custom']
            if frequency not in valid_frequencies:
                return {
                    'success': False,
                    'error': f'Недопустимая частота. Допустимые значения: {", ".join(valid_frequencies)}'
                }
            
            # Валидируем месяцы
            if not months:
                return {
                    'success': False,
                    'error': 'Не указаны месяцы выполнения'
                }
            
            for month in months:
                if month < 1 or month > 12:
                    return {
                        'success': False,
                        'error': f'Недопустимый месяц: {month}. Допустимы значения от 1 до 12'
                    }
            
            # Создаем запись ТО
            maintenance = Maintenance(
                object_id=object_id,
                description=description,
                frequency=frequency,
                months=months,
                notes=notes or '',
                created_by_id=user_id,
                created_by_name=user_name,
                created_at=datetime.now(),
                is_active=True
            )
            
            # Сохраняем в БД
            saved_maintenance = await self.service_repository.create_maintenance(maintenance)
            
            # Создаем напоминания для ТО
            await self._create_reminders_for_maintenance(saved_maintenance, object_info)
            
            # Логируем создание ТО
            await self.context.log_manager.log_change(
                user_id=user_id,
                user_name=user_name,
                entity_type='maintenance',
                entity_id=str(saved_maintenance.id),
                entity_name=f"ТО: {description[:50]}...",
                action='create',
                changes={
                    'description': {'new': description},
                    'frequency': {'new': frequency},
                    'months': {'new': str(months)},
                    'notes': {'new': notes or ''}
                }
            )
            
            return {
                'success': True,
                'maintenance_id': str(saved_maintenance.id),
                'object_name': object_info.short_name,
                'frequency': frequency,
                'months': months,
                'timestamp': saved_maintenance.created_at
            }
            
        except Exception as e:
            logger.error("Failed to add maintenance", error=str(e), object_id=object_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_maintenance_list(
        self,
        object_id: str,
        page: int = 0,
        limit: int = 10,
        active_only: bool = True
    ) -> Dict[str, Any]:
        """
        Получает список ТО объекта с пагинацией.
        
        Args:
            object_id: ID объекта обслуживания
            page: Номер страницы (начиная с 0)
            limit: Количество записей на страницу
            active_only: Только активные ТО
            
        Returns:
            Dict с ТО и информацией о пагинации
        """
        try:
            # Получаем ТО из БД
            maintenance_list = await self.service_repository.get_maintenance_list(
                object_id=object_id,
                skip=page * limit,
                limit=limit,
                active_only=active_only
            )
            
            # Получаем общее количество
            total = await self.service_repository.count_maintenance(object_id, active_only)
            
            # Форматируем ТО для отображения
            formatted_maintenance = []
            for maintenance in maintenance_list:
                formatted_maintenance.append({
                    'id': str(maintenance.id),
                    'description': maintenance.description,
                    'frequency': maintenance.frequency,
                    'months': maintenance.months,
                    'frequency_text': self._get_frequency_text(maintenance.frequency, maintenance.months),
                    'notes': maintenance.notes,
                    'created_by': maintenance.created_by_name,
                    'created_at': maintenance.created_at,
                    'last_performed': maintenance.last_performed,
                    'next_due': maintenance.next_due,
                    'is_active': maintenance.is_active
                })
            
            return {
                'success': True,
                'maintenance': formatted_maintenance,
                'total': total,
                'page': page,
                'limit': limit,
                'total_pages': (total + limit - 1) // limit
            }
            
        except Exception as e:
            logger.error("Failed to get maintenance list", error=str(e), object_id=object_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def update_maintenance(
        self,
        maintenance_id: str,
        user_id: int,
        user_name: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Редактирует ТО.
        
        Args:
            maintenance_id: ID ТО
            user_id: ID пользователя
            user_name: Имя пользователя
            updates: Словарь обновлений
            
        Returns:
            Dict с результатом обновления
        """
        try:
            # Получаем текущее ТО
            maintenance = await self.service_repository.get_maintenance_by_id(maintenance_id)
            if not maintenance:
                return {
                    'success': False,
                    'error': 'ТО не найдено'
                }
            
            # Проверяем права доступа
            from modules.admin.admin_manager import AdminManager
            admin_manager = AdminManager(self.context)
            user_role = await admin_manager.get_user_role(user_id)
            if user_role not in ['main_admin', 'admin']:
                return {
                    'success': False,
                    'error': 'Нет прав для редактирования ТО'
                }
            
            # Получаем информацию об объекте
            object_info = await self.service_repository.get_object_by_id(maintenance.object_id)
            
            # Подготавливаем изменения для логирования
            changes = {}
            
            # Проверяем каждое обновляемое поле
            if 'description' in updates and updates['description'] != maintenance.description:
                changes['description'] = {
                    'old': maintenance.description,
                    'new': updates['description']
                }
                maintenance.description = updates['description']
            
            if 'frequency' in updates and updates['frequency'] != maintenance.frequency:
                changes['frequency'] = {
                    'old': maintenance.frequency,
                    'new': updates['frequency']
                }
                maintenance.frequency = updates['frequency']
            
            if 'months' in updates and updates['months'] != maintenance.months:
                changes['months'] = {
                    'old': str(maintenance.months),
                    'new': str(updates['months'])
                }
                maintenance.months = updates['months']
            
            if 'notes' in updates and updates['notes'] != maintenance.notes:
                changes['notes'] = {
                    'old': maintenance.notes,
                    'new': updates['notes']
                }
                maintenance.notes = updates['notes']
            
            if 'is_active' in updates and updates['is_active'] != maintenance.is_active:
                changes['is_active'] = {
                    'old': maintenance.is_active,
                    'new': updates['is_active']
                }
                maintenance.is_active = updates['is_active']
                
                # Если активировали ТО, обновляем напоминания
                if updates['is_active'] and object_info:
                    await self._update_reminders_for_maintenance(maintenance, object_info)
            
            # Сохраняем изменения
            updated_maintenance = await self.service_repository.update_maintenance(maintenance)
            
            # Логируем изменения если они были
            if changes:
                await self.context.log_manager.log_change(
                    user_id=user_id,
                    user_name=user_name,
                    entity_type='maintenance',
                    entity_id=maintenance_id,
                    entity_name=f"ТО: {maintenance.description[:50]}...",
                    action='update',
                    changes=changes
                )
            
            return {
                'success': True,
                'maintenance_id': maintenance_id,
                'updated_fields': list(changes.keys())
            }
            
        except Exception as e:
            logger.error("Failed to update maintenance", error=str(e), maintenance_id=maintenance_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def delete_maintenance(
        self,
        maintenance_id: str,
        user_id: int,
        user_name: str
    ) -> Dict[str, Any]:
        """
        Удаляет ТО.
        
        Args:
            maintenance_id: ID ТО
            user_id: ID пользователя
            user_name: Имя пользователя
            
        Returns:
            Dict с результатом удаления
        """
        try:
            # Получаем ТО
            maintenance = await self.service_repository.get_maintenance_by_id(maintenance_id)
            if not maintenance:
                return {
                    'success': False,
                    'error': 'ТО не найдено'
                }
            
            # Проверяем права доступа
            from modules.admin.admin_manager import AdminManager
            admin_manager = AdminManager(self.context)
            user_role = await admin_manager.get_user_role(user_id)
            if user_role not in ['main_admin', 'admin']:
                return {
                    'success': False,
                    'error': 'Нет прав для удаления ТО'
                }
            
            # Сохраняем информацию для архива
            maintenance_info = {
                'id': str(maintenance.id),
                'description': maintenance.description,
                'object_id': maintenance.object_id,
                'created_by': maintenance.created_by_name,
                'created_at': maintenance.created_at,
                'deleted_by': user_name,
                'deleted_at': datetime.now()
            }
            
            # Удаляем ТО
            deleted = await self.service_repository.delete_maintenance(maintenance_id)
            
            if deleted:
                # Удаляем связанные напоминания
                await self._delete_reminders_for_maintenance(maintenance_id)
                
                # Логируем удаление
                await self.context.log_manager.log_change(
                    user_id=user_id,
                    user_name=user_name,
                    entity_type='maintenance',
                    entity_id=maintenance_id,
                    entity_name=f"ТО: {maintenance.description[:50]}...",
                    action='delete',
                    changes={'maintenance': {'old': maintenance_info, 'new': None}}
                )
                
                return {
                    'success': True,
                    'maintenance_id': maintenance_id
                }
            else:
                return {
                    'success': False,
                    'error': 'Не удалось удалить ТО'
                }
            
        except Exception as e:
            logger.error("Failed to delete maintenance", error=str(e), maintenance_id=maintenance_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def mark_as_performed(
        self,
        maintenance_id: str,
        user_id: int,
        user_name: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Отмечает ТО как выполненное.
        
        Args:
            maintenance_id: ID ТО
            user_id: ID пользователя
            user_name: Имя пользователя
            notes: Примечания к выполнению
            
        Returns:
            Dict с результатом
        """
        try:
            # Получаем ТО
            maintenance = await self.service_repository.get_maintenance_by_id(maintenance_id)
            if not maintenance:
                return {
                    'success': False,
                    'error': 'ТО не найдено'
                }
            
            # Обновляем дату последнего выполнения
            maintenance.last_performed = datetime.now()
            maintenance.performed_by_id = user_id
            maintenance.performed_by_name = user_name
            
            if notes:
                maintenance.performance_notes = notes
            
            # Рассчитываем следующую дату выполнения
            await self._calculate_next_due_date(maintenance)
            
            # Сохраняем изменения
            updated_maintenance = await self.service_repository.update_maintenance(maintenance)
            
            # Логируем выполнение
            await self.context.log_manager.log_change(
                user_id=user_id,
                user_name=user_name,
                entity_type='maintenance',
                entity_id=maintenance_id,
                entity_name=f"ТО: {maintenance.description[:50]}...",
                action='update',
                changes={
                    'last_performed': {
                        'old': None if not maintenance.last_performed else format_date(maintenance.last_performed),
                        'new': format_date(datetime.now())
                    },
                    'performed_by': {
                        'old': None,
                        'new': user_name
                    }
                }
            )
            
            return {
                'success': True,
                'maintenance_id': maintenance_id,
                'last_performed': updated_maintenance.last_performed,
                'next_due': updated_maintenance.next_due,
                'performed_by': user_name
            }
            
        except Exception as e:
            logger.error("Failed to mark maintenance as performed", error=str(e), maintenance_id=maintenance_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_upcoming_maintenance(
        self,
        object_id: Optional[str] = None,
        days_ahead: int = 30
    ) -> Dict[str, Any]:
        """
        Получает предстоящие ТО.
        
        Args:
            object_id: ID объекта (опционально)
            days_ahead: Количество дней вперед для поиска
            
        Returns:
            Dict с предстоящими ТО
        """
        try:
            # Получаем ТО из БД
            maintenance_list = await self.service_repository.get_upcoming_maintenance(
                object_id=object_id,
                days_ahead=days_ahead
            )
            
            # Форматируем результат
            formatted_maintenance = []
            for maintenance in maintenance_list:
                # Получаем информацию об объекте
                object_info = await self.service_repository.get_object_by_id(maintenance.object_id)
                
                formatted_maintenance.append({
                    'id': str(maintenance.id),
                    'description': maintenance.description,
                    'frequency': maintenance.frequency,
                    'months': maintenance.months,
                    'frequency_text': self._get_frequency_text(maintenance.frequency, maintenance.months),
                    'object_id': maintenance.object_id,
                    'object_name': object_info.short_name if object_info else 'Неизвестно',
                    'last_performed': maintenance.last_performed,
                    'next_due': maintenance.next_due,
                    'is_due_soon': self._is_due_soon(maintenance.next_due, days_ahead)
                })
            
            return {
                'success': True,
                'maintenance': formatted_maintenance,
                'total': len(formatted_maintenance),
                'days_ahead': days_ahead
            }
            
        except Exception as e:
            logger.error("Failed to get upcoming maintenance", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    async def check_monthly_maintenance(self, current_month: Optional[int] = None) -> Dict[str, Any]:
        """
        Проверяет ТО на текущий месяц.
        
        Args:
            current_month: Текущий месяц (1-12), если None - берется текущий
            
        Returns:
            Dict с ТО на текущий месяц
        """
        try:
            if current_month is None:
                current_month = datetime.now().month
            
            # Получаем ТО для текущего месяца
            maintenance_list = await self.service_repository.get_maintenance_by_month(current_month)
            
            # Группируем по объектам
            maintenance_by_object = {}
            for maintenance in maintenance_list:
                if maintenance.object_id not in maintenance_by_object:
                    object_info = await self.service_repository.get_object_by_id(maintenance.object_id)
                    maintenance_by_object[maintenance.object_id] = {
                        'object_name': object_info.short_name if object_info else 'Неизвестно',
                        'object_id': maintenance.object_id,
                        'maintenance': []
                    }
                
                maintenance_by_object[maintenance.object_id]['maintenance'].append({
                    'id': str(maintenance.id),
                    'description': maintenance.description,
                    'frequency': maintenance.frequency,
                    'notes': maintenance.notes
                })
            
            return {
                'success': True,
                'current_month': current_month,
                'maintenance_by_object': list(maintenance_by_object.values()),
                'total_objects': len(maintenance_by_object),
                'total_maintenance': len(maintenance_list)
            }
            
        except Exception as e:
            logger.error("Failed to check monthly maintenance", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _create_reminders_for_maintenance(
        self,
        maintenance: Maintenance,
        object_info: ServiceObject
    ) -> None:
        """Создает напоминания для ТО."""
        try:
            if not self.reminder_service or not maintenance.is_active:
                return
            
            # Создаем напоминание для каждого месяца выполнения
            for month in maintenance.months:
                # Создаем дату напоминания (первый день месяца)
                reminder_date = date(datetime.now().year, month, 1)
                
                # Если месяц уже прошел в этом году, планируем на следующий год
                if reminder_date < datetime.now().date():
                    reminder_date = date(datetime.now().year + 1, month, 1)
                
                reminder_text = f"ТО: {maintenance.description}"
                if object_info:
                    reminder_text += f" ({object_info.short_name})"
                
                await self.reminder_service.create_maintenance_reminder(
                    maintenance_id=str(maintenance.id),
                    object_id=maintenance.object_id,
                    object_name=object_info.short_name if object_info else 'Неизвестно',
                    reminder_date=reminder_date,
                    reminder_text=reminder_text,
                    frequency=maintenance.frequency,
                    month=month
                )
            
        except Exception as e:
            logger.error("Failed to create reminders for maintenance", error=str(e))
    
    async def _update_reminders_for_maintenance(
        self,
        maintenance: Maintenance,
        object_info: ServiceObject
    ) -> None:
        """Обновляет напоминания для ТО."""
        try:
            # Удаляем старые напоминания
            await self._delete_reminders_for_maintenance(str(maintenance.id))
            
            # Создаем новые напоминания
            await self._create_reminders_for_maintenance(maintenance, object_info)
            
        except Exception as e:
            logger.error("Failed to update reminders for maintenance", error=str(e))
    
    async def _delete_reminders_for_maintenance(self, maintenance_id: str) -> None:
        """Удаляет напоминания для ТО."""
        try:
            if self.reminder_service:
                await self.reminder_service.delete_maintenance_reminders(maintenance_id)
        except Exception as e:
            logger.error("Failed to delete reminders for maintenance", error=str(e))
    
    async def _calculate_next_due_date(self, maintenance: Maintenance) -> None:
        """Рассчитывает следующую дату выполнения ТО."""
        try:
            if not maintenance.last_performed:
                return
            
            last_performed = maintenance.last_performed
            next_due = None
            
            if maintenance.frequency == 'weekly':
                next_due = last_performed + timedelta(days=7)
            elif maintenance.frequency == 'monthly':
                next_due = last_performed + timedelta(days=30)
            elif maintenance.frequency == 'quarterly':
                next_due = last_performed + timedelta(days=90)
            elif maintenance.frequency == 'yearly':
                next_due = last_performed + timedelta(days=365)
            elif maintenance.frequency == 'custom' and maintenance.months:
                # Для custom находим следующий месяц из списка
                current_month = last_performed.month
                next_month = None
                
                # Ищем следующий месяц в списке
                for month in sorted(maintenance.months):
                    if month > current_month:
                        next_month = month
                        break
                
                # Если не нашли в этом году, берем первый месяц следующего года
                if not next_month and maintenance.months:
                    next_month = min(maintenance.months)
                    next_year = last_performed.year + 1
                else:
                    next_year = last_performed.year
                
                next_due = date(next_year, next_month, 1)
            
            maintenance.next_due = next_due
            
        except Exception as e:
            logger.error("Failed to calculate next due date", error=str(e))
    
    def _get_frequency_text(self, frequency: str, months: List[int]) -> str:
        """Возвращает читаемый текст частоты выполнения."""
        frequency_texts = {
            'weekly': 'Раз в неделю',
            'monthly': 'Раз в месяц',
            'quarterly': 'Раз в квартал',
            'yearly': 'Раз в год',
            'custom': f'В месяцы: {", ".join(str(m) for m in months)}'
        }
        return frequency_texts.get(frequency, frequency)
    
    def _is_due_soon(self, next_due: Optional[datetime], days_ahead: int) -> bool:
        """Проверяет, наступает ли ТО в ближайшие дни."""
        if not next_due:
            return False
        
        today = datetime.now().date()
        if isinstance(next_due, datetime):
            next_due_date = next_due.date()
        else:
            next_due_date = next_due
        
        days_until_due = (next_due_date - today).days
        return 0 <= days_until_due <= days_ahead