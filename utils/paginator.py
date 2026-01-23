"""
Утилиты пагинации.
Реализует разбивку данных на страницы по 10 элементов.
"""
import math
from typing import List, Tuple, Any, Dict, Optional
from dataclasses import dataclass

from utils.constants import PAGE_SIZE, MAX_PAGES


@dataclass
class PageInfo:
    """
    Информация о странице пагинации.
    """
    page: int
    page_size: int
    total_pages: int
    total_items: int
    has_prev: bool
    has_next: bool
    start_index: int
    end_index: int
    
    @property
    def offset(self) -> int:
        """Смещение для запроса к БД."""
        return (self.page - 1) * self.page_size
    
    @property
    def limit(self) -> int:
        """Лимит для запроса к БД."""
        return self.page_size


def paginate_list(
    items: List[Any],
    page: int = 1,
    page_size: int = PAGE_SIZE
) -> Tuple[List[Any], PageInfo]:
    """
    Разбивает список на страницы.
    
    Args:
        items: Полный список элементов
        page: Номер страницы (начинается с 1)
        page_size: Размер страницы
    
    Returns:
        Кортеж (элементы страницы, информация о странице)
    """
    if not items:
        return [], PageInfo(
            page=1,
            page_size=page_size,
            total_pages=1,
            total_items=0,
            has_prev=False,
            has_next=False,
            start_index=0,
            end_index=0
        )
    
    # Валидация параметров
    page = max(1, page)
    page_size = max(1, min(page_size, 100))  # Ограничиваем размер страницы
    
    total_items = len(items)
    total_pages = max(1, math.ceil(total_items / page_size))
    
    # Корректируем номер страницы если он превышает общее количество
    if page > total_pages:
        page = total_pages
    
    # Вычисляем индексы
    start_index = (page - 1) * page_size
    end_index = min(start_index + page_size, total_items)
    
    # Получаем элементы для текущей страницы
    page_items = items[start_index:end_index]
    
    # Информация о странице
    page_info = PageInfo(
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        total_items=total_items,
        has_prev=page > 1,
        has_next=page < total_pages,
        start_index=start_index,
        end_index=end_index
    )
    
    return page_items, page_info


def calculate_page_info(
    total_items: int,
    page: int = 1,
    page_size: int = PAGE_SIZE
) -> PageInfo:
    """
    Вычисляет информацию о странице без разбивки данных.
    
    Args:
        total_items: Общее количество элементов
        page: Номер страницы
        page_size: Размер страницы
    
    Returns:
        Информация о странице
    """
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    
    total_pages = max(1, math.ceil(total_items / page_size))
    
    # Корректируем номер страницы
    if page > total_pages:
        page = total_pages
    
    start_index = (page - 1) * page_size
    end_index = min(start_index + page_size, total_items)
    
    return PageInfo(
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        total_items=total_items,
        has_prev=page > 1,
        has_next=page < total_pages,
        start_index=start_index,
        end_index=end_index
    )


def create_pagination_buttons(
    page_info: PageInfo,
    callback_prefix: str,
    extra_data: Optional[Dict[str, Any]] = None
) -> Dict[str, str]:
    """
    Создает данные для кнопок пагинации.
    
    Args:
        page_info: Информация о странице
        callback_prefix: Префикс для callback данных
        extra_data: Дополнительные данные для callback
    
    Returns:
        Словарь с данными для кнопок
    """
    buttons = {}
    extra_str = ""
    
    if extra_data:
        # Конвертируем дополнительные данные в строку
        extra_parts = []
        for key, value in extra_data.items():
            if value is not None:
                extra_parts.append(f"{key}:{value}")
        if extra_parts:
            extra_str = ":" + ":".join(extra_parts)
    
    if page_info.has_prev:
        buttons['prev'] = f"{callback_prefix}:page:{page_info.page - 1}{extra_str}"
    
    if page_info.has_next:
        buttons['next'] = f"{callback_prefix}:page:{page_info.page + 1}{extra_str}"
    
    # Кнопка текущей страницы (для информации)
    buttons['current'] = f"{callback_prefix}:page:{page_info.page}{extra_str}"
    
    return buttons


def validate_page_number(
    page_str: str,
    max_pages: int = MAX_PAGES
) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Валидирует номер страницы.
    
    Args:
        page_str: Строка с номером страницы
        max_pages: Максимальное количество страниц
    
    Returns:
        Кортеж (валидно ли, номер страницы, сообщение об ошибке)
    """
    if not page_str:
        return False, None, "Номер страницы не указан"
    
    try:
        page = int(page_str)
    except ValueError:
        return False, None, f"Номер страницы должен быть числом: {page_str}"
    
    if page < 1:
        return False, None, f"Номер страницы должен быть положительным: {page}"
    
    if page > max_pages:
        return False, None, f"Номер страницы не может превышать {max_pages}"
    
    return True, page, None


def split_into_chunks(
    items: List[Any],
    chunk_size: int = PAGE_SIZE,
    max_chunks: int = MAX_PAGES
) -> List[List[Any]]:
    """
    Разбивает список на чанки фиксированного размера.
    
    Args:
        items: Список элементов
        chunk_size: Размер чанка
        max_chunks: Максимальное количество чанков
    
    Returns:
        Список чанков
    """
    if not items:
        return []
    
    # Ограничиваем общее количество элементов
    max_items = chunk_size * max_chunks
    if len(items) > max_items:
        items = items[:max_items]
    
    chunks = []
    for i in range(0, len(items), chunk_size):
        chunks.append(items[i:i + chunk_size])
    
    return chunks


def get_page_from_chunks(
    chunks: List[List[Any]],
    page: int
) -> Tuple[Optional[List[Any]], PageInfo]:
    """
    Получает страницу из предварительно разбитых чанков.
    
    Args:
        chunks: Список чанков
        page: Номер страницы
    
    Returns:
        Кортеж (элементы страницы или None, информация о странице)
    """
    if not chunks:
        return None, PageInfo(
            page=1,
            page_size=PAGE_SIZE,
            total_pages=1,
            total_items=0,
            has_prev=False,
            has_next=False,
            start_index=0,
            end_index=0
        )
    
    # Валидация номера страницы
    total_pages = len(chunks)
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages
    
    # Вычисляем общее количество элементов
    total_items = sum(len(chunk) for chunk in chunks)
    
    # Вычисляем индексы
    start_index = sum(len(chunk) for chunk in chunks[:page-1])
    end_index = start_index + len(chunks[page-1])
    
    page_info = PageInfo(
        page=page,
        page_size=len(chunks[page-1]) if chunks[page-1] else PAGE_SIZE,
        total_pages=total_pages,
        total_items=total_items,
        has_prev=page > 1,
        has_next=page < total_pages,
        start_index=start_index,
        end_index=end_index
    )
    
    return chunks[page-1], page_info


def create_numbered_buttons(
    items: List[Any],
    page: int = 1,
    page_size: int = PAGE_SIZE,
    start_from: int = 1
) -> List[Tuple[int, Any]]:
    """
    Создает нумерованные кнопки для элементов страницы.
    
    Args:
        items: Элементы страницы
        page: Номер страницы
        page_size: Размер страницы
        start_from: Начальный номер (обычно 1)
    
    Returns:
        Список кортежей (номер, элемент)
    """
    if not items:
        return []
    
    page_items, page_info = paginate_list(items, page, page_size)
    
    # Вычисляем глобальные номера
    global_start = page_info.start_index + start_from
    
    numbered_items = []
    for i, item in enumerate(page_items, global_start):
        numbered_items.append((i, item))
    
    return numbered_items