"""
Менеджер изменений в проектах.
Управление изменениями в проектах монтажа с прикреплением файлов.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from storage.models.installation import InstallationChange
from storage.repositories.installation_repository import InstallationRepository
from modules.file.archive_manager import ArchiveManager
from modules.admin.log_manager import LogManager

logger = logging.getLogger(__name__)


class ChangeManager:
    """Менеджер изменений в проектах."""
    
    def __init__(self, context):
        self.context = context
        self.repository = InstallationRepository(context.db_session)
        self.archive_manager = ArchiveManager(context)
        self.log_manager = LogManager(context)
    
    async def add_change(self, object_id: str, user_id: int, data: Dict[str, Any], 
                        file_data: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[InstallationChange], str]:
        """
        Добавление изменения в проект.
        
        Args:
            object_id: UUID объекта
            user_id: ID пользователя
            data: Данные изменения
            file_data: Данные файла (если есть)
            
        Returns:
            Кортеж (успех, изменение, сообщение об ошибке)
        """
        try:
            # Проверяем существование объекта
            installation_object = await self.repository.get_installation_object_by_id(object_id)
            if not installation_object:
                return False, None, "Объект монтажа не найден"
            
            # Архивация файла если есть
            file_info = None
            if file_data:
                file_info = await self.archive_manager.archive_installation_file(
                    object_id=object_id,
                    file_data=file_data,
                    file_type='change',
                    uploaded_by=user_id,
                    description=f"Файл изменения: {data.get('description', '')[:100]}"
                )
            
            # Создание изменения
            change = InstallationChange(
                installation_object_id=object_id,
                description=data['description'],
                has_file=file_info is not None,
                file_id=file_info['file_id'] if file_info else None,
                created_by=user_id
            )
            
            await self.repository.save_change(change)
            
            # Логирование
            log_details = {
                'description': data['description'],
                'has_file': file_info is not None
            }
            if file_info:
                log_details['file_name'] = file_info.get('file_name')
                log_details['file_size'] = file_info.get('file_size')
            
            await self.log_manager.log_change_action(
                user_id=user_id,
                object_id=object_id,
                object_name=installation_object.full_name,
                change_id=change.id,
                action='add',
                details=log_details
            )
            
            return True, change, "Изменение успешно добавлено"
            
        except Exception as e:
            logger.error(f"Ошибка добавления изменения к объекту {object_id}: {e}", exc_info=True)
            return False, None, f"Ошибка добавления изменения: {str(e)}"
    
    async def get_changes(self, object_id: str) -> List[Dict[str, Any]]:
        """
        Получение списка изменений объекта.
        
        Args:
            object_id: UUID объекта
            
        Returns:
            Список изменений с дополнительной информацией
        """
        try:
            changes = await self.repository.get_changes_by_object(object_id)
            result = []
            
            for change in changes:
                # Получаем информацию о файле если есть
                file_info = None
                if change.has_file and change.file_id:
                    file_info = await self.archive_manager.get_file_info(change.file_id)
                
                result.append({
                    'id': str(change.id),
                    'description': change.description,
                    'has_file': change.has_file,
                    'file_info': file_info,
                    'created_at': change.created_at.isoformat() if change.created_at else None,
                    'created_by': change.created_by,
                    'updated_at': change.updated_at.isoformat() if change.updated_at else None
                })
            
            # Сортируем по дате создания (новые сначала)
            result.sort(key=lambda x: x['created_at'] or '', reverse=True)
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка получения изменений объекта {object_id}: {e}", exc_info=True)
            return []
    
    async def update_change(self, change_id: str, user_id: int, data: Dict[str, Any],
                           file_data: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        Обновление изменения.
        
        Args:
            change_id: UUID изменения
            user_id: ID пользователя
            data: Новые данные
            file_data: Новый файл (если есть)
            
        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            change = await self.repository.get_change_by_id(change_id)
            if not change:
                return False, "Изменение не найдено"
            
            old_data = {
                'description': change.description,
                'has_file': change.has_file,
                'file_id': change.file_id
            }
            
            old_file_id = change.file_id
            
            # Обновление полей
            if 'description' in data:
                change.description = data['description']
            
            # Обработка файла
            new_file_info = None
            if file_data:
                # Архивация нового файла
                new_file_info = await self.archive_manager.archive_installation_file(
                    object_id=change.installation_object_id,
                    file_data=file_data,
                    file_type='change',
                    uploaded_by=user_id,
                    description=f"Файл изменения (обновление): {data.get('description', change.description)[:100]}"
                )
                
                change.has_file = True
                change.file_id = new_file_info['file_id']
            
            # Если файл удален
            elif 'remove_file' in data and data['remove_file']:
                change.has_file = False
                change.file_id = None
            
            change.updated_at = datetime.now()
            
            await self.repository.save_change(change)
            
            # Удаляем старый файл если он был заменен
            if old_file_id and new_file_info and old_file_id != new_file_info['file_id']:
                await self.archive_manager.delete_file(old_file_id)
            
            # Логирование
            new_data = {k: data.get(k) for k in old_data.keys() if k in data}
            if new_file_info:
                new_data['file_name'] = new_file_info.get('file_name')
                new_data['file_size'] = new_file_info.get('file_size')
            
            await self.log_manager.log_change_action(
                user_id=user_id,
                object_id=change.installation_object_id,
                object_name=(await self._get_object_name(change.installation_object_id)),
                change_id=change_id,
                action='update',
                old_data=old_data,
                new_data=new_data
            )
            
            return True, "Изменение успешно обновлено"
            
        except Exception as e:
            logger.error(f"Ошибка обновления изменения {change_id}: {e}", exc_info=True)
            return False, f"Ошибка обновления: {str(e)}"
    
    async def delete_change(self, change_id: str, user_id: int) -> Tuple[bool, str]:
        """
        Удаление изменения.
        
        Args:
            change_id: UUID изменения
            user_id: ID пользователя
            
        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            change = await self.repository.get_change_by_id(change_id)
            if not change:
                return False, "Изменение не найдено"
            
            # Удаляем файл если есть
            if change.has_file and change.file_id:
                await self.archive_manager.delete_file(change.file_id)
            
            # Логирование перед удалением
            await self.log_manager.log_change_action(
                user_id=user_id,
                object_id=change.installation_object_id,
                object_name=(await self._get_object_name(change.installation_object_id)),
                change_id=change_id,
                action='delete',
                details={
                    'description': change.description,
                    'had_file': change.has_file
                }
            )
            
            # Удаление
            await self.repository.delete_change(change_id)
            
            return True, "Изменение успешно удалено"
            
        except Exception as e:
            logger.error(f"Ошибка удаления изменения {change_id}: {e}", exc_info=True)
            return False, f"Ошибка удаления: {str(e)}"
    
    async def get_change_with_file(self, change_id: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Получение изменения с информацией о файле для скачивания.
        
        Args:
            change_id: UUID изменения
            
        Returns:
            Кортеж (успех, данные изменения, сообщение об ошибке)
        """
        try:
            change = await self.repository.get_change_by_id(change_id)
            if not change:
                return False, None, "Изменение не найдено"
            
            result = {
                'id': str(change.id),
                'description': change.description,
                'has_file': change.has_file,
                'created_at': change.created_at.isoformat() if change.created_at else None,
                'created_by': change.created_by
            }
            
            # Получаем информацию о файле если есть
            if change.has_file and change.file_id:
                file_info = await self.archive_manager.get_file_info(change.file_id)
                if file_info:
                    result['file_info'] = file_info
                    result['download_url'] = await self.archive_manager.get_file_download_url(change.file_id)
            
            return True, result, ""
            
        except Exception as e:
            logger.error(f"Ошибка получения изменения {change_id}: {e}", exc_info=True)
            return False, None, f"Ошибка получения: {str(e)}"
    
    async def search_changes(self, object_id: str, search_text: str) -> List[Dict[str, Any]]:
        """
        Поиск изменений по тексту.
        
        Args:
            object_id: UUID объекта
            search_text: Текст для поиска
            
        Returns:
            Список найденных изменений
        """
        try:
            if not search_text or len(search_text.strip()) < 2:
                return []
            
            search_text = search_text.strip().lower()
            changes = await self.repository.get_changes_by_object(object_id)
            
            result = []
            for change in changes:
                if search_text in change.description.lower():
                    result.append({
                        'id': str(change.id),
                        'description': change.description,
                        'has_file': change.has_file,
                        'created_at': change.created_at.isoformat() if change.created_at else None,
                        'created_by': change.created_by
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка поиска изменений объекта {object_id}: {e}", exc_info=True)
            return []
    
    # ========== Вспомогательные методы ==========
    
    async def _get_object_name(self, object_id: str) -> str:
        """Получение названия объекта."""
        try:
            installation_object = await self.repository.get_installation_object_by_id(object_id)
            return installation_object.full_name if installation_object else ""
        except Exception:
            return ""