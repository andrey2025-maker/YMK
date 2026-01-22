"""
Модуль файлов - управление файлами в Telegram (архивация, загрузка, управление).
"""

from .archive_manager import ArchiveManager
from .telegram_file_manager import TelegramFileManager
from .file_id_manager import FileIDManager


class FileModule:
    """Модуль файлов."""
    
    def __init__(self, context):
        self.context = context
        self.archive_manager = ArchiveManager(context)
        self.telegram_file_manager = TelegramFileManager(context)
        self.file_id_manager = FileIDManager(context)
    
    async def initialize(self):
        """Инициализация модуля файлов."""
        await self.archive_manager.initialize()
        await self.telegram_file_manager.initialize()
        return self


# Экспорт для удобного импорта из других модулей
__all__ = [
    'FileModule',
    'ArchiveManager',
    'TelegramFileManager',
    'FileIDManager',
]