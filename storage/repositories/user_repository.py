from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy import select, update, delete, func, or_
from sqlalchemy.orm import selectinload, joinedload

from .base import BaseRepository
from storage.models.user import User, Admin, AdminPermission, UserAccess, AdminLevel


class UserRepository(BaseRepository[User]):
    """Репозиторий для работы с пользователями."""
    
    def __init__(self, session):
        super().__init__(User, session)
    
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Получает пользователя по Telegram ID."""
        query = select(User).where(
            User.telegram_id == telegram_id,
            User.is_deleted == False
        ).options(
            selectinload(User.admin).selectinload(Admin.permissions)
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def create_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> User:
        """Создает нового пользователя."""
        user = await self.create(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
            last_active=datetime.now()
        )
        return user
    
    async def update_last_active(self, user_id: UUID) -> None:
        """Обновляет время последней активности пользователя."""
        query = (
            update(User)
            .where(User.id == user_id)
            .values(last_active=datetime.now())
        )
        await self.session.execute(query)
    
    async def get_admins_with_users(self) -> List[Admin]:
        """Получает всех админов с информацией о пользователях."""
        query = select(Admin).where(
            Admin.is_deleted == False,
            Admin.is_active == True
        ).options(
            joinedload(Admin.user),
            joinedload(Admin.permissions)
        ).order_by(Admin.level.desc(), Admin.assigned_at.desc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_admin_by_user_id(self, user_id: UUID) -> Optional[Admin]:
        """Получает админа по ID пользователя."""
        query = select(Admin).where(
            Admin.user_id == user_id,
            Admin.is_deleted == False,
            Admin.is_active == True
        ).options(
            joinedload(Admin.user),
            joinedload(Admin.permissions)
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def create_admin(
        self,
        user_id: UUID,
        level: str,
        assigned_by: Optional[UUID] = None
    ) -> Admin:
        """Создает нового админа."""
        admin = Admin(
            user_id=user_id,
            level=level,
            assigned_by=assigned_by,
            assigned_at=datetime.now(),
            is_active=True
        )
        self.session.add(admin)
        await self.session.flush()
        return admin
    
    async def delete_admin(self, admin_id: UUID) -> bool:
        """Удаляет админа."""
        # Сначала удаляем разрешения
        await self.session.execute(
            delete(AdminPermission).where(AdminPermission.admin_id == admin_id)
        )
        
        # Затем удаляем админа
        query = delete(Admin).where(Admin.id == admin_id)
        result = await self.session.execute(query)
        return result.rowcount > 0
    
    async def create_admin_permissions(self, admin_id: UUID) -> AdminPermission:
        """Создает пустые разрешения для админа."""
        permissions = AdminPermission(
            admin_id=admin_id,
            pm_permissions={},
            group_permissions={}
        )
        self.session.add(permissions)
        await self.session.flush()
        return permissions
    
    async def get_admins_by_level(self, level: str) -> List[Admin]:
        """Получает админов по уровню."""
        query = select(Admin).where(
            Admin.level == level,
            Admin.is_deleted == False,
            Admin.is_active == True
        ).options(
            joinedload(Admin.user),
            joinedload(Admin.permissions)
        )
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_admins_by_levels(self, levels: List[str]) -> List[Admin]:
        """Получает админов по списку уровней."""
        query = select(Admin).where(
            Admin.level.in_(levels),
            Admin.is_deleted == False,
            Admin.is_active == True
        ).options(
            joinedload(Admin.user)
        )
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_admin_by_id(self, admin_id: UUID) -> Optional[Admin]:
        """Получает админа по ID."""
        query = select(Admin).where(
            Admin.id == admin_id,
            Admin.is_deleted == False
        ).options(
            joinedload(Admin.user),
            joinedload(Admin.permissions)
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def update_admin_level(self, admin_id: UUID, new_level: str) -> bool:
        """Обновляет уровень админа."""
        query = (
            update(Admin)
            .where(Admin.id == admin_id)
            .values(level=new_level)
        )
        result = await self.session.execute(query)
        return result.rowcount > 0
    
    async def update_admin_status(self, admin_id: UUID, is_active: bool) -> bool:
        """Обновляет статус активности админа."""
        query = (
            update(Admin)
            .where(Admin.id == admin_id)
            .values(is_active=is_active)
        )
        result = await self.session.execute(query)
        return result.rowcount > 0
    
    async def create_admin_log(
        self,
        admin_id: UUID,
        action: str,
        old_value: str,
        new_value: str,
        performed_by: UUID
    ) -> None:
        """Создает запись в лог изменений админа."""
        # В реальном приложении здесь была бы модель AdminLog
        # Пока просто логируем
        pass
    
    async def get_all_admins_with_users(self) -> List[Admin]:
        """Получает всех админов с пользователями."""
        return await self.get_admins_with_users()