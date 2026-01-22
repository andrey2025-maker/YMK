"""
Менеджер для управления письмами объектов обслуживания.
Реализует хранение переписки с номерами, датами и прикрепленными файлами.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import structlog

from core.context import AppContext
from storage.models.service import Letter, ServiceObject
from storage.repositories.service_repository import ServiceRepository
from utils.date_utils import parse_date, format_date
from modules.file.archive_manager import ArchiveManager


logger = structlog.get_logger(__name__)


class LetterManager:
    """Менеджер для управления письмами объектов обслуживания."""
    
    def __init__(self, context: AppContext):
        self.context = context
        self.service_repository: Optional[ServiceRepository] = None
        self.archive_manager: Optional[ArchiveManager] = None
    
    async def initialize(self) -> None:
        """Инициализирует менеджер писем."""
        self.service_repository = ServiceRepository(self.context.db_session)
        self.archive_manager = ArchiveManager(self.context)
        logger.info("LetterManager initialized")
    
    async def add_letter(
        self,
        object_id: str,
        user_id: int,
        user_name: str,
        letter_number: str,
        letter_date: str,
        description: str,
        file_id: Optional[str] = None,
        file_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Добавляет письмо к объекту обслуживания.
        
        Args:
            object_id: ID объекта обслуживания
            user_id: ID пользователя
            user_name: Имя пользователя
            letter_number: Номер письма (формат: 26/01)
            letter_date: Дата письма (формат: ДД.ММ.ГГГГ)
            description: Описание письма
            file_id: ID файла в Telegram (опционально)
            file_name: Имя файла (опционально)
            
        Returns:
            Dict с информацией о созданном письме
        """
        try:
            # Проверяем существование объекта
            object_info = await self.service_repository.get_object_by_id(object_id)
            if not object_info:
                return {
                    'success': False,
                    'error': 'Объект не найден'
                }
            
            # Парсим дату
            parsed_date = parse_date(letter_date)
            if not parsed_date:
                return {
                    'success': False,
                    'error': 'Неверный формат даты. Используйте ДД.ММ.ГГГГ'
                }
            
            # Проверяем уникальность номера письма для объекта
            existing_letter = await self.service_repository.get_letter_by_number(object_id, letter_number)
            if existing_letter:
                return {
                    'success': False,
                    'error': f'Письмо с номером {letter_number} уже существует для этого объекта'
                }
            
            # Создаем запись письма
            letter = Letter(
                object_id=object_id,
                letter_number=letter_number,
                letter_date=parsed_date,
                description=description,
                has_file=file_id is not None,
                file_id=file_id,
                file_name=file_name,
                added_by_id=user_id,
                added_by_name=user_name,
                added_at=datetime.now()
            )
            
            # Сохраняем в БД
            saved_letter = await self.service_repository.create_letter(letter)
            
            # Если есть файл, сохраняем его в архив
            if file_id and self.archive_manager:
                await self.archive_manager.save_file_to_archive(
                    file_id=file_id,
                    file_name=file_name or f"letter_{saved_letter.id}.file",
                    file_type='other',
                    user_id=user_id,
                    metadata={
                        'letter_id': str(saved_letter.id),
                        'object_id': object_id,
                        'object_name': object_info.short_name,
                        'letter_number': letter_number,
                        'letter_date': letter_date
                    }
                )
            
            # Логируем создание письма
            await self.context.log_manager.log_change(
                user_id=user_id,
                user_name=user_name,
                entity_type='letter',
                entity_id=str(saved_letter.id),
                entity_name=f"Письмо {letter_number}",
                action='create',
                changes={
                    'letter_number': {'new': letter_number},
                    'letter_date': {'new': letter_date},
                    'description': {'new': description}
                }
            )
            
            return {
                'success': True,
                'letter_id': str(saved_letter.id),
                'letter_number': letter_number,
                'letter_date': letter_date,
                'object_name': object_info.short_name,
                'timestamp': saved_letter.added_at
            }
            
        except Exception as e:
            logger.error("Failed to add letter", error=str(e), object_id=object_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_letters(
        self,
        object_id: str,
        page: int = 0,
        limit: int = 10,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Получает список писем объекта с пагинацией.
        
        Args:
            object_id: ID объекта обслуживания
            page: Номер страницы (начиная с 0)
            limit: Количество записей на страницу
            year: Фильтр по году (опционально)
            
        Returns:
            Dict с письмами и информацией о пагинации
        """
        try:
            # Получаем письма из БД
            letters = await self.service_repository.get_letters(
                object_id=object_id,
                skip=page * limit,
                limit=limit,
                year=year
            )
            
            # Получаем общее количество
            total = await self.service_repository.count_letters(object_id, year)
            
            # Форматируем письма для отображения
            formatted_letters = []
            for letter in letters:
                formatted_letters.append({
                    'id': str(letter.id),
                    'letter_number': letter.letter_number,
                    'letter_date': letter.letter_date,
                    'formatted_date': format_date(letter.letter_date),
                    'description': letter.description,
                    'has_file': letter.has_file,
                    'file_name': letter.file_name,
                    'added_by': letter.added_by_name,
                    'added_at': letter.added_at
                })
            
            # Получаем доступные годы для фильтрации
            available_years = await self.service_repository.get_letter_years(object_id)
            
            return {
                'success': True,
                'letters': formatted_letters,
                'total': total,
                'page': page,
                'limit': limit,
                'total_pages': (total + limit - 1) // limit,
                'available_years': available_years,
                'current_year': year
            }
            
        except Exception as e:
            logger.error("Failed to get letters", error=str(e), object_id=object_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def update_letter(
        self,
        letter_id: str,
        user_id: int,
        user_name: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Редактирует письмо.
        
        Args:
            letter_id: ID письма
            user_id: ID пользователя
            user_name: Имя пользователя
            updates: Словарь обновлений
            
        Returns:
            Dict с результатом обновления
        """
        try:
            # Получаем текущее письмо
            letter = await self.service_repository.get_letter_by_id(letter_id)
            if not letter:
                return {
                    'success': False,
                    'error': 'Письмо не найдено'
                }
            
            # Проверяем права доступа
            from modules.admin.admin_manager import AdminManager
            admin_manager = AdminManager(self.context)
            user_role = await admin_manager.get_user_role(user_id)
            if user_role not in ['main_admin', 'admin']:
                return {
                    'success': False,
                    'error': 'Нет прав для редактирования письма'
                }
            
            # Подготавливаем изменения для логирования
            changes = {}
            
            # Проверяем каждое обновляемое поле
            if 'letter_number' in updates and updates['letter_number'] != letter.letter_number:
                # Проверяем уникальность нового номера
                existing_letter = await self.service_repository.get_letter_by_number(
                    letter.object_id, 
                    updates['letter_number']
                )
                if existing_letter and str(existing_letter.id) != letter_id:
                    return {
                        'success': False,
                        'error': f'Письмо с номером {updates["letter_number"]} уже существует для этого объекта'
                    }
                
                changes['letter_number'] = {
                    'old': letter.letter_number,
                    'new': updates['letter_number']
                }
                letter.letter_number = updates['letter_number']
            
            if 'letter_date' in updates:
                parsed_date = parse_date(updates['letter_date'])
                if not parsed_date:
                    return {
                        'success': False,
                        'error': 'Неверный формат даты. Используйте ДД.ММ.ГГГГ'
                    }
                
                if parsed_date != letter.letter_date:
                    changes['letter_date'] = {
                        'old': format_date(letter.letter_date),
                        'new': updates['letter_date']
                    }
                    letter.letter_date = parsed_date
            
            if 'description' in updates and updates['description'] != letter.description:
                changes['description'] = {
                    'old': letter.description,
                    'new': updates['description']
                }
                letter.description = updates['description']
            
            # Сохраняем изменения
            updated_letter = await self.service_repository.update_letter(letter)
            
            # Логируем изменения если они были
            if changes:
                await self.context.log_manager.log_change(
                    user_id=user_id,
                    user_name=user_name,
                    entity_type='letter',
                    entity_id=letter_id,
                    entity_name=f"Письмо {letter.letter_number}",
                    action='update',
                    changes=changes
                )
            
            return {
                'success': True,
                'letter_id': letter_id,
                'updated_fields': list(changes.keys())
            }
            
        except Exception as e:
            logger.error("Failed to update letter", error=str(e), letter_id=letter_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def delete_letter(
        self,
        letter_id: str,
        user_id: int,
        user_name: str
    ) -> Dict[str, Any]:
        """
        Удаляет письмо.
        
        Args:
            letter_id: ID письма
            user_id: ID пользователя
            user_name: Имя пользователя
            
        Returns:
            Dict с результатом удаления
        """
        try:
            # Получаем письмо
            letter = await self.service_repository.get_letter_by_id(letter_id)
            if not letter:
                return {
                    'success': False,
                    'error': 'Письмо не найдено'
                }
            
            # Проверяем права доступа
            from modules.admin.admin_manager import AdminManager
            admin_manager = AdminManager(self.context)
            user_role = await admin_manager.get_user_role(user_id)
            if user_role not in ['main_admin', 'admin']:
                return {
                    'success': False,
                    'error': 'Нет прав для удаления письма'
                }
            
            # Сохраняем информацию для архива
            letter_info = {
                'id': str(letter.id),
                'letter_number': letter.letter_number,
                'letter_date': format_date(letter.letter_date),
                'description': letter.description,
                'object_id': letter.object_id,
                'added_by': letter.added_by_name,
                'added_at': letter.added_at,
                'deleted_by': user_name,
                'deleted_at': datetime.now()
            }
            
            # Удаляем письмо
            deleted = await self.service_repository.delete_letter(letter_id)
            
            if deleted:
                # Логируем удаление
                await self.context.log_manager.log_change(
                    user_id=user_id,
                    user_name=user_name,
                    entity_type='letter',
                    entity_id=letter_id,
                    entity_name=f"Письмо {letter.letter_number}",
                    action='delete',
                    changes={'letter': {'old': letter_info, 'new': None}}
                )
                
                return {
                    'success': True,
                    'letter_id': letter_id,
                    'letter_number': letter.letter_number
                }
            else:
                return {
                    'success': False,
                    'error': 'Не удалось удалить письмо'
                }
            
        except Exception as e:
            logger.error("Failed to delete letter", error=str(e), letter_id=letter_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def attach_file_to_letter(
        self,
        letter_id: str,
        user_id: int,
        user_name: str,
        file_id: str,
        file_name: str
    ) -> Dict[str, Any]:
        """
        Прикрепляет файл к письму.
        
        Args:
            letter_id: ID письма
            user_id: ID пользователя
            user_name: Имя пользователя
            file_id: ID файла в Telegram
            file_name: Имя файла
            
        Returns:
            Dict с результатом
        """
        try:
            # Получаем письмо
            letter = await self.service_repository.get_letter_by_id(letter_id)
            if not letter:
                return {
                    'success': False,
                    'error': 'Письмо не найдено'
                }
            
            # Проверяем права доступа
            from modules.admin.admin_manager import AdminManager
            admin_manager = AdminManager(self.context)
            user_role = await admin_manager.get_user_role(user_id)
            if user_role not in ['main_admin', 'admin']:
                return {
                    'success': False,
                    'error': 'Нет прав для изменения письма'
                }
            
            # Сохраняем файл в архив
            if self.archive_manager:
                # Получаем информацию об объекте
                object_info = await self.service_repository.get_object_by_id(letter.object_id)
                
                await self.archive_manager.save_file_to_archive(
                    file_id=file_id,
                    file_name=file_name,
                    file_type='other',
                    user_id=user_id,
                    metadata={
                        'letter_id': letter_id,
                        'letter_number': letter.letter_number,
                        'object_id': letter.object_id,
                        'object_name': object_info.short_name if object_info else 'Неизвестно'
                    }
                )
            
            # Обновляем письмо
            letter.has_file = True
            letter.file_id = file_id
            letter.file_name = file_name
            
            updated_letter = await self.service_repository.update_letter(letter)
            
            # Логируем прикрепление файла
            await self.context.log_manager.log_change(
                user_id=user_id,
                user_name=user_name,
                entity_type='letter',
                entity_id=letter_id,
                entity_name=f"Письмо {letter.letter_number}",
                action='update',
                changes={
                    'file': {
                        'old': None,
                        'new': file_name
                    }
                }
            )
            
            return {
                'success': True,
                'letter_id': letter_id,
                'file_name': file_name
            }
            
        except Exception as e:
            logger.error("Failed to attach file to letter", error=str(e), letter_id=letter_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_letter_details(self, letter_id: str) -> Dict[str, Any]:
        """
        Получает детальную информацию о письме.
        
        Args:
            letter_id: ID письма
            
        Returns:
            Dict с детальной информацией о письме
        """
        try:
            letter = await self.service_repository.get_letter_by_id(letter_id)
            if not letter:
                return {
                    'success': False,
                    'error': 'Письмо не найдено'
                }
            
            # Получаем информацию об объекте
            object_info = await self.service_repository.get_object_by_id(letter.object_id)
            
            letter_details = {
                'id': str(letter.id),
                'letter_number': letter.letter_number,
                'letter_date': letter.letter_date,
                'formatted_date': format_date(letter.letter_date),
                'description': letter.description,
                'has_file': letter.has_file,
                'file_name': letter.file_name,
                'file_id': letter.file_id,
                'added_by': letter.added_by_name,
                'added_at': letter.added_at,
                'object_id': letter.object_id,
                'object_name': object_info.short_name if object_info else 'Неизвестно',
                'object_full_name': object_info.full_name if object_info else 'Неизвестно'
            }
            
            return {
                'success': True,
                'letter': letter_details
            }
            
        except Exception as e:
            logger.error("Failed to get letter details", error=str(e), letter_id=letter_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def search_letters(
        self,
        object_id: str,
        search_query: str,
        page: int = 0,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Ищет письма по номеру или описанию.
        
        Args:
            object_id: ID объекта обслуживания
            search_query: Поисковый запрос
            page: Номер страницы
            limit: Количество записей на страницу
            
        Returns:
            Dict с результатами поиска
        """
        try:
            # Ищем письма
            letters = await self.service_repository.search_letters(
                object_id=object_id,
                search_query=search_query,
                skip=page * limit,
                limit=limit
            )
            
            # Получаем общее количество
            total = await self.service_repository.count_search_letters(object_id, search_query)
            
            # Форматируем результаты
            formatted_letters = []
            for letter in letters:
                formatted_letters.append({
                    'id': str(letter.id),
                    'letter_number': letter.letter_number,
                    'letter_date': letter.letter_date,
                    'formatted_date': format_date(letter.letter_date),
                    'description': letter.description,
                    'has_file': letter.has_file,
                    'added_by': letter.added_by_name
                })
            
            return {
                'success': True,
                'letters': formatted_letters,
                'total': total,
                'page': page,
                'limit': limit,
                'total_pages': (total + limit - 1) // limit,
                'search_query': search_query
            }
            
        except Exception as e:
            logger.error("Failed to search letters", error=str(e), object_id=object_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_letter_statistics(self, object_id: str) -> Dict[str, Any]:
        """
        Получает статистику по письмам объекта.
        
        Args:
            object_id: ID объекта обслуживания
            
        Returns:
            Dict со статистикой
        """
        try:
            # Получаем общее количество писем
            total_letters = await self.service_repository.count_letters(object_id)
            
            # Получаем количество писем по годам
            letters_by_year = await self.service_repository.get_letters_by_year(object_id)
            
            # Получаем количество писем с файлами
            letters_with_files = await self.service_repository.count_letters_with_files(object_id)
            
            # Получаем последнее письмо
            last_letter = await self.service_repository.get_last_letter(object_id)
            
            statistics = {
                'total_letters': total_letters,
                'letters_with_files': letters_with_files,
                'letters_without_files': total_letters - letters_with_files,
                'letters_by_year': letters_by_year,
                'last_letter': None
            }
            
            if last_letter:
                statistics['last_letter'] = {
                    'letter_number': last_letter.letter_number,
                    'letter_date': format_date(last_letter.letter_date),
                    'added_at': last_letter.added_at
                }
            
            return {
                'success': True,
                'statistics': statistics
            }
            
        except Exception as e:
            logger.error("Failed to get letter statistics", error=str(e), object_id=object_id)
            return {
                'success': False,
                'error': str(e)
            }