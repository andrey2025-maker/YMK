"""
Менеджер для управления оборудованием объектов обслуживания.
Реализует учет оборудования по адресам с количеством и единицами измерения.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import structlog

from core.context import AppContext
from storage.models.service import Equipment, ServiceObject, Address
from storage.repositories.service_repository import ServiceRepository
from utils.date_utils import format_date


logger = structlog.get_logger(__name__)


class EquipmentManager:
    """Менеджер для управления оборудованием объектов обслуживания."""
    
    def __init__(self, context: AppContext):
        self.context = context
        self.service_repository: Optional[ServiceRepository] = None
    
    async def initialize(self) -> None:
        """Инициализирует менеджер оборудования."""
        self.service_repository = ServiceRepository(self.context.db_session)
        logger.info("EquipmentManager initialized")
    
    async def add_equipment(
        self,
        object_id: str,
        address_id: Optional[str],
        user_id: int,
        user_name: str,
        name: str,
        quantity: float,
        unit: str,
        description: Optional[str] = None,
        specifications: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Добавляет оборудование к объекту или адресу.
        
        Args:
            object_id: ID объекта обслуживания
            address_id: ID адреса (опционально, если у объекта несколько адресов)
            user_id: ID пользователя
            user_name: Имя пользователя
            name: Наименование оборудования
            quantity: Количество
            unit: Единица измерения (шт., м., уп., компл.)
            description: Описание оборудования
            specifications: Технические характеристики
            
        Returns:
            Dict с информацией о созданном оборудовании
        """
        try:
            # Проверяем существование объекта
            object_info = await self.service_repository.get_object_by_id(object_id)
            if not object_info:
                return {
                    'success': False,
                    'error': 'Объект не найден'
                }
            
            # Если указан адрес, проверяем его существование
            if address_id:
                address = await self.service_repository.get_address_by_id(address_id)
                if not address or address.object_id != object_id:
                    return {
                        'success': False,
                        'error': 'Адрес не найден или не принадлежит объекту'
                    }
            
            # Валидируем единицу измерения
            valid_units = ['шт.', 'м.', 'уп.', 'компл.']
            if unit not in valid_units:
                return {
                    'success': False,
                    'error': f'Недопустимая единица измерения. Допустимые значения: {", ".join(valid_units)}'
                }
            
            # Создаем запись оборудования
            equipment = Equipment(
                object_id=object_id,
                address_id=address_id,
                name=name,
                quantity=quantity,
                unit=unit,
                description=description or '',
                specifications=specifications or {},
                added_by_id=user_id,
                added_by_name=user_name,
                added_at=datetime.now(),
                last_updated=datetime.now()
            )
            
            # Сохраняем в БД
            saved_equipment = await self.service_repository.create_equipment(equipment)
            
            # Получаем информацию об адресе для отображения
            address_info = None
            if address_id:
                address_info = await self.service_repository.get_address_by_id(address_id)
            
            # Логируем добавление оборудования
            await self.context.log_manager.log_change(
                user_id=user_id,
                user_name=user_name,
                entity_type='equipment',
                entity_id=str(saved_equipment.id),
                entity_name=name,
                action='create',
                changes={
                    'name': {'new': name},
                    'quantity': {'new': str(quantity)},
                    'unit': {'new': unit},
                    'address': {'new': address_info.address if address_info else 'Общее'}
                }
            )
            
            return {
                'success': True,
                'equipment_id': str(saved_equipment.id),
                'object_name': object_info.short_name,
                'address': address_info.address if address_info else 'Общее',
                'name': name,
                'quantity': quantity,
                'unit': unit,
                'timestamp': saved_equipment.added_at
            }
            
        except Exception as e:
            logger.error("Failed to add equipment", error=str(e), object_id=object_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_equipment_list(
        self,
        object_id: str,
        address_id: Optional[str] = None,
        page: int = 0,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Получает список оборудования с пагинацией.
        
        Args:
            object_id: ID объекта обслуживания
            address_id: ID адреса (опционально)
            page: Номер страницы (начиная с 0)
            limit: Количество записей на страницу
            
        Returns:
            Dict с оборудованием и информацией о пагинации
        """
        try:
            # Получаем оборудование из БД
            equipment_list = await self.service_repository.get_equipment_list(
                object_id=object_id,
                address_id=address_id,
                skip=page * limit,
                limit=limit
            )
            
            # Получаем общее количество
            total = await self.service_repository.count_equipment(object_id, address_id)
            
            # Форматируем оборудование для отображения
            formatted_equipment = []
            for equipment in equipment_list:
                # Получаем информацию об адресе
                address_info = None
                if equipment.address_id:
                    address_info = await self.service_repository.get_address_by_id(equipment.address_id)
                
                formatted_equipment.append({
                    'id': str(equipment.id),
                    'name': equipment.name,
                    'quantity': equipment.quantity,
                    'unit': equipment.unit,
                    'description': equipment.description,
                    'specifications': equipment.specifications,
                    'address_id': equipment.address_id,
                    'address': address_info.address if address_info else 'Общее',
                    'added_by': equipment.added_by_name,
                    'added_at': equipment.added_at,
                    'last_updated': equipment.last_updated
                })
            
            # Получаем информацию об адресах объекта
            addresses = await self.service_repository.get_object_addresses(object_id)
            
            return {
                'success': True,
                'equipment': formatted_equipment,
                'addresses': [
                    {
                        'id': str(addr.id),
                        'address': addr.address,
                        'equipment_count': await self.service_repository.count_equipment(object_id, str(addr.id))
                    }
                    for addr in addresses
                ],
                'total': total,
                'page': page,
                'limit': limit,
                'total_pages': (total + limit - 1) // limit
            }
            
        except Exception as e:
            logger.error("Failed to get equipment list", error=str(e), object_id=object_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def update_equipment(
        self,
        equipment_id: str,
        user_id: int,
        user_name: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Редактирует оборудование.
        
        Args:
            equipment_id: ID оборудования
            user_id: ID пользователя
            user_name: Имя пользователя
            updates: Словарь обновлений
            
        Returns:
            Dict с результатом обновления
        """
        try:
            # Получаем текущее оборудование
            equipment = await self.service_repository.get_equipment_by_id(equipment_id)
            if not equipment:
                return {
                    'success': False,
                    'error': 'Оборудование не найдено'
                }
            
            # Проверяем права доступа
            from modules.admin.admin_manager import AdminManager
            admin_manager = AdminManager(self.context)
            user_role = await admin_manager.get_user_role(user_id)
            if user_role not in ['main_admin', 'admin']:
                return {
                    'success': False,
                    'error': 'Нет прав для редактирования оборудования'
                }
            
            # Подготавливаем изменения для логирования
            changes = {}
            
            # Проверяем каждое обновляемое поле
            if 'name' in updates and updates['name'] != equipment.name:
                changes['name'] = {
                    'old': equipment.name,
                    'new': updates['name']
                }
                equipment.name = updates['name']
            
            if 'quantity' in updates and updates['quantity'] != equipment.quantity:
                changes['quantity'] = {
                    'old': str(equipment.quantity),
                    'new': str(updates['quantity'])
                }
                equipment.quantity = updates['quantity']
            
            if 'unit' in updates and updates['unit'] != equipment.unit:
                # Валидируем единицу измерения
                valid_units = ['шт.', 'м.', 'уп.', 'компл.']
                if updates['unit'] not in valid_units:
                    return {
                        'success': False,
                        'error': f'Недопустимая единица измерения. Допустимые значения: {", ".join(valid_units)}'
                    }
                
                changes['unit'] = {
                    'old': equipment.unit,
                    'new': updates['unit']
                }
                equipment.unit = updates['unit']
            
            if 'description' in updates and updates['description'] != equipment.description:
                changes['description'] = {
                    'old': equipment.description,
                    'new': updates['description']
                }
                equipment.description = updates['description']
            
            if 'specifications' in updates:
                changes['specifications'] = {
                    'old': str(equipment.specifications),
                    'new': str(updates['specifications'])
                }
                equipment.specifications = updates['specifications']
            
            # Обновляем дату изменения
            equipment.last_updated = datetime.now()
            
            # Сохраняем изменения
            updated_equipment = await self.service_repository.update_equipment(equipment)
            
            # Логируем изменения если они были
            if changes:
                await self.context.log_manager.log_change(
                    user_id=user_id,
                    user_name=user_name,
                    entity_type='equipment',
                    entity_id=equipment_id,
                    entity_name=equipment.name,
                    action='update',
                    changes=changes
                )
            
            return {
                'success': True,
                'equipment_id': equipment_id,
                'updated_fields': list(changes.keys()),
                'last_updated': updated_equipment.last_updated
            }
            
        except Exception as e:
            logger.error("Failed to update equipment", error=str(e), equipment_id=equipment_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def delete_equipment(
        self,
        equipment_id: str,
        user_id: int,
        user_name: str
    ) -> Dict[str, Any]:
        """
        Удаляет оборудование.
        
        Args:
            equipment_id: ID оборудования
            user_id: ID пользователя
            user_name: Имя пользователя
            
        Returns:
            Dict с результатом удаления
        """
        try:
            # Получаем оборудование
            equipment = await self.service_repository.get_equipment_by_id(equipment_id)
            if not equipment:
                return {
                    'success': False,
                    'error': 'Оборудование не найдено'
                }
            
            # Проверяем права доступа
            from modules.admin.admin_manager import AdminManager
            admin_manager = AdminManager(self.context)
            user_role = await admin_manager.get_user_role(user_id)
            if user_role not in ['main_admin', 'admin']:
                return {
                    'success': False,
                    'error': 'Нет прав для удаления оборудования'
                }
            
            # Сохраняем информацию для архива
            equipment_info = {
                'id': str(equipment.id),
                'name': equipment.name,
                'quantity': equipment.quantity,
                'unit': equipment.unit,
                'object_id': equipment.object_id,
                'address_id': equipment.address_id,
                'added_by': equipment.added_by_name,
                'added_at': equipment.added_at,
                'deleted_by': user_name,
                'deleted_at': datetime.now()
            }
            
            # Удаляем оборудование
            deleted = await self.service_repository.delete_equipment(equipment_id)
            
            if deleted:
                # Логируем удаление
                await self.context.log_manager.log_change(
                    user_id=user_id,
                    user_name=user_name,
                    entity_type='equipment',
                    entity_id=equipment_id,
                    entity_name=equipment.name,
                    action='delete',
                    changes={'equipment': {'old': equipment_info, 'new': None}}
                )
                
                return {
                    'success': True,
                    'equipment_id': equipment_id,
                    'equipment_name': equipment.name
                }
            else:
                return {
                    'success': False,
                    'error': 'Не удалось удалить оборудование'
                }
            
        except Exception as e:
            logger.error("Failed to delete equipment", error=str(e), equipment_id=equipment_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_equipment_by_address(
        self,
        object_id: str,
        address_id: str
    ) -> Dict[str, Any]:
        """
        Получает оборудование по адресу.
        
        Args:
            object_id: ID объекта обслуживания
            address_id: ID адреса
            
        Returns:
            Dict с оборудованием на указанном адресе
        """
        try:
            # Проверяем существование адреса
            address = await self.service_repository.get_address_by_id(address_id)
            if not address or address.object_id != object_id:
                return {
                    'success': False,
                    'error': 'Адрес не найден или не принадлежит объекту'
                }
            
            # Получаем оборудование
            equipment_list = await self.service_repository.get_equipment_by_address(address_id)
            
            # Форматируем результат
            formatted_equipment = []
            total_quantity = 0
            
            for equipment in equipment_list:
                formatted_equipment.append({
                    'id': str(equipment.id),
                    'name': equipment.name,
                    'quantity': equipment.quantity,
                    'unit': equipment.unit,
                    'description': equipment.description,
                    'added_by': equipment.added_by_name,
                    'added_at': equipment.added_at
                })
                total_quantity += equipment.quantity
            
            return {
                'success': True,
                'address': address.address,
                'equipment': formatted_equipment,
                'total_items': len(formatted_equipment),
                'total_quantity': total_quantity
            }
            
        except Exception as e:
            logger.error("Failed to get equipment by address", error=str(e), address_id=address_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def move_equipment(
        self,
        equipment_id: str,
        new_address_id: Optional[str],
        user_id: int,
        user_name: str
    ) -> Dict[str, Any]:
        """
        Перемещает оборудование между адресами.
        
        Args:
            equipment_id: ID оборудования
            new_address_id: Новый ID адреса (None для общего)
            user_id: ID пользователя
            user_name: Имя пользователя
            
        Returns:
            Dict с результатом перемещения
        """
        try:
            # Получаем оборудование
            equipment = await self.service_repository.get_equipment_by_id(equipment_id)
            if not equipment:
                return {
                    'success': False,
                    'error': 'Оборудование не найдено'
                }
            
            # Проверяем права доступа
            from modules.admin.admin_manager import AdminManager
            admin_manager = AdminManager(self.context)
            user_role = await admin_manager.get_user_role(user_id)
            if user_role not in ['main_admin', 'admin']:
                return {
                    'success': False,
                    'error': 'Нет прав для перемещения оборудования'
                }
            
            # Если указан новый адрес, проверяем его существование
            old_address_info = None
            new_address_info = None
            
            if equipment.address_id:
                old_address = await self.service_repository.get_address_by_id(equipment.address_id)
                old_address_info = old_address.address if old_address else 'Общее'
            
            if new_address_id:
                new_address = await self.service_repository.get_address_by_id(new_address_id)
                if not new_address or new_address.object_id != equipment.object_id:
                    return {
                        'success': False,
                        'error': 'Новый адрес не найден или не принадлежит объекту'
                    }
                new_address_info = new_address.address
            else:
                new_address_info = 'Общее'
            
            # Сохраняем старый адрес для логирования
            old_address_id = equipment.address_id
            
            # Обновляем адрес
            equipment.address_id = new_address_id
            equipment.last_updated = datetime.now()
            
            updated_equipment = await self.service_repository.update_equipment(equipment)
            
            # Логируем перемещение
            await self.context.log_manager.log_change(
                user_id=user_id,
                user_name=user_name,
                entity_type='equipment',
                entity_id=equipment_id,
                entity_name=equipment.name,
                action='update',
                changes={
                    'address': {
                        'old': old_address_info,
                        'new': new_address_info
                    }
                }
            )
            
            return {
                'success': True,
                'equipment_id': equipment_id,
                'equipment_name': equipment.name,
                'old_address': old_address_info,
                'new_address': new_address_info,
                'last_updated': updated_equipment.last_updated
            }
            
        except Exception as e:
            logger.error("Failed to move equipment", error=str(e), equipment_id=equipment_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def export_equipment_data(
        self,
        object_id: Optional[str] = None,
        address_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Подготавливает данные оборудования для экспорта.
        
        Args:
            object_id: ID объекта (опционально)
            address_id: ID адреса (опционально)
            
        Returns:
            Dict с данными для экспорта
        """
        try:
            # Получаем оборудование
            if object_id:
                equipment_list = await self.service_repository.get_equipment_list(
                    object_id=object_id,
                    address_id=address_id,
                    skip=0,
                    limit=1000  # Большой лимит для экспорта
                )
            else:
                equipment_list = await self.service_repository.get_all_equipment_for_export()
            
            # Получаем информацию об объектах и адресах
            export_data = []
            
            for equipment in equipment_list:
                # Получаем информацию об объекте
                object_info = await self.service_repository.get_object_by_id(equipment.object_id)
                
                # Получаем информацию об адресе
                address_info = None
                if equipment.address_id:
                    address_info = await self.service_repository.get_address_by_id(equipment.address_id)
                
                export_data.append({
                    'object_id': equipment.object_id,
                    'object_name': object_info.short_name if object_info else 'Неизвестно',
                    'object_full_name': object_info.full_name if object_info else 'Неизвестно',
                    'address_id': equipment.address_id,
                    'address': address_info.address if address_info else 'Общее',
                    'equipment_id': str(equipment.id),
                    'equipment_name': equipment.name,
                    'quantity': equipment.quantity,
                    'unit': equipment.unit,
                    'description': equipment.description,
                    'specifications': equipment.specifications,
                    'added_by': equipment.added_by_name,
                    'added_at': equipment.added_at,
                    'last_updated': equipment.last_updated
                })
            
            return {
                'success': True,
                'equipment': export_data,
                'total': len(export_data),
                'export_date': datetime.now()
            }
            
        except Exception as e:
            logger.error("Failed to export equipment data", error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_equipment_summary(self, object_id: str) -> Dict[str, Any]:
        """
        Получает сводную информацию по оборудованию объекта.
        
        Args:
            object_id: ID объекта обслуживания
            
        Returns:
            Dict со сводной информацией
        """
        try:
            # Получаем все адреса объекта
            addresses = await self.service_repository.get_object_addresses(object_id)
            
            summary = {
                'total_equipment': 0,
                'total_quantity': 0,
                'by_address': [],
                'by_unit': {}
            }
            
            # Обрабатываем каждый адрес
            for address in addresses:
                address_equipment = await self.service_repository.get_equipment_by_address(str(address.id))
                
                address_summary = {
                    'address_id': str(address.id),
                    'address': address.address,
                    'equipment_count': len(address_equipment),
                    'total_quantity': sum(e.quantity for e in address_equipment),
                    'equipment': []
                }
                
                for equipment in address_equipment:
                    address_summary['equipment'].append({
                        'name': equipment.name,
                        'quantity': equipment.quantity,
                        'unit': equipment.unit
                    })
                    
                    # Суммируем по единицам измерения
                    unit_key = equipment.unit
                    if unit_key not in summary['by_unit']:
                        summary['by_unit'][unit_key] = 0
                    summary['by_unit'][unit_key] += equipment.quantity
                
                summary['by_address'].append(address_summary)
                summary['total_equipment'] += len(address_equipment)
                summary['total_quantity'] += address_summary['total_quantity']
            
            # Обрабатываем общее оборудование (без адреса)
            general_equipment = await self.service_repository.get_equipment_list(
                object_id=object_id,
                address_id=None,
                skip=0,
                limit=1000
            )
            
            if general_equipment:
                general_summary = {
                    'address_id': None,
                    'address': 'Общее',
                    'equipment_count': len(general_equipment),
                    'total_quantity': sum(e.quantity for e in general_equipment),
                    'equipment': []
                }
                
                for equipment in general_equipment:
                    general_summary['equipment'].append({
                        'name': equipment.name,
                        'quantity': equipment.quantity,
                        'unit': equipment.unit
                    })
                    
                    unit_key = equipment.unit
                    if unit_key not in summary['by_unit']:
                        summary['by_unit'][unit_key] = 0
                    summary['by_unit'][unit_key] += equipment.quantity
                
                summary['by_address'].append(general_summary)
                summary['total_equipment'] += len(general_equipment)
                summary['total_quantity'] += general_summary['total_quantity']
            
            return {
                'success': True,
                'summary': summary
            }
            
        except Exception as e:
            logger.error("Failed to get equipment summary", error=str(e), object_id=object_id)
            return {
                'success': False,
                'error': str(e)
            }