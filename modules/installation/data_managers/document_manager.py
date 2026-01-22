"""
Общий менеджер документов монтажа.
Управление документами разных типов (доп. соглашения, письма, допуски, журналы).
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from storage.models.installation import InstallationDocument
from storage.repositories.installation_repository import InstallationRepository
from modules.file.archive_manager import ArchiveManager
from modules.admin.log_manager import LogManager
from utils.date_utils import parse_date, format_date

logger = logging.getLogger(__name__)


class InstallationDocumentManager:
    """Общий менеджер документов монтажа."""
    
    def __init__(self, context):
        self.context = context
        self.repository = InstallationRepository(context.db_session)
        self.archive_manager = ArchiveManager(context)
        self.log_manager = LogManager(context)
    
    # ========== Общие методы для всех типов документов ==========
    
    async def add_document(self, object_id: str, user_id: int, document_type: str, 
                          data: Dict[str, Any], file_data: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[InstallationDocument], str]:
        """
        Добавление документа любого типа.
        
        Args:
            object_id: UUID объекта
            user_id: ID пользователя
            document_type: Тип документа ('доп_соглашение', 'письмо', 'допуск', 'журнал')
            data: Данные документа
            file_data: Данные файла (если есть)
            
        Returns:
            Кортеж (успех, документ, сообщение об ошибке)
        """
        try:
            # Проверяем существование объекта
            installation_object = await self.repository.get_installation_object_by_id(object_id)
            if not installation_object:
                return False, None, "Объект монтажа не найден"
            
            # Определяем тип документа для архивации
            archive_file_type = self._get_archive_file_type(document_type)
            
            # Архивация файла если есть
            file_info = None
            if file_data:
                file_info = await self.archive_manager.archive_installation_file(
                    object_id=object_id,
                    file_data=file_data,
                    file_type=archive_file_type,
                    uploaded_by=user_id,
                    description=f"{document_type}: {data.get('name', data.get('number', 'документ'))}"
                )
            
            # Парсим даты если они есть
            document_date = parse_date(data.get('date')) if data.get('date') else None
            start_date = parse_date(data.get('start_date')) if data.get('start_date') else None
            end_date = parse_date(data.get('end_date')) if data.get('end_date') else None
            
            # Создание документа
            document = InstallationDocument(
                installation_object_id=object_id,
                name=data.get('name', ''),
                document_type=document_type,
                document_number=data.get('number'),
                document_date=document_date,
                start_date=start_date,
                end_date=end_date,
                description=data.get('description', ''),
                has_file=file_info is not None,
                file_id=file_info['file_id'] if file_info else None,
                created_by=user_id
            )
            
            await self.repository.save_document(document)
            
            # Логирование
            log_details = {
                'document_type': document_type,
                'name': data.get('name'),
                'number': data.get('number'),
                'description': data.get('description'),
                'has_file': file_info is not None
            }
            if file_info:
                log_details['file_name'] = file_info.get('file_name')
                log_details['file_size'] = file_info.get('file_size')
            
            await self.log_manager.log_general_document_action(
                user_id=user_id,
                object_id=object_id,
                object_name=installation_object.full_name,
                document_id=document.id,
                document_type=document_type,
                action='add',
                details=log_details
            )
            
            return True, document, "Документ успешно добавлен"
            
        except Exception as e:
            logger.error(f"Ошибка добавления документа типа {document_type} к объекту {object_id}: {e}", exc_info=True)
            return False, None, f"Ошибка добавления документа: {str(e)}"
    
    async def get_documents_by_type(self, object_id: str, document_type: str) -> List[Dict[str, Any]]:
        """
        Получение документов определенного типа.
        
        Args:
            object_id: UUID объекта
            document_type: Тип документа
            
        Returns:
            Список документов с дополнительной информацией
        """
        try:
            documents = await self.repository.get_documents_by_type(object_id, document_type)
            result = []
            
            for document in documents:
                # Получаем информацию о файле если есть
                file_info = None
                if document.has_file and document.file_id:
                    file_info = await self.archive_manager.get_file_info(document.file_id)
                
                # Определяем статус для документов с датами окончания
                status = None
                status_text = None
                
                if document.end_date:
                    today = datetime.now().date()
                    if document.end_date < today:
                        status = 'expired'
                        days_passed = (today - document.end_date).days
                        status_text = f"Истек {days_passed} дн. назад"
                    elif document.end_date == today:
                        status = 'expires_today'
                        status_text = "Истекает сегодня"
                    else:
                        status = 'active'
                        days_until = (document.end_date - today).days
                        status_text = f"Истекает через {days_until} дн."
                
                result.append({
                    'id': str(document.id),
                    'name': document.name,
                    'document_type': document.document_type,
                    'document_number': document.document_number,
                    'document_date': format_date(document.document_date) if document.document_date else None,
                    'start_date': format_date(document.start_date) if document.start_date else None,
                    'end_date': format_date(document.end_date) if document.end_date else None,
                    'description': document.description,
                    'has_file': document.has_file,
                    'file_info': file_info,
                    'status': status,
                    'status_text': status_text,
                    'created_at': document.created_at.isoformat() if document.created_at else None,
                    'created_by': document.created_by,
                    'updated_at': document.updated_at.isoformat() if document.updated_at else None
                })
            
            # Сортируем по дате документа (новые сначала)
            result.sort(key=lambda x: (
                x['document_date'] is None,  # Без даты в конец
                x['document_date'] if x['document_date'] else '0001-01-01'
            ), reverse=True)
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка получения документов типа {document_type} объекта {object_id}: {e}", exc_info=True)
            return []
    
    async def update_document(self, document_id: str, user_id: int, data: Dict[str, Any],
                            file_data: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        Обновление документа.
        
        Args:
            document_id: UUID документа
            user_id: ID пользователя
            data: Новые данные
            file_data: Новый файл (если нужно заменить)
            
        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            document = await self.repository.get_document_by_id(document_id)
            if not document:
                return False, "Документ не найден"
            
            old_data = {
                'name': document.name,
                'document_number': document.document_number,
                'document_date': format_date(document.document_date) if document.document_date else None,
                'start_date': format_date(document.start_date) if document.start_date else None,
                'end_date': format_date(document.end_date) if document.end_date else None,
                'description': document.description,
                'has_file': document.has_file,
                'file_id': document.file_id
            }
            
            old_file_id = document.file_id
            
            # Обновление полей
            if 'name' in data:
                document.name = data['name']
            if 'number' in data:
                document.document_number = data['number']
            if 'date' in data:
                document.document_date = parse_date(data['date']) if data['date'] else None
            if 'start_date' in data:
                document.start_date = parse_date(data['start_date']) if data['start_date'] else None
            if 'end_date' in data:
                document.end_date = parse_date(data['end_date']) if data['end_date'] else None
            if 'description' in data:
                document.description = data['description']
            
            # Обработка файла
            new_file_info = None
            if file_data:
                # Определяем тип документа для архивации
                archive_file_type = self._get_archive_file_type(document.document_type)
                
                # Архивация нового файла
                new_file_info = await self.archive_manager.archive_installation_file(
                    object_id=document.installation_object_id,
                    file_data=file_data,
                    file_type=archive_file_type,
                    uploaded_by=user_id,
                    description=f"{document.document_type} (обновление): {data.get('name', document.name)}"
                )
                
                document.has_file = True
                document.file_id = new_file_info['file_id']
            
            # Если файл удален
            elif 'remove_file' in data and data['remove_file']:
                document.has_file = False
                document.file_id = None
            
            document.updated_at = datetime.now()
            
            await self.repository.save_document(document)
            
            # Удаляем старый файл если он был заменен
            if old_file_id and new_file_info and old_file_id != new_file_info['file_id']:
                await self.archive_manager.delete_file(old_file_id)
            
            # Логирование
            new_data = {k: data.get(k) for k in old_data.keys() if k in data}
            if new_file_info:
                new_data['file_name'] = new_file_info.get('file_name')
                new_data['file_size'] = new_file_info.get('file_size')
            
            await self.log_manager.log_general_document_action(
                user_id=user_id,
                object_id=document.installation_object_id,
                object_name=(await self._get_object_name(document.installation_object_id)),
                document_id=document_id,
                document_type=document.document_type,
                action='update',
                old_data=old_data,
                new_data=new_data
            )
            
            return True, "Документ успешно обновлен"
            
        except Exception as e:
            logger.error(f"Ошибка обновления документа {document_id}: {e}", exc_info=True)
            return False, f"Ошибка обновления: {str(e)}"
    
    async def delete_document(self, document_id: str, user_id: int) -> Tuple[bool, str]:
        """
        Удаление документа.
        
        Args:
            document_id: UUID документа
            user_id: ID пользователя
            
        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            document = await self.repository.get_document_by_id(document_id)
            if not document:
                return False, "Документ не найден"
            
            # Удаляем файл если есть
            if document.has_file and document.file_id:
                await self.archive_manager.delete_file(document.file_id)
            
            # Логирование перед удалением
            await self.log_manager.log_general_document_action(
                user_id=user_id,
                object_id=document.installation_object_id,
                object_name=(await self._get_object_name(document.installation_object_id)),
                document_id=document_id,
                document_type=document.document_type,
                action='delete',
                details={
                    'name': document.name,
                    'number': document.document_number,
                    'had_file': document.has_file
                }
            )
            
            # Удаление
            await self.repository.delete_document(document_id)
            
            return True, "Документ успешно удален"
            
        except Exception as e:
            logger.error(f"Ошибка удаления документа {document_id}: {e}", exc_info=True)
            return False, f"Ошибка удаления: {str(e)}"
    
    async def get_document_with_file(self, document_id: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Получение документа с информацией о файле для скачивания.
        
        Args:
            document_id: UUID документа
            
        Returns:
            Кортеж (успех, данные документа, сообщение об ошибке)
        """
        try:
            document = await self.repository.get_document_by_id(document_id)
            if not document:
                return False, None, "Документ не найден"
            
            result = {
                'id': str(document.id),
                'name': document.name,
                'document_type': document.document_type,
                'document_number': document.document_number,
                'document_date': format_date(document.document_date) if document.document_date else None,
                'start_date': format_date(document.start_date) if document.start_date else None,
                'end_date': format_date(document.end_date) if document.end_date else None,
                'description': document.description,
                'has_file': document.has_file,
                'created_at': document.created_at.isoformat() if document.created_at else None,
                'created_by': document.created_by
            }
            
            # Получаем информацию о файле если есть
            if document.has_file and document.file_id:
                file_info = await self.archive_manager.get_file_info(document.file_id)
                if file_info:
                    result['file_info'] = file_info
                    result['download_url'] = await self.archive_manager.get_file_download_url(document.file_id)
            
            return True, result, ""
            
        except Exception as e:
            logger.error(f"Ошибка получения документа {document_id}: {e}", exc_info=True)
            return False, None, f"Ошибка получения: {str(e)}"
    
    async def get_expiring_documents(self, object_id: str, document_type: str, days_threshold: int = 30) -> List[Dict[str, Any]]:
        """
        Получение документов, срок действия которых истекает в ближайшее время.
        
        Args:
            object_id: UUID объекта
            document_type: Тип документа
            days_threshold: Порог дней для предупреждения
            
        Returns:
            Список истекающих документов
        """
        try:
            documents = await self.repository.get_documents_by_type(object_id, document_type)
            today = datetime.now().date()
            threshold_date = today + datetime.timedelta(days=days_threshold)
            
            result = []
            for document in documents:
                if document.end_date and document.end_date <= threshold_date and document.end_date >= today:
                    days_until = (document.end_date - today).days
                    
                    result.append({
                        'id': str(document.id),
                        'name': document.name,
                        'document_number': document.document_number,
                        'end_date': format_date(document.end_date),
                        'days_until': days_until,
                        'description': document.description,
                        'has_file': document.has_file
                    })
            
            # Сортируем по дате окончания (ближайшие сначала)
            result.sort(key=lambda x: x['days_until'])
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка получения истекающих документов типа {document_type} объекта {object_id}: {e}", exc_info=True)
            return []
    
    async def search_documents(self, object_id: str, document_type: str, search_text: str) -> List[Dict[str, Any]]:
        """
        Поиск документов по тексту.
        
        Args:
            object_id: UUID объекта
            document_type: Тип документа
            search_text: Текст для поиска
            
        Returns:
            Список найденных документов
        """
        try:
            if not search_text or len(search_text.strip()) < 2:
                return []
            
            search_text = search_text.strip().lower()
            documents = await self.repository.get_documents_by_type(object_id, document_type)
            
            result = []
            for document in documents:
                # Поиск в названии, номере и описании
                if (search_text in document.name.lower() or
                    (document.document_number and search_text in document.document_number.lower()) or
                    (document.description and search_text in document.description.lower())):
                    
                    result.append({
                        'id': str(document.id),
                        'name': document.name,
                        'document_number': document.document_number,
                        'document_date': format_date(document.document_date) if document.document_date else None,
                        'description': document.description,
                        'has_file': document.has_file,
                        'created_at': document.created_at.isoformat() if document.created_at else None,
                        'created_by': document.created_by
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка поиска документов типа {document_type} объекта {object_id}: {e}", exc_info=True)
            return []
    
    # ========== Вспомогательные методы ==========
    
    def _get_archive_file_type(self, document_type: str) -> str:
        """
        Получение типа файла для архивации на основе типа документа.
        
        Args:
            document_type: Тип документа
            
        Returns:
            Тип файла для архивации
        """
        mapping = {
            'доп_соглашение': 'additional_document',
            'письмо': 'letter',
            'допуск': 'permit',
            'журнал': 'journal',
            'ИД': 'id_document'
        }
        
        return mapping.get(document_type, 'other_document')
    
    async def _get_object_name(self, object_id: str) -> str:
        """Получение названия объекта."""
        try:
            installation_object = await self.repository.get_installation_object_by_id(object_id)
            return installation_object.full_name if installation_object else ""
        except Exception:
            return ""