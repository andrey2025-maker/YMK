"""
Репозиторий для работы с напоминаниями.
Реализует управление напоминаниями для контрактов, ТО, поставок
и пользовательских напоминаний согласно ТЗ.
"""
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models.reminder import (
    Reminder,
    ReminderRecipient,
    ReminderType,
    ReminderStatus,
    ReminderFrequency
)
from storage.repositories.base import BaseRepository


class ReminderRepository(BaseRepository[Reminder]):
    """
    Репозиторий для управления напоминаниями.
    """
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, Reminder)
    
    async def create_reminder(
        self,
        title: str,
        reminder_type: ReminderType,
        due_date: datetime,
        object_type: str,
        object_id: uuid.UUID,
        created_by: int,
        description: Optional[str] = None,
        frequency: Optional[ReminderFrequency] = None,
        days_before: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Reminder:
        """
        Создает новое напоминание.
        
        Args:
            title: Заголовок напоминания
            reminder_type: Тип напоминания (контракт, ТО, поставка, пользовательское)
            due_date: Дата и время напоминания
            object_type: Тип связанного объекта
            object_id: ID связанного объекта
            created_by: ID создателя напоминания
            description: Описание напоминания (опционально)
            frequency: Частота повторения (опционально)
            days_before: За сколько дней напоминать (опционально)
            metadata: Дополнительные метаданные (опционально)
            
        Returns:
            Созданный объект Reminder
        """
        reminder_data = {
            "title": title,
            "reminder_type": reminder_type,
            "due_date": due_date,
            "object_type": object_type,
            "object_id": object_id,
            "created_by": created_by,
            "description": description,
            "frequency": frequency,
            "days_before": days_before,
            "status": ReminderStatus.PENDING,
            "metadata": metadata or {},
            "created_at": datetime.utcnow()
        }
        
        return await self.create(reminder_data)
    
    async def add_recipient(
        self,
        reminder_id: uuid.UUID,
        user_id: int,
        notify_days_before: Optional[List[int]] = None
    ) -> ReminderRecipient:
        """
        Добавляет получателя к напоминанию.
        
        Args:
            reminder_id: ID напоминания
            user_id: ID пользователя
            notify_days_before: За сколько дней уведомлять (опционально)
            
        Returns:
            Созданный объект ReminderRecipient
        """
        recipient_data = {
            "reminder_id": reminder_id,
            "user_id": user_id,
            "notify_days_before": notify_days_before or [],
            "added_at": datetime.utcnow()
        }
        
        stmt = select(ReminderRecipient).where(
            and_(
                ReminderRecipient.reminder_id == reminder_id,
                ReminderRecipient.user_id == user_id
            )
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            # Обновляем существующего получателя
            existing.notify_days_before = notify_days_before or []
            await self.session.commit()
            return existing
        else:
            # Создаем нового получателя
            recipient = ReminderRecipient(**recipient_data)
            self.session.add(recipient)
            await self.session.commit()
            await self.session.refresh(recipient)
            return recipient
    
    async def get_upcoming_reminders(
        self,
        days_ahead: int = 30,
        include_today: bool = True
    ) -> List[Reminder]:
        """
        Получает предстоящие напоминания.
        
        Args:
            days_ahead: На сколько дней вперед искать (по умолчанию 30 как в ТЗ)
            include_today: Включать ли напоминания на сегодня
            
        Returns:
            Список предстоящих напоминаний
        """
        now = datetime.utcnow()
        start_date = now if include_today else now + timedelta(days=1)
        end_date = now + timedelta(days=days_ahead)
        
        stmt = (
            select(Reminder)
            .where(
                and_(
                    Reminder.due_date >= start_date,
                    Reminder.due_date <= end_date,
                    Reminder.status == ReminderStatus.PENDING
                )
            )
            .order_by(Reminder.due_date)
        )
        
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def get_reminders_by_object(
        self,
        object_type: str,
        object_id: uuid.UUID,
        reminder_type: Optional[ReminderType] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Reminder]:
        """
        Получает напоминания для объекта.
        
        Args:
            object_type: Тип объекта
            object_id: ID объекта
            reminder_type: Фильтр по типу напоминания (опционально)
            skip: Количество пропущенных записей
            limit: Максимальное количество записей
            
        Returns:
            Список напоминаний объекта
        """
        conditions = [
            Reminder.object_type == object_type,
            Reminder.object_id == object_id
        ]
        
        if reminder_type:
            conditions.append(Reminder.reminder_type == reminder_type)
        
        stmt = (
            select(Reminder)
            .where(and_(*conditions))
            .order_by(desc(Reminder.due_date))
            .offset(skip)
            .limit(limit)
        )
        
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def get_expired_reminders(self) -> List[Reminder]:
        """
        Получает просроченные напоминания.
        
        Returns:
            Список просроченных напоминаний
        """
        now = datetime.utcnow()
        
        stmt = (
            select(Reminder)
            .where(
                and_(
                    Reminder.due_date < now,
                    Reminder.status == ReminderStatus.PENDING
                )
            )
            .order_by(Reminder.due_date)
        )
        
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def mark_reminder_completed(
        self,
        reminder_id: uuid.UUID,
        completed_by: int
    ) -> Optional[Reminder]:
        """
        Отмечает напоминание как выполненное.
        
        Args:
            reminder_id: ID напоминания
            completed_by: ID пользователя выполнившего напоминание
            
        Returns:
            Обновленный объект Reminder или None
        """
        reminder = await self.get_by_id(reminder_id)
        if reminder:
            reminder.status = ReminderStatus.COMPLETED
            reminder.completed_at = datetime.utcnow()
            reminder.completed_by = completed_by
            
            # Для повторяющихся напоминаний создаем следующее
            if reminder.frequency and reminder.frequency != ReminderFrequency.ONCE:
                next_date = self._calculate_next_date(reminder.due_date, reminder.frequency)
                if next_date:
                    # Создаем копию напоминания на следующую дату
                    new_reminder_data = {
                        "title": reminder.title,
                        "reminder_type": reminder.reminder_type,
                        "due_date": next_date,
                        "object_type": reminder.object_type,
                        "object_id": reminder.object_id,
                        "created_by": reminder.created_by,
                        "description": reminder.description,
                        "frequency": reminder.frequency,
                        "days_before": reminder.days_before,
                        "status": ReminderStatus.PENDING,
                        "metadata": reminder.metadata
                    }
                    
                    new_reminder = Reminder(**new_reminder_data)
                    self.session.add(new_reminder)
                    
                    # Копируем получателей
                    recipients_stmt = select(ReminderRecipient).where(
                        ReminderRecipient.reminder_id == reminder_id
                    )
                    recipients_result = await self.session.execute(recipients_stmt)
                    recipients = recipients_result.scalars().all()
                    
                    for recipient in recipients:
                        new_recipient = ReminderRecipient(
                            reminder_id=new_reminder.id,
                            user_id=recipient.user_id,
                            notify_days_before=recipient.notify_days_before.copy()
                        )
                        self.session.add(new_recipient)
            
            await self.session.commit()
            await self.session.refresh(reminder)
        
        return reminder
    
    async def mark_reminder_sent(
        self,
        reminder_id: uuid.UUID,
        notification_id: Optional[str] = None
    ) -> Optional[Reminder]:
        """
        Отмечает напоминание как отправленное.
        
        Args:
            reminder_id: ID напоминания
            notification_id: ID отправленного уведомления (опционально)
            
        Returns:
            Обновленный объект Reminder или None
        """
        reminder = await self.get_by_id(reminder_id)
        if reminder:
            reminder.last_notified_at = datetime.utcnow()
            reminder.notification_id = notification_id
            reminder.notification_count = (reminder.notification_count or 0) + 1
            
            await self.session.commit()
            await self.session.refresh(reminder)
        
        return reminder
    
    async def get_reminder_recipients(
        self,
        reminder_id: uuid.UUID
    ) -> List[ReminderRecipient]:
        """
        Получает получателей напоминания.
        
        Args:
            reminder_id: ID напоминания
            
        Returns:
            Список получателей напоминания
        """
        stmt = (
            select(ReminderRecipient)
            .where(ReminderRecipient.reminder_id == reminder_id)
            .order_by(ReminderRecipient.added_at)
        )
        
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def get_reminders_for_user(
        self,
        user_id: int,
        include_completed: bool = False,
        days_ahead: Optional[int] = None
    ) -> List[Reminder]:
        """
        Получает напоминания для пользователя.
        
        Args:
            user_id: ID пользователя
            include_completed: Включать ли выполненные напоминания
            days_ahead: Фильтр по дням вперед (опционально)
            
        Returns:
            Список напоминаний пользователя
        """
        now = datetime.utcnow()
        
        # Базовые условия
        conditions = [
            ReminderRecipient.user_id == user_id
        ]
        
        if not include_completed:
            conditions.append(Reminder.status == ReminderStatus.PENDING)
        
        if days_ahead:
            end_date = now + timedelta(days=days_ahead)
            conditions.append(Reminder.due_date <= end_date)
        
        stmt = (
            select(Reminder)
            .join(ReminderRecipient, Reminder.id == ReminderRecipient.reminder_id)
            .where(and_(*conditions))
            .order_by(Reminder.due_date)
        )
        
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def delete_reminder(self, reminder_id: uuid.UUID) -> bool:
        """
        Удаляет напоминание и всех его получателей.
        
        Args:
            reminder_id: ID напоминания для удаления
            
        Returns:
            True если удаление успешно, False если напоминание не найдено
        """
        # Удаляем всех получателей
        recipients_stmt = select(ReminderRecipient).where(
            ReminderRecipient.reminder_id == reminder_id
        )
        recipients_result = await self.session.execute(recipients_stmt)
        recipients = recipients_result.scalars().all()
        
        for recipient in recipients:
            await self.session.delete(recipient)
        
        # Удаляем само напоминание
        reminder = await self.get_by_id(reminder_id)
        if reminder:
            await self.session.delete(reminder)
            await self.session.commit()
            return True
        
        return False
    
    async def get_reminder_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Получает статистику по напоминаниям.
        
        Args:
            start_date: Начальная дата периода (опционально)
            end_date: Конечная дата периода (опционально)
            
        Returns:
            Словарь со статистикой
        """
        conditions = []
        
        if start_date:
            conditions.append(Reminder.created_at >= start_date)
        if end_date:
            conditions.append(Reminder.created_at <= end_date)
        
        where_clause = and_(*conditions) if conditions else None
        
        # Общее количество напоминаний
        total_stmt = select(func.count(Reminder.id))
        if where_clause:
            total_stmt = total_stmt.where(where_clause)
        total_result = await self.session.execute(total_stmt)
        total_reminders = total_result.scalar() or 0
        
        # Количество по типам
        type_stmt = (
            select(Reminder.reminder_type, func.count(Reminder.id))
            .group_by(Reminder.reminder_type)
        )
        if where_clause:
            type_stmt = type_stmt.where(where_clause)
        type_result = await self.session.execute(type_stmt)
        by_type = dict(type_result.all())
        
        # Количество по статусам
        status_stmt = (
            select(Reminder.status, func.count(Reminder.id))
            .group_by(Reminder.status)
        )
        if where_clause:
            status_stmt = status_stmt.where(where_clause)
        status_result = await self.session.execute(status_stmt)
        by_status = dict(status_result.all())
        
        # Количество напоминаний по месяцам
        monthly_stmt = (
            select(
                func.date_trunc('month', Reminder.created_at).label('month'),
                func.count(Reminder.id)
            )
            .group_by('month')
            .order_by(desc('month'))
            .limit(12)
        )
        if where_clause:
            monthly_stmt = monthly_stmt.where(where_clause)
        monthly_result = await self.session.execute(monthly_stmt)
        by_month = [
            {"month": row[0].strftime("%Y-%m"), "count": row[1]}
            for row in monthly_result.all()
        ]
        
        return {
            "total_reminders": total_reminders,
            "by_type": by_type,
            "by_status": by_status,
            "by_month": by_month
        }
    
    def _calculate_next_date(
        self,
        current_date: datetime,
        frequency: ReminderFrequency
    ) -> Optional[datetime]:
        """
        Вычисляет следующую дату для повторяющегося напоминания.
        
        Args:
            current_date: Текущая дата напоминания
            frequency: Частота повторения
            
        Returns:
            Следующая дата или None если частота ONCE
        """
        if frequency == ReminderFrequency.DAILY:
            return current_date + timedelta(days=1)
        elif frequency == ReminderFrequency.WEEKLY:
            return current_date + timedelta(weeks=1)
        elif frequency == ReminderFrequency.MONTHLY:
            # Добавляем месяц, учитывая разные длины месяцев
            month = current_date.month + 1
            year = current_date.year
            if month > 12:
                month = 1
                year += 1
            # Находим последний день следующего месяца
            next_month = current_date.replace(year=year, month=month, day=1)
            if next_month.month == 2:  # Февраль
                last_day = 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28
            elif next_month.month in [4, 6, 9, 11]:  # 30 дней
                last_day = 30
            else:  # 31 день
                last_day = 31
            return next_month.replace(day=min(current_date.day, last_day))
        elif frequency == ReminderFrequency.YEARLY:
            return current_date.replace(year=current_date.year + 1)
        elif frequency == ReminderFrequency.QUARTERLY:
            return current_date + timedelta(days=90)  # Приблизительно квартал
        else:
            return None