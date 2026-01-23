"""
Воркер для проверки и отправки напоминаний.
Запускается по расписанию для проверки предстоящих напоминаний.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from core.context import AppContext
from services.reminder_service import ReminderService
from services.notification_service import NotificationService
from utils.constants import EMOJI_REMINDER, EMOJI_WARNING, EMOJI_ERROR
from utils.formatters import format_reminder, format_warning_message
from utils.date_utils import get_current_datetime


logger = logging.getLogger(__name__)


class ReminderWorker:
    """
    Воркер для работы с напоминаниями.
    """
    
    def __init__(self, context: AppContext):
        """
        Инициализирует воркер напоминаний.
        
        Args:
            context: Контекст приложения
        """
        self.context = context
        self.reminder_service: ReminderService = context.reminder_service
        self.notification_service: NotificationService = context.notification_service
        self.is_running = False
        self.task = None
        
    async def start(self):
        """
        Запускает воркер.
        """
        if self.is_running:
            logger.warning("ReminderWorker уже запущен")
            return
        
        self.is_running = True
        logger.info("ReminderWorker запущен")
        
        # Запускаем фоновую задачу
        self.task = asyncio.create_task(self._run_worker())
        
    async def stop(self):
        """
        Останавливает воркер.
        """
        if not self.is_running:
            return
        
        self.is_running = False
        logger.info("Остановка ReminderWorker...")
        
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                logger.info("ReminderWorker остановлен")
                
    async def _run_worker(self):
        """
        Основной цикл воркера.
        """
        try:
            while self.is_running:
                try:
                    # Проверяем напоминания
                    await self.check_reminders()
                    
                    # Ждем 1 минуту перед следующей проверкой
                    await asyncio.sleep(60)
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Ошибка в ReminderWorker: {e}", exc_info=True)
                    await asyncio.sleep(60)  # Ждем перед повторной попыткой
                    
        except asyncio.CancelledError:
            logger.info("ReminderWorker получил сигнал отмены")
        except Exception as e:
            logger.error(f"Критическая ошибка в ReminderWorker: {e}", exc_info=True)
        finally:
            self.is_running = False
            logger.info("ReminderWorker завершил работу")
            
    async def check_reminders(self):
        """
        Проверяет и отправляет напоминания.
        """
        try:
            logger.debug("Начало проверки напоминаний")
            
            # Получаем текущее время
            now = get_current_datetime()
            
            # 1. Проверяем напоминания на сегодня
            reminders_today = await self.reminder_service.get_reminders_for_today()
            
            for reminder in reminders_today:
                await self._process_reminder(reminder, now, "сегодня")
                
            # 2. Проверяем напоминания завтра
            tomorrow = now + timedelta(days=1)
            reminders_tomorrow = await self.reminder_service.get_reminders_for_date(tomorrow)
            
            for reminder in reminders_tomorrow:
                await self._process_reminder(reminder, now, "завтра")
                
            # 3. Проверяем напоминания через неделю (для долгосрочных)
            week_later = now + timedelta(days=7)
            reminders_week = await self.reminder_service.get_reminders_for_date(week_later)
            
            for reminder in reminders_week:
                # Только для важных напоминаний (контракты и т.д.)
                if reminder.get('importance', 0) >= 2:
                    await self._process_reminder(reminder, now, "через неделю")
                    
            # 4. Проверяем просроченные напоминания
            expired_reminders = await self.reminder_service.get_expired_reminders()
            
            for reminder in expired_reminders:
                await self._process_expired_reminder(reminder, now)
                
            logger.debug(f"Проверка напоминаний завершена: сегодня={len(reminders_today)}, "
                        f"завтра={len(reminders_tomorrow)}, просрочено={len(expired_reminders)}")
                        
        except Exception as e:
            logger.error(f"Ошибка при проверке напоминаний: {e}", exc_info=True)
            
    async def _process_reminder(self, reminder: Dict[str, Any], now: datetime, time_frame: str):
        """
        Обрабатывает одно напоминание.
        
        Args:
            reminder: Данные напоминания
            now: Текущее время
            time_frame: Временной интервал ("сегодня", "завтра", "через неделю")
        """
        try:
            reminder_id = reminder.get('id')
            if not reminder_id:
                return
                
            # Проверяем, было ли уже отправлено уведомление
            last_notified = reminder.get('last_notified_at')
            if last_notified:
                # Если уже отправляли сегодня, пропускаем
                last_notified_date = last_notified.date() if isinstance(last_notified, datetime) else last_notified
                if last_notified_date == now.date():
                    return
                    
            # Получаем получателей
            recipients = await self.reminder_service.get_reminder_recipients(reminder_id)
            if not recipients:
                logger.warning(f"У напоминания {reminder_id} нет получателей")
                return
                
            # Форматируем сообщение
            message = self._format_reminder_message(reminder, time_frame)
            
            # Отправляем уведомления получателям
            sent_count = 0
            for recipient in recipients:
                user_id = recipient.get('user_id')
                if user_id:
                    try:
                        await self.notification_service.send_notification(
                            user_id=user_id,
                            message=message,
                            notification_type="reminder",
                            data=reminder
                        )
                        sent_count += 1
                    except Exception as e:
                        logger.error(f"Не удалось отправить напоминание пользователю {user_id}: {e}")
                        
            # Обновляем статус напоминания
            if sent_count > 0:
                await self.reminder_service.mark_reminder_notified(
                    reminder_id=reminder_id,
                    notification_id=f"batch_{now.strftime('%Y%m%d_%H%M')}"
                )
                
                logger.info(f"Отправлено напоминание {reminder_id} для {sent_count} получателей")
                
        except Exception as e:
            logger.error(f"Ошибка при обработке напоминания: {e}", exc_info=True)
            
    async def _process_expired_reminder(self, reminder: Dict[str, Any], now: datetime):
        """
        Обрабатывает просроченное напоминание.
        
        Args:
            reminder: Данные напоминания
            now: Текущее время
        """
        try:
            reminder_id = reminder.get('id')
            if not reminder_id:
                return
                
            # Проверяем, не отправляли ли уже уведомление о просрочке
            overdue_notified = reminder.get('overdue_notified', False)
            if overdue_notified:
                return
                
            # Получаем получателей
            recipients = await self.reminder_service.get_reminder_recipients(reminder_id)
            if not recipients:
                return
                
            # Форматируем сообщение о просрочке
            message = self._format_overdue_message(reminder)
            
            # Отправляем уведомления
            sent_count = 0
            for recipient in recipients:
                user_id = recipient.get('user_id')
                if user_id:
                    try:
                        await self.notification_service.send_notification(
                            user_id=user_id,
                            message=message,
                            notification_type="overdue_reminder",
                            data=reminder
                        )
                        sent_count += 1
                    except Exception as e:
                        logger.error(f"Не удалось отправить уведомление о просрочке пользователю {user_id}: {e}")
                        
            # Отмечаем что уведомили о просрочке
            if sent_count > 0:
                await self.reminder_service.mark_reminder_overdue_notified(reminder_id)
                logger.info(f"Отправлено уведомление о просрочке для напоминания {reminder_id}")
                
        except Exception as e:
            logger.error(f"Ошибка при обработке просроченного напоминания: {e}", exc_info=True)
            
    def _format_reminder_message(self, reminder: Dict[str, Any], time_frame: str) -> str:
        """
        Форматирует сообщение напоминания.
        
        Args:
            reminder: Данные напоминания
            time_frame: Временной интервал
        
        Returns:
            Отформатированное сообщение
        """
        from utils.formatters import format_reminder as fmt_reminder
        
        # Основное сообщение
        reminder_text = fmt_reminder(reminder)
        
        # Добавляем информацию о времени
        time_text = {
            "сегодня": "⏰ **Напоминание на сегодня!**",
            "завтра": "⏰ **Напоминание на завтра**",
            "через неделю": "⏰ **Напоминание через неделю**"
        }.get(time_frame, "⏰ **Напоминание**")
        
        return f"{time_text}\n\n{reminder_text}"
        
    def _format_overdue_message(self, reminder: Dict[str, Any]) -> str:
        """
        Форматирует сообщение о просроченном напоминании.
        
        Args:
            reminder: Данные напоминания
        
        Returns:
            Отформатированное сообщение
        """
        from utils.formatters import format_reminder as fmt_reminder
        
        reminder_text = fmt_reminder(reminder)
        
        return f"{EMOJI_WARNING} **ПРОСРОЧЕНО!**\n\n{reminder_text}"
        
    async def send_immediate_reminder(self, reminder_data: Dict[str, Any], user_ids: List[int]) -> bool:
        """
        Немедленно отправляет напоминание указанным пользователям.
        
        Args:
            reminder_data: Данные напоминания
            user_ids: Список ID пользователей
        
        Returns:
            True если успешно отправлено хотя бы одному пользователю
        """
        try:
            if not user_ids:
                return False
                
            message = self._format_reminder_message(reminder_data, "сейчас")
            sent_count = 0
            
            for user_id in user_ids:
                try:
                    await self.notification_service.send_notification(
                        user_id=user_id,
                        message=message,
                        notification_type="immediate_reminder",
                        data=reminder_data
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Не удалось отправить немедленное напоминание пользователю {user_id}: {e}")
                    
            return sent_count > 0
            
        except Exception as e:
            logger.error(f"Ошибка при отправке немедленного напоминания: {e}", exc_info=True)
            return False
            
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Получает статистику работы воркера.
        
        Returns:
            Словарь со статистикой
        """
        try:
            # Получаем статистику от сервиса напоминаний
            stats = await self.reminder_service.get_statistics()
            
            # Добавляем информацию о работе воркера
            stats['worker'] = {
                'is_running': self.is_running,
                'last_check': get_current_datetime().isoformat() if self.is_running else None
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            return {
                'error': str(e),
                'worker': {
                    'is_running': self.is_running
                }
            }