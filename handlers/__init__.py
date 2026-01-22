from .group_handlers import router as group_router
from .file_handlers import router as file_router
from .search_handlers import router as search_router
from .user_handlers import router as user_router
from .reminder_handlers import router as reminder_router

__all__ = [
    'group_router',
    'file_router', 
    'search_router',
    'user_router',
    'reminder_router'
]