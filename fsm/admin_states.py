"""
Состояния FSM для админских сценариев.
Реализует состояния для добавления администраторов, управления разрешениями и настроек.
"""

from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    """Состояния для админских операций."""
    
    # ========== Состояния добавления админов ==========
    
    class AddMainAdmin(StatesGroup):
        """Добавление главного администратора."""
        waiting_for_user_identifier = State()  # Ожидание ID/ссылки/username пользователя
        waiting_for_confirmation = State()     # Ожидание подтверждения
    
    class AddAdmin(StatesGroup):
        """Добавление администратора."""
        waiting_for_user_identifier = State()  # Ожидание ID/ссылки/username пользователя
        waiting_for_confirmation = State()     # Ожидание подтверждения
    
    class AddServiceAdmin(StatesGroup):
        """Добавление администратора обслуживания."""
        waiting_for_user_identifier = State()  # Ожидание ID/ссылки/username пользователя
        waiting_for_confirmation = State()     # Ожидание подтверждения
    
    class AddInstallationAdmin(StatesGroup):
        """Добавление администратора монтажа."""
        waiting_for_user_identifier = State()  # Ожидание ID/ссылки/username пользователя
        waiting_for_confirmation = State()     # Ожидание подтверждения
    
    # ========== Состояния управления разрешениями ==========
    
    class PermissionsManagement(StatesGroup):
        """Управление разрешениями команд."""
        waiting_for_admin_level_selection = State()  # Ожидание выбора уровня админа
        waiting_for_command_selection = State()      # Ожидание выбора команды
        waiting_for_permission_toggle = State()      # Ожидание включения/выключения команды
        waiting_for_group_permission_selection = State()  # Ожидание выбора групповых команд
    
    # ========== Состояния настроек сохранения ==========
    
    class StorageSettings(StatesGroup):
        """Настройки сохранения изменений."""
        waiting_for_group_link = State()        # Ожидание ссылки на группу для сохранения
        waiting_for_confirmation = State()      # Ожидание подтверждения
    
    class FileSettings(StatesGroup):
        """Настройки архивов файлов."""
        waiting_for_file_type_selection = State()   # Ожидание выбора типа файлов
        waiting_for_topic_link = State()            # Ожидание ссылки на тему
        waiting_for_confirmation = State()          # Ожидание подтверждения
    
    # ========== Состояния управления кэшем ==========
    
    class CacheManagement(StatesGroup):
        """Управление кэшем."""
        waiting_for_confirmation = State()      # Ожидание подтверждения очистки кэша
    
    # ========== Состояния экспорта данных ==========
    
    class ExportData(StatesGroup):
        """Экспорт данных в Excel."""
        waiting_for_export_type_selection = State()  # Ожидание выбора типа экспорта
        waiting_for_object_selection = State()       # Ожидание выбора объекта
        waiting_for_confirmation = State()           # Ожидание подтверждения
    
    # ========== Состояния управления пользователями ==========
    
    class UserManagement(StatesGroup):
        """Управление доступом пользователей к объектам."""
        waiting_for_user_identifier = State()   # Ожидание ID пользователя
        waiting_for_object_type_selection = State()  # Ожидание выбора типа объекта
        waiting_for_object_selection = State()       # Ожидание выбора объекта
        waiting_for_permission_level = State()       # Ожидание уровня доступа
        waiting_for_confirmation = State()           # Ожидание подтверждения
    
    # ========== Состояния системных настроек ==========
    
    class SystemSettings(StatesGroup):
        """Системные настройки."""
        waiting_for_setting_selection = State()  # Ожидание выбора настройки
        waiting_for_value_input = State()        # Ожидание ввода значения
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    # ========== Состояния бэкапа и восстановления ==========
    
    class BackupRestore(StatesGroup):
        """Резервное копирование и восстановление."""
        waiting_for_action_selection = State()   # Ожидание выбора действия
        waiting_for_backup_type = State()        # Ожидание типа бэкапа
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    # ========== Состояния просмотра логов ==========
    
    class ViewLogs(StatesGroup):
        """Просмотр логов системы."""
        waiting_for_log_type_selection = State()  # Ожидание выбора типа логов
        waiting_for_date_range_selection = State()  # Ожидание выбора диапазона дат
        waiting_for_confirmation = State()        # Ожидание подтверждения
    
    # ========== Общие состояния админки ==========
    
    # Состояние для выбора действия в админ-панели
    waiting_for_admin_action = State()
    
    # Состояние для подтверждения опасных действий
    waiting_for_dangerous_action_confirmation = State()
    
    # Состояние для ввода произвольного текста (комментария, описания)
    waiting_for_admin_text_input = State()
    
    # Состояние для выбора из списка
    waiting_for_admin_selection = State()