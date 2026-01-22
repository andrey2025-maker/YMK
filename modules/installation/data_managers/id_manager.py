"""
Менеджер исполнительной документации (ИД).
Управление файлами исполнительной документации монтажа.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from storage.models.installation import InstallationDocument
from storage.repositories.installation_repository import InstallationRepository
from modules.file.archive_manager import ArchiveManager
from modules.admin.log_manager import LogManager

logger = logging.getLogger(__name__)


class IDManager:
    """Менеджер исполнительной документации."""
    
    def __init__(self, context):
        self.context = context
        self.repository = InstallationRepository(context.db_session)
        self.archive_manager = ArchiveManager(context)
        self.log_manager = LogManager(context)
    
    async def add_id_document(self, object_id: str, user_id: int, name: str, 
                             file_data: Dict[str, Any]) -> Tuple[bool, Optional[InstallationDocument], str]:
        """
        Добавление документа ИД.
        
        Args:
            object_id: UUID объекта
            user_id: ID пользователя
            name: Наименование документа
            file_data: Данные файла
            
        Returns:
            Кортеж (успех, документ, сообщение об ошибке)
        """
        try:
            # Проверяем существование объекта
            installation_object = await self.repository.get_installation_object_by_id(object_id)
            if not installation_object:
                return False, None, "Объект монтажа не найден"
            
            # Архивация файла
            file_info = await self.archive_manager.archive_installation_file(
                object_id=object_id,
                file_data=file_data,
                file_type='id_document',
                uploaded_by=user_id,
                description=f"Документ ИД: {name}"
            )
            
            # Создание документа
            document = InstallationDocument(
                installation_object_id=object_id,
                name=name,
                document_type='ИД',
                has_file=True,
                file_id=file_info['file_id'],
                created_by=user_id
            )
            
            await self.repository.save_document(document)
            
            # Логирование
            await self.log_manager.log_id_document_action(
                user_id=user_id,
                object_id=object_id,
                object_name=installation_object.full_name,
                document_id=document.id,
                document_name=name,
                action='add',
                details={
                    'file_name': file_info.get('file_name'),
                    'file_size': file_info.get('file_size'),
                    'file_type': file_info.get('file_type')
                }
            )
            
            return True, document, "Документ ИД успешно добавлен"
            
        except Exception as e:
            logger.error(f"Ошибка добавления документа ИД к объекту {object_id}: {e}", exc_info=True)
            return False, None, f"Ошибка добавления документа: {str(e)}"
    
    async def get_id_documents(self, object_id: str) -> List[Dict[str, Any]]:
        """
        Получение списка документов ИД объекта.
        
        Args:
            object_id: UUID объекта
            
        Returns:
            Список документов ИД с дополнительной информацией
        """
        try:
            # Получаем все документы типа 'ИД'
            documents = await self.repository.get_documents_by_type(object_id, 'ИД')
            result = []
            
            for document in documents:
                # Получаем информацию о файле
                file_info = None
                if document.has_file and document.file_id:
                    file_info = await self.archive_manager.get_file_info(document.file_id)
                
                result.append({
                    'id': str(document.id),
                    'name': document.name,
                    'has_file': document.has_file,
                    'file_info': file_info,
                    'created_at': document.created_at.isoformat() if document.created_at else None,
                    'created_by': document.created_by,
                    'updated_at': document.updated_at.isoformat() if document.updated_at else None
                })
            
            # Сортируем по дате создания (новые сначала)
            result.sort(key=lambda x: x['created_at'] or '', reverse=True)
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка получения документов ИД объекта {object_id}: {e}", exc_info=True)
            return []
    
    async def update_id_document(self, document_id: str, user_id: int, name: Optional[str] = None,
                               file_data: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        Обновление документа ИД.
        
        Args:
            document_id: UUID документа
            user_id: ID пользователя
            name: Новое наименование (если нужно обновить)
            file_data: Новый файл (если нужно заменить)
            
        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            document = await self.repository.get_document_by_id(document_id)
            if not document or document.document_type != 'ИД':
                return False, "Документ ИД не найден"
            
            old_data = {
                'name': document.name,
                'has_file': document.has_file,
                'file_id': document.file_id
            }
            
            old_file_id = document.file_id
            
            # Обновление наименования
            if name:
                document.name = name
            
            # Обработка файла
            new_file_info = None
            if file_data:
                # Архивация нового файла
                new_file_info = await self.archive_manager.archive_installation_file(
                    object_id=document.installation_object_id,
                    file_data=file_data,
                    file_type='id_document',
                    uploaded_by=user_id,
                    description=f"Документ ИД (обновление): {name or document.name}"
                )
                
                document.has_file = True
                document.file_id = new_file_info['file_id']
            
            document.updated_at = datetime.now()
            
            await self.repository.save_document(document)
            
            # Удаляем старый файл если он был заменен
            if old_file_id and new_file_info and old_file_id != new_file_info['file_id']:
                await self.archive_manager.delete_file(old_file_id)
            
            # Логирование
            new_data = {}
            if name:
                new_data['name'] = name
            if new_file_info:
                new_data['file_name'] = new_file_info.get('file_name')
                new_data['file_size'] = new_file_info.get('file_size')
            
            await self.log_manager.log_id_document_action(
                user_id=user_id,
                object_id=document.installation_object_id,
                object_name=(await self._get_object_name(document.installation_object_id)),
                document_id=document_id,
                document_name=document.name,
                action='update',
                old_data=old_data,
                new_data=new_data
            )
            
            return True, "Документ ИД успешно обновлен"
            
        except Exception as e:
            logger.error(f"Ошибка обновления документа ИД {document_id}: {e}", exc_info=True)
            return False, f"Ошибка обновления: {str(e)}"
    
    async def delete_id_document(self, document_id: str, user_id: int) -> Tuple[bool, str]:
        """
        Удаление документа ИД.
        
        Args:
            document_id: UUID документа
            user_id: ID пользователя
            
        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            document = await self.repository.get_document_by_id(document_id)
            if not document or document.document_type != 'ИД':
                return False, "Документ ИД не найден"
            
            # Удаляем файл если есть
            if document.has_file and document.file_id:
                await self.archive_manager.delete_file(document.file_id)
            
            # Логирование перед удалением
            await self.log_manager.log_id_document_action(
                user_id=user_id,
                object_id=document.installation_object_id,
                object_name=(await self._get_object_name(document.installation_object_id)),
                document_id=document_id,
                document_name=document.name,
                action='delete',
                details={
                    'name': document.name,
                    'had_file': document.has_file
                }
            )
            
            # Удаление
            await self.repository.delete_document(document_id)
            
            return True, "Документ ИД успешно удален"
            
        except Exception as e:
            logger.error(f"Ошибка удаления документа ИД {document_id}: {e}", exc_info=True)
            return False, f"Ошибка удаления: {str(e)}"
    
    async def get_document_with_file(self, document_id: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Получение документа ИД с информацией о файле для скачивания.
        
        Args:
            document_id: UUID документа
            
        Returns:
            Кортеж (успех, данные документа, сообщение об ошибке)
        """
        try:
            document = await self.repository.get_document_by_id(document_id)
            if not document or document.document_type != 'ИД':
                return False, None, "Документ ИД не найден"
            
            result = {
                'id': str(document.id),
                'name': document.name,
                'document_type': document.document_type,
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
            logger.error(f"Ошибка получения документа ИД {document_id}: {e}", exc_info=True)
            return False, None, f"Ошибка получения: {str(e)}"
    
    async def search_id_documents(self, object_id: str, search_text: str) -> List[Dict[str, Any]]:
        """
        Поиск документов ИД по наименованию.
        
        Args:
            object_id: UUID объекта
            search_text: Текст для поиска
            
        Returns:
            Список найденных документов
        """
        try:
            if not search_text or len(search_text.strip()) < 2:
                return []
            
            search_text = search_text.strip().lower()
            documents = await self.repository.get_documents_by_type(object_id, 'ИД')
            
            result = []
            for document in documents:
                if search_text in document.name.lower():
                    result.append({
                        'id': str(document.id),
                        'name': document.name,
                        'has_file': document.has_file,
                        'created_at': document.created_at.isoformat() if document.created_at else None,
                        'created_by': document.created_by
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка поиска документов ИД объекта {object_id}: {e}", exc_info=True)
            return []
    
    # ========== Вспомогательные методы ==========
    
    async def _get_object_name(self, object_id: str) -> str:
        """Получение названия объекта."""
        try:
            installation_object = await self.repository.get_installation_object_by_id(object_id)
            return installation_object.full_name if installation_object else ""
        except Exception:
            return ""