from aiogram.fsm.state import StatesGroup, State


class ServiceRegionStates(StatesGroup):
    """Состояния для работы с регионами обслуживания."""
    
    # Создание региона
    waiting_region_short_name = State()  # Ожидание сокращенного названия
    waiting_region_full_name = State()   # Ожидание полного названия
    region_creation_complete = State()   # Регион создан
    
    # Редактирование региона
    waiting_region_edit_field = State()  # Ожидание выбора поля для редактирования
    waiting_region_edit_value = State()  # Ожидание нового значения
    region_edit_complete = State()       # Редактирование региона завершено


class ServiceObjectStates(StatesGroup):
    """Состояния для работы с объектами обслуживания."""
    
    # Создание объекта
    waiting_object_short_name = State()           # Сокращенное название
    waiting_object_full_name = State()            # Полное название
    waiting_object_address_count = State()        # Количество адресов
    waiting_object_address = State()              # Конкретный адрес (повторяется)
    waiting_object_document_type = State()        # Тип документа
    waiting_object_document_number = State()      # Номер документа
    waiting_object_document_date = State()        # Дата документа
    waiting_object_contract_start = State()       # Дата начала контракта
    waiting_object_contract_end = State()         # Дата окончания контракта
    waiting_object_systems = State()              # Обслуживаемые системы
    waiting_object_zip_purchaser = State()        # Кто покупает ЗИП
    waiting_object_dispatching = State()          # Наличие диспетчеризации
    waiting_object_notes = State()                # Примечания
    object_creation_complete = State()            # Объект создан
    
    # Редактирование объекта
    waiting_object_edit_field = State()           # Ожидание выбора поля
    waiting_object_edit_value = State()           # Ожидание нового значения
    object_edit_complete = State()                # Редактирование завершено


class ServiceProblemStates(StatesGroup):
    """Состояния для работы с проблемами."""
    
    # Добавление проблемы
    waiting_problem_description = State()         # Описание проблемы
    waiting_problem_file = State()                # Файл проблемы (опционально)
    problem_addition_complete = State()           # Проблема добавлена
    
    # Редактирование проблемы
    waiting_problem_selection = State()           # Выбор проблемы
    waiting_problem_edit_field = State()          # Выбор поля для редактирования
    waiting_problem_edit_value = State()          # Новое значение
    problem_edit_complete = State()               # Редактирование завершено
    
    # Решение проблемы
    waiting_problem_solution = State()            # Описание решения
    problem_solution_complete = State()           # Проблема решена


class ServiceMaintenanceStates(StatesGroup):
    """Состояния для работы с ТО."""
    
    # Добавление ТО
    waiting_maintenance_frequency = State()       # Частота обслуживания
    waiting_maintenance_month = State()           # Месяц (если ежемесячно)
    waiting_maintenance_description = State()     # Описание работ
    maintenance_addition_complete = State()       # ТО добавлен
    
    # Отметка о выполнении
    waiting_maintenance_completion = State()      # Подтверждение выполнения
    maintenance_completion_complete = State()     # Выполнение отмечено


class ServiceLetterStates(StatesGroup):
    """Состояния для работы с письмами."""
    
    # Добавление письма
    waiting_letter_number = State()               # Номер письма
    waiting_letter_date = State()                 # Дата письма
    waiting_letter_description = State()          # Описание письма
    waiting_letter_file = State()                 # Файл письма (опционально)
    letter_addition_complete = State()            # Письмо добавлено


class ServiceEquipmentStates(StatesGroup):
    """Состояния для работы с оборудованием."""
    
    # Добавление оборудования
    waiting_equipment_name = State()              # Наименование
    waiting_equipment_quantity = State()          # Количество
    waiting_equipment_unit = State()              # Единица измерения
    waiting_equipment_description = State()       # Описание (опционально)
    waiting_equipment_continue = State()          # Продолжить добавление?
    equipment_addition_complete = State()         # Добавление завершено
    
    # Редактирование оборудования
    waiting_equipment_selection = State()         # Выбор оборудования
    waiting_equipment_edit_field = State()        # Выбор поля
    waiting_equipment_edit_value = State()        # Новое значение
    equipment_edit_complete = State()             # Редактирование завершено


class ServiceAdditionalDocumentStates(StatesGroup):
    """Состояния для работы с дополнительными соглашениями."""
    
    # Добавление документа
    waiting_document_type = State()               # Тип документа
    waiting_document_number = State()             # Номер документа
    waiting_document_date = State()               # Дата документа
    waiting_document_start_date = State()         # Дата начала (опционально)
    waiting_document_end_date = State()           # Дата окончания (опционально)
    waiting_document_description = State()        # Описание
    document_addition_complete = State()          # Документ добавлен


class ServiceReminderStates(StatesGroup):
    """Состояния для работы с напоминаниями."""
    
    # Создание напоминания через команду !напомнить
    waiting_reminder_object = State()             # Выбор объекта
    waiting_reminder_date = State()               # Дата напоминания
    waiting_reminder_message = State()            # Текст напоминания
    waiting_reminder_notify_day_before = State()  # Уведомлять за день?
    waiting_reminder_notify_on_day = State()      # Уведомлять в день?
    reminder_creation_complete = State()          # Напоминание создано
    
    # Создание напоминания из раздела объекта
    waiting_reminder_description = State()        # Описание напоминания
    reminder_addition_complete = State()          # Напоминание добавлено


class ServiceSearchStates(StatesGroup):
    """Состояния для поиска в обслуживании."""
    
    waiting_search_region = State()               # Выбор региона для поиска
    waiting_search_object = State()               # Выбор объекта для поиска
    waiting_search_query = State()                # Поисковый запрос
    search_results_display = State()              # Отображение результатов
    waiting_result_action = State()               # Действие с результатом


class ServiceExportStates(StatesGroup):
    """Состояния для экспорта данных обслуживания."""
    
    waiting_export_type = State()                 # Тип экспорта
    waiting_export_object = State()               # Объект для экспорта
    waiting_export_format = State()               # Формат экспорта
    export_in_progress = State()                  # Экспорт выполняется
    export_complete = State()                     # Экспорт завершен