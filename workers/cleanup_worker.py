"""
Воркер для очистки кэша и временных данных.
Регулярно очищает просроченные FSM сессии, пагинации и временные файлы.
"""
import asyncio
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

from core.context import AppContext
from services.cleanup_service import CleanupService
from utils.constants import EMOJI_SUCCESS, EMOJI_WARNING, EMOJI_ERROR
from utils.formatters import format_success_message, format_warning_message
from utils.date_utils import get_current_datetime, format_datetime


logger = logging.getLogger(__name__)


class CleanupWorker:
    """
    Воркер для очистки временных данных.
    """
    
    def __init__(self, context: AppContext):
        """
        Инициализирует воркер очистки.
        
        Args:
            context: Контекст приложения
        """
        self.context = context
        self.cleanup_service: CleanupService = context.cleanup_service
        self.is_running = False
        self.task = None
        self.last_cleanup_time: Optional[datetime] = None
        self.cleanup_count = 0
        self.total_cleaned = 0
        
    async def start(self):
        """
        Запускает воркер.
        """
        if self.is_running:
            logger.warning("CleanupWorker уже запущен")
            return
        
        self.is_running = True
        logger.info("CleanupWorker запущен")
        
        # Запускаем фоновую задачу
        self.task = asyncio.create_task(self._run_worker())
        
    async def stop(self):
        """
        Останавливает воркер.
        """
        if not self.is_running:
            return
        
        self.is_running = False
        logger.info("Остановка CleanupWorker...")
        
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                logger.info("CleanupWorker остановлен")
                
    async def _run_worker(self):
        """
        Основной цикл воркера.
        """
        try:
            while self.is_running:
                try:
                    # Проверяем, нужно ли выполнять очистку
                    if self._should_run_cleanup():
                        await self.run_cleanup()
                    
                    # Ждем 5 минут перед следующей проверкой
                    await asyncio.sleep(300)
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Ошибка в CleanupWorker: {e}", exc_info=True)
                    await asyncio.sleep(60)  # Ждем перед повторной попыткой
                    
        except asyncio.CancelledError:
            logger.info("CleanupWorker получил сигнал отмены")
        except Exception as e:
            logger.error(f"Критическая ошибка в CleanupWorker: {e}", exc_info=True)
        finally:
            self.is_running = False
            logger.info("CleanupWorker завершил работу")
            
    def _should_run_cleanup(self) -> bool:
        """
        Проверяет, нужно ли запускать очистку.
        
        Returns:
            True если нужно выполнить очистку
        """
        # Если еще не делали очистку
        if not self.last_cleanup_time:
            return True
            
        now = get_current_datetime()
        
        # Проверяем, прошло ли более 1 часа с последней очистки
        time_since_last = now - self.last_cleanup_time
        return time_since_last.total_seconds() >= 3600  # 1 час
            
    async def run_cleanup(self):
        """
        Выполняет полный процесс очистки.
        """
        try:
            logger.info("Запуск процесса очистки...")
            
            start_time = get_current_datetime()
            cleanup_stats = {
                'fsm_sessions': 0,
                'pagination_data': 0,
                'temp_files': 0,
                'cache_entries': 0,
                'total_freed_kb': 0
            }
            
            # 1. Очистка просроченных FSM сессий (таймаут 120 минут)
            fsm_result = await self.cleanup_service.cleanup_expired_fsm_sessions()
            if fsm_result.get('success'):
                cleanup_stats['fsm_sessions'] = fsm_result.get('cleaned_count', 0)
                logger.info(f"Очищено FSM сессий: {cleanup_stats['fsm_sessions']}")
            else:
                logger.warning(f"Ошибка очистки FSM сессий: {fsm_result.get('error')}")
            
            # 2. Очистка старых пагинаций (TTL 5-10 минут)
            pagination_result = await self.cleanup_service.cleanup_expired_pagination()
            if pagination_result.get('success'):
                cleanup_stats['pagination_data'] = pagination_result.get('cleaned_count', 0)
                logger.info(f"Очищено пагинаций: {cleanup_stats['pagination_data']}")
            else:
                logger.warning(f"Ошибка очистки пагинаций: {pagination_result.get('error')}")
            
            # 3. Очистка временных файлов
            files_result = await self.cleanup_service.cleanup_temp_files()
            if files_result.get('success'):
                cleanup_stats['temp_files'] = files_result.get('cleaned_count', 0)
                cleanup_stats['total_freed_kb'] += files_result.get('freed_space_kb', 0)
                logger.info(f"Очищено временных файлов: {cleanup_stats['temp_files']}")
            else:
                logger.warning(f"Ошибка очистки временных файлов: {files_result.get('error')}")
            
            # 4. Очистка кэша по паттернам
            cache_result = await self.cleanup_service.cleanup_cache_patterns()
            if cache_result.get('success'):
                cleanup_stats['cache_entries'] = cache_result.get('cleaned_count', 0)
                logger.info(f"Очищено записей кэша: {cleanup_stats['cache_entries']}")
            else:
                logger.warning(f"Ошибка очистки кэша: {cache_result.get('error')}")
            
            # 5. Очистка старых логов (старше 90 дней)
            logs_result = await self.cleanup_service.cleanup_old_logs()
            if logs_result.get('success'):
                logs_cleaned = logs_result.get('cleaned_count', 0)
                logger.info(f"Очищено старых логов: {logs_cleaned}")
                # Добавляем к статистике если нужно
                if 'logs' not in cleanup_stats:
                    cleanup_stats['logs'] = logs_cleaned
            else:
                logger.warning(f"Ошибка очистки логов: {logs_result.get('error')}")
            
            # Обновляем статистику
            self.last_cleanup_time = get_current_datetime()
            self.cleanup_count += 1
            self.total_cleaned += sum([
                cleanup_stats['fsm_sessions'],
                cleanup_stats['pagination_data'],
                cleanup_stats['temp_files'],
                cleanup_stats['cache_entries']
            ])
            
            # Рассчитываем время выполнения
            end_time = get_current_datetime()
            duration = (end_time - start_time).total_seconds()
            
            # Логируем результаты
            total_cleaned_items = sum([
                cleanup_stats['fsm_sessions'],
                cleanup_stats['pagination_data'],
                cleanup_stats['temp_files'],
                cleanup_stats['cache_entries']
            ])
            
            logger.info(
                f"Очистка завершена за {duration:.1f} секунд. "
                f"Очищено: {total_cleaned_items} элементов, "
                f"освобождено: {cleanup_stats['total_freed_kb'] / 1024:.2f} MB"
            )
            
            # Отправляем уведомление если было очищено много данных
            if total_cleaned_items > 1000 or cleanup_stats['total_freed_kb'] > 10240:  # > 10 MB
                await self._notify_cleanup_completed(cleanup_stats, duration)
            
            return {
                'success': True,
                'stats': cleanup_stats,
                'duration_seconds': duration,
                'timestamp': self.last_cleanup_time
            }
            
        except Exception as e:
            logger.error(f"Ошибка при выполнении очистки: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'timestamp': get_current_datetime()
            }
            
    async def run_manual_cleanup(self, cleanup_type: str = "all") -> Dict[str, Any]:
        """
        Запускает ручную очистку указанного типа.
        
        Args:
            cleanup_type: Тип очистки (all, fsm, pagination, files, cache, logs)
        
        Returns:
            Результат очистки
        """
        try:
            logger.info(f"Запуск ручной очистки типа: {cleanup_type}")
            
            start_time = get_current_datetime()
            result = {}
            
            if cleanup_type in ["all", "fsm"]:
                fsm_result = await self.cleanup_service.cleanup_expired_fsm_sessions()
                result['fsm'] = fsm_result
            
            if cleanup_type in ["all", "pagination"]:
                pagination_result = await self.cleanup_service.cleanup_expired_pagination()
                result['pagination'] = pagination_result
            
            if cleanup_type in ["all", "files"]:
                files_result = await self.cleanup_service.cleanup_temp_files()
                result['files'] = files_result
            
            if cleanup_type in ["all", "cache"]:
                cache_result = await self.cleanup_service.cleanup_cache_patterns()
                result['cache'] = cache_result
            
            if cleanup_type in ["all", "logs"]:
                logs_result = await self.cleanup_service.cleanup_old_logs()
                result['logs'] = logs_result
            
            # Рассчитываем время выполнения
            end_time = get_current_datetime()
            duration = (end_time - start_time).total_seconds()
            
            # Обновляем статистику
            self.last_cleanup_time = get_current_datetime()
            self.cleanup_count += 1
            
            # Подсчитываем общие результаты
            total_cleaned = 0
            for res in result.values():
                total_cleaned += res.get('cleaned_count', 0)
            
            self.total_cleaned += total_cleaned
            
            logger.info(
                f"Ручная очистка типа '{cleanup_type}' завершена за {duration:.1f} секунд. "
                f"Очищено: {total_cleaned} элементов"
            )
            
            return {
                'success': True,
                'type': cleanup_type,
                'results': result,
                'total_cleaned': total_cleaned,
                'duration_seconds': duration,
                'timestamp': self.last_cleanup_time
            }
            
        except Exception as e:
            logger.error(f"Ошибка при выполнении ручной очистки: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'type': cleanup_type,
                'timestamp': get_current_datetime()
            }
            
    async def cleanup_specific_pattern(self, pattern: str) -> Dict[str, Any]:
        """
        Очищает данные по конкретному паттерну.
        
        Args:
            pattern: Паттерн для поиска (например, "cache:*", "pagination:*")
        
        Returns:
            Результат очистки
        """
        try:
            logger.info(f"Очистка по паттерну: {pattern}")
            
            result = await self.cleanup_service.cleanup_by_pattern(pattern)
            
            if result.get('success'):
                cleaned_count = result.get('cleaned_count', 0)
                self.total_cleaned += cleaned_count
                logger.info(f"Очищено по паттерну '{pattern}': {cleaned_count} элементов")
            else:
                logger.warning(f"Ошибка очистки по паттерну '{pattern}': {result.get('error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при очистке по паттерну: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'pattern': pattern
            }
            
    async def cleanup_user_data(self, user_id: int) -> Dict[str, Any]:
        """
        Очищает все временные данные пользователя.
        
        Args:
            user_id: ID пользователя
        
        Returns:
            Результат очистки
        """
        try:
            logger.info(f"Очистка данных пользователя {user_id}")
            
            results = {}
            
            # 1. Очистка FSM состояний пользователя
            fsm_result = await self.cleanup_service.cleanup_user_fsm_sessions(user_id)
            results['fsm'] = fsm_result
            
            # 2. Очистка пагинаций пользователя
            pagination_result = await self.cleanup_service.cleanup_user_pagination(user_id)
            results['pagination'] = pagination_result
            
            # 3. Очистка временных файлов пользователя
            files_result = await self.cleanup_service.cleanup_user_temp_files(user_id)
            results['files'] = files_result
            
            # Подсчитываем общие результаты
            total_cleaned = 0
            for res in results.values():
                total_cleaned += res.get('cleaned_count', 0)
            
            self.total_cleaned += total_cleaned
            
            logger.info(f"Очищено данных пользователя {user_id}: {total_cleaned} элементов")
            
            return {
                'success': True,
                'user_id': user_id,
                'results': results,
                'total_cleaned': total_cleaned,
                'timestamp': get_current_datetime()
            }
            
        except Exception as e:
            logger.error(f"Ошибка при очистке данных пользователя: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'user_id': user_id
            }
            
    async def _notify_cleanup_completed(self, stats: Dict[str, Any], duration: float):
        """
        Отправляет уведомление о завершении очистки.
        
        Args:
            stats: Статистика очистки
            duration: Время выполнения в секундах
        """
        try:
            total_cleaned = sum([
                stats.get('fsm_sessions', 0),
                stats.get('pagination_data', 0),
                stats.get('temp_files', 0),
                stats.get('cache_entries', 0)
            ])
            
            if total_cleaned == 0:
                return  # Не отправляем уведомление если ничего не очищено
            
            freed_mb = stats.get('total_freed_kb', 0) / 1024
            
            message = (
                f"🧹 **Автоматическая очистка завершена**\n\n"
                f"⏱ Время выполнения: {duration:.1f} сек.\n"
                f"📊 Очищено элементов: {total_cleaned}\n"
                f"💾 Освобождено места: {freed_mb:.2f} MB\n\n"
                f"**Детали:**\n"
            )
            
            if stats.get('fsm_sessions', 0) > 0:
                message += f"• FSM сессии: {stats['fsm_sessions']}\n"
            
            if stats.get('pagination_data', 0) > 0:
                message += f"• Пагинации: {stats['pagination_data']}\n"
            
            if stats.get('temp_files', 0) > 0:
                message += f"• Временные файлы: {stats['temp_files']}\n"
            
            if stats.get('cache_entries', 0) > 0:
                message += f"• Записи кэша: {stats['cache_entries']}\n"
            
            if stats.get('logs', 0) > 0:
                message += f"• Логи: {stats['logs']}\n"
            
            message += f"\n⏰ Время: {format_datetime(get_current_datetime())}"
            
            # Отправляем главному админу
            main_admin_id = self.context.config.main_admin_id
            if main_admin_id:
                await self.context.notification_service.send_notification(
                    user_id=main_admin_id,
                    message=message,
                    notification_type="cleanup_completed",
                    data={'stats': stats, 'duration': duration}
                )
                
            logger.info("Уведомление об очистке отправлено")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления об очистке: {e}")
            
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Получает статистику работы воркера.
        
        Returns:
            Словарь со статистикой
        """
        # Получаем текущее состояние кэша и временных данных
        cache_info = await self.cleanup_service.get_cache_info()
        temp_files_info = await self.cleanup_service.get_temp_files_info()
        
        return {
            'worker': {
                'is_running': self.is_running,
                'cleanup_count': self.cleanup_count,
                'total_cleaned': self.total_cleaned,
                'last_cleanup_time': self.last_cleanup_time.isoformat() if self.last_cleanup_time else None
            },
            'current_state': {
                'cache': cache_info,
                'temp_files': temp_files_info
            }
        }
        
    async def force_cleanup(self) -> Dict[str, Any]:
        """
        Принудительная очистка всех временных данных.
        
        Returns:
            Результат очистки
        """
        try:
            logger.info("Запуск принудительной очистки всех временных данных")
            
            # Выполняем все виды очистки
            result = await self.run_manual_cleanup("all")
            
            # Дополнительно очищаем все паттерны кэша
            patterns = [
                "fsm:*",
                "pagination:*", 
                "temp:*",
                "cache:*",
                "search:*",
                "dialog:*"
            ]
            
            pattern_results = {}
            for pattern in patterns:
                pattern_result = await self.cleanup_specific_pattern(pattern)
                pattern_results[pattern] = pattern_result
            
            result['pattern_results'] = pattern_results
            
            # Очищаем все временные директории
            temp_dirs = await self.cleanup_service.get_temp_directories()
            dir_cleaned = 0
            
            for temp_dir in temp_dirs:
                try:
                    if Path(temp_dir).exists():
                        # Удаляем только содержимое, не саму директорию
                        for item in Path(temp_dir).iterdir():
                            if item.is_file():
                                item.unlink()
                                dir_cleaned += 1
                            elif item.is_dir():
                                shutil.rmtree(item)
                                dir_cleaned += 1
                except Exception as e:
                    logger.warning(f"Не удалось очистить директорию {temp_dir}: {e}")
            
            if dir_cleaned > 0:
                result['directories_cleaned'] = dir_cleaned
            
            logger.info(f"Принудительная очистка завершена")
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при принудительной очистке: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }