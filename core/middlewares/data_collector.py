"""
Middleware для сбора статистики использования бота.
Собирает анонимную статистику для анализа нагрузки и популярности команд.
"""

import time
from typing import Any, Awaitable, Callable, Dict
from datetime import datetime, timedelta

from aiogram import BaseMiddleware
from aiogram.types import Update, Message, CallbackQuery
from aiogram.dispatcher.middlewares.base import NextMiddlewareType

from core.context import AppContext
from structlog import get_logger


class DataCollectorMiddleware(BaseMiddleware):
    """Middleware для сбора статистики использования бота"""
    
    def __init__(self, context: AppContext):
        super().__init__()
        self.context = context
        self.logger = get_logger(__name__)
        self.stats = {
            "total_requests": 0,
            "commands_by_type": {},
            "active_users": set(),
            "requests_by_hour": {},
            "errors_count": 0,
        }
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        """
        Собирает статистику перед выполнением обработчика.
        
        Args:
            handler: Обработчик события
            event: Событие Telegram
            data: Данные события
            
        Returns:
            Результат обработчика
        """
        start_time = time.time()
        
        # Собираем статистику
        await self._collect_stats(event, data)
        
        # Выполняем обработчик
        result = await handler(event, data)
        
        # Замеряем время выполнения
        processing_time = time.time() - start_time
        await self._record_processing_time(processing_time, event)
        
        return result
    
    async def _collect_stats(self, event: Update, data: Dict[str, Any]) -> None:
        """
        Собирает статистическую информацию о событии.
        
        Args:
            event: Событие Telegram
            data: Данные события
        """
        # Обновляем общий счетчик
        self.stats["total_requests"] += 1
        
        # Определяем тип события
        event_type = event.event_type
        self.stats["commands_by_type"][event_type] = \
            self.stats["commands_by_type"].get(event_type, 0) + 1
        
        # Извлекаем информацию о пользователе
        user_id = self._extract_user_id(event)
        if user_id:
            self.stats["active_users"].add(user_id)
        
        # Записываем час запроса
        current_hour = datetime.now().hour
        self.stats["requests_by_hour"][current_hour] = \
            self.stats["requests_by_hour"].get(current_hour, 0) + 1
        
        # Для команд собираем дополнительную статистику
        if event.message and event.message.text and event.message.text.startswith('!'):
            await self._collect_command_stats(event.message)
    
    def _extract_user_id(self, event: Update) -> int | None:
        """
        Извлекает ID пользователя из события.
        
        Args:
            event: Событие Telegram
            
        Returns:
            ID пользователя или None
        """
        try:
            if event.message:
                return event.message.from_user.id
            elif event.callback_query:
                return event.callback_query.from_user.id
            elif event.my_chat_member:
                return event.my_chat_member.from_user.id
            elif event.chat_member:
                return event.chat_member.from_user.id
        except Exception:
            return None
        return None
    
    async def _collect_command_stats(self, message: Message) -> None:
        """
        Собирает статистику по командам.
        
        Args:
            message: Сообщение с командой
        """
        try:
            command = message.text.split()[0].lower()
            
            # Используем кэш для хранения статистики команд
            cache_key = f"stats:commands:{datetime.now().strftime('%Y-%m-%d')}"
            
            # Сохраняем в Redis для долговременного хранения
            if hasattr(self.context, 'cache'):
                await self.context.cache.hincrby(
                    cache_key,
                    command,
                    1
                )
                
                # Сохраняем информацию о пользователе команды
                user_key = f"stats:command_users:{command}"
                await self.context.cache.sadd(
                    user_key,
                    message.from_user.id
                )
                await self.context.cache.expire(user_key, 86400 * 30)  # 30 дней
        except Exception as e:
            self.logger.warning("failed_to_collect_command_stats", error=str(e))
    
    async def _record_processing_time(self, processing_time: float, event: Update) -> None:
        """
        Записывает время обработки события.
        
        Args:
            processing_time: Время обработки в секундах
            event: Событие Telegram
        """
        try:
            # Сохраняем в Redis среднее время обработки
            if hasattr(self.context, 'cache'):
                cache_key = "stats:processing_times"
                
                # Добавляем новое значение
                await self.context.cache.rpush(
                    cache_key,
                    processing_time
                )
                
                # Ограничиваем список 1000 последними значениями
                await self.context.cache.ltrim(cache_key, -1000, -1)
        except Exception as e:
            self.logger.warning("failed_to_record_processing_time", error=str(e))
    
    async def get_daily_stats(self) -> Dict[str, Any]:
        """
        Возвращает дневную статистику.
        
        Returns:
            Словарь со статистикой
        """
        today = datetime.now().strftime("%Y-%m-%d")
        
        stats = {
            "date": today,
            "total_requests": self.stats["total_requests"],
            "unique_users": len(self.stats["active_users"]),
            "requests_by_type": dict(self.stats["commands_by_type"]),
            "requests_by_hour": dict(self.stats["requests_by_hour"]),
        }
        
        # Получаем статистику команд из Redis
        if hasattr(self.context, 'cache'):
            cache_key = f"stats:commands:{today}"
            command_stats = await self.context.cache.hgetall(cache_key)
            stats["command_stats"] = {
                cmd.decode(): int(count.decode()) 
                for cmd, count in command_stats.items()
            }
        
        return stats
    
    async def get_weekly_report(self) -> Dict[str, Any]:
        """
        Генерирует недельный отчет по статистике.
        
        Returns:
            Словарь с недельным отчетом
        """
        if not hasattr(self.context, 'cache'):
            return {}
        
        now = datetime.now()
        week_ago = now - timedelta(days=7)
        
        report = {
            "period": {
                "from": week_ago.strftime("%Y-%m-%d"),
                "to": now.strftime("%Y-%m-%d")
            },
            "total_requests": 0,
            "unique_users": set(),
            "popular_commands": {},
        }
        
        # Собираем данные за неделю
        for i in range(7):
            date = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            cache_key = f"stats:commands:{date}"
            
            try:
                command_stats = await self.context.cache.hgetall(cache_key)
                for cmd, count in command_stats.items():
                    cmd_str = cmd.decode()
                    report["popular_commands"][cmd_str] = \
                        report["popular_commands"].get(cmd_str, 0) + int(count.decode())
                    
                    # Собираем уникальных пользователей для каждой команды
                    user_key = f"stats:command_users:{cmd_str}"
                    users = await self.context.cache.smembers(user_key)
                    if users:
                        report["unique_users"].update(
                            int(user_id.decode()) for user_id in users
                        )
            except Exception:
                continue
        
        report["unique_users"] = len(report["unique_users"])
        report["total_requests"] = sum(report["popular_commands"].values())
        
        # Сортируем команды по популярности
        report["popular_commands"] = dict(
            sorted(
                report["popular_commands"].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]  # Топ-10 команд
        )
        
        return report
    
    async def reset_daily_stats(self) -> None:
        """Сбрасывает дневную статистику."""
        today = datetime.now().strftime("%Y-%m-%d")
        
        self.stats = {
            "total_requests": 0,
            "commands_by_type": {},
            "active_users": set(),
            "requests_by_hour": {},
            "errors_count": 0,
        }
        
        # Очищаем кэш статистики
        if hasattr(self.context, 'cache'):
            await self.context.cache.delete(f"stats:commands:{today}")