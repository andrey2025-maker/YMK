"""
Сервис для глобального поиска по всем данным системы.
Реализует поиск с пагинацией, фильтрацией и подсветкой результатов согласно ТЗ.
"""

import re
import logging
from typing import Dict, List, Optional, Any, Tuple, Set
from datetime import datetime
from enum import Enum

from storage.database import async_session_maker
from storage.models.service import ServiceObject, ServiceRegion, ServiceProblem, ServiceMaintenance
from storage.models.installation import InstallationObject, InstallationProject, InstallationMaterial
from storage.models.user import User, Admin
from storage.repositories.service_repository import ServiceRepository
from storage.repositories.installation_repository import InstallationRepository
from storage.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


class SearchResultType(str, Enum):
    """Типы результатов поиска."""
    SERVICE_OBJECT = "объект обслуживания"
    SERVICE_REGION = "регион обслуживания"
    SERVICE_PROBLEM = "проблема обслуживания"
    SERVICE_MAINTENANCE = "ТО обслуживания"
    INSTALLATION_OBJECT = "объект монтажа"
    INSTALLATION_PROJECT = "проект монтажа"
    INSTALLATION_MATERIAL = "материал монтажа"
    USER = "пользователь"
    ADMIN = "администратор"


class SearchResult:
    """Результат поиска."""
    
    def __init__(
        self,
        id: str,
        type: SearchResultType,
        title: str,
        description: str,
        relevance: float,
        entity_data: Optional[Dict[str, Any]] = None
    ):
        self.id = id
        self.type = type
        self.title = title
        self.description = description
        self.relevance = relevance
        self.entity_data = entity_data or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь."""
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "description": self.description,
            "relevance": self.relevance,
            "entity_data": self.entity_data
        }


class SearchService:
    """Сервис для поиска по данным системы."""
    
    def __init__(
        self,
        service_repo: ServiceRepository,
        installation_repo: InstallationRepository,
        user_repo: UserRepository
    ):
        self.service_repo = service_repo
        self.installation_repo = installation_repo
        self.user_repo = user_repo
        
    async def global_search(
        self,
        query: str,
        user_id: Optional[int] = None,
        search_types: Optional[List[SearchResultType]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[SearchResult], int]:
        """
        Глобальный поиск по всем данным.
        
        Args:
            query: Поисковый запрос
            user_id: ID пользователя (для фильтрации доступных данных)
            search_types: Типы данных для поиска
            limit: Максимальное количество результатов
            offset: Смещение для пагинации
            
        Returns:
            Кортеж (список результатов, общее количество)
        """
        try:
            if not query or len(query.strip()) < 2:
                return [], 0
            
            search_query = query.strip().lower()
            
            # Если типы не указаны, ищем во всех
            if not search_types:
                search_types = list(SearchResultType)
            
            # Собираем результаты из всех модулей
            all_results = []
            
            # Поиск в обслуживании
            if (SearchResultType.SERVICE_OBJECT in search_types or 
                SearchResultType.SERVICE_REGION in search_types):
                service_results = await self._search_service_data(search_query, user_id)
                all_results.extend(service_results)
            
            # Поиск в монтаже
            if (SearchResultType.INSTALLATION_OBJECT in search_types or
                SearchResultType.INSTALLATION_PROJECT in search_types or
                SearchResultType.INSTALLATION_MATERIAL in search_types):
                installation_results = await self._search_installation_data(search_query, user_id)
                all_results.extend(installation_results)
            
            # Поиск пользователей и админов (только для админов)
            if (SearchResultType.USER in search_types or 
                SearchResultType.ADMIN in search_types) and user_id:
                user_results = await self._search_user_data(search_query, user_id)
                all_results.extend(user_results)
            
            # Сортируем по релевантности
            all_results.sort(key=lambda x: x.relevance, reverse=True)
            
            # Применяем пагинацию
            total_count = len(all_results)
            paginated_results = all_results[offset:offset + limit]
            
            return paginated_results, total_count
            
        except Exception as e:
            logger.error(f"Error in global search for query '{query}': {e}")
            return [], 0
    
    async def _search_service_data(
        self, 
        query: str, 
        user_id: Optional[int] = None
    ) -> List[SearchResult]:
        """
        Поиск в данных обслуживания.
        
        Args:
            query: Поисковый запрос
            user_id: ID пользователя
            
        Returns:
            Список результатов
        """
        results = []
        
        try:
            # Поиск объектов обслуживания
            service_objects = await self.service_repo.search_objects(query)
            for obj in service_objects:
                relevance = self._calculate_relevance(
                    query,
                    [obj.short_name, obj.full_name, obj.contract_number]
                )
                
                if relevance > 0:
                    result = SearchResult(
                        id=obj.id,
                        type=SearchResultType.SERVICE_OBJECT,
                        title=obj.short_name,
                        description=f"{obj.full_name} | {obj.contract_number}",
                        relevance=relevance,
                        entity_data={
                            "region_id": obj.region_id,
                            "addresses": obj.addresses,
                            "contract_date": obj.contract_date.isoformat() if obj.contract_date else None
                        }
                    )
                    results.append(result)
            
            # Поиск регионов
            regions = await self.service_repo.search_regions(query)
            for region in regions:
                relevance = self._calculate_relevance(
                    query,
                    [region.short_name, region.full_name]
                )
                
                if relevance > 0:
                    result = SearchResult(
                        id=region.id,
                        type=SearchResultType.SERVICE_REGION,
                        title=region.short_name,
                        description=region.full_name,
                        relevance=relevance,
                        entity_data={
                            "object_count": region.object_count if hasattr(region, 'object_count') else 0
                        }
                    )
                    results.append(result)
            
            # Поиск проблем
            problems = await self.service_repo.search_problems(query)
            for problem in problems:
                relevance = self._calculate_relevance(
                    query,
                    [problem.description]
                )
                
                if relevance > 0:
                    result = SearchResult(
                        id=problem.id,
                        type=SearchResultType.SERVICE_PROBLEM,
                        title="Проблема",
                        description=self._truncate_text(problem.description, 100),
                        relevance=relevance,
                        entity_data={
                            "object_id": problem.object_id,
                            "created_at": problem.created_at.isoformat(),
                            "has_file": problem.file_id is not None
                        }
                    )
                    results.append(result)
            
            # Поиск ТО
            maintenance_records = await self.service_repo.search_maintenance(query)
            for maintenance in maintenance_records:
                relevance = self._calculate_relevance(
                    query,
                    [maintenance.description or "", maintenance.frequency]
                )
                
                if relevance > 0:
                    result = SearchResult(
                        id=maintenance.id,
                        type=SearchResultType.SERVICE_MAINTENANCE,
                        title="Техническое обслуживание",
                        description=f"{maintenance.frequency} | {maintenance.description or 'Без описания'}",
                        relevance=relevance,
                        entity_data={
                            "object_id": maintenance.object_id,
                            "frequency": maintenance.frequency,
                            "month": maintenance.month
                        }
                    )
                    results.append(result)
            
        except Exception as e:
            logger.error(f"Error searching service data: {e}")
        
        return results
    
    async def _search_installation_data(
        self, 
        query: str, 
        user_id: Optional[int] = None
    ) -> List[SearchResult]:
        """
        Поиск в данных монтажа.
        
        Args:
            query: Поисковый запрос
            user_id: ID пользователя
            
        Returns:
            Список результатов
        """
        results = []
        
        try:
            # Поиск объектов монтажа
            installation_objects = await self.installation_repo.search_objects(query)
            for obj in installation_objects:
                relevance = self._calculate_relevance(
                    query,
                    [obj.short_name, obj.full_name, obj.contract_number]
                )
                
                if relevance > 0:
                    result = SearchResult(
                        id=obj.id,
                        type=SearchResultType.INSTALLATION_OBJECT,
                        title=obj.short_name,
                        description=f"{obj.full_name} | {obj.contract_number}",
                        relevance=relevance,
                        entity_data={
                            "addresses": obj.addresses,
                            "systems": obj.systems,
                            "contract_date": obj.contract_date.isoformat() if obj.contract_date else None
                        }
                    )
                    results.append(result)
            
            # Поиск проектов
            projects = await self.installation_repo.search_projects(query)
            for project in projects:
                relevance = self._calculate_relevance(
                    query,
                    [project.name, project.description or ""]
                )
                
                if relevance > 0:
                    result = SearchResult(
                        id=project.id,
                        type=SearchResultType.INSTALLATION_PROJECT,
                        title=project.name,
                        description=project.description or "Без описания",
                        relevance=relevance,
                        entity_data={
                            "object_id": project.object_id,
                            "has_file": project.file_id is not None
                        }
                    )
                    results.append(result)
            
            # Поиск материалов
            materials = await self.installation_repo.search_materials(query)
            for material in materials:
                relevance = self._calculate_relevance(
                    query,
                    [material.name, material.description or ""]
                )
                
                if relevance > 0:
                    result = SearchResult(
                        id=material.id,
                        type=SearchResultType.INSTALLATION_MATERIAL,
                        title=material.name,
                        description=f"{material.quantity} {material.unit} | {material.description or ''}",
                        relevance=relevance,
                        entity_data={
                            "object_id": material.object_id,
                            "section_id": material.section_id,
                            "quantity": material.quantity,
                            "unit": material.unit,
                            "installed_quantity": material.installed_quantity
                        }
                    )
                    results.append(result)
            
        except Exception as e:
            logger.error(f"Error searching installation data: {e}")
        
        return results
    
    async def _search_user_data(
        self, 
        query: str, 
        user_id: int
    ) -> List[SearchResult]:
        """
        Поиск пользователей и админов.
        
        Args:
            query: Поисковый запрос
            user_id: ID пользователя (для проверки прав)
            
        Returns:
            Список результатов
        """
        results = []
        
        try:
            # Проверяем права пользователя (должен быть админом)
            is_admin = await self.user_repo.is_user_admin(user_id)
            if not is_admin:
                return results
            
            # Поиск пользователей
            users = await self.user_repo.search_users(query)
            for user in users:
                relevance = self._calculate_relevance(
                    query,
                    [user.username or "", user.first_name or "", user.last_name or ""]
                )
                
                if relevance > 0:
                    user_type = SearchResultType.ADMIN if user.is_admin else SearchResultType.USER
                    title = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or "Пользователь"
                    
                    result = SearchResult(
                        id=str(user.id),
                        type=user_type,
                        title=title,
                        description=f"@{user.username}" if user.username else "Без username",
                        relevance=relevance,
                        entity_data={
                            "telegram_id": user.telegram_id,
                            "is_admin": user.is_admin,
                            "admin_level": user.admin_level if hasattr(user, 'admin_level') else None
                        }
                    )
                    results.append(result)
            
        except Exception as e:
            logger.error(f"Error searching user data: {e}")
        
        return results
    
    def _calculate_relevance(self, query: str, fields: List[str]) -> float:
        """
        Расчет релевантности результата.
        
        Args:
            query: Поисковый запрос
            fields: Поля для поиска
            
        Returns:
            Коэффициент релевантности от 0 до 1
        """
        if not query or not fields:
            return 0.0
        
        query = query.lower()
        max_relevance = 0.0
        
        for field in fields:
            if not field:
                continue
            
            field_lower = field.lower()
            
            # Проверка точного совпадения
            if field_lower == query:
                return 1.0
            
            # Проверка начала строки
            if field_lower.startswith(query):
                relevance = 0.9
                max_relevance = max(max_relevance, relevance)
                continue
            
            # Проверка содержания подстроки
            if query in field_lower:
                relevance = 0.7
                max_relevance = max(max_relevance, relevance)
                continue
            
            # Поиск отдельных слов
            query_words = query.split()
            field_words = set(field_lower.split())
            
            matched_words = 0
            for q_word in query_words:
                for f_word in field_words:
                    if q_word in f_word or f_word in q_word:
                        matched_words += 1
                        break
            
            if matched_words > 0:
                relevance = 0.5 * (matched_words / len(query_words))
                max_relevance = max(max_relevance, relevance)
        
        return max_relevance
    
    def _truncate_text(self, text: str, max_length: int) -> str:
        """
        Обрезка текста с добавлением многоточия.
        
        Args:
            text: Исходный текст
            max_length: Максимальная длина
            
        Returns:
            Обрезанный текст
        """
        if not text:
            return ""
        
        if len(text) <= max_length:
            return text
        
        return text[:max_length - 3] + "..."
    
    def highlight_matches(self, text: str, query: str) -> str:
        """
        Подсветка найденных фрагментов в тексте.
        
        Args:
            text: Исходный текст
            query: Поисковый запрос
            
        Returns:
            Текст с подсветкой
        """
        if not text or not query:
            return text
        
        try:
            # Экранируем специальные символы для регулярного выражения
            escaped_query = re.escape(query)
            
            # Заменяем все вхождения на подсвеченную версию
            highlighted = re.sub(
                f'({escaped_query})',
                r'<b>\1</b>',
                text,
                flags=re.IGNORECASE
            )
            
            return highlighted
            
        except Exception as e:
            logger.error(f"Error highlighting matches in text: {e}")
            return text
    
    async def search_by_type(
        self,
        query: str,
        search_type: SearchResultType,
        user_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[SearchResult], int]:
        """
        Поиск по конкретному типу данных.
        
        Args:
            query: Поисковый запрос
            search_type: Тип данных для поиска
            user_id: ID пользователя
            limit: Максимальное количество результатов
            offset: Смещение для пагинации
            
        Returns:
            Кортеж (список результатов, общее количество)
        """
        try:
            if search_type in [
                SearchResultType.SERVICE_OBJECT,
                SearchResultType.SERVICE_REGION,
                SearchResultType.SERVICE_PROBLEM,
                SearchResultType.SERVICE_MAINTENANCE
            ]:
                results = await self._search_service_data(query, user_id)
            elif search_type in [
                SearchResultType.INSTALLATION_OBJECT,
                SearchResultType.INSTALLATION_PROJECT,
                SearchResultType.INSTALLATION_MATERIAL
            ]:
                results = await self._search_installation_data(query, user_id)
            elif search_type in [SearchResultType.USER, SearchResultType.ADMIN]:
                results = await self._search_user_data(query, user_id)
            else:
                results = []
            
            # Фильтруем по типу
            filtered_results = [r for r in results if r.type == search_type]
            
            # Сортируем по релевантности
            filtered_results.sort(key=lambda x: x.relevance, reverse=True)
            
            # Применяем пагинацию
            total_count = len(filtered_results)
            paginated_results = filtered_results[offset:offset + limit]
            
            return paginated_results, total_count
            
        except Exception as e:
            logger.error(f"Error in type-specific search for {search_type}: {e}")
            return [], 0
    
    async def advanced_search(
        self,
        filters: Dict[str, Any],
        user_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[SearchResult], int]:
        """
        Расширенный поиск с фильтрами.
        
        Args:
            filters: Словарь фильтров
            user_id: ID пользователя
            limit: Максимальное количество результатов
            offset: Смещение для пагинации
            
        Returns:
            Кортеж (список результатов, общее количество)
        """
        try:
            # Здесь должна быть реализация расширенного поиска
            # с учетом различных фильтров: дата, тип объекта, статус и т.д.
            
            # Временная реализация - возвращаем пустой список
            logger.info(f"Advanced search with filters: {filters}")
            return [], 0
            
        except Exception as e:
            logger.error(f"Error in advanced search: {e}")
            return [], 0
    
    async def get_search_suggestions(
        self,
        partial_query: str,
        user_id: Optional[int] = None,
        limit: int = 10
    ) -> List[str]:
        """
        Получение подсказок для поиска.
        
        Args:
            partial_query: Частичный запрос
            user_id: ID пользователя
            limit: Максимальное количество подсказок
            
        Returns:
            Список подсказок
        """
        try:
            if len(partial_query) < 2:
                return []
            
            # Здесь должна быть реализация подсказок на основе
            # популярных запросов или автодополнения
            
            # Временная реализация
            suggestions = []
            
            # Добавляем подсказки из обслуживания
            service_objects = await self.service_repo.search_objects(partial_query, limit=5)
            for obj in service_objects:
                suggestions.append(obj.short_name)
                suggestions.append(obj.full_name)
            
            # Добавляем подсказки из монтажа
            installation_objects = await self.installation_repo.search_objects(partial_query, limit=5)
            for obj in installation_objects:
                suggestions.append(obj.short_name)
                suggestions.append(obj.full_name)
            
            # Убираем дубликаты и ограничиваем количество
            unique_suggestions = []
            seen = set()
            for suggestion in suggestions:
                if suggestion and suggestion.lower().startswith(partial_query.lower()):
                    if suggestion not in seen:
                        seen.add(suggestion)
                        unique_suggestions.append(suggestion)
                
                if len(unique_suggestions) >= limit:
                    break
            
            return unique_suggestions
            
        except Exception as e:
            logger.error(f"Error getting search suggestions: {e}")
            return []