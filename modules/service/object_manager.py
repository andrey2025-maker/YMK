import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models.service import ServiceObject, ServiceProblem, ServiceMaintenance, ServiceEquipment
from storage.repositories.service_repository import ServiceRepository
from modules.file.archive_manager import ArchiveManager
from utils.date_utils import parse_date, format_date
from core.context import AppContext


class ObjectManager:
    """Менеджер объектов обслуживания"""
    
    def __init__(self, context: AppContext):
        self.context = context
        self.repo = ServiceRepository(context.db)
        self.archive_manager = ArchiveManager(context)
    
    async def create_object(
        self,
        region_id: uuid.UUID,
        short_name: str,
        full_name: str,
        addresses: List[Dict[str, str]],
        contract_type: str,
        contract_number: str,
        contract_date: datetime,
        contract_start: datetime,
        contract_end: datetime,
        systems: List[str],
        zip_payer: str,
        has_dispatching: bool,
        notes: Optional[str],
        created_by: int
    ) -> ServiceObject:
        """Создание нового объекта обслуживания"""
        
        # Проверка на существование объекта с таким именем в регионе
        existing = await self.repo.get_object_by_name(region_id, short_name)
        if existing:
            raise ValueError(f"Объект с названием '{short_name}' уже существует в этом регионе")
        
        # Создаем объект
        obj = ServiceObject(
            short_name=short_name.strip(),
            full_name=full_name.strip(),
            region_id=region_id,
            addresses=addresses,
            contract_type=contract_type,
            contract_number=contract_number,
            contract_date=contract_date,
            contract_start=contract_start,
            contract_end=contract_end,
            systems=systems,
            zip_payer=zip_payer,
            has_dispatching=has_dispatching,
            notes=notes if notes and notes.lower() != 'нет' else None
        )
        
        await self.repo.add_object(obj)
        
        # Логирование создания
        await self._log_object_creation(obj, created_by)
        
        return obj
    
    async def get_object_by_id(self, object_id: uuid.UUID) -> Optional[ServiceObject]:
        """Получение объекта по ID"""
        return await self.repo.get_object_by_id(object_id)
    
    async def get_objects_by_region(self, region_id: uuid.UUID) -> List[ServiceObject]:
        """Получение всех объектов региона"""
        return await self.repo.get_objects_by_region(region_id)
    
    async def format_object_info(self, obj: ServiceObject) -> str:
        """Форматирование информации об объекте для отображения"""
        
        text = f"🏢 *Объект: {obj.full_name}*\n\n"
        
        # Контракт
        text += f"📄 *Документ:* {obj.contract_type} № {obj.contract_number}\n"
        text += f"📅 *Дата:* {format_date(obj.contract_date)}\n"
        text += f"🗓 *Сроки:* с {format_date(obj.contract_start)} до {format_date(obj.contract_end)}\n\n"
        
        # Адреса
        text += "📍 *Адреса:*\n"
        for i, address in enumerate(obj.addresses, 1):
            text += f"{i}. {address}\n"
        text += "\n"
        
        # Системы
        text += f"🔥 *Системы:* {' • '.join(obj.systems)}\n\n"
        
        # ЗИП
        text += f"🛠 *ЗИП:* за счёт {obj.zip_payer}\n"
        
        # Диспетчеризация
        if obj.has_dispatching:
            text += "📞 *Диспетчеризация:* есть\n"
        
        # Примечания
        if obj.notes:
            text += f"📝 *Примечания:* {obj.notes}\n"
        
        # Ответственный
        if obj.responsible_username:
            text += f"👤 *Ответственный:* @{obj.responsible_username}\n"
        
        # Дополнительные соглашения
        additional_docs = await self.repo.get_additional_docs(obj.id)
        if additional_docs:
            text += "\n📄 *Дополнительные соглашения:*\n"
            for doc in additional_docs:
                text += f"• {doc.document_type} № {doc.document_number}\n"
                if doc.description:
                    text += f"  {doc.description}\n"
        
        return text
    
    async def add_problem(
        self,
        object_id: uuid.UUID,
        description: str,
        file_data: Optional[Dict] = None,
        created_by: int
    ) -> ServiceProblem:
        """Добавление проблемы к объекту"""
        
        problem = ServiceProblem(
            object_id=object_id,
            description=description.strip(),
            created_by=created_by
        )
        
        if file_data:
            # Сохраняем файл в архив
            file_info = await self.archive_manager.save_file(
                file_data=file_data,
                category='problems',
                object_id=object_id
            )
            problem.file_info = file_info
        
        await self.repo.add_problem(problem)
        
        # Логирование
        await self._log_problem_addition(problem, created_by)
        
        return problem
    
    async def add_maintenance(
        self,
        object_id: uuid.UUID,
        frequency: str,
        month: int,
        description: str,
        created_by: int
    ) -> ServiceMaintenance:
        """Добавление ТО"""
        
        maintenance = ServiceMaintenance(
            object_id=object_id,
            frequency=frequency,
            month=month,
            description=description.strip(),
            created_by=created_by
        )
        
        await self.repo.add_maintenance(maintenance)
        
        # Логирование
        await self._log_maintenance_addition(maintenance, created_by)
        
        return maintenance
    
    async def add_equipment(
        self,
        object_id: uuid.UUID,
        address_index: int,
        name: str,
        quantity: int,
        unit: str,
        created_by: int
    ) -> ServiceEquipment:
        """Добавление оборудования"""
        
        equipment = ServiceEquipment(
            object_id=object_id,
            address_index=address_index,
            name=name.strip(),
            quantity=quantity,
            unit=unit,
            created_by=created_by
        )
        
        await self.repo.add_equipment(equipment)
        
        # Логирование
        await self._log_equipment_addition(equipment, created_by)
        
        return equipment
    
    async def add_additional_document(
        self,
        object_id: uuid.UUID,
        document_type: str,
        document_number: str,
        document_date: datetime,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        description: Optional[str],
        created_by: int
    ) -> ServiceAdditionalDoc:
        """Добавление дополнительного документа"""
        
        doc = ServiceAdditionalDoc(
            object_id=object_id,
            document_type=document_type,
            document_number=document_number,
            document_date=document_date,
            start_date=start_date,
            end_date=end_date,
            description=description
        )
        
        await self.repo.add_additional_doc(doc)
        
        # Логирование
        await self._log_document_addition(doc, created_by)
        
        return doc
    
    async def delete_object(self, object_id: uuid.UUID, deleted_by: int) -> bool:
        """Удаление объекта с архивацией"""
        
        obj = await self.get_object_by_id(object_id)
        if not obj:
            return False
        
        # Архивирование всех данных объекта
        archive_data = {
            'object': await self._get_full_object_data(obj),
            'deleted_at': datetime.utcnow().isoformat(),
            'deleted_by': deleted_by
        }
        
        await self.archive_manager.archive_data(
            data=archive_data,
            category='service_object_deleted',
            description=f"Удален объект {obj.short_name}"
        )
        
        # Удаление из БД
        await self.repo.delete_object(object_id)
        
        # Логирование удаления
        await self._log_object_deletion(obj, deleted_by)
        
        return True
    
    async def _get_full_object_data(self, obj: ServiceObject) -> Dict[str, Any]:
        """Получение всех данных объекта для архивации"""
        
        data = {
            'basic_info': {
                'id': str(obj.id),
                'short_name': obj.short_name,
                'full_name': obj.full_name,
                'contract_type': obj.contract_type,
                'contract_number': obj.contract_number,
                'contract_date': obj.contract_date.isoformat(),
                'contract_start': obj.contract_start.isoformat(),
                'contract_end': obj.contract_end.isoformat(),
                'addresses': obj.addresses,
                'systems': obj.systems,
                'zip_payer': obj.zip_payer,
                'has_dispatching': obj.has_dispatching,
                'notes': obj.notes,
                'responsible_username': obj.responsible_username
            },
            'problems': [problem.to_dict() for problem in obj.problems],
            'maintenance': [m.to_dict() for m in obj.maintenance],
            'equipment': [e.to_dict() for e in obj.equipment],
            'letters': [l.to_dict() for l in obj.letters],
            'journals': [j.to_dict() for j in obj.journals],
            'permits': [p.to_dict() for p in obj.permits],
            'additional_docs': [d.to_dict() for d in obj.additional_docs]
        }
        
        return data
    
    async def _log_object_creation(self, obj: ServiceObject, created_by: int):
        """Логирование создания объекта"""
        log_data = {
            'action': 'create_object',
            'object_id': str(obj.id),
            'short_name': obj.short_name,
            'full_name': obj.full_name,
            'region_id': str(obj.region_id),
            'created_by': created_by,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        await self.archive_manager.send_to_log_channel(
            message=f"Создан объект: {obj.short_name} - {obj.full_name}",
            data=log_data
        )
    
    async def _log_problem_addition(self, problem: ServiceProblem, created_by: int):
        """Логирование добавления проблемы"""
        log_data = {
            'action': 'add_problem',
            'problem_id': str(problem.id),
            'object_id': str(problem.object_id),
            'description': problem.description,
            'created_by': created_by,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        await self.archive_manager.send_to_log_channel(
            message=f"Добавлена проблема к объекту",
            data=log_data
        )
    
    async def _log_maintenance_addition(self, maintenance: ServiceMaintenance, created_by: int):
        """Логирование добавления ТО"""
        log_data = {
            'action': 'add_maintenance',
            'maintenance_id': str(maintenance.id),
            'object_id': str(maintenance.object_id),
            'frequency': maintenance.frequency,
            'month': maintenance.month,
            'created_by': created_by,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        await self.archive_manager.send_to_log_channel(
            message=f"Добавлено ТО к объекту",
            data=log_data
        )
    
    async def _log_equipment_addition(self, equipment: ServiceEquipment, created_by: int):
        """Логирование добавления оборудования"""
        log_data = {
            'action': 'add_equipment',
            'equipment_id': str(equipment.id),
            'object_id': str(equipment.object_id),
            'name': equipment.name,
            'quantity': equipment.quantity,
            'unit': equipment.unit,
            'created_by': created_by,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        await self.archive_manager.send_to_log_channel(
            message=f"Добавлено оборудование: {equipment.name}",
            data=log_data
        )
    
    async def _log_document_addition(self, doc: ServiceAdditionalDoc, created_by: int):
        """Логирование добавления документа"""
        log_data = {
            'action': 'add_document',
            'document_id': str(doc.id),
            'object_id': str(doc.object_id),
            'document_type': doc.document_type,
            'document_number': doc.document_number,
            'created_by': created_by,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        await self.archive_manager.send_to_log_channel(
            message=f"Добавлен документ: {doc.document_type} № {doc.document_number}",
            data=log_data
        )
    
    async def _log_object_deletion(self, obj: ServiceObject, deleted_by: int):
        """Логирование удаления объекта"""
        log_data = {
            'action': 'delete_object',
            'object_short_name': obj.short_name,
            'object_full_name': obj.full_name,
            'deleted_by': deleted_by,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        await self.archive_manager.send_to_log_channel(
            message=f"Удален объект: {obj.short_name} - {obj.full_name}",
            data=log_data
        )