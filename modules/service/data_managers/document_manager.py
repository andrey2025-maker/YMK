"""
Менеджер для управления дополнительными документами объектов обслуживания.
Реализует добавление, редактирование и удаление доп. соглашений.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, date
import structlog

from core.context import AppContext
from storage.models.service import AdditionalDocument, ServiceObject
from storage.repositories.service_repository import ServiceRepository
from utils.date_utils import parse_date, format_date
from services.reminder_service import ReminderService


logger = structlog.get_logger(__name__)


class DocumentManager:
    """Менеджер для управления дополнительными документами объектов обслуживания."""
    
    def __init__(self, context: AppContext):
        self.context = context
        self.service_repository: Optional[ServiceRepository] = None
        self.reminder_service: Optional[ReminderService] = None
    
    async def initialize(self) -> None:
        """Инициализирует менеджер документов."""
        self.service_repository = ServiceRepository(self.context.db_session)
        self.reminder_service = ReminderService(self.context)
        logger.info("DocumentManager initialized")
    
    async def add_document(
        self,
        object_id: str,
        user_id: int,
        user_name: str,
        document_name: str,
        document_number: str,
        document_date: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Добавляет дополнительный документ к объекту.
        
        Args:
            object_id: ID объекта обслуживания
            user_id: ID пользователя
            user_name: Имя пользователя
            document_name: Наименование документа (Доп. соглашение, Изменение и т.д.)
            document_number: Номер документа
            document_date: Дата документа (формат: ДД.ММ.ГГГГ)
            start_date: Дата начала действия (формат: ДД.ММ.ГГГГ, опционально)
            end_date: Дата окончания действия (формат: ДД.ММ.ГГГГ, опционально)
            description: Описание документа (опционально)
            
        Returns:
            Dict с информацией о созданном документе
        """
        try:
            # Проверяем существование объекта
            object_info = await self.service_repository.get_object_by_id(object_id)
            if not object_info:
                return {
                    'success': False,
                    'error': 'Объект не найден'
                }
            
            # Парсим дату документа
            parsed_document_date = parse_date(document_date)
            if not parsed_document_date:
                return {
                    'success': False,
                    'error': 'Неверный формат даты документа. Используйте ДД.ММ.ГГГГ'
                }
            
            # Парсим даты начала и окончания если указаны
            parsed_start_date = None
            if start_date and start_date.lower() != 'нет':
                parsed_start_date = parse_date(start_date)
                if not parsed_start_date:
                    return {
                        'success': False,
                        'error': 'Неверный формат даты начала. Используйте ДД.ММ.ГГГГ или "нет"'
                    }
            
            parsed_end_date = None
            if end_date and end_date.lower() != 'нет':
                parsed_end_date = parse_date(end_date)
                if not parsed_end_date:
                    return {
                        'success': False,
                        'error': 'Неверный формат даты окончания. Используйте ДД.ММ.ГГГГ или "нет"'
                    }
            
            # Проверяем уникальность номера документа для объекта
            existing_document = await self.service_repository.get_document_by_number(object_id, document_number)
            if existing_document:
                return {
                    'success': False,
                    'error': f'Документ с номером {document_number} уже существует для этого объекта'
                }
            
            # Создаем запись документа
            document = AdditionalDocument(
                object_id=object_id,
                document_name=document_name,
                document_number=document_number,
                document_date=parsed_document_date,
                start_date=parsed_start_date,
                end_date=parsed_end_date,
                description=description or '',
                added_by_id=user_id,
                added_by_name=user_name,
                added_at=datetime.now()
            )
            
            # Сохраняем в БД
            saved_document = await self.service_repository.create_document(document)
            
            # Создаем напоминания для документа
            await self._create_document_reminders(saved_document, object_info, user_id)
            
            # Логируем создание документа
            changes = {
                'document_name': {'new': document_name},
                'document_number': {'new': document_number},
                'document_date': {'new': document_date}
            }
            
            if start_date and start_date.lower() != 'нет':
                changes['start_date'] = {'new': start_date}
            
            if end_date and end_date.lower() != 'нет':
                changes['end_date'] = {'new': end_date}
            
            if description:
                changes['description'] = {'new': description}
            
            await self.context.log_manager.log_change(
                user_id=user_id,
                user_name=user_name,
                entity_type='document',
                entity_id=str(saved_document.id),
                entity_name=f"{document_name} {document_number}",
                action='create',
                changes=changes
            )
            
            return {
                'success': True,
                'document_id': str(saved_document.id),
                'document_name': document_name,
                'document_number': document_number,
                'object_name': object_info.short_name,
                'timestamp': saved_document.added_at
            }
            
        except Exception as e:
            logger.error("Failed to add document", error=str(e), object_id=object_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_documents(
        self,
        object_id: str,
        page: int = 0,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Получает список документов объекта.
        
        Args:
            object_id: ID объекта обслуживания
            page: Номер страницы (начиная с 0)
            limit: Количество записей на страницу
            
        Returns:
            Dict с документами и информацией о пагинации
        """
        try:
            # Получаем документы из БД
            documents = await self.service_repository.get_documents(
                object_id=object_id,
                skip=page * limit,
                limit=limit
            )
            
            # Получаем общее количество
            total = await self.service_repository.count_documents(object_id)
            
            # Форматируем документы для отображения
            formatted_documents = []
            for document in documents:
                # Проверяем актуальность документа
                status = 'active'
                if document.end_date:
                    if document.end_date < datetime.now().date():
                        status = 'expired'
                    elif (document.end_date - datetime.now().date()).days <= 30:
                        status = 'expiring_soon'
                
                formatted_documents.append({
                    'id': str(document.id),
                    'document_name': document.document_name,
                    'document_number': document.document_number,
                    'document_date': document.document_date,
                    'formatted_document_date': format_date(document.document_date),
                    'start_date': document.start_date,
                    'formatted_start_date': format_date(document.start_date) if document.start_date else 'Не указана',
                    'end_date': document.end_date,
                    'formatted_end_date': format_date(document.end_date) if document.end_date else 'Не указана',
                    'description': document.description,
                    'status': status,
                    'added_by': document.added_by_name,
                    'added_at': document.added_at
                })
            
            return {
                'success': True,
                'documents': formatted_documents,
                'total': total,
                'page': page,
                'limit': limit,
                'total_pages': (total + limit - 1) // limit
            }
            
        except Exception as e:
            logger.error("Failed to get documents", error=str(e), object_id=object_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def update_document(
        self,
        document_id: str,
        user_id: int,
        user_name: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Редактирует документ.
        
        Args:
            document_id: ID документа
            user_id: ID пользователя
            user_name: Имя пользователя
            updates: Словарь обновлений
            
        Returns:
            Dict с результатом обновления
        """
        try:
            # Получаем текущий документ
            document = await self.service_repository.get_document_by_id(document_id)
            if not document:
                return {
                    'success': False,
                    'error': 'Документ не найден'
                }
            
            # Проверяем права доступа
            from modules.admin.admin_manager import AdminManager
            admin_manager = AdminManager(self.context)
            user_role = await admin_manager.get_user_role(user_id)
            if user_role not in ['main_admin', 'admin']:
                return {
                    'success': False,
                    'error': 'Нет прав для редактирования документа'
                }
            
            # Получаем информацию об объекте
            object_info = await self.service_repository.get_object_by_id(document.object_id)
            
            # Подготавливаем изменения для логирования
            changes = {}
            
            # Проверяем каждое обновляемое поле
            if 'document_name' in updates and updates['document_name'] != document.document_name:
                changes['document_name'] = {
                    'old': document.document_name,
                    'new': updates['document_name']
                }
                document.document_name = updates['document_name']
            
            if 'document_number' in updates and updates['document_number'] != document.document_number:
                # Проверяем уникальность нового номера
                existing_document = await self.service_repository.get_document_by_number(
                    document.object_id, 
                    updates['document_number']
                )
                if existing_document and str(existing_document.id) != document_id:
                    return {
                        'success': False,
                        'error': f'Документ с номером {updates["document_number"]} уже существует для этого объекта'
                    }
                
                changes['document_number'] = {
                    'old': document.document_number,
                    'new': updates['document_number']
                }
                document.document_number = updates['document_number']
            
            if 'document_date' in updates:
                parsed_date = parse_date(updates['document_date'])
                if not parsed_date:
                    return {
                        'success': False,
                        'error': 'Неверный формат даты документа. Используйте ДД.ММ.ГГГГ'
                    }
                
                if parsed_date != document.document_date:
                    changes['document_date'] = {
                        'old': format_date(document.document_date),
                        'new': updates['document_date']
                    }
                    document.document_date = parsed_date
            
            if 'start_date' in updates:
                if updates['start_date'] and updates['start_date'].lower() != 'нет':
                    parsed_start_date = parse_date(updates['start_date'])
                    if not parsed_start_date:
                        return {
                            'success': False,
                            'error': 'Неверный формат даты начала. Используйте ДД.ММ.ГГГГ или "нет"'
                        }
                    
                    if parsed_start_date != document.start_date:
                        changes['start_date'] = {
                            'old': format_date(document.start_date) if document.start_date else 'Не указана',
                            'new': updates['start_date']
                        }
                        document.start_date = parsed_start_date
                else:
                    changes['start_date'] = {
                        'old': format_date(document.start_date) if document.start_date else 'Не указана',
                        'new': 'Не указана'
                    }
                    document.start_date = None
            
            if 'end_date' in updates:
                if updates['end_date'] and updates['end_date'].lower() != 'нет':
                    parsed_end_date = parse_date(updates['end_date'])
                    if not parsed_end_date:
                        return {
                            'success': False,
                            'error': 'Неверный формат даты окончания. Используйте ДД.ММ.ГГГГ или "нет"'
                        }
                    
                    if parsed_end_date != document.end_date:
                        changes['end_date'] = {
                            'old': format_date(document.end_date) if document.end_date else 'Не указана',
                            'new': updates['end_date']
                        }
                        document.end_date = parsed_end_date
                else:
                    changes['end_date'] = {
                        'old': format_date(document.end_date) if document.end_date else 'Не указана',
                        'new': 'Не указана'
                    }
                    document.end_date = None
            
            if 'description' in updates and updates['description'] != document.description:
                changes['description'] = {
                    'old': document.description,
                    'new': updates['description']
                }
                document.description = updates['description']
            
            # Сохраняем изменения
            updated_document = await self.service_repository.update_document(document)
            
            # Обновляем напоминания
            await self._update_document_reminders(document, object_info, user_id)
            
            # Логируем изменения если они были
            if changes:
                await self.context.log_manager.log_change(
                    user_id=user_id,
                    user_name=user_name,
                    entity_type='document',
                    entity_id=document_id,
                    entity_name=f"{document.document_name} {document.document_number}",
                    action='update',
                    changes=changes
                )
            
            return {
                'success': True,
                'document_id': document_id,
                'updated_fields': list(changes.keys())
            }
            
        except Exception as e:
            logger.error("Failed to update document", error=str(e), document_id=document_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def delete_document(
        self,
        document_id: str,
        user_id: int,
        user_name: str
    ) -> Dict[str, Any]:
        """
        Удаляет документ.
        
        Args:
            document_id: ID документа
            user_id: ID пользователя
            user_name: Имя пользователя
            
        Returns:
            Dict с результатом удаления
        """
        try:
            # Получаем документ
            document = await self.service_repository.get_document_by_id(document_id)
            if not document:
                return {
                    'success': False,
                    'error': 'Документ не найден'
                }
            
            # Проверяем права доступа
            from modules.admin.admin_manager import AdminManager
            admin_manager = AdminManager(self.context)
            user_role = await admin_manager.get_user_role(user_id)
            if user_role not in ['main_admin', 'admin']:
                return {
                    'success': False,
                    'error': 'Нет прав для удаления документа'
                }
            
            # Сохраняем информацию для архива
            document_info = {
                'id': str(document.id),
                'document_name': document.document_name,
                'document_number': document.document_number,
                'document_date': format_date(document.document_date),
                'start_date': format_date(document.start_date) if document.start_date else None,
                'end_date': format_date(document.end_date) if document.end_date else None,
                'description': document.description,
                'object_id': document.object_id,
                'added_by': document.added_by_name,
                'added_at': document.added_at,
                'deleted_by': user_name,
                'deleted_at': datetime.now()
            }
            
            # Удаляем документ
            deleted = await self.service_repository.delete_document(document_id)
            
            if deleted:
                # Удаляем связанные напоминания
                await self._delete_document_reminders(document_id)
                
                # Логируем удаление
                await self.context.log_manager.log_change(
                    user_id=user_id,
                    user_name=user_name,
                    entity_type='document',
                    entity_id=document_id,
                    entity_name=f"{document.document_name} {document.document_number}",
                    action='delete',
                    changes={'document': {'old': document_info, 'new': None}}
                )
                
                return {
                    'success': True,
                    'document_id': document_id,
                    'document_name': document.document_name,
                    'document_number': document.document_number
                }
            else:
                return {
                    'success': False,
                    'error': 'Не удалось удалить документ'
                }
            
        except Exception as e:
            logger.error("Failed to delete document", error=str(e), document_id=document_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_document_details(self, document_id: str) -> Dict[str, Any]:
        """
        Получает детальную информацию о документе.
        
        Args:
            document_id: ID документа
            
        Returns:
            Dict с детальной информацией о документе
        """
        try:
            document = await self.service_repository.get_document_by_id(document_id)
            if not document:
                return {
                    'success': False,
                    'error': 'Документ не найден'
                }
            
            # Получаем информацию об объекте
            object_info = await self.service_repository.get_object_by_id(document.object_id)
            
            # Проверяем актуальность документа
            status = 'active'
            days_until_expiry = None
            
            if document.end_date:
                today = datetime.now().date()
                days_until_expiry = (document.end_date - today).days
                
                if days_until_expiry < 0:
                    status = 'expired'
                elif days_until_expiry <= 30:
                    status = 'expiring_soon'
            
            document_details = {
                'id': str(document.id),
                'document_name': document.document_name,
                'document_number': document.document_number,
                'document_date': document.document_date,
                'formatted_document_date': format_date(document.document_date),
                'start_date': document.start_date,
                'formatted_start_date': format_date(document.start_date) if document.start_date else 'Не указана',
                'end_date': document.end_date,
                'formatted_end_date': format_date(document.end_date) if document.end_date else 'Не указана',
                'description': document.description,
                'status': status,
                'days_until_expiry': days_until_expiry,
                'added_by': document.added_by_name,
                'added_at': document.added_at,
                'object_id': document.object_id,
                'object_name': object_info.short_name if object_info else 'Неизвестно',
                'object_full_name': object_info.full_name if object_info else 'Неизвестно'
            }
            
            return {
                'success': True,
                'document': document_details
            }
            
        except Exception as e:
            logger.error("Failed to get document details", error=str(e), document_id=document_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def check_document_dates(
        self,
        object_id: Optional[str] = None,
        check_expired: bool = True,
        check_expiring: bool = True,
        days_threshold: int = 30
    ) -> Dict[str, Any]:
        """
        Проверяет сроки действия документов.
        
        Args:
            object_id: ID объекта (опционально)
            check_expired: Проверять истекшие документы
            check_expiring: Проверять истекающие документы
            days_threshold: Порог дней для истекающих документов
            
        Returns:
            Dict с результатами проверки
        """
        try:
            today = datetime.now().date()
            
            # Получаем все документы
            documents = await self.service_repository.get_all_documents_with_dates(object_id)
            
            expired_documents = []
            expiring_documents = []
            active_documents = []
            
            for document in documents:
                # Получаем информацию об объекте
                object_info = await self.service_repository.get_object_by_id(document.object_id)
                
                doc_info = {
                    'id': str(document.id),
                    'document_name': document.document_name,
                    'document_number': document.document_number,
                    'document_date': format_date(document.document_date),
                    'end_date': format_date(document.end_date) if document.end_date else 'Бессрочно',
                    'object_id': document.object_id,
                    'object_name': object_info.short_name if object_info else 'Неизвестно'
                }
                
                if document.end_date:
                    days_until_expiry = (document.end_date - today).days
                    
                    if days_until_expiry < 0 and check_expired:
                        expired_documents.append(doc_info)
                    elif 0 <= days_until_expiry <= days_threshold and check_expiring:
                        doc_info['days_until_expiry'] = days_until_expiry
                        expiring_documents.append(doc_info)
                    else:
                        active_documents.append(doc_info)
                else:
                    active_documents.append(doc_info)
            
            return {
                'success': True,
                'expired_documents': expired_documents,
                'expiring_documents': expiring_documents,
                'active_documents': active_documents,
                'total_expired': len(expired_documents),
                'total_expiring': len(expiring_documents),
                'total_active': len(active_documents),
                'total': len(documents),
                'days_threshold': days_threshold
            }
            
        except Exception as e:
            logger.error("Failed to check document dates", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _create_document_reminders(
        self,
        document: AdditionalDocument,
        object_info: ServiceObject,
        user_id: int
    ) -> None:
        """Создает напоминания для документа."""
        try:
            if not self.reminder_service:
                return
            
            # Создаем напоминание о дате документа
            if document.document_date:
                reminder_text = f"Дата документа: {document.document_name} №{document.document_number} ({object_info.short_name})"
                
                await self.reminder_service.create_reminder(
                    user_id=user_id,
                    object_type='service',
                    object_id=document.object_id,
                    object_name=object_info.short_name,
                    reminder_date=document.document_date,
                    reminder_text=reminder_text,
                    notify_before_days=[0]
                )
            
            # Создаем напоминания о начале действия если указана дата
            if document.start_date:
                reminder_text = f"Начало действия: {document.document_name} №{document.document_number} ({object_info.short_name})"
                
                # Напоминание за 1 день
                await self.reminder_service.create_reminder(
                    user_id=user_id,
                    object_type='service',
                    object_id=document.object_id,
                    object_name=object_info.short_name,
                    reminder_date=document.start_date,
                    reminder_text=f"Завтра: {reminder_text}",
                    notify_before_days=[0]
                )
                
                # Напоминание в день начала
                await self.reminder_service.create_reminder(
                    user_id=user_id,
                    object_type='service',
                    object_id=document.object_id,
                    object_name=object_info.short_name,
                    reminder_date=document.start_date,
                    reminder_text=reminder_text,
                    notify_before_days=[]
                )
            
            # Создаем напоминания об окончании действия если указана дата
            if document.end_date:
                reminder_text = f"Окончание действия: {document.document_name} №{document.document_number} ({object_info.short_name})"
                
                # Напоминание за 7 дней
                from datetime import timedelta
                reminder_date_7 = document.end_date - timedelta(days=7)
                if reminder_date_7 > datetime.now().date():
                    await self.reminder_service.create_reminder(
                        user_id=user_id,
                        object_type='service',
                        object_id=document.object_id,
                        object_name=object_info.short_name,
                        reminder_date=reminder_date_7,
                        reminder_text=f"Через 7 дней: {reminder_text}",
                        notify_before_days=[1]
                    )
                
                # Напоминание за 1 день
                reminder_date_1 = document.end_date - timedelta(days=1)
                if reminder_date_1 > datetime.now().date():
                    await self.reminder_service.create_reminder(
                        user_id=user_id,
                        object_type='service',
                        object_id=document.object_id,
                        object_name=object_info.short_name,
                        reminder_date=reminder_date_1,
                        reminder_text=f"Завтра: {reminder_text}",
                        notify_before_days=[0]
                    )
                
                # Напоминание в день окончания
                await self.reminder_service.create_reminder(
                    user_id=user_id,
                    object_type='service',
                    object_id=document.object_id,
                    object_name=object_info.short_name,
                    reminder_date=document.end_date,
                    reminder_text=reminder_text,
                    notify_before_days=[]
                )
            
        except Exception as e:
            logger.error("Failed to create document reminders", error=str(e))
    
    async def _update_document_reminders(
        self,
        document: AdditionalDocument,
        object_info: ServiceObject,
        user_id: int
    ) -> None:
        """Обновляет напоминания для документа."""
        try:
            # Удаляем старые напоминания
            await self._delete_document_reminders(str(document.id))
            
            # Создаем новые напоминания
            await self._create_document_reminders(document, object_info, user_id)
            
        except Exception as e:
            logger.error("Failed to update document reminders", error=str(e))
    
    async def _delete_document_reminders(self, document_id: str) -> None:
        """Удаляет напоминания для документа."""
        try:
            # Здесь нужно реализовать поиск и удаление напоминаний для этого документа
            # В реальной реализации нужно хранить связь между документом и напоминанием
            pass
            
        except Exception as e:
            logger.error("Failed to delete document reminders", error=str(e))