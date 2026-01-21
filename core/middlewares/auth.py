from typing import Any, Dict, Callable, Awaitable, Optional
from functools import wraps

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, User as TelegramUser
from aiogram.dispatcher.flags import get_flag
from aiogram.filters import CommandObject
import structlog

from core.context import AppContext
from storage.models.user import User, Admin, AdminLevel
from storage.repositories.user_repository import UserRepository


logger = structlog.get_logger(__name__)


class AuthMiddleware(BaseMiddleware):
    """Middleware для проверки прав доступа."""
    
    def __init__(self, context: AppContext):
        super().__init__()
        self.context = context
        self.user_repo = UserRepository(context.database)
    
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем информацию о пользователе
        telegram_user: TelegramUser = data.get("event_from_user")
        
        if not telegram_user:
            # Если нет пользователя (не должно происходить)
            logger.warning("No user in event", event_type=type(event).__name__)
            return await handler(event, data)
        
        # Получаем или создаем пользователя в БД
        user = await self._get_or_create_user(telegram_user)
        data["user"] = user
        
        # Получаем информацию об админе (если есть)
        admin = await self._get_user_admin(user)
        data["admin"] = admin
        
        # Проверяем флаги доступа команды
        required_level = get_flag(data, "required_level")
        required_permission = get_flag(data, "required_permission")
        
        if required_level or required_permission:
            # Проверяем доступ
            has_access = await self._check_access(
                user, admin, required_level, required_permission, data
            )
            
            if not has_access:
                # Отправляем сообщение об отсутствии прав
                await self._send_access_denied(event, user)
                return
        
        # Продолжаем обработку если доступ есть
        return await handler(event, data)
    
    async def _get_or_create_user(self, telegram_user: TelegramUser) -> User:
        """Получает или создает пользователя в БД."""
        async with self.context.get_session() as session:
            repo = UserRepository(session)
            
            # Ищем существующего пользователя
            user = await repo.get_by_telegram_id(telegram_user.id)
            
            if not user:
                # Создаем нового пользователя
                user = await repo.create_user(
                    telegram_id=telegram_user.id,
                    username=telegram_user.username,
                    first_name=telegram_user.first_name,
                    last_name=telegram_user.last_name
                )
                logger.info("New user created", user_id=user.id, telegram_id=telegram_user.id)
            
            # Обновляем последнюю активность
            await repo.update_last_active(user.id)
            
            return user
    
    async def _get_user_admin(self, user: User) -> Optional[Admin]:
        """Получает информацию об админе пользователя."""
        if not user.admin:
            return None
        
        # Проверяем, активен ли админ
        if not user.admin.is_active:
            return None
        
        return user.admin
    
    async def _check_access(
        self,
        user: User,
        admin: Optional[Admin],
        required_level: Optional[str],
        required_permission: Optional[str],
        data: Dict[str, Any]
    ) -> bool:
        """Проверяет, есть ли у пользователя доступ к команде."""
        
        # Если команда не требует специальных прав
        if not required_level and not required_permission:
            return True
        
        # Проверяем уровень админа
        if required_level:
            if not admin:
                return False
            
            # Проверяем уровень доступа
            if not self._check_admin_level(admin, required_level):
                logger.warning(
                    "Admin level check failed",
                    user_id=user.id,
                    admin_level=admin.level,
                    required_level=required_level
                )
                return False
        
        # Проверяем конкретное разрешение
        if required_permission:
            if not admin:
                return False
            
            # Извлекаем команду из данных
            command = self._extract_command(data)
            if not command:
                return True  # Если нет конкретной команды, пропускаем
            
            # Проверяем разрешение
            if not admin.has_permission(required_permission, command):
                logger.warning(
                    "Permission check failed",
                    user_id=user.id,
                    permission=required_permission,
                    command=command
                )
                return False
        
        return True
    
    def _check_admin_level(self, admin: Admin, required_level: str) -> bool:
        """Проверяет уровень админа."""
        
        # Уровни админов в порядке возрастания привилегий
        level_hierarchy = {
            AdminLevel.INSTALLATION.value: 1,
            AdminLevel.SERVICE.value: 2,
            AdminLevel.ADMIN.value: 3,
            AdminLevel.MAIN_ADMIN.value: 4,
        }
        
        admin_level_value = level_hierarchy.get(admin.level, 0)
        required_level_value = level_hierarchy.get(required_level, 0)
        
        return admin_level_value >= required_level_value
    
    def _extract_command(self, data: Dict[str, Any]) -> Optional[str]:
        """Извлекает команду из данных события."""
        # Пробуем получить команду из различных источников
        
        # Из Message
        if "command" in data:
            command_obj: CommandObject = data["command"]
            if command_obj and command_obj.command:
                return command_obj.command
        
        # Из CallbackQuery
        if "callback_data" in data:
            callback_data = data.get("callback_data")
            if isinstance(callback_data, str) and callback_data.startswith("cmd_"):
                return callback_data[4:]  # Убираем префикс "cmd_"
        
        # Из текста сообщения
        message: Optional[Message] = data.get("event")
        if message and message.text:
            # Пытаемся извлечь команду из текста
            text = message.text.strip()
            if text.startswith("!"):
                # Команда в формате !команда
                return text.split()[0][1:].lower()
            elif text.startswith("/"):
                # Команда в формате /команда
                return text.split()[0][1:].lower().split("@")[0]
        
        return None
    
    async def _send_access_denied(self, event: Message | CallbackQuery, user: User) -> None:
        """Отправляет сообщение об отсутствии прав."""
        message_text = "⛔ У вас нет прав для выполнения этой команды."
        
        if isinstance(event, Message):
            await event.answer(message_text)
        elif isinstance(event, CallbackQuery):
            await event.answer(message_text, show_alert=True)
        
        logger.info(
            "Access denied",
            user_id=user.id,
            telegram_id=user.telegram_id,
            event_type=type(event).__name__
        )
    
    @staticmethod
    def require_admin(level: str = AdminLevel.ADMIN.value):
        """Декоратор для требований к уровню админа."""
        def decorator(handler):
            @wraps(handler)
            async def wrapper(*args, **kwargs):
                return await handler(*args, **kwargs)
            
            # Устанавливаем флаг для middleware
            wrapper.__aiogram_middleware_flags__ = {
                "required_level": level
            }
            return wrapper
        return decorator
    
    @staticmethod
    def require_permission(permission_type: str):
        """Декоратор для требований к конкретному разрешению."""
        def decorator(handler):
            @wraps(handler)
            async def wrapper(*args, **kwargs):
                return await handler(*args, **kwargs)
            
            # Устанавливаем флаг для middleware
            wrapper.__aiogram_middleware_flags__ = {
                "required_permission": permission_type
            }
            return wrapper
        return decorator