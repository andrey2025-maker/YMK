import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import uuid

import structlog
from aiogram import Bot

from core.context import AppContext
from config import config
from storage.repositories.service_repository import ServiceRepository
from storage.repositories.installation_repository import InstallationRepository
from utils.date_utils import DateUtils
from utils.formatters import format_reminder_message


logger = structlog.get_logger(__name__)


class ReminderService:
    """Сервис для управления напоминаниями."""
    
    def __init__(self, context: AppContext):
        self.context = context
        self.bot = Bot(token=config.bot.token)
        self.date_utils = DateUtils()
        self._initialized = False
    
    async def initialize(self) -> None:
        """Инициализирует сервис напоминаний."""
        if self._initialized:
            return
        
        self._initialized = True
        logger.info("Reminder service initialized")
    
    async def check_and_send_reminders(self) -> Dict[str, Any]:
        """
        Проверяет и отправляет напоминания.
        
        Returns:
            Статистика отправленных напоминаний
        """
        try:
            stats = {
                "service_reminders": 0,
                "installation_reminders": 0,
                "contract_reminders": 0,
                "maintenance_reminders": 0,
                "supply_reminders": 0,
                "errors": 0,
            }
            
            # Получаем текущую дату
            today = datetime.now()
            
            # Проверяем напоминания обслуживания
            stats["service_reminders"] = await self._check_service_reminders(today)
            
            # Проверяем напоминания монтажа
            stats["installation_reminders"] = await self._check_installation_reminders(today)
            
            # Проверяем контракты
            stats["contract_reminders"] = await self._check_contract_reminders(today)
            
            # Проверяем ТО обслуживания
            stats["maintenance_reminders"] = await self._check_maintenance_reminders(today)
            
            # Проверяем поставки монтажа
            stats["supply_reminders"] = await self._check_supply_reminders(today)
            
            logger.info("Reminders checked", stats=stats)
            return stats
        
        except Exception as e:
            logger.error("Check reminders failed", error=str(e))
            return {"errors": 1}
    
    async def _check_service_reminders(self, today: datetime) -> int:
        """Проверяет напоминания обслуживания."""
        try:
            async with self.context.get_session() as session:
                repo = ServiceRepository(session)
                
                # Получаем активные напоминания
                reminders = await repo.get_active_service_reminders()
                
                sent_count = 0
                for reminder in reminders:
                    if reminder.should_notify_today():
                        # Отправляем напоминание
                        success = await self._send_service_reminder(reminder)
                        if success:
                            sent_count += 1
                
                return sent_count
        
        except Exception as e:
            logger.error("Check service reminders failed", error=str(e))
            return 0
    
    async def _check_installation_reminders(self, today: datetime) -> int:
        """Проверяет напоминания монтажа."""
        try:
            async with self.context.get_session() as session:
                repo = InstallationRepository(session)
                
                # Получаем активные напоминания
                reminders = await repo.get_active_installation_reminders()
                
                sent_count = 0
                for reminder in reminders:
                    if reminder.should_notify_today():
                        # Отправляем напоминание
                        success = await self._send_installation_reminder(reminder)
                        if success:
                            sent_count += 1
                
                return sent_count
        
        except Exception as e:
            logger.error("Check installation reminders failed", error=str(e))
            return 0
    
    async def _check_contract_reminders(self, today: datetime) -> int:
        """Проверяет напоминания о контрактах."""
        try:
            async with self.context.get_session() as session:
                service_repo = ServiceRepository(session)
                installation_repo = InstallationRepository(session)
                
                sent_count = 0
                
                # Проверяем контракты обслуживания
                service_objects = await service_repo.get_all_active_objects()
                for obj in service_objects:
                    # Проверяем, нужно ли напоминать о контракте
                    reminders_sent = await self._check_object_contract(obj, today, "service")
                    sent_count += reminders_sent
                
                # Проверяем контракты монтажа
                installation_objects = await installation_repo.get_all_active_objects()
                for obj in installation_objects:
                    reminders_sent = await self._check_object_contract(obj, today, "installation")
                    sent_count += reminders_sent
                
                return sent_count
        
        except Exception as e:
            logger.error("Check contract reminders failed", error=str(e))
            return 0
    
    async def _check_object_contract(
        self, 
        obj: Any, 
        today: datetime, 
        object_type: str
    ) -> int:
        """Проверяет контракт конкретного объекта."""
        sent_count = 0
        
        # Проверяем окончание контракта
        days_until_end = (obj.contract_end_date - today.date()).days
        
        # Отправляем напоминания за указанное количество дней
        for days_before in config.bot.contract_warning_days:
            if days_until_end == days_before:
                success = await self._send_contract_reminder(obj, days_until_end, object_type)
                if success:
                    sent_count += 1
        
        # Проверяем начало контракта (за 7 дней и за 1 день)
        days_until_start = (obj.contract_start_date - today.date()).days
        
        if days_until_start == 7 or days_until_start == 1:
            success = await self._send_contract_start_reminder(obj, days_until_start, object_type)
            if success:
                sent_count += 1
        
        return sent_count
    
    async def _check_maintenance_reminders(self, today: datetime) -> int:
        """Проверяет напоминания о ТО."""
        try:
            async with self.context.get_session() as session:
                repo = ServiceRepository(session)
                
                # Получаем все активные ТО
                maintenance_list = await repo.get_all_maintenance()
                
                sent_count = 0
                current_month = today.month
                
                for maintenance in maintenance_list:
                    # Проверяем, нужно ли напоминать о ТО в этом месяце
                    if maintenance.month == current_month:
                        # Проверяем, было ли уже выполнено в этом месяце
                        if (not maintenance.last_completed or 
                            maintenance.last_completed.month != current_month):
                            
                            success = await self._send_maintenance_reminder(maintenance)
                            if success:
                                sent_count += 1
                
                return sent_count
        
        except Exception as e:
            logger.error("Check maintenance reminders failed", error=str(e))
            return 0
    
    async def _check_supply_reminders(self, today: datetime) -> int:
        """Проверяет напоминания о поставках."""
        try:
            async with self.context.get_session() as session:
                repo = InstallationRepository(session)
                
                # Получаем запланированные поставки
                supplies = await repo.get_planned_supplies()
                
                sent_count = 0
                
                for supply in supplies:
                    # Проверяем, нужно ли напоминать о поставке
                    days_until_delivery = (supply.delivery_date - today.date()).days
                    
                    if days_until_delivery == 1:  # За день до поставки
                        success = await self._send_supply_reminder(supply)
                        if success:
                            sent_count += 1
                
                return sent_count
        
        except Exception as e:
            logger.error("Check supply reminders failed", error=str(e))
            return 0
    
    async def _send_service_reminder(self, reminder) -> bool:
        """Отправляет напоминание обслуживания."""
        try:
            # Форматируем сообщение
            message = format_reminder_message(reminder, "service")
            
            # Получаем пользователей для отправки
            users_to_notify = await self._get_users_to_notify(
                reminder.service_object,
                reminder.reminder_type
            )
            
            # Отправляем каждому пользователю
            for user in users_to_notify:
                try:
                    await self.bot.send_message(
                        chat_id=user.telegram_id,
                        text=message,
                        parse_mode="HTML"
                    )
                    logger.info(
                        "Service reminder sent",
                        reminder_id=reminder.id,
                        user_id=user.id
                    )
                except Exception as e:
                    logger.error(
                        "Failed to send service reminder to user",
                        reminder_id=reminder.id,
                        user_id=user.id,
                        error=str(e)
                    )
            
            # Помечаем как отправленное (если это разовое напоминание)
            if reminder.reminder_type == "custom":
                await self._mark_reminder_notified(reminder)
            
            return True
        
        except Exception as e:
            logger.error("Send service reminder failed", reminder_id=reminder.id, error=str(e))
            return False
    
    async def _send_installation_reminder(self, reminder) -> bool:
        """Отправляет напоминание монтажа."""
        try:
            # Форматируем сообщение
            message = format_reminder_message(reminder, "installation")
            
            # Получаем пользователей для отправки
            users_to_notify = await self._get_users_to_notify(
                reminder.installation_object,
                reminder.reminder_type
            )
            
            # Отправляем каждому пользователю
            for user in users_to_notify:
                try:
                    await self.bot.send_message(
                        chat_id=user.telegram_id,
                        text=message,
                        parse_mode="HTML"
                    )
                    logger.info(
                        "Installation reminder sent",
                        reminder_id=reminder.id,
                        user_id=user.id
                    )
                except Exception as e:
                    logger.error(
                        "Failed to send installation reminder to user",
                        reminder_id=reminder.id,
                        user_id=user.id,
                        error=str(e)
                    )
            
            # Помечаем как отправленное
            if reminder.reminder_type == "custom":
                await self._mark_reminder_notified(reminder)
            
            return True
        
        except Exception as e:
            logger.error("Send installation reminder failed", reminder_id=reminder.id, error=str(e))
            return False
    
    async def _send_contract_reminder(self, obj, days_until_end: int, object_type: str) -> bool:
        """Отправляет напоминание о контракте."""
        try:
            # Форматируем сообщение
            if object_type == "service":
                message = (
                    f"📅 <b>Напоминание о контракте обслуживания</b>\n\n"
                    f"Объект: {obj.short_name} ({obj.full_name})\n"
                    f"Контракт заканчивается через {days_until_end} дней\n"
                    f"Дата окончания: {obj.contract_end_date.strftime('%d.%m.%Y')}\n"
                    f"Номер контракта: {obj.document_number}"
                )
            else:
                message = (
                    f"📅 <b>Напоминание о контракте монтажа</b>\n\n"
                    f"Объект: {obj.short_name} ({obj.full_name})\n"
                    f"Контракт заканчивается через {days_until_end} дней\n"
                    f"Дата окончания: {obj.contract_end_date.strftime('%d.%m.%Y')}\n"
                    f"Номер контракта: {obj.document_number}"
                )
            
            # Получаем пользователей для отправки
            users_to_notify = await self._get_users_to_notify(obj, "contract")
            
            # Отправляем каждому пользователю
            for user in users_to_notify:
                try:
                    await self.bot.send_message(
                        chat_id=user.telegram_id,
                        text=message,
                        parse_mode="HTML"
                    )
                    logger.info(
                        "Contract reminder sent",
                        object_id=obj.id,
                        object_type=object_type,
                        user_id=user.id,
                        days_until_end=days_until_end
                    )
                except Exception as e:
                    logger.error(
                        "Failed to send contract reminder to user",
                        object_id=obj.id,
                        user_id=user.id,
                        error=str(e)
                    )
            
            return True
        
        except Exception as e:
            logger.error(
                "Send contract reminder failed", 
                object_id=obj.id,
                object_type=object_type,
                error=str(e)
            )
            return False
    
    async def _send_contract_start_reminder(self, obj, days_until_start: int, object_type: str) -> bool:
        """Отправляет напоминание о начале контракта."""
        try:
            # Форматируем сообщение
            if object_type == "service":
                message = (
                    f"🆕 <b>Напоминание о начале контракта обслуживания</b>\n\n"
                    f"Объект: {obj.short_name} ({obj.full_name})\n"
                    f"Контракт начинается через {days_until_start} дней\n"
                    f"Дата начала: {obj.contract_start_date.strftime('%d.%m.%Y')}\n"
                    f"Номер контракта: {obj.document_number}"
                )
            else:
                message = (
                    f"🆕 <b>Напоминание о начале контракта монтажа</b>\n\n"
                    f"Объект: {obj.short_name} ({obj.full_name})\n"
                    f"Контракт начинается через {days_until_start} дней\n"
                    f"Дата начала: {obj.contract_start_date.strftime('%d.%m.%Y')}\n"
                    f"Номер контракта: {obj.document_number}"
                )
            
            # Получаем пользователей для отправки
            users_to_notify = await self._get_users_to_notify(obj, "contract_start")
            
            # Отправляем каждому пользователю
            for user in users_to_notify:
                try:
                    await self.bot.send_message(
                        chat_id=user.telegram_id,
                        text=message,
                        parse_mode="HTML"
                    )
                    logger.info(
                        "Contract start reminder sent",
                        object_id=obj.id,
                        object_type=object_type,
                        user_id=user.id,
                        days_until_start=days_until_start
                    )
                except Exception as e:
                    logger.error(
                        "Failed to send contract start reminder to user",
                        object_id=obj.id,
                        user_id=user.id,
                        error=str(e)
                    )
            
            return True
        
        except Exception as e:
            logger.error(
                "Send contract start reminder failed", 
                object_id=obj.id,
                object_type=object_type,
                error=str(e)
            )
            return False
    
    async def _send_maintenance_reminder(self, maintenance) -> bool:
        """Отправляет напоминание о ТО."""
        try:
            # Форматируем сообщение
            message = (
                f"🔧 <b>Напоминание о техническом обслуживании</b>\n\n"
                f"Объект: {maintenance.service_object.short_name}\n"
                f"Частота: {maintenance.frequency}\n"
                f"Описание работ: {maintenance.description[:100]}...\n"
                f"Месяц выполнения: {maintenance.month or 'Ежемесячно'}"
            )
            
            # Получаем пользователей для отправки
            users_to_notify = await self._get_users_to_notify(
                maintenance.service_object,
                "maintenance"
            )
            
            # Отправляем каждому пользователю
            for user in users_to_notify:
                try:
                    await self.bot.send_message(
                        chat_id=user.telegram_id,
                        text=message,
                        parse_mode="HTML"
                    )
                    logger.info(
                        "Maintenance reminder sent",
                        maintenance_id=maintenance.id,
                        user_id=user.id
                    )
                except Exception as e:
                    logger.error(
                        "Failed to send maintenance reminder to user",
                        maintenance_id=maintenance.id,
                        user_id=user.id,
                        error=str(e)
                    )
            
            return True
        
        except Exception as e:
            logger.error("Send maintenance reminder failed", maintenance_id=maintenance.id, error=str(e))
            return False
    
    async def _send_supply_reminder(self, supply) -> bool:
        """Отправляет напоминание о поставке."""
        try:
            # Форматируем сообщение
            message = (
                f"🚚 <b>Напоминание о поставке</b>\n\n"
                f"Объект: {supply.installation_object.short_name}\n"
                f"Сервис доставки: {supply.delivery_service}\n"
                f"Дата доставки: {supply.delivery_date.strftime('%d.%m.%Y')}\n"
                f"Описание: {supply.description[:100]}..."
            )
            
            # Получаем пользователей для отправки
            users_to_notify = await self._get_users_to_notify(
                supply.installation_object,
                "supply"
            )
            
            # Отправляем каждому пользователю
            for user in users_to_notify:
                try:
                    await self.bot.send_message(
                        chat_id=user.telegram_id,
                        text=message,
                        parse_mode="HTML"
                    )
                    logger.info(
                        "Supply reminder sent",
                        supply_id=supply.id,
                        user_id=user.id
                    )
                except Exception as e:
                    logger.error(
                        "Failed to send supply reminder to user",
                        supply_id=supply.id,
                        user_id=user.id,
                        error=str(e)
                    )
            
            return True
        
        except Exception as e:
            logger.error("Send supply reminder failed", supply_id=supply.id, error=str(e))
            return False
    
    async def _get_users_to_notify(self, obj, reminder_type: str) -> List[Any]:
        """Получает список пользователей для уведомления."""
        users = []
        
        try:
            # Всегда уведомляем ответственного
            if obj.responsible and obj.responsible.is_active:
                users.append(obj.responsible)
            
            # Для контрактов также уведомляем главного админа и админов
            if reminder_type in ["contract", "contract_start"]:
                async with self.context.get_session() as session:
                    from storage.repositories.user_repository import UserRepository
                    repo = UserRepository(session)
                    
                    # Получаем главных админов и админов
                    admins = await repo.get_admins_by_levels(["main_admin", "admin"])
                    for admin in admins:
                        if admin.user.is_active and admin.user not in users:
                            users.append(admin.user)
            
            # Для ТО уведомляем обслугу
            elif reminder_type == "maintenance":
                async with self.context.get_session() as session:
                    from storage.repositories.user_repository import UserRepository
                    repo = UserRepository(session)
                    
                    service_admins = await repo.get_admins_by_levels(["service"])
                    for admin in service_admins:
                        if admin.user.is_active and admin.user not in users:
                            users.append(admin.user)
            
            # Для поставок уведомляем монтаж
            elif reminder_type == "supply":
                async with self.context.get_session() as session:
                    from storage.repositories.user_repository import UserRepository
                    repo = UserRepository(session)
                    
                    installation_admins = await repo.get_admins_by_levels(["installation"])
                    for admin in installation_admins:
                        if admin.user.is_active and admin.user not in users:
                            users.append(admin.user)
        
        except Exception as e:
            logger.error("Get users to notify failed", reminder_type=reminder_type, error=str(e))
        
        return users
    
    async def _mark_reminder_notified(self, reminder) -> None:
        """Помечает напоминание как отправленное."""
        try:
            async with self.context.get_session() as session:
                if hasattr(reminder, 'service_object_id'):
                    # Напоминание обслуживания
                    from storage.repositories.service_repository import ServiceRepository
                    repo = ServiceRepository(session)
                    await repo.mark_reminder_notified(reminder.id)
                else:
                    # Напоминание монтажа
                    from storage.repositories.installation_repository import InstallationRepository
                    repo = InstallationRepository(session)
                    await repo.mark_reminder_notified(reminder.id)
                
                await session.commit()
        
        except Exception as e:
            logger.error("Mark reminder notified failed", reminder_id=reminder.id, error=str(e))
    
    async def create_reminder(
        self,
        object_type: str,
        object_id: uuid.UUID,
        due_date: datetime,
        message: str,
        created_by: uuid.UUID,
        notify_day_before: bool = True,
        notify_on_day: bool = True
    ) -> Dict[str, Any]:
        """Создает новое напоминание."""
        try:
            async with self.context.get_session() as session:
                if object_type == "service":
                    from storage.repositories.service_repository import ServiceRepository
                    repo = ServiceRepository(session)
                    reminder = await repo.create_reminder(
                        object_id=object_id,
                        due_date=due_date,
                        message=message,
                        notify_day_before=notify_day_before,
                        notify_on_day=notify_on_day
                    )
                else:
                    from storage.repositories.installation_repository import InstallationRepository
                    repo = InstallationRepository(session)
                    reminder = await repo.create_reminder(
                        object_id=object_id,
                        due_date=due_date,
                        message=message,
                        notify_day_before=notify_day_before,
                        notify_on_day=notify_on_day
                    )
                
                await session.commit()
                
                logger.info(
                    "Reminder created",
                    reminder_id=reminder.id,
                    object_type=object_type,
                    object_id=object_id,
                    created_by=created_by
                )
                
                return {
                    "success": True,
                    "message": "Напоминание создано",
                    "reminder": {
                        "id": str(reminder.id),
                        "due_date": reminder.due_date.isoformat(),
                        "message": reminder.message,
                    }
                }
        
        except Exception as e:
            logger.error("Create reminder failed", object_type=object_type, object_id=object_id, error=str(e))
            return {
                "success": False,
                "message": f"Ошибка при создании напоминания: {str(e)}"
            }
    
    async def get_upcoming_reminders(
        self,
        user_id: uuid.UUID,
        days_ahead: int = 30
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Получает предстоящие напоминания для пользователя."""
        try:
            result = {
                "service": [],
                "installation": [],
                "contracts": [],
            }
            
            today = datetime.now().date()
            end_date = today + timedelta(days=days_ahead)
            
            async with self.context.get_session() as session:
                # Получаем объекты, за которые ответственен пользователь
                service_repo = ServiceRepository(session)
                installation_repo = InstallationRepository(session)
                
                # Напоминания обслуживания
                service_reminders = await service_repo.get_reminders_in_period(today, end_date)
                for reminder in service_reminders:
                    # Проверяем, имеет ли пользователь доступ к объекту
                    if await self._check_user_access_to_object(user_id, reminder.service_object_id, "service"):
                        result["service"].append({
                            "id": str(reminder.id),
                            "object_name": reminder.service_object.short_name,
                            "due_date": reminder.due_date.isoformat(),
                            "message": reminder.message,
                            "type": "reminder",
                        })
                
                # Напоминания монтажа
                installation_reminders = await installation_repo.get_reminders_in_period(today, end_date)
                for reminder in installation_reminders:
                    if await self._check_user_access_to_object(user_id, reminder.installation_object_id, "installation"):
                        result["installation"].append({
                            "id": str(reminder.id),
                            "object_name": reminder.installation_object.short_name,
                            "due_date": reminder.due_date.isoformat(),
                            "message": reminder.message,
                            "type": "reminder",
                        })
                
                # Контракты обслуживания (окончание в ближайшие дни)
                service_objects = await service_repo.get_objects_with_contracts_ending(end_date)
                for obj in service_objects:
                    if await self._check_user_access_to_object(user_id, obj.id, "service"):
                        days_until_end = (obj.contract_end_date - today).days
                        result["contracts"].append({
                            "id": str(obj.id),
                            "object_name": obj.short_name,
                            "due_date": obj.contract_end_date.isoformat(),
                            "message": f"Окончание контракта обслуживания",
                            "type": "contract",
                            "days_until": days_until_end,
                        })
                
                # Контракты монтажа
                installation_objects = await installation_repo.get_objects_with_contracts_ending(end_date)
                for obj in installation_objects:
                    if await self._check_user_access_to_object(user_id, obj.id, "installation"):
                        days_until_end = (obj.contract_end_date - today).days
                        result["contracts"].append({
                            "id": str(obj.id),
                            "object_name": obj.short_name,
                            "due_date": obj.contract_end_date.isoformat(),
                            "message": f"Окончание контракта монтажа",
                            "type": "contract",
                            "days_until": days_until_end,
                        })
            
            return result
        
        except Exception as e:
            logger.error("Get upcoming reminders failed", user_id=user_id, error=str(e))
            return {"service": [], "installation": [], "contracts": []}
    
    async def _check_user_access_to_object(
        self,
        user_id: uuid.UUID,
        object_id: uuid.UUID,
        object_type: str
    ) -> bool:
        """Проверяет, имеет ли пользователь доступ к объекту."""
        try:
            async with self.context.get_session() as session:
                from storage.repositories.user_repository import UserRepository
                repo = UserRepository(session)
                
                # Проверяем, является ли пользователь ответственным за объект
                if object_type == "service":
                    from storage.repositories.service_repository import ServiceRepository
                    obj_repo = ServiceRepository(session)
                    obj = await obj_repo.get_object_by_id(object_id)
                    if obj and obj.responsible_user_id == user_id:
                        return True
                else:
                    from storage.repositories.installation_repository import InstallationRepository
                    obj_repo = InstallationRepository(session)
                    obj = await obj_repo.get_object_by_id(object_id)
                    if obj and obj.responsible_user_id == user_id:
                        return True
                
                # Проверяем, является ли пользователь админом с доступом к этому типу объектов
                admin = await repo.get_admin_by_user_id(user_id)
                if admin:
                    if object_type == "service" and admin.level in ["main_admin", "admin", "service"]:
                        return True
                    elif object_type == "installation" and admin.level in ["main_admin", "admin", "installation"]:
                        return True
                
                return False
        
        except Exception as e:
            logger.error("Check user access failed", user_id=user_id, object_id=object_id, error=str(e))
            return False
    
    async def close(self) -> None:
        """Закрывает соединение с ботом."""
        await self.bot.session.close()