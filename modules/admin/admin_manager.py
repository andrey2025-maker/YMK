import re
from typing import Optional, Dict, Any, List
import uuid

import structlog

from core.context import AppContext
from storage.models.user import User, Admin, AdminLevel
from storage.repositories.user_repository import UserRepository
from services.database_service import DatabaseService


logger = structlog.get_logger(__name__)


class AdminManager:
    """Менеджер для управления администраторами."""
    
    def __init__(self, context: AppContext):
        self.context = context
        self.db_service = DatabaseService(context)
    
    async def add_admin(
        self,
        admin_identifier: str,
        level: str,
        added_by: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Добавляет администратора.
        
        Args:
            admin_identifier: ID, username или ссылка пользователя
            level: Уровень админа (main_admin, admin, service, installation)
            added_by: ID админа, который добавляет (для логов)
            
        Returns:
            Результат операции
        """
        try:
            # Валидируем уровень админа
            if level not in [l.value for l in AdminLevel]:
                return {
                    "success": False,
                    "message": f"Неверный уровень админа: {level}"
                }
            
            # Извлекаем информацию о пользователе из идентификатора
            user_info = await self._parse_user_identifier(admin_identifier)
            if not user_info:
                return {
                    "success": False,
                    "message": f"Не удалось распознать пользователя: {admin_identifier}"
                }
            
            async with self.context.get_session() as session:
                repo = UserRepository(session)
                
                # Ищем существующего пользователя
                user = await repo.get_by_telegram_id(user_info["telegram_id"])
                
                if not user:
                    # Создаем нового пользователя
                    user = await repo.create_user(
                        telegram_id=user_info["telegram_id"],
                        username=user_info.get("username"),
                        first_name=user_info.get("first_name"),
                        last_name=user_info.get("last_name")
                    )
                
                # Проверяем, не является ли пользователь уже админом
                if user.admin:
                    return {
                        "success": False,
                        "message": f"Пользователь уже является админом (уровень: {user.admin.level})"
                    }
                
                # Создаем админа
                admin = await repo.create_admin(
                    user_id=user.id,
                    level=level,
                    assigned_by=added_by
                )
                
                # Создаем пустые разрешения для админа
                await repo.create_admin_permissions(admin.id)
                
                await session.commit()
                
                return {
                    "success": True,
                    "message": f"Админ уровня '{level}' успешно добавлен",
                    "user": {
                        "id": str(user.id),
                        "telegram_id": user.telegram_id,
                        "username": user.username,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                    },
                    "admin": {
                        "id": str(admin.id),
                        "level": admin.level,
                        "level_display": admin.get_level_display(),
                        "assigned_at": admin.assigned_at.isoformat(),
                    }
                }
        
        except Exception as e:
            logger.error("Add admin failed", identifier=admin_identifier, error=str(e))
            return {
                "success": False,
                "message": f"Ошибка при добавлении админа: {str(e)}"
            }
    
    async def remove_admin(
        self,
        admin_identifier: str,
        removed_by: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Удаляет администратора.
        
        Args:
            admin_identifier: ID, username или ссылка пользователя
            removed_by: ID админа, который удаляет (для логов)
            
        Returns:
            Результат операции
        """
        try:
            # Извлекаем информацию о пользователе
            user_info = await self._parse_user_identifier(admin_identifier)
            if not user_info:
                return {
                    "success": False,
                    "message": f"Не удалось распознать пользователя: {admin_identifier}"
                }
            
            async with self.context.get_session() as session:
                repo = UserRepository(session)
                
                # Ищем пользователя
                user = await repo.get_by_telegram_id(user_info["telegram_id"])
                
                if not user:
                    return {
                        "success": False,
                        "message": "Пользователь не найден"
                    }
                
                if not user.admin:
                    return {
                        "success": False,
                        "message": "Пользователь не является админом"
                    }
                
                # Нельзя удалить главного админа через эту команду
                if user.admin.level == AdminLevel.MAIN_ADMIN.value:
                    return {
                        "success": False,
                        "message": "Главного админа нельзя удалить через эту команду"
                    }
                
                # Удаляем админа
                admin_id = user.admin.id
                await repo.delete_admin(admin_id)
                
                await session.commit()
                
                return {
                    "success": True,
                    "message": "Админ успешно удален",
                    "user": {
                        "id": str(user.id),
                        "username": user.username,
                    },
                    "admin": {
                        "id": str(admin_id),
                        "level": user.admin.level,
                    }
                }
        
        except Exception as e:
            logger.error("Remove admin failed", identifier=admin_identifier, error=str(e))
            return {
                "success": False,
                "message": f"Ошибка при удалении админа: {str(e)}"
            }
    
    async def get_all_admins(self) -> List[Dict[str, Any]]:
        """Получает список всех админов."""
        try:
            async with self.context.get_session() as session:
                repo = UserRepository(session)
                admins = await repo.get_all_admins_with_users()
                
                result = []
                for admin in admins:
                    result.append({
                        "id": str(admin.id),
                        "level": admin.level,
                        "level_display": admin.get_level_display(),
                        "user": {
                            "id": str(admin.user.id),
                            "telegram_id": admin.user.telegram_id,
                            "username": admin.user.username,
                            "first_name": admin.user.first_name,
                            "last_name": admin.user.last_name,
                        },
                        "assigned_at": admin.assigned_at.isoformat(),
                        "is_active": admin.is_active,
                    })
                
                return result
        
        except Exception as e:
            logger.error("Get all admins failed", error=str(e))
            return []
    
    async def get_admin_by_user_id(self, user_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Получает информацию об админе по ID пользователя."""
        try:
            async with self.context.get_session() as session:
                repo = UserRepository(session)
                admin = await repo.get_admin_by_user_id(user_id)
                
                if not admin:
                    return None
                
                return {
                    "id": str(admin.id),
                    "level": admin.level,
                    "level_display": admin.get_level_display(),
                    "user_id": str(admin.user_id),
                    "assigned_by": str(admin.assigned_by) if admin.assigned_by else None,
                    "assigned_at": admin.assigned_at.isoformat(),
                    "is_active": admin.is_active,
                }
        
        except Exception as e:
            logger.error("Get admin by user_id failed", user_id=user_id, error=str(e))
            return None
    
    async def update_admin_level(
        self,
        admin_id: uuid.UUID,
        new_level: str,
        updated_by: uuid.UUID
    ) -> Dict[str, Any]:
        """Обновляет уровень админа."""
        try:
            # Валидируем уровень
            if new_level not in [l.value for l in AdminLevel]:
                return {
                    "success": False,
                    "message": f"Неверный уровень админа: {new_level}"
                }
            
            async with self.context.get_session() as session:
                repo = UserRepository(session)
                
                # Получаем админа
                admin = await repo.get_admin_by_id(admin_id)
                if not admin:
                    return {
                        "success": False,
                        "message": "Админ не найден"
                    }
                
                # Обновляем уровень
                await repo.update_admin_level(admin_id, new_level)
                
                # Логируем изменение
                await repo.create_admin_log(
                    admin_id=admin_id,
                    action="level_update",
                    old_value=admin.level,
                    new_value=new_level,
                    performed_by=updated_by
                )
                
                await session.commit()
                
                return {
                    "success": True,
                    "message": f"Уровень админа обновлен на '{new_level}'",
                    "admin": {
                        "id": str(admin_id),
                        "old_level": admin.level,
                        "new_level": new_level,
                    }
                }
        
        except Exception as e:
            logger.error("Update admin level failed", admin_id=admin_id, error=str(e))
            return {
                "success": False,
                "message": f"Ошибка при обновлении уровня: {str(e)}"
            }
    
    async def toggle_admin_status(
        self,
        admin_id: uuid.UUID,
        updated_by: uuid.UUID
    ) -> Dict[str, Any]:
        """Переключает статус активности админа."""
        try:
            async with self.context.get_session() as session:
                repo = UserRepository(session)
                
                # Получаем админа
                admin = await repo.get_admin_by_id(admin_id)
                if not admin:
                    return {
                        "success": False,
                        "message": "Админ не найден"
                    }
                
                # Переключаем статус
                new_status = not admin.is_active
                await repo.update_admin_status(admin_id, new_status)
                
                # Логируем изменение
                await repo.create_admin_log(
                    admin_id=admin_id,
                    action="status_toggle",
                    old_value=str(admin.is_active),
                    new_value=str(new_status),
                    performed_by=updated_by
                )
                
                await session.commit()
                
                status_text = "активирован" if new_status else "деактивирован"
                return {
                    "success": True,
                    "message": f"Админ {status_text}",
                    "admin": {
                        "id": str(admin_id),
                        "new_status": new_status,
                    }
                }
        
        except Exception as e:
            logger.error("Toggle admin status failed", admin_id=admin_id, error=str(e))
            return {
                "success": False,
                "message": f"Ошибка при изменении статуса: {str(e)}"
            }
    
    async def _parse_user_identifier(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Парсит идентификатор пользователя.
        
        Поддерживает:
        - Telegram ID (цифры)
        - @username
        - Ссылку t.me/username
        - Полную ссылку https://t.me/username
        
        Returns:
            Словарь с информацией о пользователе или None
        """
        identifier = identifier.strip()
        
        # Если это просто цифры - вероятно Telegram ID
        if identifier.isdigit():
            return {
                "telegram_id": int(identifier),
                "type": "telegram_id"
            }
        
        # Удаляем пробелы и лишние символы
        identifier = identifier.replace(" ", "").replace("@", "")
        
        # Обработка ссылок
        if identifier.startswith("t.me/"):
            identifier = identifier[5:]
        elif identifier.startswith("https://t.me/"):
            identifier = identifier[13:]
        elif identifier.startswith("http://t.me/"):
            identifier = identifier[12:]
        
        # Проверяем, является ли оставшаяся часть username
        # Username может содержать буквы, цифры и подчеркивания
        if re.match(r'^[a-zA-Z0-9_]{5,32}$', identifier):
            # В реальном приложении здесь нужно было бы
            # получить Telegram ID по username через API
            # Пока возвращаем заглушку
            return {
                "username": identifier,
                "telegram_id": None,  # Будет получено позже
                "type": "username"
            }
        
        return None
    
    async def validate_main_admin(self, user_id: uuid.UUID) -> bool:
        """Проверяет, является ли пользователь главным админом."""
        try:
            admin_info = await self.get_admin_by_user_id(user_id)
            if not admin_info:
                return False
            
            return admin_info["level"] == AdminLevel.MAIN_ADMIN.value
        
        except Exception as e:
            logger.error("Validate main admin failed", user_id=user_id, error=str(e))
            return False
    
    async def get_admins_by_level(self, level: str) -> List[Dict[str, Any]]:
        """Получает всех админов указанного уровня."""
        try:
            all_admins = await self.get_all_admins()
            return [admin for admin in all_admins if admin["level"] == level]
        
        except Exception as e:
            logger.error("Get admins by level failed", level=level, error=str(e))
            return []