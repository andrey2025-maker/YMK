import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession, AsyncEngine, 
    async_sessionmaker, create_async_engine
)
from sqlalchemy.pool import NullPool
import structlog

from config import config
from storage.models.base import Base
from storage.models.user import User, Admin, AdminPermission, UserAccess


logger = structlog.get_logger(__name__)


class DatabaseManager:
    """Менеджер базы данных."""
    
    def __init__(self):
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Инициализирует подключение к базе данных."""
        if self._initialized:
            return
        
        try:
            # Создаем async engine для PostgreSQL
            self.engine = create_async_engine(
                config.database.dsn,
                echo=config.bot.debug,
                poolclass=NullPool,  # Для асинхронности используем NullPool
                future=True,
                pool_pre_ping=True,  # Проверка соединения перед использованием
                connect_args={
                    "command_timeout": 60,
                    "server_settings": {
                        "application_name": "electric_bot",
                        "timezone": config.bot.timezone,
                    }
                }
            )
            
            # Создаем фабрику сессий
            self.session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
            
            # Проверяем подключение
            await self._test_connection()
            
            # Создаем таблицы (если их нет)
            await self._create_tables()
            
            self._initialized = True
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error("Database initialization failed", error=str(e))
            await self.close()
            raise
    
    async def _test_connection(self) -> None:
        """Тестирует подключение к базе данных."""
        async with self.engine.connect() as conn:
            await conn.execute("SELECT 1")
            logger.debug("Database connection test passed")
    
    async def _create_tables(self) -> None:
        """Создает все таблицы в базе данных."""
        try:
            async with self.engine.begin() as conn:
                # Создаем все таблицы из метаданных Base
                await conn.run_sync(Base.metadata.create_all)
                logger.info("Database tables created/verified")
        except Exception as e:
            logger.error("Failed to create tables", error=str(e))
            raise
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Предоставляет сессию базы данных в контекстном менеджере.
        
        Yields:
            AsyncSession: Асинхронная сессия SQLAlchemy
        """
        if not self.session_factory:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        
        session: AsyncSession = self.session_factory()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    
    async def execute_in_transaction(self, func, *args, **kwargs):
        """
        Выполняет функцию в транзакции.
        
        Args:
            func: Функция для выполнения
            *args, **kwargs: Аргументы функции
            
        Returns:
            Результат выполнения функции
        """
        async with self.get_session() as session:
            try:
                async with session.begin():
                    result = await func(session, *args, **kwargs)
                    return result
            except Exception as e:
                logger.error("Transaction failed", error=str(e))
                raise
    
    async def health_check(self) -> dict:
        """Проверяет здоровье базы данных."""
        try:
            async with self.engine.connect() as conn:
                # Проверяем подключение
                await conn.execute("SELECT 1")
                
                # Получаем статистику
                result = await conn.execute("SELECT version()")
                version = result.scalar()
                
                # Получаем количество подключений
                result = await conn.execute(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = :db_name",
                    {"db_name": config.database.name}
                )
                connections = result.scalar()
                
                return {
                    "status": "healthy",
                    "version": version,
                    "connections": connections,
                    "database": config.database.name,
                }
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def backup(self) -> Optional[str]:
        """
        Создает резервную копию базы данных.
        
        Returns:
            Путь к файлу резервной копии или None
        """
        import subprocess
        import os
        from datetime import datetime
        
        try:
            # Создаем имя файла резервной копии
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = "./assets/backups"
            os.makedirs(backup_dir, exist_ok=True)
            backup_file = os.path.join(backup_dir, f"backup_{timestamp}.sql")
            
            # Команда для создания резервной копии PostgreSQL
            env = os.environ.copy()
            env["PGPASSWORD"] = config.database.password
            
            cmd = [
                "pg_dump",
                "-h", config.database.host,
                "-p", str(config.database.port),
                "-U", config.database.user,
                "-d", config.database.name,
                "-f", backup_file,
                "--format=custom",  # Бинарный формат для быстрого восстановления
                "--compress=9",
                "--verbose"
            ]
            
            # Выполняем команду
            process = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info("Database backup created", file=backup_file)
                return backup_file
            else:
                logger.error("Database backup failed", 
                           stderr=stderr.decode(), 
                           returncode=process.returncode)
                return None
                
        except Exception as e:
            logger.error("Database backup error", error=str(e))
            return None
    
    async def close(self) -> None:
        """Закрывает все соединения с базой данных."""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None
            self._initialized = False
            logger.info("Database connections closed")


# Глобальный экземпляр менеджера БД
db_manager = DatabaseManager()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency для получения сессии БД.
    Используется в FastAPI или других местах, где нужна инъекция зависимостей.
    """
    async with db_manager.get_session() as session:
        yield session


async def init_database() -> None:
    """Инициализирует базу данных при запуске приложения."""
    await db_manager.initialize()


async def close_database() -> None:
    """Закрывает соединения с базой данных при завершении приложения."""
    await db_manager.close()