"""
Менеджер материалов монтажа.
Управление материалами, разделами и проверка соответствия количеств.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime

from storage.models.installation import (
    InstallationObject, InstallationMaterial, InstallationMaterialSection,
    InstallationMaterialQuantity
)
from storage.repositories.installation_repository import InstallationRepository
from utils.date_utils import format_date
from modules.admin.log_manager import LogManager

logger = logging.getLogger(__name__)


class MaterialManager:
    """Менеджер материалов монтажа."""
    
    def __init__(self, context):
        self.context = context
        self.repository = InstallationRepository(context.db_session)
        self.log_manager = LogManager(context)
    
    # ========== Общие материалы ==========
    
    async def add_material(self, object_id: str, user_id: int, data: Dict[str, Any]) -> Tuple[bool, Optional[InstallationMaterial], str]:
        """
        Добавление материала к объекту монтажа.
        
        Args:
            object_id: UUID объекта
            user_id: ID пользователя
            data: Данные материала
            
        Returns:
            Кортеж (успех, материал, сообщение об ошибке)
        """
        try:
            # Получение объекта
            installation_object = await self.repository.get_installation_object_by_id(object_id)
            if not installation_object:
                return False, None, "Объект монтажа не найден"
            
            # Создание материала
            material = InstallationMaterial(
                installation_object_id=object_id,
                name=data['name'],
                quantity=data['quantity'],
                unit=data['unit'],
                description=data.get('description', ''),
                created_by=user_id
            )
            
            await self.repository.save_material(material)
            
            # Логирование
            await self.log_manager.log_material_action(
                user_id=user_id,
                object_id=object_id,
                object_name=installation_object.full_name,
                material_id=material.id,
                material_name=material.name,
                action='add',
                details=data
            )
            
            return True, material, "Материал успешно добавлен"
            
        except Exception as e:
            logger.error(f"Ошибка добавления материала к объекту {object_id}: {e}", exc_info=True)
            return False, None, f"Ошибка добавления материала: {str(e)}"
    
    async def get_materials(self, object_id: str, include_sections: bool = False) -> List[Dict[str, Any]]:
        """
        Получение списка материалов объекта.
        
        Args:
            object_id: UUID объекта
            include_sections: Включать ли информацию о разделах
            
        Returns:
            Список материалов с дополнительной информацией
        """
        try:
            materials = await self.repository.get_materials_by_object(object_id)
            result = []
            
            for material in materials:
                material_data = {
                    'id': str(material.id),
                    'name': material.name,
                    'quantity': material.quantity,
                    'unit': material.unit,
                    'description': material.description,
                    'total_allocated': 0.0,
                    'remaining': material.quantity
                }
                
                if include_sections:
                    # Получаем количество материала в разделах
                    allocations = await self.repository.get_material_allocations(material.id)
                    allocated_quantity = sum([alloc.quantity for alloc in allocations])
                    
                    material_data['total_allocated'] = allocated_quantity
                    material_data['remaining'] = material.quantity - allocated_quantity
                    
                    # Получаем информацию о разделах
                    section_allocations = []
                    for alloc in allocations:
                        section = await self.repository.get_material_section_by_id(alloc.material_section_id)
                        if section:
                            section_allocations.append({
                                'section_id': str(section.id),
                                'section_name': section.name,
                                'allocated_quantity': alloc.quantity
                            })
                    
                    material_data['section_allocations'] = section_allocations
                
                result.append(material_data)
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка получения материалов объекта {object_id}: {e}", exc_info=True)
            return []
    
    async def update_material(self, material_id: str, user_id: int, data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Обновление материала.
        
        Args:
            material_id: UUID материала
            user_id: ID пользователя
            data: Новые данные
            
        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            material = await self.repository.get_material_by_id(material_id)
            if not material:
                return False, "Материал не найден"
            
            old_data = {
                'name': material.name,
                'quantity': material.quantity,
                'unit': material.unit,
                'description': material.description
            }
            
            # Обновление полей
            if 'name' in data:
                material.name = data['name']
            if 'quantity' in data:
                # Проверяем, что новое количество не меньше уже распределенного
                allocations = await self.repository.get_material_allocations(material_id)
                allocated_quantity = sum([alloc.quantity for alloc in allocations])
                
                new_quantity = float(data['quantity'])
                if new_quantity < allocated_quantity:
                    return False, f"Новое количество ({new_quantity}) меньше уже распределенного ({allocated_quantity})"
                
                material.quantity = new_quantity
            if 'unit' in data:
                material.unit = data['unit']
            if 'description' in data:
                material.description = data['description']
            
            material.updated_at = datetime.now()
            
            await self.repository.save_material(material)
            
            # Логирование
            new_data = {k: data.get(k) for k in old_data.keys() if k in data}
            if new_data:
                await self.log_manager.log_material_action(
                    user_id=user_id,
                    object_id=material.installation_object_id,
                    object_name=(await self._get_object_name(material.installation_object_id)),
                    material_id=material_id,
                    material_name=material.name,
                    action='update',
                    old_data=old_data,
                    new_data=new_data
                )
            
            return True, "Материал успешно обновлен"
            
        except Exception as e:
            logger.error(f"Ошибка обновления материала {material_id}: {e}", exc_info=True)
            return False, f"Ошибка обновления: {str(e)}"
    
    async def delete_material(self, material_id: str, user_id: int) -> Tuple[bool, str]:
        """
        Удаление материала.
        
        Args:
            material_id: UUID материала
            user_id: ID пользователя
            
        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            material = await self.repository.get_material_by_id(material_id)
            if not material:
                return False, "Материал не найден"
            
            # Проверяем, что материал не используется в разделах
            allocations = await self.repository.get_material_allocations(material_id)
            if allocations:
                return False, "Невозможно удалить материал: он используется в разделах"
            
            # Логирование перед удалением
            await self.log_manager.log_material_action(
                user_id=user_id,
                object_id=material.installation_object_id,
                object_name=(await self._get_object_name(material.installation_object_id)),
                material_id=material_id,
                material_name=material.name,
                action='delete',
                details={'quantity': material.quantity, 'unit': material.unit}
            )
            
            # Удаление
            await self.repository.delete_material(material_id)
            
            return True, "Материал успешно удален"
            
        except Exception as e:
            logger.error(f"Ошибка удаления материала {material_id}: {e}", exc_info=True)
            return False, f"Ошибка удаления: {str(e)}"
    
    # ========== Разделы материалов ==========
    
    async def create_section(self, object_id: str, user_id: int, name: str) -> Tuple[bool, Optional[InstallationMaterialSection], str]:
        """
        Создание раздела материалов.
        
        Args:
            object_id: UUID объекта
            user_id: ID пользователя
            name: Название раздела
            
        Returns:
            Кортеж (успех, раздел, сообщение об ошибке)
        """
        try:
            # Проверяем существование объекта
            installation_object = await self.repository.get_installation_object_by_id(object_id)
            if not installation_object:
                return False, None, "Объект монтажа не найден"
            
            # Создание раздела
            section = InstallationMaterialSection(
                installation_object_id=object_id,
                name=name,
                created_by=user_id
            )
            
            await self.repository.save_material_section(section)
            
            # Логирование
            await self.log_manager.log_section_action(
                user_id=user_id,
                object_id=object_id,
                object_name=installation_object.full_name,
                section_id=section.id,
                section_name=name,
                action='create'
            )
            
            return True, section, "Раздел успешно создан"
            
        except Exception as e:
            logger.error(f"Ошибка создания раздела для объекта {object_id}: {e}", exc_info=True)
            return False, None, f"Ошибка создания раздела: {str(e)}"
    
    async def get_sections(self, object_id: str) -> List[InstallationMaterialSection]:
        """
        Получение разделов материалов объекта.
        
        Args:
            object_id: UUID объекта
            
        Returns:
            Список разделов
        """
        return await self.repository.get_material_sections_by_object(object_id)
    
    async def add_materials_to_section(self, section_id: str, material_data: List[Dict[str, Any]], user_id: int) -> Tuple[bool, str]:
        """
        Добавление материалов в раздел.
        
        Args:
            section_id: UUID раздела
            material_data: Список данных материалов [{'material_id': '...', 'quantity': 10.0}]
            user_id: ID пользователя
            
        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            section = await self.repository.get_material_section_by_id(section_id)
            if not section:
                return False, "Раздел не найден"
            
            added_materials = []
            
            for item in material_data:
                material_id = item['material_id']
                quantity = float(item['quantity'])
                
                # Получаем материал
                material = await self.repository.get_material_by_id(material_id)
                if not material:
                    return False, f"Материал {material_id} не найден"
                
                # Проверяем доступное количество
                allocations = await self.repository.get_material_allocations(material_id)
                total_allocated = sum([alloc.quantity for alloc in allocations if str(alloc.material_section_id) != section_id])
                available = material.quantity - total_allocated
                
                if quantity > available:
                    return False, f"Недостаточно материала '{material.name}'. Доступно: {available}, требуется: {quantity}"
                
                # Проверяем, существует ли уже распределение
                existing = await self.repository.get_material_allocation(material_id, section_id)
                if existing:
                    # Обновляем существующее
                    existing.quantity = quantity
                    existing.updated_at = datetime.now()
                    await self.repository.save_material_allocation(existing)
                else:
                    # Создаем новое
                    allocation = InstallationMaterialQuantity(
                        material_id=material_id,
                        material_section_id=section_id,
                        quantity=quantity,
                        created_by=user_id
                    )
                    await self.repository.save_material_allocation(allocation)
                
                added_materials.append({
                    'material_id': material_id,
                    'material_name': material.name,
                    'quantity': quantity,
                    'unit': material.unit
                })
            
            # Логирование
            await self.log_manager.log_section_action(
                user_id=user_id,
                object_id=section.installation_object_id,
                object_name=(await self._get_object_name(section.installation_object_id)),
                section_id=section_id,
                section_name=section.name,
                action='add_materials',
                details={'materials': added_materials}
            )
            
            return True, "Материалы успешно добавлены в раздел"
            
        except Exception as e:
            logger.error(f"Ошибка добавления материалов в раздел {section_id}: {e}", exc_info=True)
            return False, f"Ошибка добавления материалов: {str(e)}"
    
    async def get_section_materials(self, section_id: str) -> List[Dict[str, Any]]:
        """
        Получение материалов раздела с детальной информацией.
        
        Args:
            section_id: UUID раздела
            
        Returns:
            Список материалов раздела
        """
        try:
            allocations = await self.repository.get_material_allocations_by_section(section_id)
            result = []
            
            for alloc in allocations:
                material = await self.repository.get_material_by_id(alloc.material_id)
                if material:
                    result.append({
                        'material_id': str(material.id),
                        'material_name': material.name,
                        'quantity': alloc.quantity,
                        'unit': material.unit,
                        'total_quantity': material.quantity,
                        'description': material.description,
                        'allocation_id': str(alloc.id)
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка получения материалов раздела {section_id}: {e}", exc_info=True)
            return []
    
    async def remove_material_from_section(self, allocation_id: str, user_id: int) -> Tuple[bool, str]:
        """
        Удаление материала из раздела.
        
        Args:
            allocation_id: UUID распределения
            user_id: ID пользователя
            
        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            allocation = await self.repository.get_material_allocation_by_id(allocation_id)
            if not allocation:
                return False, "Распределение не найдено"
            
            # Получаем информацию для логирования
            material = await self.repository.get_material_by_id(allocation.material_id)
            section = await self.repository.get_material_section_by_id(allocation.material_section_id)
            
            # Удаление
            await self.repository.delete_material_allocation(allocation_id)
            
            # Логирование
            if material and section:
                await self.log_manager.log_section_action(
                    user_id=user_id,
                    object_id=section.installation_object_id,
                    object_name=(await self._get_object_name(section.installation_object_id)),
                    section_id=str(section.id),
                    section_name=section.name,
                    action='remove_material',
                    details={
                        'material_id': str(material.id),
                        'material_name': material.name,
                        'quantity': allocation.quantity,
                        'unit': material.unit
                    }
                )
            
            return True, "Материал успешно удален из раздела"
            
        except Exception as e:
            logger.error(f"Ошибка удаления материала из раздела: {e}", exc_info=True)
            return False, f"Ошибка удаления: {str(e)}"
    
    async def update_section_material_quantity(self, allocation_id: str, quantity: float, user_id: int) -> Tuple[bool, str]:
        """
        Обновление количества материала в разделе.
        
        Args:
            allocation_id: UUID распределения
            quantity: Новое количество
            user_id: ID пользователя
            
        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            allocation = await self.repository.get_material_allocation_by_id(allocation_id)
            if not allocation:
                return False, "Распределение не найдено"
            
            old_quantity = allocation.quantity
            
            # Получаем материал для проверки доступного количества
            material = await self.repository.get_material_by_id(allocation.material_id)
            if not material:
                return False, "Материал не найден"
            
            # Проверяем доступное количество (исключая текущее распределение)
            allocations = await self.repository.get_material_allocations(material.id)
            total_allocated = sum([alloc.quantity for alloc in allocations if str(alloc.id) != allocation_id])
            available = material.quantity - total_allocated
            
            if quantity > available:
                return False, f"Недостаточно материала '{material.name}'. Доступно: {available}, требуется: {quantity}"
            
            # Обновление
            allocation.quantity = quantity
            allocation.updated_at = datetime.now()
            
            await self.repository.save_material_allocation(allocation)
            
            # Логирование
            section = await self.repository.get_material_section_by_id(allocation.material_section_id)
            if section:
                await self.log_manager.log_section_action(
                    user_id=user_id,
                    object_id=section.installation_object_id,
                    object_name=(await self._get_object_name(section.installation_object_id)),
                    section_id=str(section.id),
                    section_name=section.name,
                    action='update_material_quantity',
                    details={
                        'material_id': str(material.id),
                        'material_name': material.name,
                        'old_quantity': old_quantity,
                        'new_quantity': quantity,
                        'unit': material.unit
                    }
                )
            
            return True, "Количество материала успешно обновлено"
            
        except Exception as e:
            logger.error(f"Ошибка обновления количества материала: {e}", exc_info=True)
            return False, f"Ошибка обновления: {str(e)}"
    
    async def check_material_balance(self, object_id: str) -> Dict[str, Any]:
        """
        Проверка соответствия сумм материалов (общее = сумма по разделам).
        
        Args:
            object_id: UUID объекта
            
        Returns:
            Словарь с результатами проверки
        """
        try:
            materials = await self.repository.get_materials_by_object(object_id)
            sections = await self.repository.get_material_sections_by_object(object_id)
            
            results = {
                'is_balanced': True,
                'materials': [],
                'total_mismatch': 0,
                'sections_count': len(sections)
            }
            
            for material in materials:
                # Общее количество материала
                total_quantity = material.quantity
                
                # Количество в разделах
                allocations = await self.repository.get_material_allocations(material.id)
                allocated_quantity = sum([alloc.quantity for alloc in allocations])
                
                # Разница
                difference = total_quantity - allocated_quantity
                is_balanced = abs(difference) < 0.001  # Учитываем погрешность округления
                
                if not is_balanced:
                    results['is_balanced'] = False
                    results['total_mismatch'] += abs(difference)
                
                material_info = {
                    'id': str(material.id),
                    'name': material.name,
                    'total_quantity': total_quantity,
                    'allocated_quantity': allocated_quantity,
                    'difference': difference,
                    'is_balanced': is_balanced,
                    'unit': material.unit
                }
                
                # Информация по разделам
                section_details = []
                for alloc in allocations:
                    section = await self.repository.get_material_section_by_id(alloc.material_section_id)
                    if section:
                        section_details.append({
                            'section_id': str(section.id),
                            'section_name': section.name,
                            'quantity': alloc.quantity
                        })
                
                material_info['section_details'] = section_details
                results['materials'].append(material_info)
            
            return results
            
        except Exception as e:
            logger.error(f"Ошибка проверки баланса материалов объекта {object_id}: {e}", exc_info=True)
            return {'is_balanced': False, 'error': str(e), 'materials': []}
    
    # ========== Вспомогательные методы ==========
    
    async def _get_object_name(self, object_id: str) -> str:
        """
        Получение названия объекта.
        
        Args:
            object_id: UUID объекта
            
        Returns:
            Название объекта или пустая строка
        """
        try:
            installation_object = await self.repository.get_installation_object_by_id(object_id)
            return installation_object.full_name if installation_object else ""
        except Exception:
            return ""