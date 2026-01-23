"""
API модуль для веб-панели управления ботом.
Предоставляет REST API для интеграции с внешними системами
и веб-интерфейсом.
"""
from typing import Dict, Any

from .main import app
from .dependencies import get_db, get_cache, get_current_user

__all__ = [
    'app',
    'get_db',
    'get_cache',
    'get_current_user',
]

__version__ = "1.0.0"


def get_api_info() -> Dict[str, Any]:
    """
    Возвращает информацию о API.
    
    Returns:
        Словарь с информацией об API
    """
    return {
        "name": "YMK Bot API",
        "version": __version__,
        "description": "REST API для бота электрики YMK",
        "endpoints": {
            "admin": "/api/v1/admin/",
            "service": "/api/v1/service/",
            "installation": "/api/v1/installation/",
            "cache": "/api/v1/cache/",
            "users": "/api/v1/users/",
            "files": "/api/v1/files/",
        }
    }