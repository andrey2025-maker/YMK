"""
Репозиторий для работы с логами изменений.
Реализует хранение логов действий пользователей, изменений данных
и ошибок системы согласно ТЗ.
"""
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models.log import (
    SystemLog,
    ChangeLog,
    ErrorLog,
    LogLevel,
    ChangeType,
    ObjectType
)
from storage.repositories.base import BaseRepository


class LogRepository(BaseRepository[SystemLog]):
    """
    Репозиторий для управления логами системы.
    """
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, SystemLog)
    
    async def create_system_log(
        self,
        user_id: int,
        action: str,
        level: LogLevel = LogLevel.INFO,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> SystemLog:
        """
        Создает системный лог действия пользователя.
        
        Args:
            user_id: ID пользователя
            action: Описание действия
            level: Уровень лога (по умолчанию INFO)
            details: Детали действия (опционально)
            ip_address: IP адрес (опционально)
            user_agent: User-Agent (опционально)
            
        Returns:
            Созданный объект SystemLog
        """
        log_data = {
            "user_id": user_id,
            "action": action,
            "level": level,
            "details": details or {},
            "ip_address": ip_address,
            "user_agent": user_agent,
            "timestamp": datetime.utcnow()
        }
        
        return await self.create(log_data)
    
    async def create_change_log(
        self,
        user_id: int,
        object_type: ObjectType,
        object_id: uuid.UUID,
        change_type: ChangeType,
        old_data: Dict[str, Any],
        new_data: Dict[str, Any],
        description: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> ChangeLog:
        """
        Создает лог изменения данных (формат "было → стало").
        
        Args:
            user_id: ID пользователя
            object_type: Тип измененного объекта
            object_id: ID измененного объекта
            change_type: Тип изменения (создание, обновление, удаление)
            old_data: Данные до изменения
            new_data: Данные после изменения
            description: Описание изменения (опционально)
            ip_address: IP адрес (опционально)
            
        Returns:
            Созданный объект ChangeLog
        """
        change_data = {
            "user_id": user_id,
            "object_type": object_type,
            "object_id": object_id,
            "change_type": change_type,
            "old_data": old_data,
            "new_data": new_data,
            "description": description,
            "ip_address": ip_address,
            "change_date": datetime.utcnow()
        }
        
        change_log = ChangeLog(**change_data)
        self.session.add(change_log)
        await self.session.commit()
        await self.session.refresh(change_log)
        
        return change_log
    
    async def create_error_log(
        self,
        error_type: str,
        error_message: str,
        traceback: Optional[str] = None,
        user_id: Optional[int] = None,
        request_data: Optional[Dict[str, Any]] = None,
        severity: str = "ERROR"
    ) -> ErrorLog:
        """
        Создает лог ошибки системы.
        
        Args:
            error_type: Тип ошибки
            error_message: Сообщение об ошибке
            traceback: Traceback ошибки (опционально)
            user_id: ID пользователя (опционально)
            request_data: Данные запроса (опционально)
            severity: Уровень серьезности (по умолчанию ERROR)
            
        Returns:
            Созданный объект ErrorLog
        """
        error_data = {
            "error_type": error_type,
            "error_message": error_message,
            "traceback": traceback,
            "user_id": user_id,
            "request_data": request_data or {},
            "severity": severity,
            "timestamp": datetime.utcnow(),
            "resolved": False
        }
        
        error_log = ErrorLog(**error_data)
        self.session.add(error_log)
        await self.session.commit()
        await self.session.refresh(error_log)
        
        return error_log
    
    async def get_system_logs(
        self,
        user_id: Optional[int] = None,
        level: Optional[LogLevel] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        action_filter: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[SystemLog]:
        """
        Получает системные логи с фильтрацией.
        
        Args:
            user_id: Фильтр по ID пользователя (опционально)
            level: Фильтр по уровню лога (опционально)
            start_date: Начальная дата периода (опционально)
            end_date: Конечная дата периода (опционально)
            action_filter: Фильтр по действию (опционально)
            skip: Количество пропущенных записей
            limit: Максимальное количество записей
            
        Returns:
            Список системных логов
        """
        conditions = []
        
        if user_id:
            conditions.append(SystemLog.user_id == user_id)
        
        if level:
            conditions.append(SystemLog.level == level)
        
        if start_date:
            conditions.append(SystemLog.timestamp >= start_date)
        
        if end_date:
            conditions.append(SystemLog.timestamp <= end_date)
        
        if action_filter:
            conditions.append(SystemLog.action.ilike(f"%{action_filter}%"))
        
        where_clause = and_(*conditions) if conditions else None
        
        stmt = select(SystemLog).order_by(desc(SystemLog.timestamp))
        
        if where_clause:
            stmt = stmt.where(where_clause)
        
        stmt = stmt.offset(skip).limit(limit)
        
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def get_change_logs(
        self,
        object_type: Optional[ObjectType] = None,
        object_id: Optional[uuid.UUID] = None,
        change_type: Optional[ChangeType] = None,
        user_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[ChangeLog]:
        """
        Получает логи изменений с фильтрацией.
        
        Args:
            object_type: Фильтр по типу объекта (опционально)
            object_id: Фильтр по ID объекта (опционально)
            change_type: Фильтр по типу изменения (опционально)
            user_id: Фильтр по ID пользователя (опционально)
            start_date: Начальная дата периода (опционально)
            end_date: Конечная дата периода (опционально)
            skip: Количество пропущенных записей
            limit: Максимальное количество записей
            
        Returns:
            Список логов изменений
        """
        conditions = []
        
        if object_type:
            conditions.append(ChangeLog.object_type == object_type)
        
        if object_id:
            conditions.append(ChangeLog.object_id == object_id)
        
        if change_type:
            conditions.append(ChangeLog.change_type == change_type)
        
        if user_id:
            conditions.append(ChangeLog.user_id == user_id)
        
        if start_date:
            conditions.append(ChangeLog.change_date >= start_date)
        
        if end_date:
            conditions.append(ChangeLog.change_date <= end_date)
        
        where_clause = and_(*conditions) if conditions else None
        
        stmt = select(ChangeLog).order_by(desc(ChangeLog.change_date))
        
        if where_clause:
            stmt = stmt.where(where_clause)
        
        stmt = stmt.offset(skip).limit(limit)
        
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def get_error_logs(
        self,
        resolved: Optional[bool] = None,
        severity: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[ErrorLog]:
        """
        Получает логи ошибок с фильтрацией.
        
        Args:
            resolved: Фильтр по статусу решения (опционально)
            severity: Фильтр по уровню серьезности (опционально)
            start_date: Начальная дата периода (опционально)
            end_date: Конечная дата периода (опционально)
            skip: Количество пропущенных записей
            limit: Максимальное количество записей
            
        Returns:
            Список логов ошибок
        """
        conditions = []
        
        if resolved is not None:
            conditions.append(ErrorLog.resolved == resolved)
        
        if severity:
            conditions.append(ErrorLog.severity == severity)
        
        if start_date:
            conditions.append(ErrorLog.timestamp >= start_date)
        
        if end_date:
            conditions.append(ErrorLog.timestamp <= end_date)
        
        where_clause = and_(*conditions) if conditions else None
        
        stmt = select(ErrorLog).order_by(desc(ErrorLog.timestamp))
        
        if where_clause:
            stmt = stmt.where(where_clause)
        
        stmt = stmt.offset(skip).limit(limit)
        
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def mark_error_resolved(
        self,
        error_id: uuid.UUID,
        resolved_by: int,
        resolution_notes: Optional[str] = None
    ) -> Optional[ErrorLog]:
        """
        Отмечает ошибку как решенную.
        
        Args:
            error_id: ID ошибки
            resolved_by: ID пользователя решившего ошибку
            resolution_notes: Заметки о решении (опционально)
            
        Returns:
            Обновленный объект ErrorLog или None
        """
        stmt = select(ErrorLog).where(ErrorLog.id == error_id)
        result = await self.session.execute(stmt)
        error_log = result.scalar_one_or_none()
        
        if error_log:
            error_log.resolved = True
            error_log.resolved_at = datetime.utcnow()
            error_log.resolved_by = resolved_by
            error_log.resolution_notes = resolution_notes
            
            await self.session.commit()
            await self.session.refresh(error_log)
        
        return error_log
    
    async def get_log_statistics(
        self,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Получает статистику по логам за указанный период.
        
        Args:
            days: Количество дней для анализа (по умолчанию 30)
            
        Returns:
            Словарь со статистикой
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Статистика по системным логам
        system_stmt = (
            select(
                func.date_trunc('day', SystemLog.timestamp).label('date'),
                SystemLog.level,
                func.count(SystemLog.id)
            )
            .where(SystemLog.timestamp >= start_date)
            .group_by('date', SystemLog.level)
            .order_by(desc('date'))
        )
        system_result = await self.session.execute(system_stmt)
        system_stats = {}
        
        for row in system_result.all():
            date_str = row[0].strftime("%Y-%m-%d")
            if date_str not in system_stats:
                system_stats[date_str] = {}
            system_stats[date_str][row[1].value] = row[2]
        
        # Статистика по изменениям
        change_stmt = (
            select(
                func.date_trunc('day', ChangeLog.change_date).label('date'),
                ChangeLog.change_type,
                func.count(ChangeLog.id)
            )
            .where(ChangeLog.change_date >= start_date)
            .group_by('date', ChangeLog.change_type)
            .order_by(desc('date'))
        )
        change_result = await self.session.execute(change_stmt)
        change_stats = {}
        
        for row in change_result.all():
            date_str = row[0].strftime("%Y-%m-%d")
            if date_str not in change_stats:
                change_stats[date_str] = {}
            change_stats[date_str][row[1].value] = row[2]
        
        # Статистика по ошибкам
        error_stmt = (
            select(
                func.date_trunc('day', ErrorLog.timestamp).label('date'),
                ErrorLog.severity,
                func.count(ErrorLog.id)
            )
            .where(ErrorLog.timestamp >= start_date)
            .group_by('date', ErrorLog.severity)
            .order_by(desc('date'))
        )
        error_result = await self.session.execute(error_stmt)
        error_stats = {}
        
        for row in error_result.all():
            date_str = row[0].strftime("%Y-%m-%d")
            if date_str not in error_stats:
                error_stats[date_str] = {}
            error_stats[date_str][row[1]] = row[2]
        
        # Общая статистика
        total_system = await self._count_logs(SystemLog, start_date)
        total_changes = await self._count_logs(ChangeLog, start_date)
        total_errors = await self._count_logs(ErrorLog, start_date)
        unresolved_errors = await self._count_logs(
            ErrorLog, start_date, ErrorLog.resolved == False
        )
        
        # Топ пользователей по активности
        user_activity_stmt = (
            select(
                SystemLog.user_id,
                func.count(SystemLog.id).label('activity_count')
            )
            .where(SystemLog.timestamp >= start_date)
            .group_by(SystemLog.user_id)
            .order_by(desc('activity_count'))
            .limit(10)
        )
        user_activity_result = await self.session.execute(user_activity_stmt)
        top_users = [
            {"user_id": row[0], "activity_count": row[1]}
            for row in user_activity_result.all()
        ]
        
        return {
            "period_days": days,
            "total_system_logs": total_system,
            "total_changes": total_changes,
            "total_errors": total_errors,
            "unresolved_errors": unresolved_errors,
            "system_stats_by_day": system_stats,
            "change_stats_by_day": change_stats,
            "error_stats_by_day": error_stats,
            "top_active_users": top_users
        }
    
    async def cleanup_old_logs(
        self,
        older_than_days: int = 90,
        batch_size: int = 1000
    ) -> Dict[str, int]:
        """
        Удаляет старые логи (очистка согласно ТЗ).
        
        Args:
            older_than_days: Удалять логи старше X дней (по умолчанию 90)
            batch_size: Размер пачки для удаления
            
        Returns:
            Словарь с количеством удаленных логов каждого типа
        """
        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
        
        # Удаляем старые системные логи
        system_delete_stmt = (
            select(SystemLog.id)
            .where(SystemLog.timestamp < cutoff_date)
            .limit(batch_size)
        )
        system_result = await self.session.execute(system_delete_stmt)
        system_ids = system_result.scalars().all()
        
        system_deleted = 0
        if system_ids:
            delete_stmt = (
                select(SystemLog)
                .where(SystemLog.id.in_(system_ids))
            )
            delete_result = await self.session.execute(delete_stmt)
            logs_to_delete = delete_result.scalars().all()
            
            for log in logs_to_delete:
                await self.session.delete(log)
            system_deleted = len(logs_to_delete)
        
        # Удаляем старые логи изменений
        change_delete_stmt = (
            select(ChangeLog.id)
            .where(ChangeLog.change_date < cutoff_date)
            .limit(batch_size)
        )
        change_result = await self.session.execute(change_delete_stmt)
        change_ids = change_result.scalars().all()
        
        change_deleted = 0
        if change_ids:
            delete_stmt = (
                select(ChangeLog)
                .where(ChangeLog.id.in_(change_ids))
            )
            delete_result = await self.session.execute(delete_stmt)
            logs_to_delete = delete_result.scalars().all()
            
            for log in logs_to_delete:
                await self.session.delete(log)
            change_deleted = len(logs_to_delete)
        
        # Удаляем решенные старые ошибки (неурешенные оставляем)
        error_delete_stmt = (
            select(ErrorLog.id)
            .where(
                and_(
                    ErrorLog.timestamp < cutoff_date,
                    ErrorLog.resolved == True
                )
            )
            .limit(batch_size)
        )
        error_result = await self.session.execute(error_delete_stmt)
        error_ids = error_result.scalars().all()
        
        error_deleted = 0
        if error_ids:
            delete_stmt = (
                select(ErrorLog)
                .where(ErrorLog.id.in_(error_ids))
            )
            delete_result = await self.session.execute(delete_stmt)
            logs_to_delete = delete_result.scalars().all()
            
            for log in logs_to_delete:
                await self.session.delete(log)
            error_deleted = len(logs_to_delete)
        
        await self.session.commit()
        
        return {
            "system_logs_deleted": system_deleted,
            "change_logs_deleted": change_deleted,
            "error_logs_deleted": error_deleted,
            "total_deleted": system_deleted + change_deleted + error_deleted
        }
    
    async def _count_logs(
        self,
        model_class,
        start_date: Optional[datetime] = None,
        additional_condition = None
    ) -> int:
        """
        Вспомогательный метод для подсчета логов.
        
        Args:
            model_class: Класс модели
            start_date: Начальная дата (опционально)
            additional_condition: Дополнительное условие (опционально)
            
        Returns:
            Количество логов
        """
        conditions = []
        
        if start_date:
            timestamp_field = getattr(model_class, 'timestamp', None)
            if not timestamp_field:
                timestamp_field = getattr(model_class, 'change_date', None)
            if timestamp_field:
                conditions.append(timestamp_field >= start_date)
        
        if additional_condition:
            conditions.append(additional_condition)
        
        stmt = select(func.count(model_class.id))
        
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        result = await self.session.execute(stmt)
        return result.scalar() or 0