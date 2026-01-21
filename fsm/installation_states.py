from aiogram.fsm.state import StatesGroup, State


class InstallationObjectStates(StatesGroup):
    """Состояния для работы с объектами монтажа."""
    
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
    waiting_object_systems = State()              # Монтируемые системы
    waiting_object_notes = State()                # Примечания
    waiting_object_documents_count = State()      # Количество доп. соглашений
    installation_object_creation_complete = State() # Объект создан
    
    # Дополнительные соглашения
    waiting_document_type = State()               # Тип документа
    waiting_document_number = State()             # Номер документа
    waiting_document_date = State()               # Дата документа
    waiting_document_start_date = State()         # Дата начала (опционально)
    waiting_document_end_date = State()           # Дата окончания (опционально)
    waiting_document_description = State()        # Описание
    waiting_document_continue = State()           # Продолжить добавление?
    document_addition_complete = State()          # Добавление документов завершено


class InstallationProjectStates(StatesGroup):
    """Состояния для работы с проектами монтажа."""
    
    # Добавление проекта
    waiting_project_count = State()               # Количество проектов
    waiting_project_name = State()                # Название проекта
    waiting_project_file = State()                # Файл проекта
    waiting_project_continue = State()            # Продолжить добавление?
    project_addition_complete = State()           # Проекты добавлены
    
    # Редактирование проекта
    waiting_project_selection = State()           # Выбор проекта
    waiting_project_edit_field = State()          # Выбор поля для редактирования
    waiting_project_edit_value = State()          # Новое значение
    project_edit_complete = State()               # Редактирование завершено


class InstallationMaterialStates(StatesGroup):
    """Состояния для работы с материалами монтажа."""
    
    # Добавление материала
    waiting_material_name = State()               # Наименование материала
    waiting_material_quantity = State()           # Количество
    waiting_material_unit = State()               # Единица измерения
    waiting_material_description = State()        # Описание (опционально)
    waiting_material_continue = State()           # Продолжить добавление?
    material_addition_complete = State()          # Добавление завершено
    
    # Распределение по разделам
    waiting_section_name = State()                # Название раздела
    waiting_section_materials = State()           # Выбор материалов для раздела
    waiting_section_quantities = State()          # Количества материалов в разделе
    waiting_section_continue = State()            # Продолжить создание разделов?
    section_creation_complete = State()           # Разделы созданы
    
    # Редактирование материалов в разделе
    waiting_section_selection = State()           # Выбор раздела
    waiting_material_selection = State()          # Выбор материала в разделе
    waiting_material_quantity_update = State()    # Новое количество
    material_update_complete = State()            # Обновление завершено


class InstallationMontageStates(StatesGroup):
    """Состояния для учета монтажа."""
    
    # Выбор раздела для монтажа
    waiting_section_selection = State()           # Выбор раздела
    waiting_material_montage = State()            # Монтаж материала
    
    # Ввод количества смонтированного
    waiting_montage_quantity = State()            # Количество смонтировано
    waiting_montage_notes = State()               # Примечания к монтажу
    waiting_montage_continue = State()            # Продолжить монтаж?
    montage_recording_complete = State()          # Учет монтажа завершен


class InstallationSupplyStates(StatesGroup):
    """Состояния для работы с поставками."""
    
    # Добавление поставки
    waiting_supply_service = State()              # Сервис доставки
    waiting_supply_date = State()                 # Дата доставки
    waiting_supply_document = State()             # Номер документа (опционально)
    waiting_supply_document_date = State()        # Дата документа (опционально)
    waiting_supply_description = State()          # Описание поставки
    waiting_supply_materials = State()            # Материалы в поставке
    waiting_supply_quantities = State()           # Количества материалов
    supply_addition_complete = State()            # Поставка добавлена


class InstallationChangeStates(StatesGroup):
    """Состояния для работы с изменениями."""
    
    # Добавление изменения
    waiting_change_description = State()          # Описание изменения
    waiting_change_file = State()                 # Файл изменения (опционально)
    change_addition_complete = State()            # Изменение добавлено


class InstallationSearchStates(StatesGroup):
    """Состояния для поиска в монтаже."""
    
    waiting_search_object = State()               # Выбор объекта для поиска
    waiting_search_type = State()                 # Тип поиска (материалы, проекты и т.д.)
    waiting_search_query = State()                # Поисковый запрос
    search_results_display = State()              # Отображение результатов
    waiting_result_action = State()               # Действие с результатом


class InstallationExportStates(StatesGroup):
    """Состояния для экспорта данных монтажа."""
    
    waiting_export_type = State()                 # Тип экспорта
    waiting_export_object = State()               # Объект для экспорта
    waiting_export_section = State()              # Раздел для экспорта (опционально)
    waiting_export_format = State()               # Формат экспорта
    export_in_progress = State()                  # Экспорт выполняется
    export_complete = State()                     # Экспорт завершен