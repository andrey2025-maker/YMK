"""
Инициализатор пакета репозиториев.
Экспортирует все репозитории для работы с данными системы.
"""
from storage.repositories.base import BaseRepository
from storage.repositories.file_repository import FileRepository
from storage.repositories.reminder_repository import ReminderRepository
from storage.repositories.log_repository import LogRepository
from storage.repositories.user_repository import UserRepository
from storage.repositories.service_repository import ServiceRepository
from storage.repositories.installation_repository import InstallationRepository

__all__ = [
    "BaseRepository",
    "FileRepository",
    "ReminderRepository", 
    "LogRepository",
    "UserRepository",
    "ServiceRepository",
    "InstallationRepository"
]


class RepositoryFactory:
    """
    Фабрика для создания экземпляров репозиториев.
    Упрощает создание репозиториев с общим сессией БД.
    """
    
    def __init__(self, session_factory):
        """
        Инициализирует фабрику репозиториев.
        
        Args:
            session_factory: Фабрика сессий SQLAlchemy
        """
        self.session_factory = session_factory
    
    async def get_file_repository(self):
        """
        Создает экземпляр FileRepository.
        
        Returns:
            FileRepository
        """
        from sqlalchemy.ext.asyncio import AsyncSession
        session = AsyncSession(self.session_factory)
        return FileRepository(session)
    
    async def get_reminder_repository(self):
        """
        Создает экземпляр ReminderRepository.
        
        Returns:
            ReminderRepository
        """
        from sqlalchemy.ext.asyncio import AsyncSession
        session = AsyncSession(self.session_factory)
        return ReminderRepository(session)
    
    async def get_log_repository(self):
        """
        Создает экземпляр LogRepository.
        
        Returns:
            LogRepository
        """
        from sqlalchemy.ext.asyncio import AsyncSession
        session = AsyncSession(self.session_factory)
        return LogRepository(session)
    
    async def get_user_repository(self):
        """
        Создает экземпляр UserRepository.
        
        Returns:
            UserRepository
        """
        from sqlalchemy.ext.asyncio import AsyncSession
        session = AsyncSession(self.session_factory)
        return UserRepository(session)
    
    async def get_service_repository(self):
        """
        Создает экземпляр ServiceRepository.
        
        Returns:
            ServiceRepository
        """
        from sqlalchemy.ext.asyncio import AsyncSession
        session = AsyncSession(self.session_factory)
        return ServiceRepository(session)
    
    async def get_installation_repository(self):
        """
        Создает экземпляр InstallationRepository.
        
        Returns:
            InstallationRepository
        """
        from sqlalchemy.ext.asyncio import AsyncSession
        session = AsyncSession(self.session_factory)
        return InstallationRepository(session)
    
    async def close_all(self):
        """
        Закрывает все активные сессии.
        """
        # В реальной реализации здесь была бы логика закрытия сессий
        # Для простоты оставляем пустым - сессии управляются контекстом
        pass


# Экспортируем фабрику для использования в других модулях
__all__.append("RepositoryFactory")