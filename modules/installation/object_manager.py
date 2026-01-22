"""
Менеджер объектов монтажа.
Реализует бизнес-логику работы с объектами монтажа согласно ТЗ.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from storage.models.installation import (
    InstallationObject, InstallationProject, InstallationMaterial,
    InstallationMaterialSection, InstallationMontage,
    InstallationSupply, InstallationChange, InstallationDocument,
    InstallationGroupBinding
)
from storage.repositories.installation_repository import InstallationRepository
from modules.file.archive_manager import ArchiveManager
from modules.admin.log_manager import LogManager
from utils.date_utils import parse_date, format_date
from .validators import InstallationObjectCreateData, AdditionalDocumentData

logger = logging.getLogger(__name__)


class InstallationObjectManager:
    """Менеджер объектов монтажа."""
    
    def __init__(self, context):
        self.context = context
        self.repository = InstallationRepository(context.db_session)
        self.archive_manager = ArchiveManager(context)
        self.log_manager = LogManager(context)
    
    async def create_object(self, user_id: int, data: Dict[str, Any]) -> Tuple[bool, Optional[InstallationObject], str]:
        """
        Создание нового объекта монтажа.
        
        Args:
            user_id: ID пользователя-создателя
            data: Данные объекта
            
        Returns:
            Кортеж (успех, объект, сообщение об ошибке)
        """
        try:
            # Валидация данных
            success, validated_data, error = self.validators.validate('installation_object', data)
            if not success:
                return False, None, error
            
            # Создание объекта
            installation_object = InstallationObject(
                short_name=validated_data.short_name,
                full_name=validated_data.full_name,
                contract_type=validated_data.contract_type,
                contract_number=validated_data.contract_number,
                contract_date=parse_date(validated_data.contract_date),
                start_date=parse_date(validated_data.start_date),
                end_date=parse_date(validated_data.end_date),
                systems=validated_data.systems,
                notes=validated_data.notes or '',
                created_by=user_id,
                updated_by=user_id
            )
            
            # Добавление адресов
            for address in validated_data.addresses:
                installation_object.add_address(address)
            
            # Добавление дополнительных соглашений
            for doc_data in validated_data.additional_documents:
                document = InstallationDocument(
                    document_type=doc_data.document_type,
                    document_number=doc_data.number,
                    document_date=parse_date(doc_data.date),
                    start_date=parse_date(doc_data.start_date) if doc_data.start_date else None,
                    end_date=parse_date(doc_data.end_date) if doc_data.end_date else None,
                    description=doc_data.description,
                    created_by=user_id
                )
                installation_object.documents.append(document)
            
            # Сохранение в БД
            await self.repository.save_installation_object(installation_object)
            
            # Логирование создания
            await self.log_manager.log_object_creation(
                user_id=user_id,
                object_type='installation',
                object_id=installation_object.id,
                object_name=installation_object.full_name,
                details=data
            )
            
            return True, installation_object, "Объект монтажа успешно создан"
            
        except Exception as e:
            logger.error(f"Ошибка создания объекта монтажа: {e}", exc_info=True)
            return False, None, f"Ошибка создания объекта: {str(e)}"
    
    async def get_object_by_id(self, object_id: str) -> Optional[InstallationObject]:
        """
        Получение объекта монтажа по ID.
        
        Args:
            object_id: UUID объекта
            
        Returns:
            Объект InstallationObject или None
        """
        return await self.repository.get_installation_object_by_id(object_id)
    
    async def get_user_objects(self, user_id: int) -> List[InstallationObject]:
        """
        Получение объектов монтажа пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Список объектов InstallationObject
        """
        return await self.repository.get_installation_objects_by_user(user_id)
    
    async def update_object(self, object_id: str, user_id: int, data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Обновление данных объекта монтажа.
        
        Args:
            object_id: UUID объекта
            user_id: ID пользователя
            data: Новые данные
            
        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            object_to_update = await self.get_object_by_id(object_id)
            if not object_to_update:
                return False, "Объект не найден"
            
            old_data = {
                'short_name': object_to_update.short_name,
                'full_name': object_to_update.full_name,
                'contract_number': object_to_update.contract_number,
                'end_date': format_date(object_to_update.end_date) if object_to_update.end_date else None,
                'notes': object_to_update.notes
            }
            
            # Обновление полей
            if 'short_name' in data:
                object_to_update.short_name = data['short_name']
            if 'full_name' in data:
                object_to_update.full_name = data['full_name']
            if 'contract_number' in data:
                object_to_update.contract_number = data['contract_number']
            if 'end_date' in data and data['end_date']:
                object_to_update.end_date = parse_date(data['end_date'])
            if 'notes' in data:
                object_to_update.notes = data['notes']
            
            object_to_update.updated_by = user_id
            object_to_update.updated_at = datetime.now()
            
            await self.repository.save_installation_object(object_to_update)
            
            # Логирование изменений
            new_data = {k: data.get(k) for k in old_data.keys() if k in data}
            if new_data:
                await self.log_manager.log_object_update(
                    user_id=user_id,
                    object_type='installation',
                    object_id=object_id,
                    object_name=object_to_update.full_name,
                    old_data=old_data,
                    new_data=new_data
                )
            
            return True, "Объект успешно обновлен"
            
        except Exception as e:
            logger.error(f"Ошибка обновления объекта монтажа {object_id}: {e}", exc_info=True)
            return False, f"Ошибка обновления: {str(e)}"
    
    async def delete_object(self, object_id: str, user_id: int) -> Tuple[bool, str]:
        """
        Удаление объекта монтажа с архивацией.
        
        Args:
            object_id: UUID объекта
            user_id: ID пользователя
            
        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            object_to_delete = await self.get_object_by_id(object_id)
            if not object_to_delete:
                return False, "Объект не найден"
            
            # Архивирование данных
            archive_data = await self._prepare_archive_data(object_to_delete)
            
            # Отправка в архив
            await self.archive_manager.archive_installation_object(archive_data, user_id)
            
            # Логирование удаления
            await self.log_manager.log_object_deletion(
                user_id=user_id,
                object_type='installation',
                object_id=object_id,
                object_name=object_to_delete.full_name,
                details=archive_data
            )
            
            # Удаление из БД
            await self.repository.delete_installation_object(object_id)
            
            return True, "Объект успешно удален и заархивирован"
            
        except Exception as e:
            logger.error(f"Ошибка удаления объекта монтажа {object_id}: {e}", exc_info=True)
            return False, f"Ошибка удаления: {str(e)}"
    
    async def _prepare_archive_data(self, installation_object: InstallationObject) -> Dict[str, Any]:
        """
        Подготовка данных объекта для архивации.
        
        Args:
            installation_object: Объект монтажа
            
        Returns:
            Словарь с данными для архивации
        """
        return {
            'id': str(installation_object.id),
            'short_name': installation_object.short_name,
            'full_name': installation_object.full_name,
            'contract_type': installation_object.contract_type,
            'contract_number': installation_object.contract_number,
            'contract_date': format_date(installation_object.contract_date) if installation_object.contract_date else None,
            'start_date': format_date(installation_object.start_date) if installation_object.start_date else None,
            'end_date': format_date(installation_object.end_date) if installation_object.end_date else None,
            'systems': installation_object.systems,
            'notes': installation_object.notes,
            'created_at': installation_object.created_at.isoformat() if installation_object.created_at else None,
            'created_by': installation_object.created_by,
            'addresses': [{'address': addr.address, 'order_index': addr.order_index} 
                         for addr in installation_object.addresses],
            'documents': [{
                'document_type': doc.document_type,
                'document_number': doc.document_number,
                'document_date': format_date(doc.document_date) if doc.document_date else None,
                'start_date': format_date(doc.start_date) if doc.start_date else None,
                'end_date': format_date(doc.end_date) if doc.end_date else None,
                'description': doc.description
            } for doc in installation_object.documents],
            # Подразделы будут добавлены при полной архивации
        }
    
    async def bind_to_group(self, object_id: str, chat_id: int, user_id: int) -> Tuple[bool, str]:
        """
        Привязка объекта монтажа к группе.
        
        Args:
            object_id: UUID объекта
            chat_id: ID чата/группы
            user_id: ID пользователя
            
        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            binding = InstallationGroupBinding(
                installation_object_id=object_id,
                chat_id=chat_id,
                created_by=user_id
            )
            
            await self.repository.save_group_binding(binding)
            
            await self.log_manager.log_group_binding(
                user_id=user_id,
                chat_id=chat_id,
                object_type='installation',
                object_id=object_id,
                action='bind'
            )
            
            return True, "Объект успешно привязан к группе"
            
        except Exception as e:
            logger.error(f"Ошибка привязки объекта {object_id} к группе {chat_id}: {e}", exc_info=True)
            return False, f"Ошибка привязки: {str(e)}"
    
    async def unbind_from_group(self, object_id: str, chat_id: int, user_id: int) -> Tuple[bool, str]:
        """
        Отвязка объекта монтажа от группы.
        
        Args:
            object_id: UUID объекта
            chat_id: ID чата/группы
            user_id: ID пользователя
            
        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            success = await self.repository.delete_group_binding(object_id, chat_id)
            
            if success:
                await self.log_manager.log_group_binding(
                    user_id=user_id,
                    chat_id=chat_id,
                    object_type='installation',
                    object_id=object_id,
                    action='unbind'
                )
                return True, "Объект успешно отвязан от группы"
            else:
                return False, "Привязка не найдена"
            
        except Exception as e:
            logger.error(f"Ошибка отвязки объекта {object_id} от группы {chat_id}: {e}", exc_info=True)
            return False, f"Ошибка отвязки: {str(e)}"
    
    async def get_group_objects(self, chat_id: int) -> List[InstallationObject]:
        """
        Получение объектов монтажа, привязанных к группе.
        
        Args:
            chat_id: ID чата/группы
            
        Returns:
            Список объектов InstallationObject
        """
        return await self.repository.get_installation_objects_by_chat(chat_id)