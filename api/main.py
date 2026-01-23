"""
Основной файл FastAPI приложения.
Реализует REST API для управления ботом через веб-интерфейс.
"""
import logging
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi

from core.context import AppContext
from .dependencies import (
    get_db_session, 
    get_cache_manager,
    get_current_admin,
    verify_api_key
)
from .endpoints import (
    admin_router,
    service_router,
    installation_router,
    cache_router,
    users_router,
    files_router
)

# Настройка логирования
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Управление жизненным циклом приложения.
    
    Args:
        app: Приложение FastAPI
    """
    # Инициализация при запуске
    logger.info("Starting YMK Bot API...")
    
    # Получаем контекст приложения
    context: Optional[AppContext] = app.extra.get("app_context")
    
    if context:
        # Проверяем соединения
        await context.db_session().execute("SELECT 1")
        await context.cache_manager.ping()
        logger.info("Database and cache connections verified")
    
    yield
    
    # Завершение работы
    logger.info("Shutting down YMK Bot API...")
    if context:
        await context.close()


# Создаем приложение FastAPI
app = FastAPI(
    title="YMK Bot API",
    description="REST API для бота электрики YMK. Предоставляет доступ к данным обслуживания, монтажа, управлению админами и кэшем.",
    version="1.0.0",
    docs_url=None,  # Отключаем стандартную документацию
    redoc_url=None,
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
    dependencies=[Depends(verify_api_key)]  # Все запросы требуют API ключ
)

# Настраиваем CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В production заменить на конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Добавляем сжатие GZIP
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Регистрируем роутеры
app.include_router(admin_router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(service_router, prefix="/api/v1/service", tags=["Service"])
app.include_router(installation_router, prefix="/api/v1/installation", tags=["Installation"])
app.include_router(cache_router, prefix="/api/v1/cache", tags=["Cache"])
app.include_router(users_router, prefix="/api/v1/users", tags=["Users"])
app.include_router(files_router, prefix="/api/v1/files", tags=["Files"])


def custom_openapi() -> Dict[str, Any]:
    """
    Генерирует кастомную OpenAPI схему.
    
    Returns:
        OpenAPI схема
    """
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Добавляем информацию об аутентификации
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API ключ для доступа к API. Должен быть сгенерирован главным админом через бота."
        }
    }
    
    # Применяем security ко всем операциям
    for path in openapi_schema["paths"].values():
        for method in path.values():
            method.setdefault("security", [{"ApiKeyAuth": []}])
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.get("/", include_in_schema=False)
async def root() -> Dict[str, Any]:
    """
    Корневой эндпоинт API.
    
    Returns:
        Информация о API
    """
    return {
        "name": "YMK Bot API",
        "version": "1.0.0",
        "status": "operational",
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc",
            "openapi": "/api/v1/openapi.json"
        },
        "endpoints": {
            "admin": "/api/v1/admin/",
            "service": "/api/v1/service/",
            "installation": "/api/v1/installation/",
            "cache": "/api/v1/cache/",
            "users": "/api/v1/users/",
            "files": "/api/v1/files/",
        }
    }


@app.get("/health", tags=["Health"])
async def health_check(
    db=Depends(get_db_session),
    cache=Depends(get_cache_manager)
) -> Dict[str, Any]:
    """
    Проверка здоровья сервиса.
    
    Returns:
        Статус здоровья всех компонентов
    """
    health_status = {
        "status": "healthy",
        "components": {},
        "timestamp": None
    }
    
    try:
        import datetime
        
        # Проверяем БД
        try:
            await db.execute("SELECT 1")
            health_status["components"]["database"] = "healthy"
        except Exception as e:
            health_status["components"]["database"] = f"unhealthy: {str(e)}"
            health_status["status"] = "unhealthy"
        
        # Проверяем кэш
        try:
            await cache.ping()
            health_status["components"]["cache"] = "healthy"
        except Exception as e:
            health_status["components"]["cache"] = f"unhealthy: {str(e)}"
            health_status["status"] = "unhealthy"
        
        health_status["timestamp"] = datetime.datetime.now().isoformat()
        
        return health_status
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check failed: {str(e)}"
        )


@app.get("/docs", include_in_schema=False)
async def get_documentation():
    """
    Кастомная страница документации Swagger.
    """
    return get_swagger_ui_html(
        openapi_url="/api/v1/openapi.json",
        title="YMK Bot API - Swagger UI",
        swagger_js_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css",
    )


@app.get("/redoc", include_in_schema=False)
async def get_redoc_documentation():
    """
    Кастомная страница документации ReDoc.
    """
    return get_redoc_html(
        openapi_url="/api/v1/openapi.json",
        title="YMK Bot API - ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Глобальный обработчик исключений.
    
    Args:
        request: Запрос
        exc: Исключение
        
    Returns:
        JSON ответ с ошибкой
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "message": str(exc),
            "request_id": request.headers.get("X-Request-ID", "unknown")
        }
    )


def set_app_context(context: AppContext):
    """
    Устанавливает контекст приложения в app.extra.
    
    Args:
        context: Контекст приложения
    """
    app.extra["app_context"] = context


# Экспорт для использования в других модулях
__all__ = ["app", "set_app_context"]