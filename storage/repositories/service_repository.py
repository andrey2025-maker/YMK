from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import select, update, delete, func, or_, and_, desc
from sqlalchemy.orm import selectinload, joinedload

from .base import BaseRepository
from storage.models.service import (
    ServiceRegion, ServiceObject, ServiceProblem, ServiceMaintenance,
    ServiceLetter, ServiceJournal, ServicePermit, ServiceEquipment,
    ServiceReminder, ServiceAdditionalDocument
)


class ServiceRepository:
    """Репозиторий для работы с обслуживанием."""
    
    def __init__(self, session):
        self.session = session
        self.region_repo = BaseRepository(ServiceRegion, session)
        self.object_repo = BaseRepository(ServiceObject, session)
    
    # ===== Регионы =====
    
    async def create_region(
        self,
        short_name: str,
        full_name: str,
        created_by: Optional[UUID] = None
    ) -> ServiceRegion:
        """Создает новый регион обслуживания."""
        region = await self.region_repo.create(
            short_name=short_name,
            full_name=full_name,
            created_by=created_by,
            is_active=True
        )
        return region
    
    async def get_region_by_id(self, region_id: UUID) -> Optional[ServiceRegion]:
        """Получает регион по ID."""
        query = select(ServiceRegion).where(
            ServiceRegion.id == region_id,
            ServiceRegion.is_deleted == False,
            ServiceRegion.is_active == True
        ).options(
            selectinload(ServiceRegion.objects)
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_all_regions(self) -> List[ServiceRegion]:
        """Получает все активные регионы."""
        query = select(ServiceRegion).where(
            ServiceRegion.is_deleted == False,
            ServiceRegion.is_active == True
        ).order_by(ServiceRegion.short_name)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_region_by_short_name(self, short_name: str) -> Optional[ServiceRegion]:
        """Получает регион по короткому имени."""
        query = select(ServiceRegion).where(
            ServiceRegion.short_name == short_name,
            ServiceRegion.is_deleted == False,
            ServiceRegion.is_active == True
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    # ===== Объекты =====
    
    async def create_object(
        self,
        region_id: UUID,
        short_name: str,
        full_name: str,
        addresses: List[str],
        document_type: str,
        document_number: str,
        document_date: date,
        contract_start_date: date,
        contract_end_date: date,
        systems: List[str],
        zip_purchaser: str,
        has_dispatching: bool,
        notes: Optional[str] = None,
        responsible_user_id: Optional[UUID] = None
    ) -> ServiceObject:
        """Создает новый объект обслуживания."""
        object = await self.object_repo.create(
            region_id=region_id,
            short_name=short_name,
            full_name=full_name,
            addresses=addresses,
            document_type=document_type,
            document_number=document_number,
            document_date=document_date,
            contract_start_date=contract_start_date,
            contract_end_date=contract_end_date,
            systems=systems,
            zip_purchaser=zip_purchaser,
            has_dispatching=has_dispatching,
            notes=notes,
            responsible_user_id=responsible_user_id,
            is_active=True
        )
        return object
    
    async def get_object_by_id(self, object_id: UUID) -> Optional[ServiceObject]:
        """Получает объект по ID со всеми связанными данными."""
        query = select(ServiceObject).where(
            ServiceObject.id == object_id,
            ServiceObject.is_deleted == False,
            ServiceObject.is_active == True
        ).options(
            joinedload(ServiceObject.region),
            joinedload(ServiceObject.responsible),
            selectinload(ServiceObject.problems).selectinload(ServiceProblem.files),
            selectinload(ServiceObject.maintenance),
            selectinload(ServiceObject.letters).selectinload(ServiceLetter.files),
            selectinload(ServiceObject.journals).selectinload(ServiceJournal.files),
            selectinload(ServiceObject.permits).selectinload(ServicePermit.files),
            selectinload(ServiceObject.equipment),
            selectinload(ServiceObject.reminders),
            selectinload(ServiceObject.additional_documents).selectinload(ServiceAdditionalDocument.files)
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_objects_by_region(self, region_id: UUID) -> List[ServiceObject]:
        """Получает все объекты региона."""
        query = select(ServiceObject).where(
            ServiceObject.region_id == region_id,
            ServiceObject.is_deleted == False,
            ServiceObject.is_active == True
        ).order_by(ServiceObject.short_name)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_all_active_objects(self) -> List[ServiceObject]:
        """Получает все активные объекты."""
        query = select(ServiceObject).where(
            ServiceObject.is_deleted == False,
            ServiceObject.is_active == True
        ).options(
            joinedload(ServiceObject.region),
            joinedload(ServiceObject.responsible)
        ).order_by(ServiceObject.short_name)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_objects_with_contracts_ending(self, end_date: date) -> List[ServiceObject]:
        """Получает объекты с контрактами, заканчивающимися до указанной даты."""
        query = select(ServiceObject).where(
            ServiceObject.is_deleted == False,
            ServiceObject.is_active == True,
            ServiceObject.contract_end_date <= end_date,
            ServiceObject.contract_end_date >= date.today()
        ).options(
            joinedload(ServiceObject.region),
            joinedload(ServiceObject.responsible)
        ).order_by(ServiceObject.contract_end_date)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    # ===== Проблемы =====
    
    async def create_problem(
        self,
        object_id: UUID,
        description: str
    ) -> ServiceProblem:
        """Создает новую проблему."""
        problem = ServiceProblem(
            service_object_id=object_id,
            description=description,
            is_resolved=False
        )
        self.session.add(problem)
        await self.session.flush()
        return problem
    
    async def get_problems_by_object(self, object_id: UUID) -> List[ServiceProblem]:
        """Получает все проблемы объекта."""
        query = select(ServiceProblem).where(
            ServiceProblem.service_object_id == object_id,
            ServiceProblem.is_deleted == False
        ).order_by(desc(ServiceProblem.created_at))
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def mark_problem_resolved(
        self,
        problem_id: UUID,
        solution: str,
        solved_by: UUID
    ) -> bool:
        """Помечает проблему как решенную."""
        query = (
            update(ServiceProblem)
            .where(ServiceProblem.id == problem_id)
            .values(
                is_resolved=True,
                solution=solution,
                solved_by=solved_by,
                solved_at=datetime.now()
            )
        )
        result = await self.session.execute(query)
        return result.rowcount > 0
    
    # ===== Техническое обслуживание =====
    
    async def create_maintenance(
        self,
        object_id: UUID,
        frequency: str,
        description: str,
        month: Optional[int] = None
    ) -> ServiceMaintenance:
        """Создает новое ТО."""
        maintenance = ServiceMaintenance(
            service_object_id=object_id,
            frequency=frequency,
            month=month,
            description=description
        )
        self.session.add(maintenance)
        await self.session.flush()
        return maintenance
    
    async def get_maintenance_by_object(self, object_id: UUID) -> List[ServiceMaintenance]:
        """Получает все ТО объекта."""
        query = select(ServiceMaintenance).where(
            ServiceMaintenance.service_object_id == object_id,
            ServiceMaintenance.is_deleted == False
        ).order_by(ServiceMaintenance.month)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_all_maintenance(self) -> List[ServiceMaintenance]:
        """Получает все ТО."""
        query = select(ServiceMaintenance).where(
            ServiceMaintenance.is_deleted == False
        ).options(
            joinedload(ServiceMaintenance.service_object)
        )
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def mark_maintenance_completed(
        self,
        maintenance_id: UUID,
        completed_by: UUID
    ) -> bool:
        """Помечает ТО как выполненное."""
        query = (
            update(ServiceMaintenance)
            .where(ServiceMaintenance.id == maintenance_id)
            .values(
                last_completed=datetime.now(),
                completed_by=completed_by
            )
        )
        result = await self.session.execute(query)
        return result.rowcount > 0
    
    # ===== Письма =====
    
    async def create_letter(
        self,
        object_id: UUID,
        letter_number: str,
        letter_date: date,
        description: str
    ) -> ServiceLetter:
        """Создает новое письмо."""
        letter = ServiceLetter(
            service_object_id=object_id,
            letter_number=letter_number,
            letter_date=letter_date,
            description=description
        )
        self.session.add(letter)
        await self.session.flush()
        return letter
    
    # ===== Оборудование =====
    
    async def create_equipment(
        self,
        object_id: UUID,
        name: str,
        quantity: Decimal,
        unit: str,
        description: Optional[str] = None,
        address_index: Optional[int] = None
    ) -> ServiceEquipment:
        """Создает новое оборудование."""
        equipment = ServiceEquipment(
            service_object_id=object_id,
            address_index=address_index,
            name=name,
            quantity=quantity,
            unit=unit,
            description=description
        )
        self.session.add(equipment)
        await self.session.flush()
        return equipment
    
    async def get_equipment_by_object(
        self, 
        object_id: UUID,
        address_index: Optional[int] = None
    ) -> List[ServiceEquipment]:
        """Получает оборудование объекта."""
        query = select(ServiceEquipment).where(
            ServiceEquipment.service_object_id == object_id,
            ServiceEquipment.is_deleted == False
        )
        
        if address_index is not None:
            query = query.where(
                or_(
                    ServiceEquipment.address_index == address_index,
                    ServiceEquipment.address_index.is_(None)
                )
            )
        
        query = query.order_by(ServiceEquipment.created_at)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    # ===== Напоминания =====
    
    async def create_reminder(
        self,
        object_id: UUID,
        due_date: date,
        message: str,
        reminder_type: str = "custom",
        notify_day_before: bool = True,
        notify_on_day: bool = True
    ) -> ServiceReminder:
        """Создает новое напоминание."""
        reminder = ServiceReminder(
            service_object_id=object_id,
            reminder_type=reminder_type,
            due_date=due_date,
            message=message,
            notify_day_before=notify_day_before,
            notify_on_day=notify_on_day,
            is_completed=False
        )
        self.session.add(reminder)
        await self.session.flush()
        return reminder
    
    async def get_active_service_reminders(self) -> List[ServiceReminder]:
        """Получает активные напоминания обслуживания."""
        query = select(ServiceReminder).where(
            ServiceReminder.is_deleted == False,
            ServiceReminder.is_completed == False,
            ServiceReminder.due_date >= date.today()
        ).options(
            joinedload(ServiceReminder.service_object)
        ).order_by(ServiceReminder.due_date)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_reminders_in_period(
        self, 
        start_date: date, 
        end_date: date
    ) -> List[ServiceReminder]:
        """Получает напоминания в указанном периоде."""
        query = select(ServiceReminder).where(
            ServiceReminder.is_deleted == False,
            ServiceReminder.is_completed == False,
            ServiceReminder.due_date >= start_date,
            ServiceReminder.due_date <= end_date
        ).options(
            joinedload(ServiceReminder.service_object)
        ).order_by(ServiceReminder.due_date)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def mark_reminder_notified(self, reminder_id: UUID) -> bool:
        """Помечает напоминание как отправленное (для разовых)."""
        query = (
            update(ServiceReminder)
            .where(ServiceReminder.id == reminder_id)
            .values(is_completed=True, completed_at=datetime.now())
        )
        result = await self.session.execute(query)
        return result.rowcount > 0
    
    # ===== Дополнительные соглашения =====
    
    async def create_additional_document(
        self,
        object_id: UUID,
        document_type: str,
        document_number: str,
        document_date: date,
        description: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> ServiceAdditionalDocument:
        """Создает новое дополнительное соглашение."""
        document = ServiceAdditionalDocument(
            service_object_id=object_id,
            document_type=document_type,
            document_number=document_number,
            document_date=document_date,
            start_date=start_date,
            end_date=end_date,
            description=description
        )
        self.session.add(document)
        await self.session.flush()
        return document
    
    # ===== Поиск =====
    
    async def search_in_object(
        self,
        object_id: UUID,
        search_query: str,
        limit: int = 50
    ) -> Dict[str, List[Any]]:
        """Ищет информацию в объекте по запросу."""
        results = {
            "problems": [],
            "maintenance": [],
            "letters": [],
            "equipment": [],
            "reminders": [],
            "documents": [],
        }
        
        # Поиск в проблемах
        problems_query = select(ServiceProblem).where(
            ServiceProblem.service_object_id == object_id,
            ServiceProblem.is_deleted == False,
            or_(
                ServiceProblem.description.ilike(f"%{search_query}%"),
                ServiceProblem.solution.ilike(f"%{search_query}%")
            )
        ).limit(limit)
        
        problems_result = await self.session.execute(problems_query)
        results["problems"] = list(problems_result.scalars().all())
        
        # Поиск в ТО
        maintenance_query = select(ServiceMaintenance).where(
            ServiceMaintenance.service_object_id == object_id,
            ServiceMaintenance.is_deleted == False,
            ServiceMaintenance.description.ilike(f"%{search_query}%")
        ).limit(limit)
        
        maintenance_result = await self.session.execute(maintenance_query)
        results["maintenance"] = list(maintenance_result.scalars().all())
        
        # Поиск в письмах
        letters_query = select(ServiceLetter).where(
            ServiceLetter.service_object_id == object_id,
            ServiceLetter.is_deleted == False,
            or_(
                ServiceLetter.letter_number.ilike(f"%{search_query}%"),
                ServiceLetter.description.ilike(f"%{search_query}%")
            )
        ).limit(limit)
        
        letters_result = await self.session.execute(letters_query)
        results["letters"] = list(letters_result.scalars().all())
        
        # Поиск в оборудовании
        equipment_query = select(ServiceEquipment).where(
            ServiceEquipment.service_object_id == object_id,
            ServiceEquipment.is_deleted == False,
            or_(
                ServiceEquipment.name.ilike(f"%{search_query}%"),
                ServiceEquipment.description.ilike(f"%{search_query}%")
            )
        ).limit(limit)
        
        equipment_result = await self.session.execute(equipment_query)
        results["equipment"] = list(equipment_result.scalars().all())
        
        # Поиск в напоминаниях
        reminders_query = select(ServiceReminder).where(
            ServiceReminder.service_object_id == object_id,
            ServiceReminder.is_deleted == False,
            ServiceReminder.message.ilike(f"%{search_query}%")
        ).limit(limit)
        
        reminders_result = await self.session.execute(reminders_query)
        results["reminders"] = list(reminders_result.scalars().all())
        
        # Поиск в документах
        documents_query = select(ServiceAdditionalDocument).where(
            ServiceAdditionalDocument.service_object_id == object_id,
            ServiceAdditionalDocument.is_deleted == False,
            or_(
                ServiceAdditionalDocument.document_number.ilike(f"%{search_query}%"),
                ServiceAdditionalDocument.description.ilike(f"%{search_query}%")
            )
        ).limit(limit)
        
        documents_result = await self.session.execute(documents_query)
        results["documents"] = list(documents_result.scalars().all())
        
        return results
    
    async def search_globally(self, search_query: str, user_id: UUID, limit: int = 20) -> List[Dict[str, Any]]:
        """Глобальный поиск по всем объектам, доступным пользователю."""
        # В реальном приложении здесь была бы сложная логика с учетом прав доступа
        # Пока возвращаем упрощенную версию
        query = select(ServiceObject).where(
            ServiceObject.is_deleted == False,
            ServiceObject.is_active == True,
            or_(
                ServiceObject.short_name.ilike(f"%{search_query}%"),
                ServiceObject.full_name.ilike(f"%{search_query}%"),
                ServiceObject.document_number.ilike(f"%{search_query}%")
            )
        ).limit(limit)
        
        result = await self.session.execute(query)
        objects = list(result.scalars().all())
        
        return [
            {
                "id": str(obj.id),
                "type": "service",
                "name": obj.short_name,
                "full_name": obj.full_name,
                "region": obj.region.short_name if obj.region else "",
                "document_number": obj.document_number,
            }
            for obj in objects
        ]