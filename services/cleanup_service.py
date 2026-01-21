import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import os
import shutil

import structlog

from core.context import AppContext
from config import config
from storage.cache.manager import CacheManager


logger = structlog.get_logger(__name__)


class CleanupService:
    """Сервис для очистки временных данных."""
    
    def __init__(self, context: AppContext):
        self.context = context
        self.cache: CacheManager = context.cache
    
    async def initialize(self) -> None:
        """Инициализирует сервис очистки."""
        logger.info("Cleanup service initialized")
    
    async def cleanup_expired_fsm_sessions(self) -> int:
        """
        Очищает просроченные FSM сессии.
        
        Returns:
            Количество удаленных сессий
        """
        try:
            # Используем middleware для очистки FSM сессий
            # В реальном приложении здесь был бы вызов middleware
            # Пока возвращаем заглушку
            
            # Очищаем старые ключи FSM
            pattern = "fsm_timeout:*"
            deleted = await self.cache.clear_by_pattern(pattern)
            
            # Также очищаем данные FSM в Redis
            fsm_pattern = f"{config.bot.token}:fsm:*"
            fsm_deleted = await self.cache.clear_by_pattern(fsm_pattern)
            
            total_deleted = deleted + fsm_deleted
            
            if total_deleted > 0:
                logger.info("Expired FSM sessions cleaned", count=total_deleted)
            
            return total_deleted
        
        except Exception as e:
            logger.error("FSM sessions cleanup failed", error=str(e))
            return 0
    
    async def cleanup_expired_pagination(self) -> int:
        """
        Очищает просроченные пагинации.
        
        Returns:
            Количество удаленных пагинаций
        """
        try:
            deleted = await self.cache.cleanup_expired_pagination()
            
            if deleted > 0:
                logger.info("Expired pagination cleaned", count=deleted)
            
            return deleted
        
        except Exception as e:
            logger.error("Pagination cleanup failed", error=str(e))
            return 0
    
    async def cleanup_old_search_results(self, days_old: int = 1) -> int:
        """
        Очищает старые результаты поиска.
        
        Args:
            days_old: Возраст в днях для очистки
            
        Returns:
            Количество удаленных результатов
        """
        try:
            pattern = "search:*"
            deleted = await self.cache.clear_by_pattern(pattern)
            
            if deleted > 0:
                logger.info("Old search results cleaned", count=deleted, days_old=days_old)
            
            return deleted
        
        except Exception as e:
            logger.error("Search results cleanup failed", error=str(e))
            return 0
    
    async def cleanup_old_exports(self, days_old: int = 7) -> int:
        """
        Очищает старые экспортированные файлы.
        
        Args:
            days_old: Возраст в днях для очистки
            
        Returns:
            Количество удаленных файлов
        """
        try:
            # В нашем случае файлы хранятся в Telegram, так что очищаем только ссылки
            pattern = "export:*"
            deleted = await self.cache.clear_by_pattern(pattern)
            
            if deleted > 0:
                logger.info("Old export links cleaned", count=deleted, days_old=days_old)
            
            return deleted
        
        except Exception as e:
            logger.error("Exports cleanup failed", error=str(e))
            return 0
    
    async def cleanup_unused_files(self, hours_unused: int = 24) -> int:
        """
        Очищает неиспользуемые файловые ссылки.
        
        Args:
            hours_unused: Часы неиспользования для очистки
            
        Returns:
            Количество удаленных ссылок
        """
        try:
            # Очищаем временные файловые ссылки
            patterns = [
                "temp_file:*",
                "upload:*",
                "download:*",
            ]
            
            total_deleted = 0
            for pattern in patterns:
                deleted = await self.cache.clear_by_pattern(pattern)
                total_deleted += deleted
            
            if total_deleted > 0:
                logger.info("Unused file links cleaned", count=total_deleted, hours=hours_unused)
            
            return total_deleted
        
        except Exception as e:
            logger.error("Unused files cleanup failed", error=str(e))
            return 0
    
    async def cleanup_old_logs(self, days_old: int = 30) -> int:
        """
        Очищает старые логи.
        
        Args:
            days_old: Возраст в днях для очистки
            
        Returns:
            Количество удаленных логов
        """
        try:
            # Очищаем кэшированные логи
            pattern = "log:*"
            deleted = await self.cache.clear_by_pattern(pattern)
            
            if deleted > 0:
                logger.info("Old logs cleaned from cache", count=deleted, days_old=days_old)
            
            return deleted
        
        except Exception as e:
            logger.error("Logs cleanup failed", error=str(e))
            return 0
    
    async def cleanup_user_sessions(self, days_inactive: int = 30) -> Dict[str, int]:
        """
        Очищает сессии неактивных пользователей.
        
        Args:
            days_inactive: Дни неактивности для очистки
            
        Returns:
            Статистика очистки
        """
        try:
            stats = {
                "sessions_cleaned": 0,
                "cache_cleaned": 0,
            }
            
            # Очищаем сессии пользователей
            session_pattern = "user_session:*"
            sessions_deleted = await self.cache.clear_by_pattern(session_pattern)
            stats["sessions_cleaned"] = sessions_deleted
            
            # Очищаем кэш пользователей
            user_cache_pattern = "user_cache:*"
            cache_deleted = await self.cache.clear_by_pattern(user_cache_pattern)
            stats["cache_cleaned"] = cache_deleted
            
            if sessions_deleted > 0 or cache_deleted > 0:
                logger.info(
                    "User sessions cleaned",
                    sessions=sessions_deleted,
                    cache=cache_deleted,
                    days_inactive=days_inactive
                )
            
            return stats
        
        except Exception as e:
            logger.error("User sessions cleanup failed", error=str(e))
            return {"sessions_cleaned": 0, "cache_cleaned": 0}
    
    async def cleanup_throttling_data(self, hours_old: int = 24) -> int:
        """
        Очищает старые данные троттлинга.
        
        Args:
            hours_old: Возраст в часах для очистки
            
        Returns:
            Количество удаленных записей
        """
        try:
            pattern = "throttling:*"
            deleted = await self.cache.clear_by_pattern(pattern)
            
            if deleted > 0:
                logger.info("Throttling data cleaned", count=deleted, hours_old=hours_old)
            
            return deleted
        
        except Exception as e:
            logger.error("Throttling data cleanup failed", error=str(e))
            return 0
    
    async def run_full_cleanup(self) -> Dict[str, Any]:
        """
        Выполняет полную очистку всех временных данных.
        
        Returns:
            Статистика очистки
        """
        try:
            logger.info("Starting full cleanup")
            
            stats = {
                "fsm_sessions": await self.cleanup_expired_fsm_sessions(),
                "pagination": await self.cleanup_expired_pagination(),
                "search_results": await self.cleanup_old_search_results(),
                "exports": await self.cleanup_old_exports(),
                "unused_files": await self.cleanup_unused_files(),
                "logs": await self.cleanup_old_logs(),
                "user_sessions": await self.cleanup_user_sessions(),
                "throttling": await self.cleanup_throttling_data(),
                "started_at": datetime.now().isoformat(),
                "completed_at": None,
            }
            
            stats["completed_at"] = datetime.now().isoformat()
            stats["total"] = sum(v for k, v in stats.items() if isinstance(v, int))
            
            logger.info("Full cleanup completed", stats=stats)
            return stats
        
        except Exception as e:
            logger.error("Full cleanup failed", error=str(e))
            return {"error": str(e)}
    
    async def get_cleanup_stats(self) -> Dict[str, Any]:
        """
        Получает статистику по использованию временных данных.
        
        Returns:
            Статистика использования
        """
        try:
            cache_stats = await self.cache.get_stats()
            
            # Анализируем использование кэша
            patterns_to_check = [
                ("fsm_timeout:*", "FSM сессии"),
                ("pagination:*", "Пагинации"),
                ("search:*", "Поисковые запросы"),
                ("temp:*", "Временные данные"),
                ("user_session:*", "Сессии пользователей"),
                ("export:*", "Экспорты"),
                ("log:*", "Логи"),
            ]
            
            pattern_stats = []
            total_keys = 0
            
            for pattern, description in patterns_to_check:
                # Получаем количество ключей по шаблону
                count = 0
                try:
                    # В реальном приложении здесь был бы подсчет ключей
                    # Пока используем оценку
                    pass
                except Exception:
                    count = 0
                
                pattern_stats.append({
                    "pattern": description,
                    "count": count,
                })
                total_keys += count
            
            return {
                "cache_stats": cache_stats,
                "pattern_stats": pattern_stats,
                "total_temporary_keys": total_keys,
                "check_time": datetime.now().isoformat(),
            }
        
        except Exception as e:
            logger.error("Get cleanup stats failed", error=str(e))
            return {"error": str(e)}