import json
from typing import Dict, Any, Optional
from datetime import datetime

import structlog
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.context import AppContext
from storage.cache.manager import CacheManager
from utils.formatters import format_size


logger = structlog.get_logger(__name__)

# Создаем роутер
cache_router = Router(name="cache_service")


class CacheService:
    """Сервис для управления кэшем."""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self.router = cache_router
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Получает статистику кэша."""
        stats = await self.cache.get_stats()
        
        # Форматируем статистику для отображения
        formatted = {
            "Общая статистика": {
                "Попаданий (hits)": stats.get("hits", 0),
                "Промахов (misses)": stats.get("misses", 0),
                "Записей создано": stats.get("sets", 0),
                "Записей удалено": stats.get("deletes", 0),
                "Полных очисток": stats.get("clears", 0),
                "Последняя очистка": stats.get("last_clear", "никогда"),
            },
            "Использование Redis": {
                "Всего ключей в Redis": stats.get("redis_keys", 0),
                "Ключей нашего приложения": stats.get("our_keys", 0),
                "Используемая память": stats.get("redis_memory_used", "N/A"),
            }
        }
        
        return formatted
    
    async def clear_cache_with_confirmation(self, user_id: int) -> Dict[str, Any]:
        """
        Запрашивает подтверждение очистки кэша.
        
        Args:
            user_id: ID пользователя для подтверждения
            
        Returns:
            Результат операции
        """
        # В реальной реализации здесь должен быть запрос подтверждения
        # через инлайн клавиатуру
        return await self.clear_cache()
    
    async def clear_cache(self) -> Dict[str, Any]:
        """
        Очищает весь кэш приложения.
        
        Returns:
            Результат операции
        """
        try:
            # Получаем статистику перед очисткой
            before_stats = await self.cache.get_stats()
            before_keys = before_stats.get("our_keys", 0)
            
            # Очищаем кэш
            success = await self.cache.clear_all(confirmation=False)
            
            if success:
                # Получаем статистику после очистки
                after_stats = await self.cache.get_stats()
                
                result = {
                    "success": True,
                    "message": "✅ Кэш успешно очищен",
                    "details": {
                        "удалено_ключей": before_keys,
                        "осталось_ключей": after_stats.get("our_keys", 0),
                        "время": datetime.now().strftime("%H:%M:%S"),
                    }
                }
            else:
                result = {
                    "success": False,
                    "message": "❌ Не удалось очистить кэш",
                    "details": {}
                }
            
            logger.info("Cache cleared", result=result)
            return result
            
        except Exception as e:
            logger.error("Cache clear failed", error=str(e))
            return {
                "success": False,
                "message": f"❌ Ошибка при очистке кэша: {str(e)}",
                "details": {}
            }
    
    async def clear_pattern(self, pattern: str) -> Dict[str, Any]:
        """
        Очищает кэш по шаблону.
        
        Args:
            pattern: Шаблон для очистки
            
        Returns:
            Результат операции
        """
        try:
            deleted = await self.cache.clear_by_pattern(pattern)
            
            if deleted > 0:
                result = {
                    "success": True,
                    "message": f"✅ Очищено {deleted} ключей по шаблону: {pattern}",
                    "details": {
                        "удалено": deleted,
                        "шаблон": pattern,
                    }
                }
            else:
                result = {
                    "success": True,
                    "message": f"⚠️ Не найдено ключей по шаблону: {pattern}",
                    "details": {
                        "удалено": 0,
                        "шаблон": pattern,
                    }
                }
            
            logger.info("Cache pattern cleared", pattern=pattern, deleted=deleted)
            return result
            
        except Exception as e:
            logger.error("Cache pattern clear failed", pattern=pattern, error=str(e))
            return {
                "success": False,
                "message": f"❌ Ошибка при очистке по шаблону: {str(e)}",
                "details": {"шаблон": pattern}
            }
    
    async def get_cache_info(self) -> str:
        """Получает информацию о кэше в форматированном виде."""
        stats = await self.get_cache_stats()
        
        lines = ["📊 <b>Статистика кэша</b>\n"]
        
        for category, data in stats.items():
            lines.append(f"\n<b>{category}:</b>")
            for key, value in data.items():
                lines.append(f"  {key}: {value}")
        
        # Добавляем информацию о TTL
        lines.append("\n<b>Распространенные TTL:</b>")
        ttl_examples = {
            "Пагинация": "10 минут",
            "FSM состояния": "2 часа + 5 минут",
            "Временные файлы": "1 час",
            "Поисковые запросы": "30 минут",
        }
        
        for key, value in ttl_examples.items():
            lines.append(f"  {key}: {value}")
        
        return "\n".join(lines)


# Регистрация обработчиков команд кэша
@cache_router.message(Command("кэш"))
async def cache_command(message: Message, context: AppContext):
    """Обработчик команды !кэш."""
    
    # Проверяем права доступа (только для админов)
    # Здесь должна быть проверка прав через middleware
    
    cache_service = CacheService(context.cache)
    cache_info = await cache_service.get_cache_info()
    
    # Создаем клавиатуру для управления кэшем
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Обновить статистику", callback_data="cache_refresh")
    builder.button(text="🗑️ Очистить кэш", callback_data="cache_clear")
    builder.button(text="📋 Подробная статистика", callback_data="cache_details")
    builder.button(text="🧹 Очистить временные данные", callback_data="cache_cleanup_temp")
    builder.adjust(2)  # 2 кнопки в ряд
    
    await message.answer(
        cache_info,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@cache_router.callback_query(F.data == "cache_refresh")
async def refresh_cache_stats(callback: CallbackQuery, context: AppContext):
    """Обновляет статистику кэша."""
    cache_service = CacheService(context.cache)
    cache_info = await cache_service.get_cache_info()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Обновить статистику", callback_data="cache_refresh")
    builder.button(text="🗑️ Очистить кэш", callback_data="cache_clear")
    builder.button(text="📋 Подробная статистика", callback_data="cache_details")
    builder.button(text="🧹 Очистить временные данные", callback_data="cache_cleanup_temp")
    builder.adjust(2)
    
    await callback.message.edit_text(
        cache_info,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer("Статистика обновлена")


@cache_router.callback_query(F.data == "cache_clear")
async def clear_cache_handler(callback: CallbackQuery, context: AppContext):
    """Обработчик очистки кэша с подтверждением."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, очистить всё", callback_data="cache_clear_confirm")
    builder.button(text="❌ Нет, отмена", callback_data="cache_cancel")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "⚠️ <b>Вы уверены, что хотите очистить весь кэш?</b>\n\n"
        "Это действие удалит:\n"
        "• Все временные данные FSM\n"
        "• Кэшированные пагинации\n"
        "• Временные файловые ссылки\n"
        "• Другие кэшированные данные\n\n"
        "<i>Некоторые операции могут замедлиться до перезагрузки кэша.</i>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@cache_router.callback_query(F.data == "cache_clear_confirm")
async def confirm_clear_cache(callback: CallbackQuery, context: AppContext):
    """Подтверждение очистки кэша."""
    cache_service = CacheService(context.cache)
    result = await cache_service.clear_cache()
    
    # Возвращаемся к статистике
    cache_info = await cache_service.get_cache_info()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Обновить статистику", callback_data="cache_refresh")
    builder.button(text="🗑️ Очистить кэш", callback_data="cache_clear")
    builder.button(text="📋 Подробная статистика", callback_data="cache_details")
    builder.button(text="🧹 Очистить временные данные", callback_data="cache_cleanup_temp")
    builder.adjust(2)
    
    await callback.message.edit_text(
        f"{result['message']}\n\n{cache_info}",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer("Кэш очищен")


@cache_router.callback_query(F.data == "cache_cancel")
async def cancel_cache_action(callback: CallbackQuery, context: AppContext):
    """Отмена действия с кэшем."""
    cache_service = CacheService(context.cache)
    cache_info = await cache_service.get_cache_info()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Обновить статистику", callback_data="cache_refresh")
    builder.button(text="🗑️ Очистить кэш", callback_data="cache_clear")
    builder.button(text="📋 Подробная статистика", callback_data="cache_details")
    builder.button(text="🧹 Очистить временные данные", callback_data="cache_cleanup_temp")
    builder.adjust(2)
    
    await callback.message.edit_text(
        cache_info,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer("Действие отменено")


@cache_router.callback_query(F.data == "cache_details")
async def show_cache_details(callback: CallbackQuery, context: AppContext):
    """Показывает подробную статистику кэша."""
    cache_service = CacheService(context.cache)
    stats = await cache_service.cache.get_stats()
    
    # Форматируем подробную статистику
    details = json.dumps(stats, indent=2, ensure_ascii=False)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="cache_refresh")
    
    await callback.message.edit_text(
        f"<b>Подробная статистика кэша:</b>\n\n"
        f"<code>{details[:4000]}</code>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@cache_router.callback_query(F.data == "cache_cleanup_temp")
async def cleanup_temp_data(callback: CallbackQuery, context: AppContext):
    """Очищает временные данные."""
    cache_service = CacheService(context.cache)
    
    # Очищаем различные типы временных данных
    patterns_to_clear = [
        "fsm_timeout:*",        # Таймауты FSM
        "pagination:*",         # Пагинации
        "temp:*",              # Временные данные
        "search:*",            # Поисковые запросы
        "throttling:*",        # Данные троттлинга
    ]
    
    results = []
    for pattern in patterns_to_clear:
        result = await cache_service.clear_pattern(pattern)
        results.append(f"{pattern}: {result['message']}")
    
    # Возвращаемся к статистике
    cache_info = await cache_service.get_cache_info()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Обновить статистику", callback_data="cache_refresh")
    builder.button(text="🗑️ Очистить кэш", callback_data="cache_clear")
    builder.button(text="📋 Подробная статистика", callback_data="cache_details")
    builder.button(text="🧹 Очистить временные данные", callback_data="cache_cleanup_temp")
    builder.adjust(2)
    
    cleanup_summary = "\n".join(results)
    
    await callback.message.edit_text(
        f"🧹 <b>Очистка временных данных завершена:</b>\n{cleanup_summary}\n\n{cache_info}",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer("Временные данные очищены")