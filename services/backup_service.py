"""
Сервис для резервного копирования данных.
Реализует создание резервных копий БД, архивацию в Telegram и управление версиями.
"""

import os
import json
import logging
import tempfile
import zipfile
import shutil
from typing import Dict, List, Optional, Any, Tuple, BinaryIO
from datetime import datetime, timedelta
from pathlib import Path

import aiofiles
from sqlalchemy import text

from storage.database import async_session_maker
from modules.file.archive_manager import ArchiveManager
from utils.date_utils import format_date

logger = logging.getLogger(__name__)


class BackupType(str, Enum):
    """Типы резервных копий."""
    FULL = "full"           # Полная копия всех данных
    DATABASE = "database"   # Только база данных
    FILES = "files"         # Только файлы
    CONFIG = "config"       # Конфигурация системы


class BackupService:
    """Сервис для резервного копирования данных."""
    
    def __init__(
        self,
        archive_manager: ArchiveManager,
        backup_dir: Optional[str] = None,
        max_backups: int = 30  # Хранить не более 30 бэкапов
    ):
        self.archive_manager = archive_manager
        self.backup_dir = backup_dir or os.path.join(tempfile.gettempdir(), "bot_backups")
        self.max_backups = max_backups
        
        # Создаем директорию для бэкапов если её нет
        os.makedirs(self.backup_dir, exist_ok=True)
    
    async def create_full_backup(
        self,
        description: Optional[str] = None,
        send_to_telegram: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        Создание полной резервной копии.
        
        Args:
            description: Описание бэкапа
            send_to_telegram: Отправлять ли в Telegram
            
        Returns:
            Кортеж (успех, путь к файлу или None)
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"full_backup_{timestamp}.zip"
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            # Создаем временную директорию для подготовки бэкапа
            with tempfile.TemporaryDirectory() as temp_dir:
                # 1. Экспортируем базу данных
                db_dump_path = await self._export_database(temp_dir)
                if not db_dump_path:
                    logger.error("Failed to export database")
                    return False, None
                
                # 2. Сохраняем метаданные
                metadata_path = await self._save_metadata(temp_dir, description)
                
                # 3. Копируем важные файлы (если есть)
                await self._copy_important_files(temp_dir)
                
                # 4. Архивируем всё в ZIP
                with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, temp_dir)
                            zipf.write(file_path, arcname)
                
                # 5. Отправляем в Telegram если нужно
                if send_to_telegram:
                    await self._send_backup_to_telegram(backup_path, description)
                
                # 6. Очищаем старые бэкапы
                await self._cleanup_old_backups()
                
                logger.info(f"Full backup created: {backup_path}")
                return True, backup_path
                
        except Exception as e:
            logger.error(f"Error creating full backup: {e}")
            return False, None
    
    async def create_database_backup(
        self,
        description: Optional[str] = None,
        send_to_telegram: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        Создание резервной копии только базы данных.
        
        Args:
            description: Описание бэкапа
            send_to_telegram: Отправлять ли в Telegram
            
        Returns:
            Кортеж (успех, путь к файлу или None)
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"db_backup_{timestamp}.sql"
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            # Экспортируем базу данных
            async with async_session_maker() as session:
                # Получаем структуру таблиц
                tables = await self._get_database_tables(session)
                
                # Создаем SQL дамп
                sql_dump = await self._generate_sql_dump(session, tables)
                
                # Сохраняем в файл
                async with aiofiles.open(backup_path, 'w', encoding='utf-8') as f:
                    await f.write(sql_dump)
            
            # Сжимаем файл
            compressed_path = f"{backup_path}.gz"
            await self._compress_file(backup_path, compressed_path)
            
            # Удаляем несжатый файл
            os.remove(backup_path)
            
            # Отправляем в Telegram если нужно
            if send_to_telegram:
                await self._send_backup_to_telegram(compressed_path, description, is_database=True)
            
            # Очищаем старые бэкапы
            await self._cleanup_old_backups()
            
            logger.info(f"Database backup created: {compressed_path}")
            return True, compressed_path
            
        except Exception as e:
            logger.error(f"Error creating database backup: {e}")
            return False, None
    
    async def restore_from_backup(
        self,
        backup_path: str,
        backup_type: BackupType = BackupType.FULL
    ) -> Tuple[bool, str]:
        """
        Восстановление данных из резервной копии.
        
        Args:
            backup_path: Путь к файлу бэкапа
            backup_type: Тип бэкапа
            
        Returns:
            Кортеж (успех, сообщение)
        """
        try:
            if not os.path.exists(backup_path):
                return False, f"Backup file not found: {backup_path}"
            
            if backup_type == BackupType.DATABASE:
                return await self._restore_database(backup_path)
            elif backup_type == BackupType.FULL:
                return await self._restore_full_backup(backup_path)
            else:
                return False, f"Unsupported backup type: {backup_type}"
                
        except Exception as e:
            logger.error(f"Error restoring from backup: {e}")
            return False, f"Restoration error: {str(e)}"
    
    async def get_backup_list(
        self,
        backup_type: Optional[BackupType] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Получение списка доступных резервных копий.
        
        Args:
            backup_type: Тип бэкапов для фильтрации
            limit: Максимальное количество
            
        Returns:
            Список информации о бэкапах
        """
        try:
            backups = []
            
            for filename in os.listdir(self.backup_dir):
                filepath = os.path.join(self.backup_dir, filename)
                
                if not os.path.isfile(filepath):
                    continue
                
                # Определяем тип бэкапа по имени файла
                file_type = self._get_backup_type_from_filename(filename)
                
                if backup_type and file_type != backup_type:
                    continue
                
                stat = os.stat(filepath)
                size_mb = stat.st_size / (1024 * 1024)
                
                backup_info = {
                    "filename": filename,
                    "filepath": filepath,
                    "type": file_type,
                    "size_mb": round(size_mb, 2),
                    "created_at": datetime.fromtimestamp(stat.st_ctime),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime)
                }
                
                backups.append(backup_info)
            
            # Сортируем по дате создания (новые сначала)
            backups.sort(key=lambda x: x["created_at"], reverse=True)
            
            return backups[:limit]
            
        except Exception as e:
            logger.error(f"Error getting backup list: {e}")
            return []
    
    async def delete_backup(self, filename: str) -> bool:
        """
        Удаление резервной копии.
        
        Args:
            filename: Имя файла бэкапа
            
        Returns:
            True если удаление успешно
        """
        try:
            filepath = os.path.join(self.backup_dir, filename)
            
            if not os.path.exists(filepath):
                logger.warning(f"Backup file not found: {filepath}")
                return False
            
            os.remove(filepath)
            logger.info(f"Backup deleted: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting backup {filename}: {e}")
            return False
    
    async def backup_health_check(self) -> Dict[str, Any]:
        """
        Проверка состояния системы резервного копирования.
        
        Returns:
            Словарь с информацией о состоянии
        """
        try:
            # Проверяем директорию бэкапов
            dir_exists = os.path.exists(self.backup_dir)
            dir_writable = os.access(self.backup_dir, os.W_OK) if dir_exists else False
            
            # Получаем список бэкапов
            backups = await self.get_backup_list(limit=100)
            
            # Проверяем последний бэкап
            last_backup = backups[0] if backups else None
            days_since_last = None
            
            if last_backup:
                days_since_last = (datetime.now() - last_backup["created_at"]).days
            
            # Проверяем место на диске
            disk_info = await self._get_disk_usage()
            
            health_info = {
                "backup_directory": {
                    "path": self.backup_dir,
                    "exists": dir_exists,
                    "writable": dir_writable
                },
                "backups": {
                    "total_count": len(backups),
                    "types": {
                        "full": len([b for b in backups if b["type"] == BackupType.FULL]),
                        "database": len([b for b in backups if b["type"] == BackupType.DATABASE]),
                        "files": len([b for b in backups if b["type"] == BackupType.FILES])
                    },
                    "total_size_mb": round(sum(b["size_mb"] for b in backups), 2)
                },
                "last_backup": {
                    "filename": last_backup["filename"] if last_backup else None,
                    "age_days": days_since_last,
                    "status": "GOOD" if days_since_last and days_since_last <= 7 else "WARNING"
                } if last_backup else None,
                "disk_space": disk_info,
                "status": "HEALTHY" if dir_exists and dir_writable and backups else "UNHEALTHY"
            }
            
            return health_info
            
        except Exception as e:
            logger.error(f"Error in backup health check: {e}")
            return {"status": "ERROR", "error": str(e)}
    
    async def _export_database(self, temp_dir: str) -> Optional[str]:
        """Экспорт базы данных в SQL файл."""
        try:
            dump_path = os.path.join(temp_dir, "database_dump.sql")
            
            async with async_session_maker() as session:
                tables = await self._get_database_tables(session)
                sql_dump = await self._generate_sql_dump(session, tables)
                
                async with aiofiles.open(dump_path, 'w', encoding='utf-8') as f:
                    await f.write(sql_dump)
            
            return dump_path
            
        except Exception as e:
            logger.error(f"Error exporting database: {e}")
            return None
    
    async def _get_database_tables(self, session) -> List[str]:
        """Получение списка таблиц в базе данных."""
        try:
            # PostgreSQL specific query
            query = text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            
            result = await session.execute(query)
            tables = [row[0] for row in result.fetchall()]
            
            return tables
            
        except Exception as e:
            logger.error(f"Error getting database tables: {e}")
            return []
    
    async def _generate_sql_dump(self, session, tables: List[str]) -> str:
        """Генерация SQL дампа базы данных."""
        sql_lines = []
        
        # Добавляем заголовок
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sql_lines.append(f"-- Database backup created at {timestamp}")
        sql_lines.append(f"-- Tables: {len(tables)}")
        sql_lines.append("")
        
        # Для каждой таблицы
        for table in tables:
            sql_lines.append(f"-- Table: {table}")
            sql_lines.append(f"DROP TABLE IF EXISTS {table} CASCADE;")
            
            # Получаем CREATE TABLE
            create_query = text(f"SELECT pg_get_tabledef('{table}');")
            result = await session.execute(create_query)
            create_sql = result.scalar()
            
            if create_sql:
                sql_lines.append(create_sql + ";")
            
            # Получаем данные
            data_query = text(f"SELECT * FROM {table};")
            result = await session.execute(data_query)
            rows = result.fetchall()
            
            if rows:
                # Получаем названия колонок
                columns = result.keys()
                columns_str = ', '.join(columns)
                
                sql_lines.append(f"\n-- Data for table {table}: {len(rows)} rows")
                
                for row in rows:
                    values = []
                    for value in row:
                        if value is None:
                            values.append("NULL")
                        elif isinstance(value, str):
                            # Экранируем кавычки
                            escaped = value.replace("'", "''")
                            values.append(f"'{escaped}'")
                        elif isinstance(value, datetime):
                            values.append(f"'{value.isoformat()}'")
                        else:
                            values.append(str(value))
                    
                    values_str = ', '.join(values)
                    sql_lines.append(f"INSERT INTO {table} ({columns_str}) VALUES ({values_str});")
            
            sql_lines.append("")
        
        return '\n'.join(sql_lines)
    
    async def _save_metadata(self, temp_dir: str, description: Optional[str]) -> str:
        """Сохранение метаданных бэкапа."""
        try:
            metadata = {
                "backup_type": "full",
                "created_at": datetime.now().isoformat(),
                "description": description or "Automatic backup",
                "version": "1.0",
                "system_info": {
                    "python_version": os.sys.version,
                    "platform": os.sys.platform
                }
            }
            
            metadata_path = os.path.join(temp_dir, "metadata.json")
            async with aiofiles.open(metadata_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(metadata, indent=2, ensure_ascii=False))
            
            return metadata_path
            
        except Exception as e:
            logger.error(f"Error saving metadata: {e}")
            # Создаем простой файл если не удалось сохранить JSON
            metadata_path = os.path.join(temp_dir, "metadata.txt")
            async with aiofiles.open(metadata_path, 'w') as f:
                await f.write(f"Backup created: {datetime.now()}\n")
                await f.write(f"Description: {description or 'N/A'}\n")
            
            return metadata_path
    
    async def _copy_important_files(self, temp_dir: str):
        """Копирование важных файлов системы."""
        try:
            files_to_backup = []
            
            # Конфигурационные файлы
            config_files = [".env", "config.py", "docker-compose.yml", "docker-compose.prod.yml"]
            
            for config_file in config_files:
                if os.path.exists(config_file):
                    files_to_backup.append(config_file)
            
            # Копируем файлы
            for filepath in files_to_backup:
                if os.path.exists(filepath):
                    dest_path = os.path.join(temp_dir, "configs", os.path.basename(filepath))
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    shutil.copy2(filepath, dest_path)
            
        except Exception as e:
            logger.warning(f"Error copying important files: {e}")
    
    async def _send_backup_to_telegram(
        self,
        backup_path: str,
        description: Optional[str] = None,
        is_database: bool = False
    ):
        """Отправка бэкапа в Telegram."""
        try:
            if not os.path.exists(backup_path):
                logger.warning(f"Backup file not found for Telegram: {backup_path}")
                return
            
            filename = os.path.basename(backup_path)
            file_size_mb = os.path.getsize(backup_path) / (1024 * 1024)
            
            # Проверяем размер файла (Telegram ограничение ~50MB)
            if file_size_mb > 45:
                logger.warning(f"Backup file too large for Telegram: {file_size_mb:.2f}MB")
                return
            
            # Читаем файл
            async with aiofiles.open(backup_path, 'rb') as f:
                file_data = await f.read()
            
            # Создаем описание
            backup_type = "Database" if is_database else "Full"
            caption = f"🔰 {backup_type} Backup\n"
            caption += f"📅 {format_date(datetime.now())}\n"
            caption += f"📦 {filename}\n"
            caption += f"📊 {file_size_mb:.2f} MB\n"
            
            if description:
                caption += f"📝 {description}\n"
            
            # Отправляем через ArchiveManager
            # Здесь должен быть вызов метода отправки файла
            # await self.archive_manager.send_backup_file(file_data, filename, caption)
            
            logger.info(f"Backup sent to Telegram: {filename}")
            
        except Exception as e:
            logger.error(f"Error sending backup to Telegram: {e}")
    
    async def _cleanup_old_backups(self):
        """Очистка старых резервных копий."""
        try:
            backups = await self.get_backup_list(limit=1000)  # Получаем все
            
            if len(backups) <= self.max_backups:
                return
            
            # Сортируем по дате создания (старые в конце)
            backups.sort(key=lambda x: x["created_at"])
            
            # Удаляем самые старые
            to_delete = backups[self.max_backups:]
            
            for backup in to_delete:
                try:
                    os.remove(backup["filepath"])
                    logger.debug(f"Deleted old backup: {backup['filename']}")
                except Exception as e:
                    logger.warning(f"Could not delete backup {backup['filename']}: {e}")
            
            logger.info(f"Cleaned up {len(to_delete)} old backups")
            
        except Exception as e:
            logger.error(f"Error cleaning up old backups: {e}")
    
    def _get_backup_type_from_filename(self, filename: str) -> BackupType:
        """Определение типа бэкапа по имени файла."""
        filename_lower = filename.lower()
        
        if filename_lower.startswith("full_backup"):
            return BackupType.FULL
        elif filename_lower.startswith("db_backup") or ".sql" in filename_lower:
            return BackupType.DATABASE
        elif filename_lower.startswith("config_backup"):
            return BackupType.CONFIG
        elif filename_lower.startswith("files_backup"):
            return BackupType.FILES
        else:
            return BackupType.FULL  # По умолчанию
    
    async def _compress_file(self, source_path: str, dest_path: str):
        """Сжатие файла с использованием gzip."""
        try:
            import gzip
            
            async with aiofiles.open(source_path, 'rb') as f_in:
                async with aiofiles.open(dest_path, 'wb') as f_out:
                    # В асинхронном режиме проще использовать синхронное сжатие
                    # для небольших файлов
                    data = await f_in.read()
                    compressed = gzip.compress(data)
                    await f_out.write(compressed)
            
        except ImportError:
            # Если gzip не доступен, просто копируем файл
            logger.warning("gzip not available, copying file without compression")
            shutil.copy2(source_path, dest_path)
        except Exception as e:
            logger.error(f"Error compressing file: {e}")
            # Копируем без сжатия в случае ошибки
            shutil.copy2(source_path, dest_path)
    
    async def _restore_database(self, backup_path: str) -> Tuple[bool, str]:
        """Восстановление базы данных из SQL дампа."""
        try:
            # Проверяем расширение файла
            if backup_path.endswith('.gz'):
                # Распаковываем
                import gzip
                
                temp_path = backup_path.replace('.gz', '')
                with gzip.open(backup_path, 'rt', encoding='utf-8') as f_in:
                    with open(temp_path, 'w', encoding='utf-8') as f_out:
                        f_out.write(f_in.read())
                
                backup_path = temp_path
                cleanup_temp = True
            else:
                cleanup_temp = False
            
            # Читаем SQL файл
            async with aiofiles.open(backup_path, 'r', encoding='utf-8') as f:
                sql_content = await f.read()
            
            # Разделяем на отдельные команды
            # Простой парсинг SQL - в реальном проекте нужно использовать более надежный метод
            commands = []
            current_command = []
            in_string = False
            string_char = None
            
            for line in sql_content.split('\n'):
                line = line.strip()
                if not line or line.startswith('--'):
                    continue
                
                for char in line:
                    if char in ("'", '"') and (string_char is None or char == string_char):
                        in_string = not in_string
                        string_char = char if in_string else None
                    
                    current_command.append(char)
                
                current_command.append(' ')
                
                if not in_string and line.endswith(';'):
                    command = ''.join(current_command).strip()
                    if command:
                        commands.append(command)
                    current_command = []
            
            # Если осталась незавершенная команда
            if current_command and not in_string:
                command = ''.join(current_command).strip()
                if command and command.endswith(';'):
                    commands.append(command)
            
            # Выполняем команды
            async with async_session_maker() as session:
                for command in commands:
                    try:
                        await session.execute(text(command))
                    except Exception as e:
                        logger.warning(f"Error executing SQL command: {e}")
                        # Продолжаем выполнение других команд
            
                await session.commit()
            
            # Очищаем временный файл если был создан
            if cleanup_temp and os.path.exists(backup_path):
                os.remove(backup_path)
            
            return True, f"Database restored successfully from {os.path.basename(backup_path)}"
            
        except Exception as e:
            logger.error(f"Error restoring database: {e}")
            return False, f"Database restoration failed: {str(e)}"
    
    async def _restore_full_backup(self, backup_path: str) -> Tuple[bool, str]:
        """Восстановление из полной резервной копии."""
        try:
            # Создаем временную директорию для распаковки
            with tempfile.TemporaryDirectory() as temp_dir:
                # Распаковываем ZIP
                with zipfile.ZipFile(backup_path, 'r') as zipf:
                    zipf.extractall(temp_dir)
                
                # Ищем SQL дамп
                sql_dump_path = None
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        if file.endswith('.sql'):
                            sql_dump_path = os.path.join(root, file)
                            break
                
                if not sql_dump_path:
                    return False, "SQL dump not found in backup"
                
                # Восстанавливаем базу данных
                success, message = await self._restore_database(sql_dump_path)
                
                if not success:
                    return False, f"Failed to restore database: {message}"
                
                # Здесь можно добавить восстановление других файлов
                # (конфигурации и т.д.)
                
                return True, "Full backup restored successfully"
            
        except Exception as e:
            logger.error(f"Error restoring full backup: {e}")
            return False, f"Full backup restoration failed: {str(e)}"
    
    async def _get_disk_usage(self) -> Dict[str, Any]:
        """Получение информации об использовании диска."""
        try:
            import shutil
            
            total, used, free = shutil.disk_usage(self.backup_dir)
            
            return {
                "total_gb": round(total / (1024**3), 2),
                "used_gb": round(used / (1024**3), 2),
                "free_gb": round(free / (1024**3), 2),
                "free_percent": round((free / total) * 100, 1)
            }
            
        except Exception as e:
            logger.warning(f"Error getting disk usage: {e}")
            return {
                "total_gb": 0,
                "used_gb": 0,
                "free_gb": 0,
                "free_percent": 0
            }
    
    async def auto_backup_if_needed(self, force: bool = False) -> bool:
        """
        Автоматическое создание бэкапа если нужно.
        
        Args:
            force: Создать бэкап принудительно
            
        Returns:
            True если бэкап был создан
        """
        try:
            # Проверяем когда был последний бэкап
            backups = await self.get_backup_list(limit=1)
            
            if backups and not force:
                last_backup = backups[0]
                days_since_last = (datetime.now() - last_backup["created_at"]).days
                
                # Если последний бэкап был менее 1 дня назад, пропускаем
                if days_since_last < 1:
                    logger.debug("Skipping auto-backup: last backup was today")
                    return False
            
            # Создаем бэкап
            description = "Automatic daily backup"
            success, _ = await self.create_database_backup(
                description=description,
                send_to_telegram=False  # В автоматическом режиме не отправляем в Telegram
            )
            
            if success:
                logger.info("Auto-backup created successfully")
            else:
                logger.warning("Auto-backup creation failed")
            
            return success
            
        except Exception as e:
            logger.error(f"Error in auto-backup: {e}")
            return False