import asyncio
from datetime import datetime
from typing import Dict, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import structlog

from core.context import AppContext
from services.reminder_service import ReminderService
from services.cleanup_service import CleanupService
from services.backup_service import BackupService
from config import config


logger = structlog.get_logger(__name__)


class TaskScheduler:
    """Планировщик фоновых задач."""
    
    def __init__(self, context: AppContext):
        self.context = context
        self.scheduler = AsyncIOScheduler()
        self.reminder_service = ReminderService(context)
        self.cleanup_service = CleanupService(context)
        self.backup_service = BackupService(context)
        self._jobs = {}
    
    async def initialize(self) -> None:
        """Инициализирует планировщик и все сервисы."""
        await self.reminder_service.initialize()
        await self.cleanup_service.initialize()
        await self.backup_service.initialize()
        
        logger.info("Task scheduler services initialized")
    
    def start(self) -> None:
        """Запускает планировщик задач."""
        # Задача проверки напоминаний
        self._schedule_reminder_check()
        
        # Задача очистки кэша
        self._schedule_cache_cleanup()
        
        # Задача очистки временных данных
        self._schedule_temp_cleanup()
        
        # Задача резервного копирования БД (ежедневно в 2:00)
        self._schedule_backup()
        
        # Задача проверки здоровья
        self._schedule_health_check()
        
        # Запускаем планировщик
        self.scheduler.start()
        
        logger.info("Task scheduler started", job_count=len(self._jobs))
    
    def _schedule_reminder_check(self) -> None:
        """Планирует задачу проверки напоминаний."""
        job = self.scheduler.add_job(
            self._check_reminders_task,
            trigger=IntervalTrigger(
                seconds=config.bot.reminder_check_interval
            ),
            id="reminder_check",
            name="Проверка напоминаний",
            replace_existing=True
        )
        self._jobs["reminder_check"] = job
        
        # Также запускаем немедленно при старте
        asyncio.create_task(self._check_reminders_task())
        
        logger.info(
            "Reminder check scheduled",
            interval=config.bot.reminder_check_interval
        )
    
    def _schedule_cache_cleanup(self) -> None:
        """Планирует задачу очистки кэша."""
        job = self.scheduler.add_job(
            self._cleanup_cache_task,
            trigger=IntervalTrigger(
                seconds=config.bot.cache_cleanup_interval
            ),
            id="cache_cleanup",
            name="Очистка кэша",
            replace_existing=True
        )
        self._jobs["cache_cleanup"] = job
        
        logger.info(
            "Cache cleanup scheduled",
            interval=config.bot.cache_cleanup_interval
        )
    
    def _schedule_temp_cleanup(self) -> None:
        """Планирует задачу очистки временных данных."""
        job = self.scheduler.add_job(
            self._cleanup_temp_data_task,
            trigger=IntervalTrigger(hours=1),  # Каждый час
            id="temp_cleanup",
            name="Очистка временных данных",
            replace_existing=True
        )
        self._jobs["temp_cleanup"] = job
        
        logger.info("Temp data cleanup scheduled")
    
    def _schedule_backup(self) -> None:
        """Планирует задачу резервного копирования."""
        job = self.scheduler.add_job(
            self._backup_database_task,
            trigger="cron",
            hour=2,  # В 2:00 ночи
            minute=0,
            id="database_backup",
            name="Резервное копирование БД",
            replace_existing=True
        )
        self._jobs["database_backup"] = job
        
        logger.info("Database backup scheduled (daily at 2:00)")
    
    def _schedule_health_check(self) -> None:
        """Планирует задачу проверки здоровья системы."""
        job = self.scheduler.add_job(
            self._health_check_task,
            trigger=IntervalTrigger(minutes=5),  # Каждые 5 минут
            id="health_check",
            name="Проверка здоровья системы",
            replace_existing=True
        )
        self._jobs["health_check"] = job
        
        logger.info("Health check scheduled")
    
    async def _check_reminders_task(self) -> None:
        """Задача проверки и отправки напоминаний."""
        try:
            logger.debug("Running reminder check task")
            stats = await self.reminder_service.check_and_send_reminders()
            
            if any(stats.values()):
                logger.info("Reminders sent", stats=stats)
        
        except Exception as e:
            logger.error("Reminder check task failed", error=str(e))
    
    async def _cleanup_cache_task(self) -> None:
        """Задача очистки кэша."""
        try:
            logger.debug("Running cache cleanup task")
            
            # Очищаем просроченные данные FSM
            fsm_cleaned = await self.cleanup_service.cleanup_expired_fsm_sessions()
            
            # Очищаем просроченные пагинации
            pagination_cleaned = await self.cleanup_service.cleanup_expired_pagination()
            
            # Очищаем старые поисковые запросы
            search_cleaned = await self.cleanup_service.cleanup_old_search_results()
            
            if fsm_cleaned or pagination_cleaned or search_cleaned:
                logger.info(
                    "Cache cleanup completed",
                    fsm_sessions=fsm_cleaned,
                    pagination=pagination_cleaned,
                    search_results=search_cleaned
                )
        
        except Exception as e:
            logger.error("Cache cleanup task failed", error=str(e))
    
    async def _cleanup_temp_data_task(self) -> None:
        """Задача очистки временных данных."""
        try:
            logger.debug("Running temp data cleanup task")
            
            # Очищаем старые экспортированные файлы
            exports_cleaned = await self.cleanup_service.cleanup_old_exports()
            
            # Очищаем неиспользуемые файлы
            unused_files_cleaned = await self.cleanup_service.cleanup_unused_files()
            
            # Очищаем старые логи
            logs_cleaned = await self.cleanup_service.cleanup_old_logs()
            
            if exports_cleaned or unused_files_cleaned or logs_cleaned:
                logger.info(
                    "Temp data cleanup completed",
                    exports=exports_cleaned,
                    unused_files=unused_files_cleaned,
                    logs=logs_cleaned
                )
        
        except Exception as e:
            logger.error("Temp data cleanup task failed", error=str(e))
    
    async def _backup_database_task(self) -> None:
        """Задача резервного копирования базы данных."""
        try:
            logger.info("Running database backup task")
            
            backup_file = await self.backup_service.create_backup()
            
            if backup_file:
                logger.info("Database backup created", file=backup_file)
                
                # Отправляем уведомление главному админу
                await self._notify_backup_complete(backup_file)
            else:
                logger.warning("Database backup failed")
        
        except Exception as e:
            logger.error("Database backup task failed", error=str(e))
    
    async def _health_check_task(self) -> None:
        """Задача проверки здоровья системы."""
        try:
            logger.debug("Running health check task")
            
            health_status = await self.context.health_check()
            
            # Логируем проблемы, если есть
            if not all(health_status.values()):
                logger.warning("Health check issues", status=health_status)
            
            # Можно также отправлять алерты при серьезных проблемах
            if not health_status.get("database", False):
                await self._send_health_alert("Database connection failed")
            
            if not health_status.get("redis", False):
                await self._send_health_alert("Redis connection failed")
        
        except Exception as e:
            logger.error("Health check task failed", error=str(e))
    
    async def _notify_backup_complete(self, backup_file: str) -> None:
        """Отправляет уведомление о завершении резервного копирования."""
        try:
            # Получаем информацию о файле
            import os
            file_size = os.path.getsize(backup_file)
            file_size_mb = file_size / (1024 * 1024)
            
            message = (
                f"✅ <b>Резервное копирование БД завершено</b>\n\n"
                f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                f"📁 Файл: {os.path.basename(backup_file)}\n"
                f"📊 Размер: {file_size_mb:.2f} MB\n"
                f"📍 Путь: {backup_file}"
            )
            
            # Отправляем главному админу
            await self.context.bot.send_message(
                chat_id=config.bot.main_admin_id,
                text=message,
                parse_mode="HTML"
            )
        
        except Exception as e:
            logger.error("Failed to send backup notification", error=str(e))
    
    async def _send_health_alert(self, message: str) -> None:
        """Отправляет алерт о проблемах со здоровьем системы."""
        try:
            alert_message = (
                f"⚠️ <b>Проблема со здоровьем системы</b>\n\n"
                f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                f"🔴 {message}"
            )
            
            await self.context.bot.send_message(
                chat_id=config.bot.main_admin_id,
                text=alert_message,
                parse_mode="HTML"
            )
        
        except Exception as e:
            logger.error("Failed to send health alert", error=str(e))
    
    def get_job_status(self) -> Dict[str, Dict[str, Any]]:
        """Получает статус всех задач."""
        status = {}
        
        for job_id, job in self._jobs.items():
            status[job_id] = {
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
                "running": bool(job.next_run_time),
            }
        
        return status
    
    def pause_job(self, job_id: str) -> bool:
        """Приостанавливает задачу."""
        if job_id in self._jobs:
            self._jobs[job_id].pause()
            logger.info("Job paused", job_id=job_id)
            return True
        return False
    
    def resume_job(self, job_id: str) -> bool:
        """Возобновляет задачу."""
        if job_id in self._jobs:
            self._jobs[job_id].resume()
            logger.info("Job resumed", job_id=job_id)
            return True
        return False
    
    def run_job_now(self, job_id: str) -> bool:
        """Запускает задачу немедленно."""
        if job_id in self._jobs:
            self._jobs[job_id].modify(next_run_time=datetime.now())
            logger.info("Job scheduled to run now", job_id=job_id)
            return True
        return False
    
    def shutdown(self) -> None:
        """Останавливает планировщик."""
        self.scheduler.shutdown()
        logger.info("Task scheduler shutdown")


def create_scheduler(context: AppContext) -> TaskScheduler:
    """Создает и настраивает планировщик задач."""
    scheduler = TaskScheduler(context)
    return scheduler