"""
Менеджер учета монтажа.
Отслеживание установленных количеств материалов по разделам.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from storage.models.installation import InstallationMontage, InstallationMaterialSection
from storage.repositories.installation_repository import InstallationRepository
from modules.admin.log_manager import LogManager

logger = logging.getLogger(__name__)


class MontageManager:
    """Менеджер учета монтажа."""
    
    def __init__(self, context):
        self.context = context
        self.repository = InstallationRepository(context.db_session)
        self.log_manager = LogManager(context)
    
    async def track_montage(self, section_id: str, material_id: str, installed_quantity: float, user_id: int) -> Tuple[bool, Optional[InstallationMontage], str]:
        """
        Учет установленного материала.
        
        Args:
            section_id: UUID раздела
            material_id: UUID материала
            installed_quantity: Установленное количество
            user_id: ID пользователя
            
        Returns:
            Кортеж (успех, запись монтажа, сообщение об ошибке)
        """
        try:
            # Проверяем существование раздела и материала
            section = await self.repository.get_material_section_by_id(section_id)
            if not section:
                return False, None, "Раздел не найден"
            
            material = await self.repository.get_material_by_id(material_id)
            if not material:
                return False, None, "Материал не найден"
            
            # Проверяем распределение материала в разделе
            allocation = await self.repository.get_material_allocation(material_id, section_id)
            if not allocation:
                return False, None, "Материал не распределен в этот раздел"
            
            # Получаем текущий учет монтажа для этого материала в разделе
            existing_montage = await self.repository.get_montage_by_allocation(allocation.id)
            
            if existing_montage:
                # Обновляем существующую запись
                old_quantity = existing_montage.installed_quantity
                existing_montage.installed_quantity = installed_quantity
                existing_montage.updated_at = datetime.now()
                existing_montage.updated_by = user_id
                
                await self.repository.save_montage(existing_montage)
                montage_record = existing_montage
                
                # Логирование обновления
                await self._log_montage_update(user_id, section, material, old_quantity, installed_quantity)
                
            else:
                # Создаем новую запись
                montage_record = InstallationMontage(
                    material_allocation_id=allocation.id,
                    installed_quantity=installed_quantity,
                    created_by=user_id
                )
                
                await self.repository.save_montage(montage_record)
                
                # Логирование создания
                await self._log_montage_creation(user_id, section, material, installed_quantity)
            
            return True, montage_record, "Учет монтажа успешно обновлен"
            
        except Exception as e:
            logger.error(f"Ошибка учета монтажа для материала {material_id} в разделе {section_id}: {e}", exc_info=True)
            return False, None, f"Ошибка учета монтажа: {str(e)}"
    
    async def get_section_montage(self, section_id: str) -> List[Dict[str, Any]]:
        """
        Получение учета монтажа для раздела.
        
        Args:
            section_id: UUID раздела
            
        Returns:
            Список материалов с учетом монтажа
        """
        try:
            # Получаем все распределения материалов в разделе
            allocations = await self.repository.get_material_allocations_by_section(section_id)
            result = []
            
            for allocation in allocations:
                material = await self.repository.get_material_by_id(allocation.material_id)
                if not material:
                    continue
                
                # Получаем учет монтажа для этого распределения
                montage = await self.repository.get_montage_by_allocation(allocation.id)
                installed_quantity = montage.installed_quantity if montage else 0.0
                
                # Рассчитываем прогресс
                allocated_quantity = allocation.quantity
                if allocated_quantity > 0:
                    progress_percent = (installed_quantity / allocated_quantity) * 100
                else:
                    progress_percent = 0.0
                
                # Определяем статус
                if installed_quantity >= allocated_quantity:
                    status = 'completed'
                elif installed_quantity > 0:
                    status = 'in_progress'
                else:
                    status = 'not_started'
                
                result.append({
                    'material_id': str(material.id),
                    'material_name': material.name,
                    'unit': material.unit,
                    'allocated_quantity': allocated_quantity,
                    'installed_quantity': installed_quantity,
                    'remaining': allocated_quantity - installed_quantity,
                    'progress_percent': round(progress_percent, 1),
                    'status': status,
                    'montage_id': str(montage.id) if montage else None,
                    'last_updated': montage.updated_at.isoformat() if montage and montage.updated_at else None
                })
            
            # Сортируем по статусу и названию
            result.sort(key=lambda x: (x['status'] != 'completed', x['material_name']))
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка получения учета монтажа для раздела {section_id}: {e}", exc_info=True)
            return []
    
    async def get_object_montage_summary(self, object_id: str) -> Dict[str, Any]:
        """
        Получение сводки по монтажу для всего объекта.
        
        Args:
            object_id: UUID объекта
            
        Returns:
            Словарь со сводной информацией
        """
        try:
            sections = await self.repository.get_material_sections_by_object(object_id)
            total_sections = len(sections)
            
            summary = {
                'total_sections': total_sections,
                'sections': [],
                'overall_progress': 0.0,
                'total_materials': 0,
                'completed_materials': 0,
                'in_progress_materials': 0,
                'not_started_materials': 0
            }
            
            total_allocated = 0.0
            total_installed = 0.0
            
            for section in sections:
                section_montage = await self.get_section_montage(str(section.id))
                
                section_allocated = sum([item['allocated_quantity'] for item in section_montage])
                section_installed = sum([item['installed_quantity'] for item in section_montage])
                
                if section_allocated > 0:
                    section_progress = (section_installed / section_allocated) * 100
                else:
                    section_progress = 0.0
                
                # Статистика по материалам раздела
                section_stats = {
                    'completed': sum(1 for item in section_montage if item['status'] == 'completed'),
                    'in_progress': sum(1 for item in section_montage if item['status'] == 'in_progress'),
                    'not_started': sum(1 for item in section_montage if item['status'] == 'not_started')
                }
                
                summary['sections'].append({
                    'section_id': str(section.id),
                    'section_name': section.name,
                    'material_count': len(section_montage),
                    'allocated_quantity': section_allocated,
                    'installed_quantity': section_installed,
                    'progress_percent': round(section_progress, 1),
                    'stats': section_stats
                })
                
                total_allocated += section_allocated
                total_installed += section_installed
                
                # Обновляем общую статистику
                summary['total_materials'] += len(section_montage)
                summary['completed_materials'] += section_stats['completed']
                summary['in_progress_materials'] += section_stats['in_progress']
                summary['not_started_materials'] += section_stats['not_started']
            
            # Рассчитываем общий прогресс
            if total_allocated > 0:
                summary['overall_progress'] = round((total_installed / total_allocated) * 100, 1)
            
            return summary
            
        except Exception as e:
            logger.error(f"Ошибка получения сводки по монтажу объекта {object_id}: {e}", exc_info=True)
            return {'error': str(e)}
    
    async def reset_montage(self, section_id: str, user_id: int) -> Tuple[bool, str]:
        """
        Сброс учета монтажа для раздела.
        
        Args:
            section_id: UUID раздела
            user_id: ID пользователя
            
        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            section = await self.repository.get_material_section_by_id(section_id)
            if not section:
                return False, "Раздел не найден"
            
            # Получаем все распределения в разделе
            allocations = await self.repository.get_material_allocations_by_section(section_id)
            reset_count = 0
            
            for allocation in allocations:
                montage = await self.repository.get_montage_by_allocation(allocation.id)
                if montage:
                    # Логирование перед удалением
                    material = await self.repository.get_material_by_id(allocation.material_id)
                    if material:
                        await self._log_montage_reset(user_id, section, material, montage.installed_quantity)
                    
                    # Удаление записи монтажа
                    await self.repository.delete_montage(montage.id)
                    reset_count += 1
            
            return True, f"Учет монтажа сброшен для {reset_count} материалов"
            
        except Exception as e:
            logger.error(f"Ошибка сброса учета монтажа для раздела {section_id}: {e}", exc_info=True)
            return False, f"Ошибка сброса: {str(e)}"
    
    async def get_montage_history(self, object_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Получение истории изменений учета монтажа.
        
        Args:
            object_id: UUID объекта
            limit: Максимальное количество записей
            
        Returns:
            Список записей истории
        """
        try:
            # Здесь можно реализовать получение истории из логов
            # Временная реализация через логи менеджера
            return []  # Заглушка для будущей реализации
            
        except Exception as e:
            logger.error(f"Ошибка получения истории монтажа объекта {object_id}: {e}", exc_info=True)
            return []
    
    # ========== Вспомогательные методы ==========
    
    async def _log_montage_creation(self, user_id: int, section: InstallationMaterialSection, 
                                   material, installed_quantity: float):
        """Логирование создания записи монтажа."""
        try:
            await self.log_manager.log_montage_action(
                user_id=user_id,
                object_id=section.installation_object_id,
                object_name=(await self._get_object_name(section.installation_object_id)),
                section_id=str(section.id),
                section_name=section.name,
                material_id=str(material.id),
                material_name=material.name,
                action='track',
                details={
                    'installed_quantity': installed_quantity,
                    'unit': material.unit
                }
            )
        except Exception as e:
            logger.error(f"Ошибка логирования создания монтажа: {e}")
    
    async def _log_montage_update(self, user_id: int, section: InstallationMaterialSection, 
                                 material, old_quantity: float, new_quantity: float):
        """Логирование обновления записи монтажа."""
        try:
            await self.log_manager.log_montage_action(
                user_id=user_id,
                object_id=section.installation_object_id,
                object_name=(await self._get_object_name(section.installation_object_id)),
                section_id=str(section.id),
                section_name=section.name,
                material_id=str(material.id),
                material_name=material.name,
                action='update',
                details={
                    'old_quantity': old_quantity,
                    'new_quantity': new_quantity,
                    'unit': material.unit
                }
            )
        except Exception as e:
            logger.error(f"Ошибка логирования обновления монтажа: {e}")
    
    async def _log_montage_reset(self, user_id: int, section: InstallationMaterialSection, 
                                material, reset_quantity: float):
        """Логирование сброса монтажа."""
        try:
            await self.log_manager.log_montage_action(
                user_id=user_id,
                object_id=section.installation_object_id,
                object_name=(await self._get_object_name(section.installation_object_id)),
                section_id=str(section.id),
                section_name=section.name,
                material_id=str(material.id),
                material_name=material.name,
                action='reset',
                details={
                    'reset_quantity': reset_quantity,
                    'unit': material.unit
                }
            )
        except Exception as e:
            logger.error(f"Ошибка логирования сброса монтажа: {e}")
    
    async def _get_object_name(self, object_id: str) -> str:
        """Получение названия объекта."""
        try:
            installation_object = await self.repository.get_installation_object_by_id(object_id)
            return installation_object.full_name if installation_object else ""
        except Exception:
            return ""