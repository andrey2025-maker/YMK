import asyncio
from logging.config import fileConfig
import sys
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Добавляем корень проекта в путь Python
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

# Импортируем конфигурацию и модели
from config import config as app_config
from storage.models.base import Base
from storage.models.user import User, Admin, AdminPermission, UserAccess

# Alembic Config object
alembic_config = context.config

# Настраиваем логирование
if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

# Устанавливаем DSN из конфигурации приложения
alembic_config.set_main_option("sqlalchemy.url", app_config.database.alembic_dsn)

# Добавляем метаданные моделей для автогенерации
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Запуск миграций в offline режиме."""
    url = alembic_config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Запуск миграций с подключением."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        # Включаем поддержку batch mode для SQLite (но у нас PostgreSQL)
        render_as_batch=True,
        # Добавляем пользовательские контекстные переменные
        version_table="alembic_version",
        version_table_schema=None,
        # Настройки для улучшенной генерации миграций
        include_schemas=True,
        include_object=lambda obj, name, type_, reflected, compare_to: (
            not name.startswith('_')
        ),
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Запуск асинхронных миграций."""
    connectable = async_engine_from_config(
        alembic_config.get_section(alembic_config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Запуск миграций в online режиме."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()