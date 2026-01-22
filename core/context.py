from typing import Optional, Dict, Any
import asyncio

import aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from config import config
from storage.cache.manager import CacheManager

from modules.admin import AdminModule


class AppContext:
    """Контекст приложения, управляющий всеми внешними соединениями."""
    
    _instance: Optional['AppContext'] = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = False
            self.config = config
            self._engine = None
            self._session_factory = None
            self._redis = None
            self._cache = None
    
    async def initialize(self) -> None:
        """Инициализирует все соединения."""
        async with self._lock:
            if self._initialized:
                return
            
            try:
                # Инициализируем Redis
                await self._init_redis()
                
                # Инициализируем кэш менеджер
                await self._init_cache()
                
                # Инициализируем базу данных
                await self._init_database()
                
                self._initialized = True
                
            except Exception as e:
                await self.close()
                raise RuntimeError(f"Failed to initialize AppContext: {e}")
    
    async def _init_redis(self) -> None:
        """Инициализирует подключение к Redis."""
        self._redis = await aioredis.from_url(
            self.config.redis.dsn,
            encoding="utf-8",
            decode_responses=True,
            max_connections=10,
        )
    
    async def _init_cache(self) -> None:
        """Инициализирует менеджер кэша."""
        self._cache = CacheManager(self._redis)
        await self._cache.initialize()
    
    async def _init_database(self) -> None:
        """Инициализирует подключение к PostgreSQL."""
        self._engine = create_async_engine(
            self.config.database.dsn,
            echo=self.config.bot.debug,
            poolclass=NullPool,  # Для асинхронности
            future=True,
            pool_pre_ping=True,
        )
        
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    
    @property
    def redis(self) -> aioredis.Redis:
        """Возвращает клиент Redis."""
        if not self._redis:
            raise RuntimeError("Redis not initialized. Call initialize() first.")
        return self._redis
    
    @property
    def cache(self) -> CacheManager:
        """Возвращает менеджер кэша."""
        if not self._cache:
            raise RuntimeError("Cache not initialized. Call initialize() first.")
        return self._cache
    
    @property
    def database(self) -> AsyncSession:
        """Возвращает сессию базы данных."""
        if not self._session_factory:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._session_factory()
    
    def get_session(self) -> AsyncSession:
        """Возвращает новую сессию БД."""
        if not self._session_factory:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._session_factory()
    
    async def close(self) -> None:
        """Корректно закрывает все соединения."""
        if self._redis:
            await self._redis.close()
            self._redis = None
        
        if self._cache:
            await self._cache.close()
            self._cache = None
        
        if self._engine:
            await self._engine.dispose()
            self._engine = None
        
        self._initialized = False
    
    async def health_check(self) -> Dict[str, bool]:
        """Проверяет здоровье всех соединений."""
        checks = {}
        
        # Проверка Redis
        try:
            if self._redis:
                await self._redis.ping()
                checks['redis'] = True
            else:
                checks['redis'] = False
        except Exception:
            checks['redis'] = False
        
        # Проверка базы данных
        try:
            if self._engine:
                async with self._engine.connect() as conn:
                    await conn.execute("SELECT 1")
                checks['database'] = True
            else:
                checks['database'] = False
        except Exception:
            checks['database'] = False
        
        return checks
    
    def __str__(self) -> str:
        return f"AppContext(initialized={self._initialized})"
    
    async def get_log_channel_id(self) -> Optional[str]:
        """
        Получает ID канала для логов из базы данных
        Реализуйте в соответствии с вашей БД
        """
        # Временная заглушка - вернет None
        return None
    
    async def _init_admin_module(self):
        self.admin_module = AdminModule(self)
        await self.admin_module.initialize()

        # Доступ к отдельным менеджерам
        self.admin_manager = self.admin_module.admin_manager
        self.permission_manager = self.admin_module.permission_manager
        self.log_manager = self.admin_module.log_manager
        self.export_manager = self.admin_module.export_manager