"""
Состояния FSM для работы с файлами.
Реализует состояния для загрузки, скачивания и управления файлами.
"""

from aiogram.fsm.state import State, StatesGroup


class FileStates(StatesGroup):
    """Состояния для работы с файлами."""
    
    # ========== Состояния загрузки файлов ==========
    
    class UploadFile(StatesGroup):
        """Загрузка файла."""
        waiting_for_file_type = State()          # Ожидание выбора типа файла
        waiting_for_file = State()               # Ожидание файла
        waiting_for_description = State()        # Ожидание описания файла
        waiting_for_metadata = State()           # Ожидание метаданных
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    class UploadToArchive(StatesGroup):
        """Загрузка файла в архив."""
        waiting_for_category_selection = State()  # Ожидание выбора категории
        waiting_for_file = State()               # Ожидание файла
        waiting_for_description = State()        # Ожидание описания
        waiting_for_tags = State()               # Ожидание тегов
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    class BatchUpload(StatesGroup):
        """Пакетная загрузка файлов."""
        waiting_for_files_count = State()        # Ожидание количества файлов
        waiting_for_file = State()               # Ожидание файла (повторяется)
        waiting_for_file_description = State()   # Ожидание описания файла
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    # ========== Состояния настройки архивов ==========
    
    class SetupArchive(StatesGroup):
        """Настройка архивов файлов."""
        waiting_for_archive_type = State()       # Ожидание выбора типа архива
        waiting_for_chat_link = State()          # Ожидание ссылки на чат/канал
        waiting_for_topic_id = State()           # Ожидание ID темы
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    class ConfigureFileCategories(StatesGroup):
        """Конфигурация категорий файлов."""
        waiting_for_category_selection = State()  # Ожидание выбора категории
        waiting_for_settings_input = State()     # Ожидание ввода настроек
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    # ========== Состояния управления файлами ==========
    
    class ManageFiles(StatesGroup):
        """Управление файлами."""
        waiting_for_action_selection = State()   # Ожидание выбора действия
        waiting_for_file_selection = State()     # Ожидание выбора файла
        waiting_for_new_description = State()    # Ожидание нового описания
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    class DeleteFile(StatesGroup):
        """Удаление файла."""
        waiting_for_file_selection = State()     # Ожидание выбора файла
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    class MoveFile(StatesGroup):
        """Перемещение файла между категориями."""
        waiting_for_file_selection = State()     # Ожидание выбора файла
        waiting_for_new_category = State()       # Ожидание выбора новой категории
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    class RenameFile(StatesGroup):
        """Переименование файла."""
        waiting_for_file_selection = State()     # Ожидание выбора файла
        waiting_for_new_name = State()           # Ожидание нового имени
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    # ========== Состояния скачивания файлов ==========
    
    class DownloadFile(StatesGroup):
        """Скачивание файла."""
        waiting_for_file_selection = State()     # Ожидание выбора файла
        waiting_for_format_selection = State()   # Ожидание выбора формата
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    class BatchDownload(StatesGroup):
        """Пакетное скачивание файлов."""
        waiting_for_files_selection = State()    # Ожидание выбора файлов
        waiting_for_archive_format = State()     # Ожидание выбора формата архива
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    # ========== Состояния поиска файлов ==========
    
    class SearchFiles(StatesGroup):
        """Поиск файлов."""
        waiting_for_search_query = State()       # Ожидание поискового запроса
        waiting_for_filters_selection = State()  # Ожидание выбора фильтров
        waiting_for_result_selection = State()   # Ожидание выбора результата
    
    # ========== Состояния работы с тегами ==========
    
    class ManageTags(StatesGroup):
        """Управление тегами файлов."""
        waiting_for_action_selection = State()   # Ожидание выбора действия
        waiting_for_tag_input = State()          # Ожидание ввода тега
        waiting_for_file_selection = State()     # Ожидание выбора файла
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    # ========== Состояния статистики файлов ==========
    
    class FileStatistics(StatesGroup):
        """Статистика файлов."""
        waiting_for_stat_type_selection = State()  # Ожидание выбора типа статистики
        waiting_for_date_range = State()          # Ожидание диапазона дат
        waiting_for_confirmation = State()        # Ожидание подтверждения
    
    # ========== Состояния очистки файлов ==========
    
    class CleanupFiles(StatesGroup):
        """Очистка старых файлов."""
        waiting_for_cleanup_type = State()       # Ожидание типа очистки
        waiting_for_age_threshold = State()      # Ожидание порога возраста
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    # ========== Общие состояния работы с файлами ==========
    
    # Состояние ожидания файла любого типа
    waiting_for_any_file = State()
    
    # Состояние ожидания документа (PDF, Word, Excel и т.д.)
    waiting_for_document = State()
    
    # Состояние ожидания изображения
    waiting_for_photo = State()
    
    # Состояние ожидания нескольких файлов
    waiting_for_multiple_files = State()
    
    # Состояние для обработки загруженного файла
    processing_file = State()
    
    # Состояние для подтверждения операции с файлом
    waiting_for_file_action_confirmation = State()