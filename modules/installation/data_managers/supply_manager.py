"""
Менеджер поставок.
Управление поставками материалов с напоминаниями о датах доставки.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

from storage.models.installation import InstallationSupply
from storage.repositories.installation_repository import InstallationRepository
from services.reminder_service import ReminderService
from modules.admin.log_manager import LogManager
from utils.date_utils import parse_date, format_date

logger = logging.getLogger(__name__)


class SupplyManager:
    """Менеджер поставок."""
    
    def __init__(self, context):
        self.context = context
        self.repository = InstallationRepository(context.db_session)
        self.reminder_service = ReminderService(context)
        self.log_manager = LogManager(context)
    
    async def add_supply(self, object_id: str, user_id: int, data: Dict[str, Any]) -> Tuple[bool, Optional[InstallationSupply], str]:
        """
        Добавление поставки.
        
        Args:
            object_id: UUID объекта
            user_id: ID пользователя
            data: Данные поставки
            
        Returns:
            Кортеж (успех, поставка, сообщение об ошибке)
        """
        try:
            # Проверяем существование объекта
            installation_object = await self.repository.get_installation_object_by_id(object_id)
            if not installation_object:
                return False, None, "Объект монтажа не найден"
            
            # Парсим дату доставки
            delivery_date = parse_date(data['delivery_date'])
            
            # Создание поставки
            supply = InstallationSupply(
                installation_object_id=object_id,
                delivery_service=data['delivery_service'],
                delivery_date=delivery_date,
                document=data.get('document'),
                description=data['description'],
                created_by=user_id
            )
            
            await self.repository.save_supply(supply)
            
            # Создание напоминания за день до поставки
            if delivery_date:
                reminder_date = delivery_date - timedelta(days=1)
                await self.reminder_service.create_supply_reminder(
                    user_id=user_id,
                    object_id=object_id,
                    object_name=installation_object.full_name,
                    supply_id=supply.id,
                    supply_description=data['description'],
                    reminder_date=reminder_date
                )
            
            # Логирование
            await self.log_manager.log_supply_action(
                user_id=user_id,
                object_id=object_id,
                object_name=installation_object.full_name,
                supply_id=supply.id,
                action='add',
                details=data
            )
            
            return True, supply, "Поставка успешно добавлена"
            
        except Exception as e:
            logger.error(f"Ошибка добавления поставки к объекту {object_id}: {e}", exc_info=True)
            return False, None, f"Ошибка добавления поставки: {str(e)}"
    
    async def get_supplies(self, object_id: str, include_past: bool = True) -> List[Dict[str, Any]]:
        """
        Получение списка поставок объекта.
        
        Args:
            object_id: UUID объекта
            include_past: Включать ли прошедшие поставки
            
        Returns:
            Список поставок с дополнительной информацией
        """
        try:
            supplies = await self.repository.get_supplies_by_object(object_id)
            result = []
            today = datetime.now().date()
            
            for supply in supplies:
                # Пропускаем прошедшие поставки если не запрошены
                if not include_past and supply.delivery_date and supply.delivery_date < today:
                    continue
                
                # Определяем статус поставки
                if supply.delivery_date:
                    if supply.delivery_date < today:
                        status = 'delivered'
                        days_diff = (today - supply.delivery_date).days
                        status_text = f"Доставлено {days_diff} дн. назад"
                    elif supply.delivery_date == today:
                        status = 'today'
                        status_text = "Сегодня"
                    else:
                        status = 'upcoming'
                        days_diff = (supply.delivery_date - today).days
                        status_text = f"Через {days_diff} дн."
                else:
                    status = 'no_date'
                    status_text = "Без даты"
                
                # Информация о напоминании
                has_reminder = False
                reminder_date = None
                
                if supply.delivery_date and supply.delivery_date > today:
                    has_reminder = True
                    reminder_date = supply.delivery_date - timedelta(days=1)
                
                result.append({
                    'id': str(supply.id),
                    'delivery_service': supply.delivery_service,
                    'delivery_date': format_date(supply.delivery_date) if supply.delivery_date else None,
                    'document': supply.document,
                    'description': supply.description,
                    'status': status,
                    'status_text': status_text,
                    'has_reminder': has_reminder,
                    'reminder_date': format_date(reminder_date) if reminder_date else None,
                    'created_at': supply.created_at.isoformat() if supply.created_at else None,
                    'created_by': supply.created_by
                })
            
            # Сортируем по дате доставки (сначала ближайшие)
            result.sort(key=lambda x: (
                x['delivery_date'] is None,  # Без даты в конец
                x['delivery_date'] if x['delivery_date'] else '9999-12-31'
            ))
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка получения поставок объекта {object_id}: {e}", exc_info=True)
            return []
    
    async def update_supply(self, supply_id: str, user_id: int, data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Обновление поставки.
        
        Args:
            supply_id: UUID поставки
            user_id: ID пользователя
            data: Новые данные
            
        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            supply = await self.repository.get_supply_by_id(supply_id)
            if not supply:
                return False, "Поставка не найденa"
            
            old_data = {
                'delivery_service': supply.delivery_service,
                'delivery_date': format_date(supply.delivery_date) if supply.delivery_date else None,
                'document': supply.document,
                'description': supply.description
            }
            
            old_delivery_date = supply.delivery_date
            
            # Обновление полей
            if 'delivery_service' in data:
                supply.delivery_service = data['delivery_service']
            if 'delivery_date' in data and data['delivery_date']:
                new_delivery_date = parse_date(data['delivery_date'])
                supply.delivery_date = new_delivery_date
                
                # Обновляем напоминание если дата изменилась
                if old_delivery_date != new_delivery_date:
                    await self._update_supply_reminder(supply, user_id)
            if 'document' in data:
                supply.document = data['document']
            if 'description' in data:
                supply.description = data['description']
            
            supply.updated_at = datetime.now()
            
            await self.repository.save_supply(supply)
            
            # Логирование
            new_data = {k: data.get(k) for k in old_data.keys() if k in data}
            if new_data:
                await self.log_manager.log_supply_action(
                    user_id=user_id,
                    object_id=supply.installation_object_id,
                    object_name=(await self._get_object_name(supply.installation_object_id)),
                    supply_id=supply_id,
                    action='update',
                    old_data=old_data,
                    new_data=new_data
                )
            
            return True, "Поставка успешно обновлена"
            
        except Exception as e:
            logger.error(f"Ошибка обновления поставки {supply_id}: {e}", exc_info=True)
            return False, f"Ошибка обновления: {str(e)}"
    
    async def delete_supply(self, supply_id: str, user_id: int) -> Tuple[bool, str]:
        """
        Удаление поставки.
        
        Args:
            supply_id: UUID поставки
            user_id: ID пользователя
            
        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            supply = await self.repository.get_supply_by_id(supply_id)
            if not supply:
                return False, "Поставка не найдена"
            
            # Удаляем связанное напоминание
            await self.reminder_service.delete_supply_reminder(supply_id)
            
            # Логирование перед удалением
            await self.log_manager.log_supply_action(
                user_id=user_id,
                object_id=supply.installation_object_id,
                object_name=(await self._get_object_name(supply.installation_object_id)),
                supply_id=supply_id,
                action='delete',
                details={
                    'delivery_service': supply.delivery_service,
                    'delivery_date': format_date(supply.delivery_date) if supply.delivery_date else None,
                    'description': supply.description
                }
            )
            
            # Удаление
            await self.repository.delete_supply(supply_id)
            
            return True, "Поставка успешно удалена"
            
        except Exception as e:
            logger.error(f"Ошибка удаления поставки {supply_id}: {e}", exc_info=True)
            return False, f"Ошибка удаления: {str(e)}"
    
    async def get_upcoming_supplies(self, object_id: str, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """
        Получение предстоящих поставок.
        
        Args:
            object_id: UUID объекта
            days_ahead: Количество дней вперед для поиска
            
        Returns:
            Список предстоящих поставок
        """
        try:
            today = datetime.now().date()
            end_date = today + timedelta(days=days_ahead)
            
            supplies = await self.repository.get_supplies_by_date_range(object_id, today, end_date)
            
            result = []
            for supply in supplies:
                days_until = (supply.delivery_date - today).days
                
                result.append({
                    'id': str(supply.id),
                    'delivery_service': supply.delivery_service,
                    'delivery_date': format_date(supply.delivery_date),
                    'days_until': days_until,
                    'description': supply.description,
                    'document': supply.document,
                    'created_at': supply.created_at.isoformat() if supply.created_at else None
                })
            
            # Сортируем по дате доставки
            result.sort(key=lambda x: x['days_until'])
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка получения предстоящих поставок объекта {object_id}: {e}", exc_info=True)
            return []
    
    async def mark_as_delivered(self, supply_id: str, user_id: int) -> Tuple[bool, str]:
        """
        Отметка поставки как доставленной.
        
        Args:
            supply_id: UUID поставки
            user_id: ID пользователя
            
        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            supply = await self.repository.get_supply_by_id(supply_id)
            if not supply:
                return False, "Поставка не найдена"
            
            old_delivery_date = supply.delivery_date
            
            # Устанавливаем дату доставки на сегодня
            supply.delivery_date = datetime.now().date()
            supply.updated_at = datetime.now()
            
            await self.repository.save_supply(supply)
            
            # Удаляем напоминание
            await self.reminder_service.delete_supply_reminder(supply_id)
            
            # Логирование
            await self.log_manager.log_supply_action(
                user_id=user_id,
                object_id=supply.installation_object_id,
                object_name=(await self._get_object_name(supply.installation_object_id)),
                supply_id=supply_id,
                action='mark_delivered',
                details={
                    'old_date': format_date(old_delivery_date) if old_delivery_date else None,
                    'new_date': format_date(supply.delivery_date)
                }
            )
            
            return True, "Поставка отмечена как доставленная"
            
        except Exception as e:
            logger.error(f"Ошибка отметки поставки {supply_id} как доставленной: {e}", exc_info=True)
            return False, f"Ошибка: {str(e)}"
    
    # ========== Вспомогательные методы ==========
    
    async def _update_supply_reminder(self, supply: InstallationSupply, user_id: int):
        """
        Обновление напоминания о поставке.
        
        Args:
            supply: Объект поставки
            user_id: ID пользователя
        """
        try:
            if not supply.delivery_date:
                return
            
            # Удаляем старое напоминание
            await self.reminder_service.delete_supply_reminder(supply.id)
            
            # Создаем новое напоминание
            installation_object = await self.repository.get_installation_object_by_id(supply.installation_object_id)
            if installation_object:
                reminder_date = supply.delivery_date - timedelta(days=1)
                await self.reminder_service.create_supply_reminder(
                    user_id=user_id,
                    object_id=supply.installation_object_id,
                    object_name=installation_object.full_name,
                    supply_id=supply.id,
                    supply_description=supply.description,
                    reminder_date=reminder_date
                )
                
        except Exception as e:
            logger.error(f"Ошибка обновления напоминания поставки {supply.id}: {e}")
    
    async def _get_object_name(self, object_id: str) -> str:
        """Получение названия объекта."""
        try:
            installation_object = await self.repository.get_installation_object_by_id(object_id)
            return installation_object.full_name if installation_object else ""
        except Exception:
            return ""