from aiogram.fsm.state import StatesGroup, State


class BaseStates(StatesGroup):
    """Базовые состояния FSM."""
    
    # Состояния подтверждения
    waiting_confirmation = State()  # Ожидание подтверждения действия
    confirmation_received = State()  # Подтверждение получено
    
    # Состояния ввода текста
    waiting_text_input = State()  # Ожидание ввода текста
    text_input_received = State()  # Текст получен
    
    # Состояния ввода чисел
    waiting_number_input = State()  # Ожидание ввода числа
    number_input_received = State()  # Число получено
    
    # Состояния ввода дат
    waiting_date_input = State()  # Ожидание ввода даты
    date_input_received = State()  # Дата получена
    
    # Состояния выбора из списка
    waiting_selection = State()  # Ожидание выбора из списка
    selection_received = State()  # Выбор получен
    
    # Состояния загрузки файлов
    waiting_file_upload = State()  # Ожидание загрузки файла
    file_upload_received = State()  # Файл получен
    
    # Состояния отмены
    waiting_cancellation = State()  # Ожидание подтверждения отмены
    cancellation_received = State()  # Отмена подтверждена


class DeleteStates(StatesGroup):
    """Состояния для удаления."""
    
    waiting_delete_confirmation = State()  # Ожидание подтверждения удаления
    waiting_item_selection = State()  # Ожидание выбора элемента для удаления
    delete_completed = State()  # Удаление завершено


class EditStates(StatesGroup):
    """Состояния для редактирования."""
    
    waiting_edit_field = State()  # Ожидание выбора поля для редактирования
    waiting_edit_value = State()  # Ожидание нового значения
    edit_completed = State()  # Редактирование завершено


class SearchStates(StatesGroup):
    """Состояния для поиска."""
    
    waiting_search_query = State()  # Ожидание поискового запроса
    search_results = State()  # Результаты поиска
    waiting_result_selection = State()  # Ожидание выбора результата


class NavigationStates(StatesGroup):
    """Состояния для навигации."""
    
    waiting_back_action = State()  # Ожидание действия "Назад"
    waiting_next_page = State()  # Ожидание следующей страницы
    waiting_previous_page = State()  # Ожидание предыдущей страницы


class TimeoutStates(StatesGroup):
    """Состояния для обработки таймаута."""
    
    timeout_warning = State()  # Предупреждение о таймауте
    timeout_expired = State()  # Таймаут истек