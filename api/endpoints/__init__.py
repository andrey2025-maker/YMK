"""
Инициализатор пакета эндпоинтов API.
Регистрирует все роутеры для разных модулей системы.
"""
from fastapi import APIRouter

# Создаем роутеры для каждого модуля
admin_router = APIRouter()
service_router = APIRouter()
installation_router = APIRouter()
cache_router = APIRouter()
users_router = APIRouter()
files_router = APIRouter()

# Импортируем эндпоинты (будет загружено при использовании)
__all__ = [
    'admin_router',
    'service_router',
    'installation_router',
    'cache_router',
    'users_router',
    'files_router',
]


# Функция для динамической загрузки эндпоинтов
def register_all_endpoints():
    """
    Динамически регистрирует все эндпоинты в роутерах.
    Вызывается при инициализации API.
    """
    # Импортируем здесь, чтобы избежать циклических импортов
    from . import admin
    from . import service
    from . import installation
    from . import cache
    from . import users
    from . import files
    
    # Эндпоинты регистрируются при импорте модулей
    # через декораторы @router в каждом модуле