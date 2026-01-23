"""
Воркер для автоматического резервного копирования.
Создает резервные копии БД и архивирует данные в Telegram.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

from core.context import AppContext
from services.backup_service import BackupService
from services.notification_service import NotificationService
from utils.constants import EMOJI_SUCCESS, EMOJI_WARNING, EMOJI_ERROR, EMOJI_FILE
from utils.formatters import format_success_message, format_warning_message, format_error_message
from utils.date_utils import get_current_datetime, format_datetime


logger = logging.getLogger(__name__)


class BackupWorker:
    """
    Воркер для резервного копирования.
    """
    
    def __init__(self, context: AppContext):
        """
        Инициализирует воркер бэкапов.
        
        Args:
            context: Контекст приложения
        """
        self.context = context
        self.backup_service: BackupService = context.backup_service
        self.notification_service: NotificationService = context.notification_service
        self.is_running = False
        self.task = None
        self.last_backup_time: Optional[datetime] = None
        self.backup_count = 0
        self.error_count = 0
        
    async def start(self):
        """
        Запускает воркер.
        """
        if self.is_running:
            logger.warning("BackupWorker уже запущен")
            return
        
        self.is_running = True
        logger.info("BackupWorker запущен")
        
        # Запускаем фоновую задачу
        self.task = asyncio.create_task(self._run_worker())
        
    async def stop(self):
        """
        Останавливает воркер.
        """
        if not self.is_running:
            return
        
        self.is_running = False
        logger.info("Остановка BackupWorker...")
        
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                logger.info("BackupWorker остановлен")
                
    async def _run_worker(self):
        """
        Основной цикл воркера.
        """
        try:
            while self.is_running:
                try:
                    # Проверяем, нужно ли делать бэкап
                    if self._should_run_backup():
                        await self.run_backup()
                    
                    # Ждем 1 час перед следующей проверкой
                    await asyncio.sleep(3600)
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Ошибка в BackupWorker: {e}", exc_info=True)
                    self.error_count += 1
                    await asyncio.sleep(300)  # Ждем 5 минут перед повторной попыткой
                    
        except asyncio.CancelledError:
            logger.info("BackupWorker получил сигнал отмены")
        except Exception as e:
            logger.error(f"Критическая ошибка в BackupWorker: {e}", exc_info=True)
        finally:
            self.is_running = False
            logger.info("BackupWorker завершил работу")
            
    def _should_run_backup(self) -> bool:
        """
        Проверяет, нужно ли запускать бэкап.
        
        Returns:
            True если нужно выполнить бэкап
        """
        # Если еще не делали бэкап
        if not self.last_backup_time:
            return True
            
        now = get_current_datetime()
        
        # Проверяем, прошло ли более 24 часов с последнего бэкапа
        time_since_last = now - self.last_backup_time
        return time_since_last.total_seconds() >= 86400  # 24 часа
            
    async def run_backup(self):
        """
        Выполняет полный процесс резервного копирования.
        """
        try:
            logger.info("Запуск процесса резервного копирования...")
            
            start_time = get_current_datetime()
            
            # 1. Создание резервной копии базы данных
            db_backup_result = await self.backup_service.create_database_backup()
            
            if not db_backup_result.get('success'):
                error_msg = db_backup_result.get('error', 'Неизвестная ошибка')
                logger.error(f"Ошибка при создании бэкапа БД: {error_msg}")
                await self._notify_backup_failed("базы данных", error_msg)
                return
                
            # 2. Архивирование файлов
            files_backup_result = await self.backup_service.archive_files()
            
            if not files_backup_result.get('success'):
                error_msg = files_backup_result.get('error', 'Неизвестная ошибка')
                logger.error(f"Ошибка при архивировании файлов: {error_msg}")
                await self._notify_backup_failed("файлов", error_msg)
                return
                
            # 3. Отправка в Telegram
            telegram_result = await self.backup_service.send_to_telegram(
                db_backup_result['backup_path'],
                files_backup_result.get('archive_path')
            )
            
            if not telegram_result.get('success'):
                error_msg = telegram_result.get('error', 'Неизвестная ошибка')
                logger.error(f"Ошибка при отправке в Telegram: {error_msg}")
                await self._notify_backup_failed("отправки в Telegram", error_msg)
                return
                
            # 4. Очистка старых бэкапов
            cleanup_result = await self.backup_service.cleanup_old_backups()
            
            # Обновляем статистику
            self.last_backup_time = get_current_datetime()
            self.backup_count += 1
            
            # Рассчитываем время выполнения
            end_time = get_current_datetime()
            duration = (end_time - start_time).total_seconds()
            
            # Формируем отчет
            report = self._create_backup_report(
                db_backup_result,
                files_backup_result,
                telegram_result,
                cleanup_result,
                duration
            )
            
            # Отправляем уведомление об успешном бэкапе
            await self._notify_backup_success(report)
            
            logger.info(f"Резервное копирование успешно завершено за {duration:.1f} секунд")
            
        except Exception as e:
            logger.error(f"Ошибка при выполнении бэкапа: {e}", exc_info=True)
            self.error_count += 1
            await self._notify_backup_failed("общего процесса", str(e))
            
    async def run_manual_backup(self, notify_admins: bool = True) -> Dict[str, Any]:
        """
        Запускает ручное резервное копирование.
        
        Args:
            notify_admins: Отправлять ли уведомления администраторам
        
        Returns:
            Результат бэкапа
        """
        try:
            logger.info("Запуск ручного резервного копирования...")
            
            start_time = get_current_datetime()
            
            # Выполняем бэкап
            backup_result = await self.backup_service.create_full_backup()
            
            # Обновляем статистику
            self.last_backup_time = get_current_datetime()
            self.backup_count += 1
            
            # Рассчитываем время выполнения
            end_time = get_current_datetime()
            duration = (end_time - start_time).total_seconds()
            
            # Формируем отчет
            report = {
                'success': backup_result.get('success', False),
                'type': 'manual',
                'start_time': start_time,
                'end_time': end_time,
                'duration_seconds': duration,
                'details': backup_result,
                'error': backup_result.get('error')
            }
            
            # Отправляем уведомление если нужно
            if notify_admins and report['success']:
                await self._notify_backup_success(self._create_report_message(report))
            elif notify_admins and not report['success']:
                await self._notify_backup_failed("ручного бэкапа", backup_result.get('error', 'Неизвестная ошибка'))
                
            logger.info(f"Ручное резервное копирование завершено: успех={report['success']}")
            
            return report
            
        except Exception as e:
            logger.error(f"Ошибка при выполнении ручного бэкапа: {e}", exc_info=True)
            self.error_count += 1
            
            error_report = {
                'success': False,
                'error': str(e),
                'type': 'manual'
            }
            
            if notify_admins:
                await self._notify_backup_failed("ручного бэкапа", str(e))
                
            return error_report
            
    def _create_backup_report(
        self,
        db_result: Dict[str, Any],
        files_result: Dict[str, Any],
        telegram_result: Dict[str, Any],
        cleanup_result: Dict[str, Any],
        duration: float
    ) -> Dict[str, Any]:
        """
        Создает отчет о резервном копировании.
        
        Args:
            db_result: Результат бэкапа БД
            files_result: Результат архивирования файлов
            telegram_result: Результат отправки в Telegram
            cleanup_result: Результат очистки
            duration: Время выполнения в секундах
        
        Returns:
            Отчет о бэкапе
        """
        return {
            'success': True,
            'type': 'auto',
            'timestamp': get_current_datetime(),
            'duration_seconds': duration,
            'database': {
                'success': db_result.get('success', False),
                'backup_path': db_result.get('backup_path'),
                'size_mb': db_result.get('size_mb', 0),
                'tables_count': db_result.get('tables_count', 0)
            },
            'files': {
                'success': files_result.get('success', False),
                'archive_path': files_result.get('archive_path'),
                'files_count': files_result.get('files_count', 0),
                'size_mb': files_result.get('size_mb', 0)
            },
            'telegram': {
                'success': telegram_result.get('success', False),
                'message_id': telegram_result.get('message_id'),
                'chat_id': telegram_result.get('chat_id'),
                'files_sent': telegram_result.get('files_sent', 0)
            },
            'cleanup': {
                'success': cleanup_result.get('success', False),
                'backups_deleted': cleanup_result.get('backups_deleted', 0),
                'space_freed_mb': cleanup_result.get('space_freed_mb', 0)
            },
            'worker_stats': {
                'backup_count': self.backup_count,
                'error_count': self.error_count,
                'last_backup_time': self.last_backup_time
            }
        }
        
    def _create_report_message(self, report: Dict[str, Any]) -> str:
        """
        Создает читаемое сообщение отчета.
        
        Args:
            report: Отчет о бэкапе
        
        Returns:
            Отформатированное сообщение
        """
        if not report.get('success'):
            error = report.get('error', 'Неизвестная ошибка')
            return f"{EMOJI_ERROR} **Ошибка резервного копирования**\n\n{error}"
        
        lines = [f"{EMOJI_SUCCESS} **Резервное копирование успешно завершено**"]
        
        # Общая информация
        lines.append(f"\n📊 **Общая информация:**")
        lines.append(f"• Тип: {report.get('type', 'автоматический')}")
        
        if report.get('start_time') and report.get('end_time'):
            start_str = format_datetime(report['start_time'])
            end_str = format_datetime(report['end_time'])
            duration = report.get('duration_seconds', 0)
            lines.append(f"• Время начала: {start_str}")
            lines.append(f"• Время окончания: {end_str}")
            lines.append(f"• Длительность: {duration:.1f} сек.")
        
        # Детали по компонентам
        if report.get('database', {}).get('success'):
            db = report['database']
            lines.append(f"\n{EMOJI_FILE} **База данных:**")
            lines.append(f"• Размер: {db.get('size_mb', 0):.2f} MB")
            lines.append(f"• Таблиц: {db.get('tables_count', 0)}")
        
        if report.get('files', {}).get('success'):
            files = report['files']
            lines.append(f"\n📁 **Файлы:**")
            lines.append(f"• Файлов: {files.get('files_count', 0)}")
            lines.append(f"• Размер: {files.get('size_mb', 0):.2f} MB")
        
        if report.get('telegram', {}).get('success'):
            tg = report['telegram']
            lines.append(f"\n📤 **Telegram:**")
            lines.append(f"• Файлов отправлено: {tg.get('files_sent', 0)}")
        
        if report.get('cleanup', {}).get('success'):
            cleanup = report['cleanup']
            if cleanup.get('backups_deleted', 0) > 0:
                lines.append(f"\n🗑️ **Очистка:**")
                lines.append(f"• Удалено бэкапов: {cleanup.get('backups_deleted', 0)}")
                lines.append(f"• Освобождено: {cleanup.get('space_freed_mb', 0):.2f} MB")
        
        # Статистика воркера
        if report.get('worker_stats'):
            stats = report['worker_stats']
            lines.append(f"\n⚙️ **Статистика воркера:**")
            lines.append(f"• Всего бэкапов: {stats.get('backup_count', 0)}")
            lines.append(f"• Ошибок: {stats.get('error_count', 0)}")
        
        return "\n".join(lines)
        
    async def _notify_backup_success(self, report: Dict[str, Any]):
        """
        Отправляет уведомление об успешном бэкапе.
        
        Args:
            report: Отчет о бэкапе
        """
        try:
            message = self._create_report_message(report)
            
            # Отправляем главному админу
            main_admin_id = self.context.config.main_admin_id
            if main_admin_id:
                await self.notification_service.send_notification(
                    user_id=main_admin_id,
                    message=message,
                    notification_type="backup_success",
                    data=report
                )
                
            logger.info("Уведомление об успешном бэкапе отправлено")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления об успешном бэкапе: {e}")
            
    async def _notify_backup_failed(self, component: str, error: str):
        """
        Отправляет уведомление о неудачном бэкапе.
        
        Args:
            component: Компонент где произошла ошибка
            error: Сообщение об ошибке
        """
        try:
            message = (
                f"{EMOJI_ERROR} **Ошибка резервного копирования**\n\n"
                f"Не удалось выполнить резервное копирование {component}.\n"
                f"Ошибка: {error}\n\n"
                f"⏰ Время: {format_datetime(get_current_datetime())}"
            )
            
            # Отправляем главному админу
            main_admin_id = self.context.config.main_admin_id
            if main_admin_id:
                await self.notification_service.send_notification(
                    user_id=main_admin_id,
                    message=message,
                    notification_type="backup_failed",
                    data={'component': component, 'error': error}
                )
                
            logger.warning(f"Уведомление об ошибке бэкапа отправлено: {component} - {error}")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления об ошибке бэкапа: {e}")
            
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Получает статистику работы воркера.
        
        Returns:
            Словарь со статистикой
        """
        # Получаем информацию о бэкапах
        backups_info = await self.backup_service.get_backups_info()
        
        return {
            'worker': {
                'is_running': self.is_running,
                'backup_count': self.backup_count,
                'error_count': self.error_count,
                'last_backup_time': self.last_backup_time.isoformat() if self.last_backup_time else None
            },
            'backups': backups_info
        }
        
    async def restore_backup(self, backup_id: str, notify_admins: bool = True) -> Dict[str, Any]:
        """
        Восстанавливает данные из резервной копии.
        
        Args:
            backup_id: ID резервной копии
            notify_admins: Отправлять ли уведомления
        
        Returns:
            Результат восстановления
        """
        try:
            logger.info(f"Запуск восстановления из бэкапа {backup_id}...")
            
            # Получаем информацию о бэкапе
            backup_info = await self.backup_service.get_backup_info(backup_id)
            if not backup_info:
                return {
                    'success': False,
                    'error': f"Резервная копия {backup_id} не найдена"
                }
            
            # Восстанавливаем
            restore_result = await self.backup_service.restore_from_backup(backup_id)
            
            # Отправляем уведомление если нужно
            if notify_admins:
                if restore_result.get('success'):
                    message = (
                        f"{EMOJI_SUCCESS} **Восстановление успешно завершено**\n\n"
                        f"Данные восстановлены из резервной копии от {backup_info.get('created_at')}.\n"
                        f"• Таблиц восстановлено: {restore_result.get('tables_restored', 0)}\n"
                        f"• Файлов восстановлено: {restore_result.get('files_restored', 0)}"
                    )
                else:
                    message = (
                        f"{EMOJI_ERROR} **Ошибка восстановления**\n\n"
                        f"Не удалось восстановить данные из бэкапа {backup_id}.\n"
                        f"Ошибка: {restore_result.get('error', 'Неизвестная ошибка')}"
                    )
                
                main_admin_id = self.context.config.main_admin_id
                if main_admin_id:
                    await self.notification_service.send_notification(
                        user_id=main_admin_id,
                        message=message,
                        notification_type="restore_completed",
                        data=restore_result
                    )
            
            return restore_result
            
        except Exception as e:
            logger.error(f"Ошибка при восстановлении из бэкапа: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }