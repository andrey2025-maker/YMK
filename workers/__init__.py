"""
Инициализатор пакета фоновых воркеров.
Экспортирует все воркеры для фоновых задач: напоминания, бэкапы, очистка.
"""
from workers.reminder_worker import ReminderWorker
from workers.backup_worker import BackupWorker
from workers.cleanup_worker import CleanupWorker

__all__ = [
    "ReminderWorker",
    "BackupWorker", 
    "CleanupWorker",
]


class WorkersFactory:
    """
    Фабрика для создания всех фоновых воркеров.
    Управляет созданием и инициализацией воркеров.
    """
    
    def __init__(self, context):
        """
        Инициализирует фабрику воркеров.
        
        Args:
            context: Контекст приложения
        """
        self.context = context
        self._reminder_worker = None
        self._backup_worker = None
        self._cleanup_worker = None
        self._all_workers = {}
        
    async def init_reminder_worker(self) -> ReminderWorker:
        """
        Инициализирует и возвращает воркер напоминаний.
        
        Returns:
            ReminderWorker объект
        """
        if not self._reminder_worker:
            self._reminder_worker = ReminderWorker(self.context)
            self._all_workers['reminder'] = self._reminder_worker
        
        return self._reminder_worker
    
    async def init_backup_worker(self) -> BackupWorker:
        """
        Инициализирует и возвращает воркер бэкапов.
        
        Returns:
            BackupWorker объект
        """
        if not self._backup_worker:
            self._backup_worker = BackupWorker(self.context)
            self._all_workers['backup'] = self._backup_worker
        
        return self._backup_worker
    
    async def init_cleanup_worker(self) -> CleanupWorker:
        """
        Инициализирует и возвращает воркер очистки.
        
        Returns:
            CleanupWorker объект
        """
        if not self._cleanup_worker:
            self._cleanup_worker = CleanupWorker(self.context)
            self._all_workers['cleanup'] = self._cleanup_worker
        
        return self._cleanup_worker
    
    async def init_all_workers(self) -> dict:
        """
        Инициализирует всех воркеров.
        
        Returns:
            Словарь со всеми инициализированными воркерами
        """
        workers = {}
        
        workers['reminder'] = await self.init_reminder_worker()
        workers['backup'] = await self.init_backup_worker()
        workers['cleanup'] = await self.init_cleanup_worker()
        
        return workers
    
    async def start_all_workers(self):
        """
        Запускает всех воркеров.
        """
        logger.info("Запуск всех фоновых воркеров...")
        
        # Запускаем воркер напоминаний
        reminder_worker = await self.init_reminder_worker()
        await reminder_worker.start()
        logger.info("ReminderWorker запущен")
        
        # Запускаем воркер бэкапов
        backup_worker = await self.init_backup_worker()
        await backup_worker.start()
        logger.info("BackupWorker запущен")
        
        # Запускаем воркер очистки
        cleanup_worker = await self.init_cleanup_worker()
        await cleanup_worker.start()
        logger.info("CleanupWorker запущен")
        
        logger.info("Все фоновые воркеры запущены")
    
    async def stop_all_workers(self):
        """
        Останавливает всех воркеров.
        """
        logger.info("Остановка всех фоновых воркеров...")
        
        stopped_count = 0
        
        if self._reminder_worker:
            await self._reminder_worker.stop()
            stopped_count += 1
            logger.info("ReminderWorker остановлен")
        
        if self._backup_worker:
            await self._backup_worker.stop()
            stopped_count += 1
            logger.info("BackupWorker остановлен")
        
        if self._cleanup_worker:
            await self._cleanup_worker.stop()
            stopped_count += 1
            logger.info("CleanupWorker остановлен")
        
        logger.info(f"Остановлено воркеров: {stopped_count}")
    
    async def get_worker(self, worker_name: str):
        """
        Получает воркер по имени.
        
        Args:
            worker_name: Имя воркера (reminder, backup, cleanup)
        
        Returns:
            Воркер или None если не найден
        """
        return self._all_workers.get(worker_name)
    
    async def get_all_workers(self) -> dict:
        """
        Получает всех воркеров.
        
        Returns:
            Словарь со всеми воркерами
        """
        return self._all_workers.copy()
    
    async def get_workers_status(self) -> dict:
        """
        Получает статус всех воркеров.
        
        Returns:
            Словарь со статусами воркеров
        """
        status = {}
        
        for name, worker in self._all_workers.items():
            if hasattr(worker, 'is_running'):
                status[name] = {
                    'is_running': worker.is_running,
                    'type': worker.__class__.__name__
                }
                
                # Добавляем статистику если есть
                if hasattr(worker, 'get_statistics'):
                    try:
                        stats = await worker.get_statistics()
                        status[name]['statistics'] = stats
                    except Exception as e:
                        status[name]['statistics_error'] = str(e)
        
        return status
    
    async def run_worker_task(self, worker_name: str, task_name: str, **kwargs) -> dict:
        """
        Запускает задачу воркера.
        
        Args:
            worker_name: Имя воркера
            task_name: Имя задачи
            **kwargs: Аргументы задачи
        
        Returns:
            Результат выполнения задачи
        """
        worker = await self.get_worker(worker_name)
        if not worker:
            return {'success': False, 'error': f'Воркер {worker_name} не найден'}
        
        try:
            # Проверяем наличие метода
            if not hasattr(worker, task_name):
                return {'success': False, 'error': f'Метод {task_name} не найден у воркера {worker_name}'}
            
            method = getattr(worker, task_name)
            
            # Выполняем метод
            result = await method(**kwargs)
            
            return {
                'success': True,
                'worker': worker_name,
                'task': task_name,
                'result': result
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'worker': worker_name,
                'task': task_name
            }


class WorkerRegistry:
    """
    Реестр воркеров для управления и документирования.
    """
    
    WORKER_DESCRIPTIONS = {
        'reminder': {
            'name': 'Воркер напоминаний',
            'description': 'Проверяет и отправляет напоминания о контрактах, ТО, поставках и пользовательских напоминаниях',
            'schedule': 'Каждую минуту',
            'dependencies': ['reminder_service', 'notification_service'],
            'methods': [
                ('check_reminders', 'Проверяет все предстоящие напоминания'),
                ('run_manual_backup', 'Запускает ручной бэкап'),
                ('get_statistics', 'Получает статистику работы'),
            ]
        },
        'backup': {
            'name': 'Воркер резервного копирования',
            'description': 'Создает резервные копии БД, архивирует файлы и отправляет в Telegram',
            'schedule': 'Каждый день в 2:00',
            'dependencies': ['backup_service', 'notification_service'],
            'methods': [
                ('run_backup', 'Выполняет полный процесс бэкапа'),
                ('run_manual_backup', 'Запускает ручной бэкап'),
                ('restore_backup', 'Восстанавливает данные из бэкапа'),
                ('get_statistics', 'Получает статистику работы'),
            ]
        },
        'cleanup': {
            'name': 'Воркер очистки',
            'description': 'Очищает просроченные FSM сессии, пагинации, временные файлы и кэш',
            'schedule': 'Каждый час',
            'dependencies': ['cleanup_service', 'notification_service'],
            'methods': [
                ('run_cleanup', 'Выполняет полный процесс очистки'),
                ('run_manual_cleanup', 'Запускает ручную очистку указанного типа'),
                ('cleanup_specific_pattern', 'Очищает данные по паттерну'),
                ('cleanup_user_data', 'Очищает все данные пользователя'),
                ('force_cleanup', 'Принудительная очистка всех данных'),
                ('get_statistics', 'Получает статистику работы'),
            ]
        }
    }
    
    @classmethod
    def get_worker_info(cls, worker_name: str) -> dict:
        """
        Получает информацию о воркере.
        
        Args:
            worker_name: Имя воркера
        
        Returns:
            Словарь с информацией о воркере
        """
        return cls.WORKER_DESCRIPTIONS.get(worker_name, {})
    
    @classmethod
    def get_all_workers_info(cls) -> dict:
        """
        Получает информацию обо всех воркерах.
        
        Returns:
            Словарь с информацией о всех воркерах
        """
        return cls.WORKER_DESCRIPTIONS
    
    @classmethod
    def validate_worker_dependencies(cls, available_services: list) -> dict:
        """
        Проверяет доступность зависимостей для воркеров.
        
        Args:
            available_services: Список доступных сервисов
        
        Returns:
            Словарь с результатами проверки
        """
        results = {}
        
        for worker_name, info in cls.WORKER_DESCRIPTIONS.items():
            dependencies = info.get('dependencies', [])
            missing = []
            
            for dep in dependencies:
                if dep not in available_services:
                    missing.append(dep)
            
            results[worker_name] = {
                'has_all_dependencies': len(missing) == 0,
                'missing_dependencies': missing,
                'total_dependencies': len(dependencies),
            }
        
        return results


# Экспортируем фабрику и реестр
__all__.extend([
    "WorkersFactory",
    "WorkerRegistry"
])


import logging
logger = logging.getLogger(__name__)


async def init_workers(context, start_immediately: bool = True):
    """
    Инициализирует всех фоновых воркеров.
    
    Args:
        context: Контекст приложения
        start_immediately: Запускать ли воркеры сразу после инициализации
    
    Returns:
        WorkersFactory объект
    """
    factory = WorkersFactory(context)
    
    # Инициализируем всех воркеров
    await factory.init_all_workers()
    
    # Запускаем воркеры если нужно
    if start_immediately:
        await factory.start_all_workers()
    
    return factory


async def close_workers(factory):
    """
    Закрывает всех фоновых воркеров.
    
    Args:
        factory: WorkersFactory объект
    """
    if factory:
        await factory.stop_all_workers()


# Добавляем функции инициализации и закрытия в экспорт
__all__.extend([
    "init_workers",
    "close_workers"
])


# Утилиты для работы с воркерами
class WorkerUtils:
    """
    Утилиты для работы с воркерами.
    """
    
    @staticmethod
    def get_schedule_for_worker(worker_name: str) -> dict:
        """
        Получает расписание для воркера.
        
        Args:
            worker_name: Имя воркера
        
        Returns:
            Словарь с расписанием
        """
        schedules = {
            'reminder': {
                'interval': 60,  # секунды
                'description': 'Каждую минуту',
                'cron': '* * * * *',  # Каждую минуту
            },
            'backup': {
                'interval': 86400,  # секунды (24 часа)
                'description': 'Каждый день в 2:00',
                'cron': '0 2 * * *',  # 2:00 каждый день
                'start_delay': 300,  # Запустить через 5 минут после старта
            },
            'cleanup': {
                'interval': 3600,  # секунды (1 час)
                'description': 'Каждый час',
                'cron': '0 * * * *',  # Каждый час в :00
            }
        }
        
        return schedules.get(worker_name, {})
    
    @staticmethod
    def format_worker_status(status: dict) -> str:
        """
        Форматирует статус воркера для отображения.
        
        Args:
            status: Статус воркера
        
        Returns:
            Отформатированная строка
        """
        lines = ["⚙️ **Статус фоновых воркеров**\n"]
        
        for worker_name, info in status.items():
            is_running = info.get('is_running', False)
            status_emoji = "🟢" if is_running else "🔴"
            status_text = "работает" if is_running else "остановлен"
            
            lines.append(f"{status_emoji} **{worker_name}**: {status_text}")
            
            # Добавляем статистику если есть
            stats = info.get('statistics', {})
            if stats:
                worker_stats = stats.get('worker', {})
                if worker_stats:
                    if 'backup_count' in worker_stats:
                        lines.append(f"   • Бэкапов: {worker_stats['backup_count']}")
                    if 'cleanup_count' in worker_stats:
                        lines.append(f"   • Очисток: {worker_stats['cleanup_count']}")
                    if 'last_backup_time' in worker_stats and worker_stats['last_backup_time']:
                        lines.append(f"   • Последний: {worker_stats['last_backup_time'][:16]}")
        
        return "\n".join(lines)
    
    @staticmethod
    def validate_worker_config(config: dict) -> tuple:
        """
        Проверяет конфигурацию воркеров.
        
        Args:
            config: Конфигурация
        
        Returns:
            Кортеж (валидно ли, сообщение об ошибке)
        """
        required_settings = [
            'main_admin_id',
            'backup_enabled',
            'reminder_enabled',
            'cleanup_enabled'
        ]
        
        missing = []
        for setting in required_settings:
            if setting not in config:
                missing.append(setting)
        
        if missing:
            return False, f"Отсутствуют настройки воркеров: {', '.join(missing)}"
        
        return True, "Конфигурация воркеров валидна"


# Экспортируем утилиты
__all__.append("WorkerUtils")