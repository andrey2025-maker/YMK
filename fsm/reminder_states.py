"""
Состояния FSM для работы с напоминаниями.
Реализует состояния для создания, редактирования и управления напоминаниями.
"""

from aiogram.fsm.state import State, StatesGroup


class ReminderStates(StatesGroup):
    """Состояния для работы с напоминаниями."""
    
    # ========== Состояния создания напоминаний ==========
    
    class CreateReminder(StatesGroup):
        """Создание напоминания."""
        waiting_for_reminder_type = State()      # Ожидание выбора типа напоминания
        waiting_for_object_selection = State()   # Ожидание выбора объекта
        waiting_for_title = State()              # Ожидание заголовка
        waiting_for_description = State()        # Ожидание описания
        waiting_for_date = State()               # Ожидание даты
        waiting_for_time = State()               # Ожидание времени
        waiting_for_repeat_type = State()        # Ожидание типа повторения
        waiting_for_notification_settings = State()  # Ожидание настроек уведомлений
        waiting_for_priority = State()           # Ожидание приоритета
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    class CreateContractReminder(StatesGroup):
        """Создание напоминания о контракте."""
        waiting_for_object_selection = State()   # Ожидание выбора объекта
        waiting_for_reminder_days = State()      # Ожидание количества дней до события
        waiting_for_notification_type = State()  # Ожидание типа уведомления
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    class CreateTOReminder(StatesGroup):
        """Создание напоминания о ТО (техническом обслуживании)."""
        waiting_for_object_selection = State()   # Ожидание выбора объекта
        waiting_for_maintenance_selection = State()  # Ожидание выбора ТО
        waiting_for_reminder_days = State()      # Ожидание количества дней
        waiting_for_notification_type = State()  # Ожидание типа уведомления
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    class CreateSupplyReminder(StatesGroup):
        """Создание напоминания о поставке."""
        waiting_for_object_selection = State()   # Ожидание выбора объекта
        waiting_for_supply_selection = State()   # Ожидание выбора поставки
        waiting_for_reminder_days = State()      # Ожидание количества дней
        waiting_for_notification_type = State()  # Ожидание типа уведомления
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    # ========== Состояния редактирования напоминаний ==========
    
    class EditReminder(StatesGroup):
        """Редактирование напоминания."""
        waiting_for_reminder_selection = State()  # Ожидание выбора напоминания
        waiting_for_field_selection = State()    # Ожидание выбора поля для редактирования
        waiting_for_new_value = State()          # Ожидание нового значения
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    class EditReminderDate(StatesGroup):
        """Редактирование даты напоминания."""
        waiting_for_reminder_selection = State()  # Ожидание выбора напоминания
        waiting_for_new_date = State()           # Ожидание новой даты
        waiting_for_new_time = State()           # Ожидание нового времени
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    class EditReminderRepeat(StatesGroup):
        """Редактирование повторения напоминания."""
        waiting_for_reminder_selection = State()  # Ожидание выбора напоминания
        waiting_for_repeat_type = State()        # Ожидание типа повторения
        waiting_for_repeat_interval = State()    # Ожидание интервала повторения
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    # ========== Состояния управления напоминаниями ==========
    
    class ManageReminders(StatesGroup):
        """Управление напоминаниями."""
        waiting_for_action_selection = State()   # Ожидание выбора действия
        waiting_for_reminder_selection = State()  # Ожидание выбора напоминания
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    class DeleteReminder(StatesGroup):
        """Удаление напоминания."""
        waiting_for_reminder_selection = State()  # Ожидание выбора напоминания
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    class CompleteReminder(StatesGroup):
        """Отметка напоминания как выполненного."""
        waiting_for_reminder_selection = State()  # Ожидание выбора напоминания
        waiting_for_completion_notes = State()   # Ожидание заметок о выполнении
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    class SnoozeReminder(StatesGroup):
        """Откладывание напоминания."""
        waiting_for_reminder_selection = State()  # Ожидание выбора напоминания
        waiting_for_snooze_time = State()        # Ожидание времени откладывания
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    # ========== Состояния просмотра напоминаний ==========
    
    class ViewReminders(StatesGroup):
        """Просмотр напоминаний."""
        waiting_for_view_type = State()          # Ожидание типа просмотра
        waiting_for_date_range = State()         # Ожидание диапазона дат
        waiting_for_filter_selection = State()   # Ожидание выбора фильтров
        waiting_for_reminder_details = State()   # Ожидание деталей напоминания
    
    class ViewUpcomingReminders(StatesGroup):
        """Просмотр предстоящих напоминаний."""
        waiting_for_days_ahead = State()         # Ожидание количества дней вперед
        waiting_for_priority_filter = State()    # Ожидание фильтра по приоритету
        waiting_for_reminder_details = State()   # Ожидание деталей напоминания
    
    class ViewOverdueReminders(StatesGroup):
        """Просмотр просроченных напоминаний."""
        waiting_for_days_overdue = State()       # Ожидание количества дней просрочки
        waiting_for_action_selection = State()   # Ожидание выбора действия
        waiting_for_reminder_details = State()   # Ожидание деталей напоминания
    
    # ========== Состояния настроек уведомлений ==========
    
    class NotificationSettings(StatesGroup):
        """Настройки уведомлений."""
        waiting_for_setting_type = State()       # Ожидание выбора типа настройки
        waiting_for_value_input = State()        # Ожидание ввода значения
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    class SetNotificationTime(StatesGroup):
        """Установка времени уведомлений."""
        waiting_for_notification_type = State()  # Ожидание типа уведомления
        waiting_for_time = State()               # Ожидание времени
        waiting_for_days_before = State()        # Ожидание количества дней до
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    class ConfigureReminderTemplates(StatesGroup):
        """Конфигурация шаблонов напоминаний."""
        waiting_for_template_type = State()      # Ожидание типа шаблона
        waiting_for_template_content = State()   # Ожидание содержания шаблона
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    # ========== Состояния повторяющихся напоминаний ==========
    
    class ManageRecurringReminders(StatesGroup):
        """Управление повторяющимися напоминаниями."""
        waiting_for_action_selection = State()   # Ожидание выбора действия
        waiting_for_recurring_reminder_selection = State()  # Ожидание выбора напоминания
        waiting_for_schedule_settings = State()  # Ожидание настроек расписания
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    class CreateRecurringReminder(StatesGroup):
        """Создание повторяющегося напоминания."""
        waiting_for_object_selection = State()   # Ожидание выбора объекта
        waiting_for_title = State()              # Ожидание заголовка
        waiting_for_schedule_type = State()      # Ожидание типа расписания
        waiting_for_schedule_details = State()   # Ожидание деталей расписания
        waiting_for_start_date = State()         # Ожидание даты начала
        waiting_for_end_date = State()           # Ожидание даты окончания
        waiting_for_notification_settings = State()  # Ожидание настроек уведомлений
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    # ========== Состояния массовых операций с напоминаниями ==========
    
    class BatchReminderOperations(StatesGroup):
        """Массовые операции с напоминаниями."""
        waiting_for_operation_type = State()     # Ожидание типа операции
        waiting_for_reminders_selection = State()  # Ожидание выбора напоминаний
        waiting_for_parameters = State()         # Ожидание параметров операции
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    class ExportReminders(StatesGroup):
        """Экспорт напоминаний."""
        waiting_for_export_format = State()      # Ожидание формата экспорта
        waiting_for_date_range = State()         # Ожидание диапазона дат
        waiting_for_fields_selection = State()   # Ожидание выбора полей
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    # ========== Состояния интеграции с календарем ==========
    
    class CalendarIntegration(StatesGroup):
        """Интеграция с календарем."""
        waiting_for_calendar_type = State()      # Ожидание типа календаря
        waiting_for_credentials = State()        # Ожидание учетных данных
        waiting_for_sync_settings = State()      # Ожидание настроек синхронизации
        waiting_for_confirmation = State()       # Ожидание подтверждения
    
    # ========== Общие состояния напоминаний ==========
    
    # Состояние ожидания даты в формате ДД.ММ.ГГГГ
    waiting_for_date_input = State()
    
    # Состояние ожидания времени в формате ЧЧ:ММ
    waiting_for_time_input = State()
    
    # Состояние ожидания даты и времени
    waiting_for_datetime_input = State()
    
    # Состояние для выбора приоритета (низкий, средний, высокий, срочный)
    waiting_for_priority_selection = State()
    
    # Состояние для выбора типа повторения (ежедневно, еженедельно, ежемесячно, ежегодно)
    waiting_for_repeat_selection = State()
    
    # Состояние для подтверждения создания/изменения напоминания
    waiting_for_reminder_confirmation = State()
    
    # Состояние для ввода заметок к напоминанию
    waiting_for_reminder_notes = State()