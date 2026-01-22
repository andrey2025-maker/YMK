"""
Менеджер для управления журналами объектов обслуживания.
Реализует ведение журналов учета работ и событий.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, date
import structlog

from core.context import AppContext
from storage.models.service import JournalEntry, ServiceObject
from storage.repositories.service_repository import ServiceRepository
from utils.date_utils import format_date


logger = structlog.get_logger(__name__)


class JournalManager:
    """Менеджер для управления журналами объектов обслуживания."""
    
    def __init__(self, context: AppContext):
        self.context = context
        self.service_repository: Optional[ServiceRepository] = None
    
    async def initialize(self) -> None:
        """Инициализирует менеджер журналов."""
        self.service_repository = ServiceRepository(self.context.db_session)
        logger.info("JournalManager initialized")
    
    async def add_journal_entry(
        self,
        object_id: str,
        user_id: int,
        user_name: str,
        entry_date: str,
        entry_type: str,
        description: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Добавляет запись в журнал объекта.
        
        Args:
            object_id: ID объекта обслуживания
            user_id: ID пользователя
            user_name: Имя пользователя
            entry_date: Дата записи (формат: ДД.ММ.ГГГГ)
            entry_type: Тип записи (work, inspection, maintenance, incident, other)
            description: Описание записи
            details: Дополнительные детали
            
        Returns:
            Dict с информацией о созданной записи
        """
        try:
            # Проверяем существование объекта
            object_info = await self.service_repository.get_object_by_id(object_id)
            if not object_info:
                return {
                    'success': False,
                    'error': 'Объект не найден'
                }
            
            # Парсим дату
            from utils.date_utils import parse_date
            parsed_date = parse_date(entry_date)
            if not parsed_date:
                return {
                    'success': False,
                    'error': 'Неверный формат даты. Используйте ДД.ММ.ГГГГ'
                }
            
            # Валидируем тип записи
            valid_types = ['work', 'inspection', 'maintenance', 'incident', 'other']
            if entry_type not in valid_types:
                return {
                    'success': False,
                    'error': f'Недопустимый тип записи. Допустимые значения: {", ".join(valid_types)}'
                }
            
            # Получаем следующий номер записи для этого объекта
            entry_number = await self._get_next_journal_number(object_id)
            
            # Создаем запись журнала
            journal_entry = JournalEntry(
                object_id=object_id,
                entry_number=entry_number,
                entry_date=parsed_date,
                entry_type=entry_type,
                description=description,
                details=details or {},
                created_by_id=user_id,
                created_by_name=user_name,
                created_at=datetime.now()
            )
            
            # Сохраняем в БД
            saved_entry = await self.service_repository.create_journal_entry(journal_entry)
            
            # Логируем создание записи
            await self.context.log_manager.log_change(
                user_id=user_id,
                user_name=user_name,
                entity_type='journal',
                entity_id=str(saved_entry.id),
                entity_name=f"Запись журнала {entry_number}",
                action='create',
                changes={
                    'entry_date': {'new': entry_date},
                    'entry_type': {'new': entry_type},
                    'description': {'new': description}
                }
            )
            
            return {
                'success': True,
                'entry_id': str(saved_entry.id),
                'entry_number': entry_number,
                'object_name': object_info.short_name,
                'entry_date': entry_date,
                'entry_type': entry_type,
                'timestamp': saved_entry.created_at
            }
            
        except Exception as e:
            logger.error("Failed to add journal entry", error=str(e), object_id=object_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_journal_entries(
        self,
        object_id: str,
        page: int = 0,
        limit: int = 10,
        entry_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Получает записи журнала с пагинацией.
        
        Args:
            object_id: ID объекта обслуживания
            page: Номер страницы (начиная с 0)
            limit: Количество записей на страницу
            entry_type: Фильтр по типу записи
            start_date: Начальная дата фильтра (формат: ДД.ММ.ГГГГ)
            end_date: Конечная дата фильтра (формат: ДД.ММ.ГГГГ)
            
        Returns:
            Dict с записями журнала и информацией о пагинации
        """
        try:
            # Парсим даты если указаны
            parsed_start_date = None
            parsed_end_date = None
            
            if start_date:
                from utils.date_utils import parse_date
                parsed_start_date = parse_date(start_date)
                if not parsed_start_date:
                    return {
                        'success': False,
                        'error': 'Неверный формат начальной даты. Используйте ДД.ММ.ГГГГ'
                    }
            
            if end_date:
                from utils.date_utils import parse_date
                parsed_end_date = parse_date(end_date)
                if not parsed_end_date:
                    return {
                        'success': False,
                        'error': 'Неверный формат конечной даты. Используйте ДД.ММ.ГГГГ'
                    }
            
            # Получаем записи журнала из БД
            entries = await self.service_repository.get_journal_entries(
                object_id=object_id,
                skip=page * limit,
                limit=limit,
                entry_type=entry_type,
                start_date=parsed_start_date,
                end_date=parsed_end_date
            )
            
            # Получаем общее количество
            total = await self.service_repository.count_journal_entries(
                object_id=object_id,
                entry_type=entry_type,
                start_date=parsed_start_date,
                end_date=parsed_end_date
            )
            
            # Форматируем записи для отображения
            formatted_entries = []
            for entry in entries:
                formatted_entries.append({
                    'id': str(entry.id),
                    'entry_number': entry.entry_number,
                    'entry_date': entry.entry_date,
                    'formatted_date': format_date(entry.entry_date),
                    'entry_type': entry.entry_type,
                    'type_text': self._get_entry_type_text(entry.entry_type),
                    'description': entry.description,
                    'details': entry.details,
                    'created_by': entry.created_by_name,
                    'created_at': entry.created_at
                })
            
            # Получаем доступные типы записей для фильтрации
            available_types = await self.service_repository.get_journal_entry_types(object_id)
            
            return {
                'success': True,
                'entries': formatted_entries,
                'total': total,
                'page': page,
                'limit': limit,
                'total_pages': (total + limit - 1) // limit,
                'available_types': available_types,
                'current_type': entry_type,
                'start_date': start_date,
                'end_date': end_date
            }
            
        except Exception as e:
            logger.error("Failed to get journal entries", error=str(e), object_id=object_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def update_journal_entry(
        self,
        entry_id: str,
        user_id: int,
        user_name: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Редактирует запись журнала.
        
        Args:
            entry_id: ID записи журнала
            user_id: ID пользователя
            user_name: Имя пользователя
            updates: Словарь обновлений
            
        Returns:
            Dict с результатом обновления
        """
        try:
            # Получаем текущую запись
            entry = await self.service_repository.get_journal_entry_by_id(entry_id)
            if not entry:
                return {
                    'success': False,
                    'error': 'Запись журнала не найдена'
                }
            
            # Проверяем права доступа
            from modules.admin.admin_manager import AdminManager
            admin_manager = AdminManager(self.context)
            user_role = await admin_manager.get_user_role(user_id)
            if user_role not in ['main_admin', 'admin']:
                return {
                    'success': False,
                    'error': 'Нет прав для редактирования записи журнала'
                }
            
            # Подготавливаем изменения для логирования
            changes = {}
            
            # Проверяем каждое обновляемое поле
            if 'entry_date' in updates:
                from utils.date_utils import parse_date
                parsed_date = parse_date(updates['entry_date'])
                if not parsed_date:
                    return {
                        'success': False,
                        'error': 'Неверный формат даты. Используйте ДД.ММ.ГГГГ'
                    }
                
                if parsed_date != entry.entry_date:
                    changes['entry_date'] = {
                        'old': format_date(entry.entry_date),
                        'new': updates['entry_date']
                    }
                    entry.entry_date = parsed_date
            
            if 'entry_type' in updates and updates['entry_type'] != entry.entry_type:
                # Валидируем тип записи
                valid_types = ['work', 'inspection', 'maintenance', 'incident', 'other']
                if updates['entry_type'] not in valid_types:
                    return {
                        'success': False,
                        'error': f'Недопустимый тип записи. Допустимые значения: {", ".join(valid_types)}'
                    }
                
                changes['entry_type'] = {
                    'old': entry.entry_type,
                    'new': updates['entry_type']
                }
                entry.entry_type = updates['entry_type']
            
            if 'description' in updates and updates['description'] != entry.description:
                changes['description'] = {
                    'old': entry.description,
                    'new': updates['description']
                }
                entry.description = updates['description']
            
            if 'details' in updates:
                changes['details'] = {
                    'old': str(entry.details),
                    'new': str(updates['details'])
                }
                entry.details = updates['details']
            
            # Сохраняем изменения
            updated_entry = await self.service_repository.update_journal_entry(entry)
            
            # Логируем изменения если они были
            if changes:
                await self.context.log_manager.log_change(
                    user_id=user_id,
                    user_name=user_name,
                    entity_type='journal',
                    entity_id=entry_id,
                    entity_name=f"Запись журнала {entry.entry_number}",
                    action='update',
                    changes=changes
                )
            
            return {
                'success': True,
                'entry_id': entry_id,
                'updated_fields': list(changes.keys())
            }
            
        except Exception as e:
            logger.error("Failed to update journal entry", error=str(e), entry_id=entry_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def delete_journal_entry(
        self,
        entry_id: str,
        user_id: int,
        user_name: str
    ) -> Dict[str, Any]:
        """
        Удаляет запись журнала.
        
        Args:
            entry_id: ID записи журнала
            user_id: ID пользователя
            user_name: Имя пользователя
            
        Returns:
            Dict с результатом удаления
        """
        try:
            # Получаем запись
            entry = await self.service_repository.get_journal_entry_by_id(entry_id)
            if not entry:
                return {
                    'success': False,
                    'error': 'Запись журнала не найдена'
                }
            
            # Проверяем права доступа
            from modules.admin.admin_manager import AdminManager
            admin_manager = AdminManager(self.context)
            user_role = await admin_manager.get_user_role(user_id)
            if user_role not in ['main_admin', 'admin']:
                return {
                    'success': False,
                    'error': 'Нет прав для удаления записи журнала'
                }
            
            # Сохраняем информацию для архива
            entry_info = {
                'id': str(entry.id),
                'entry_number': entry.entry_number,
                'entry_date': format_date(entry.entry_date),
                'entry_type': entry.entry_type,
                'description': entry.description,
                'object_id': entry.object_id,
                'created_by': entry.created_by_name,
                'created_at': entry.created_at,
                'deleted_by': user_name,
                'deleted_at': datetime.now()
            }
            
            # Удаляем запись
            deleted = await self.service_repository.delete_journal_entry(entry_id)
            
            if deleted:
                # Логируем удаление
                await self.context.log_manager.log_change(
                    user_id=user_id,
                    user_name=user_name,
                    entity_type='journal',
                    entity_id=entry_id,
                    entity_name=f"Запись журнала {entry.entry_number}",
                    action='delete',
                    changes={'journal_entry': {'old': entry_info, 'new': None}}
                )
                
                return {
                    'success': True,
                    'entry_id': entry_id,
                    'entry_number': entry.entry_number
                }
            else:
                return {
                    'success': False,
                    'error': 'Не удалось удалить запись журнала'
                }
            
        except Exception as e:
            logger.error("Failed to delete journal entry", error=str(e), entry_id=entry_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_journal_statistics(
        self,
        object_id: str,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Получает статистику по журналу объекта.
        
        Args:
            object_id: ID объекта обслуживания
            year: Год для статистики (опционально)
            
        Returns:
            Dict со статистикой
        """
        try:
            # Получаем общее количество записей
            total_entries = await self.service_repository.count_journal_entries(object_id)
            
            # Получаем количество записей по типам
            entries_by_type = await self.service_repository.get_journal_entries_by_type(object_id, year)
            
            # Получаем количество записей по месяцам
            entries_by_month = await self.service_repository.get_journal_entries_by_month(object_id, year)
            
            # Получаем последнюю запись
            last_entry = await self.service_repository.get_last_journal_entry(object_id)
            
            statistics = {
                'total_entries': total_entries,
                'entries_by_type': entries_by_type,
                'entries_by_month': entries_by_month,
                'last_entry': None
            }
            
            if last_entry:
                statistics['last_entry'] = {
                    'entry_number': last_entry.entry_number,
                    'entry_date': format_date(last_entry.entry_date),
                    'entry_type': last_entry.entry_type,
                    'description': last_entry.description[:100] + '...' if len(last_entry.description) > 100 else last_entry.description,
                    'created_at': last_entry.created_at
                }
            
            return {
                'success': True,
                'statistics': statistics,
                'year': year if year else 'все время'
            }
            
        except Exception as e:
            logger.error("Failed to get journal statistics", error=str(e), object_id=object_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def export_journal_data(
        self,
        object_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Экспортирует данные журнала.
        
        Args:
            object_id: ID объекта обслуживания
            start_date: Начальная дата (формат: ДД.ММ.ГГГГ)
            end_date: Конечная дата (формат: ДД.ММ.ГГГГ)
            
        Returns:
            Dict с данными для экспорта
        """
        try:
            # Парсим даты если указаны
            parsed_start_date = None
            parsed_end_date = None
            
            if start_date:
                from utils.date_utils import parse_date
                parsed_start_date = parse_date(start_date)
            
            if end_date:
                from utils.date_utils import parse_date
                parsed_end_date = parse_date(end_date)
            
            # Получаем все записи журнала
            entries = await self.service_repository.get_all_journal_entries(
                object_id=object_id,
                start_date=parsed_start_date,
                end_date=parsed_end_date
            )
            
            # Получаем информацию об объекте
            object_info = await self.service_repository.get_object_by_id(object_id)
            
            # Форматируем данные для экспорта
            export_data = []
            
            for entry in entries:
                export_data.append({
                    'entry_number': entry.entry_number,
                    'entry_date': format_date(entry.entry_date),
                    'entry_type': entry.entry_type,
                    'type_text': self._get_entry_type_text(entry.entry_type),
                    'description': entry.description,
                    'details': entry.details,
                    'created_by': entry.created_by_name,
                    'created_at': entry.created_at
                })
            
            return {
                'success': True,
                'object_name': object_info.short_name if object_info else 'Неизвестно',
                'object_full_name': object_info.full_name if object_info else 'Неизвестно',
                'entries': export_data,
                'total_entries': len(export_data),
                'export_date': datetime.now(),
                'period': {
                    'start_date': start_date,
                    'end_date': end_date
                }
            }
            
        except Exception as e:
            logger.error("Failed to export journal data", error=str(e), object_id=object_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _get_next_journal_number(self, object_id: str) -> int:
        """Получает следующий номер записи журнала для объекта."""
        try:
            last_entry = await self.service_repository.get_last_journal_number(object_id)
            return (last_entry or 0) + 1
        except Exception as e:
            logger.error("Failed to get next journal number", error=str(e), object_id=object_id)
            return 1
    
    def _get_entry_type_text(self, entry_type: str) -> str:
        """Возвращает читаемый текст типа записи."""
        type_texts = {
            'work': 'Работа',
            'inspection': 'Проверка',
            'maintenance': 'Обслуживание',
            'incident': 'Инцидент',
            'other': 'Другое'
        }
        return type_texts.get(entry_type, entry_type)