"""
Репозиторий для работы с объектами монтажа.
Реализует CRUD операции для всех сущностей модуля монтажа.
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, date

from sqlalchemy import select, update, delete, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from storage.models.installation import (
    InstallationObject, InstallationAddress, InstallationProject,
    InstallationMaterial, InstallationMaterialSection, InstallationMaterialQuantity,
    InstallationMontage, InstallationSupply, InstallationChange,
    InstallationDocument, InstallationGroupBinding
)
from storage.models.user import UserAccess
from utils.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


class InstallationRepository:
    """Репозиторий объектов монтажа."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # ========== Объекты монтажа ==========
    
    async def save_installation_object(self, installation_object: InstallationObject) -> InstallationObject:
        """Сохранение объекта монтажа."""
        try:
            self.session.add(installation_object)
            await self.session.flush()
            await self.session.refresh(installation_object)
            return installation_object
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error saving installation object: {e}", exc_info=True)
            raise
    
    async def get_installation_object_by_id(self, object_id: str) -> Optional[InstallationObject]:
        """Получение объекта монтажа по ID."""
        try:
            stmt = select(InstallationObject).where(
                InstallationObject.id == UUID(object_id),
                InstallationObject.is_active == True
            ).options(
                selectinload(InstallationObject.addresses),
                selectinload(InstallationObject.documents),
                selectinload(InstallationObject.projects),
                selectinload(InstallationObject.materials),
                selectinload(InstallationObject.material_sections),
                selectinload(InstallationObject.supplies),
                selectinload(InstallationObject.changes)
            )
            
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting installation object {object_id}: {e}")
            return None
    
    async def get_installation_objects_by_user(self, user_id: int) -> List[InstallationObject]:
        """Получение объектов монтажа пользователя."""
        try:
            # Получаем объекты, к которым у пользователя есть доступ
            stmt = select(InstallationObject).join(
                UserAccess,
                and_(
                    UserAccess.object_type == 'installation',
                    UserAccess.object_id == InstallationObject.id,
                    UserAccess.user_id == user_id,
                    UserAccess.is_active == True
                )
            ).where(
                InstallationObject.is_active == True
            ).options(
                selectinload(InstallationObject.addresses)
            ).order_by(InstallationObject.created_at.desc())
            
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting installation objects for user {user_id}: {e}")
            return []
    
    async def get_installation_objects_by_chat(self, chat_id: int) -> List[InstallationObject]:
        """Получение объектов монтажа, привязанных к чату."""
        try:
            stmt = select(InstallationObject).join(
                InstallationGroupBinding,
                and_(
                    InstallationGroupBinding.object_type == 'installation',
                    InstallationGroupBinding.object_id == InstallationObject.id,
                    InstallationGroupBinding.chat_id == chat_id,
                    InstallationGroupBinding.is_active == True
                )
            ).where(
                InstallationObject.is_active == True
            ).options(
                selectinload(InstallationObject.addresses)
            ).order_by(InstallationObject.created_at.desc())
            
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting installation objects for chat {chat_id}: {e}")
            return []
    
    async def delete_installation_object(self, object_id: str) -> bool:
        """Удаление объекта монтажа."""
        try:
            stmt = update(InstallationObject).where(
                InstallationObject.id == UUID(object_id)
            ).values(
                is_active=False,
                deleted_at=datetime.utcnow()
            )
            
            result = await self.session.execute(stmt)
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting installation object {object_id}: {e}")
            return False
    
    async def check_object_access(self, object_id: str, user_id: int) -> bool:
        """Проверка доступа пользователя к объекту монтажа."""
        try:
            # Проверяем через UserAccess
            stmt = select(UserAccess).where(
                UserAccess.object_type == 'installation',
                UserAccess.object_id == UUID(object_id),
                UserAccess.user_id == user_id,
                UserAccess.is_active == True
            )
            
            result = await self.session.execute(stmt)
            access = result.scalar_one_or_none()
            
            # Если нет записи в UserAccess, проверяем создателя
            if not access:
                stmt = select(InstallationObject).where(
                    InstallationObject.id == UUID(object_id),
                    InstallationObject.created_by == user_id,
                    InstallationObject.is_active == True
                )
                result = await self.session.execute(stmt)
                object_ = result.scalar_one_or_none()
                return object_ is not None
            
            return True
        except Exception as e:
            logger.error(f"Error checking object access {object_id} for user {user_id}: {e}")
            return False
    
    async def get_object_name(self, object_id: str) -> Optional[str]:
        """Получение названия объекта монтажа."""
        try:
            stmt = select(InstallationObject.full_name).where(
                InstallationObject.id == UUID(object_id)
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception:
            return None
    
    # ========== Адреса ==========
    
    async def save_address(self, address: InstallationAddress) -> InstallationAddress:
        """Сохранение адреса объекта."""
        try:
            self.session.add(address)
            await self.session.flush()
            await self.session.refresh(address)
            return address
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error saving address: {e}")
            raise
    
    async def get_addresses_by_object(self, object_id: str) -> List[InstallationAddress]:
        """Получение адресов объекта."""
        try:
            stmt = select(InstallationAddress).where(
                InstallationAddress.installation_object_id == UUID(object_id)
            ).order_by(InstallationAddress.order_index)
            
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting addresses for object {object_id}: {e}")
            return []
    
    # ========== Проекты ==========
    
    async def save_project(self, project: InstallationProject) -> InstallationProject:
        """Сохранение проекта."""
        try:
            self.session.add(project)
            await self.session.flush()
            await self.session.refresh(project)
            return project
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error saving project: {e}")
            raise
    
    async def get_project_by_id(self, project_id: str) -> Optional[InstallationProject]:
        """Получение проекта по ID."""
        try:
            stmt = select(InstallationProject).where(
                InstallationProject.id == UUID(project_id),
                InstallationProject.is_active == True
            )
            
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting project {project_id}: {e}")
            return None
    
    async def get_projects_by_object(self, object_id: str) -> List[InstallationProject]:
        """Получение проектов объекта."""
        try:
            stmt = select(InstallationProject).where(
                InstallationProject.installation_object_id == UUID(object_id),
                InstallationProject.is_active == True
            ).order_by(InstallationProject.order_number)
            
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting projects for object {object_id}: {e}")
            return []
    
    async def update_project(self, project_id: str, updates: Dict[str, Any]) -> Optional[InstallationProject]:
        """Обновление проекта."""
        try:
            # Сначала получаем проект
            project = await self.get_project_by_id(project_id)
            if not project:
                return None
            
            # Обновляем поля
            for key, value in updates.items():
                if hasattr(project, key):
                    setattr(project, key, value)
            
            project.updated_at = datetime.utcnow()
            await self.session.flush()
            await self.session.refresh(project)
            return project
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating project {project_id}: {e}")
            return None
    
    async def delete_project(self, project_id: str) -> bool:
        """Удаление проекта."""
        try:
            stmt = update(InstallationProject).where(
                InstallationProject.id == UUID(project_id)
            ).values(
                is_active=False,
                deleted_at=datetime.utcnow()
            )
            
            result = await self.session.execute(stmt)
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting project {project_id}: {e}")
            return False
    
    # ========== Материалы ==========
    
    async def save_material(self, material: InstallationMaterial) -> InstallationMaterial:
        """Сохранение материала."""
        try:
            self.session.add(material)
            await self.session.flush()
            await self.session.refresh(material)
            return material
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error saving material: {e}")
            raise
    
    async def get_material_by_id(self, material_id: str) -> Optional[InstallationMaterial]:
        """Получение материала по ID."""
        try:
            stmt = select(InstallationMaterial).where(
                InstallationMaterial.id == UUID(material_id),
                InstallationMaterial.is_active == True
            )
            
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting material {material_id}: {e}")
            return None
    
    async def get_materials_by_object(self, object_id: str) -> List[InstallationMaterial]:
        """Получение материалов объекта."""
        try:
            stmt = select(InstallationMaterial).where(
                InstallationMaterial.installation_object_id == UUID(object_id),
                InstallationMaterial.is_active == True
            ).order_by(InstallationMaterial.created_at)
            
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting materials for object {object_id}: {e}")
            return []
    
    async def update_material(self, material_id: str, updates: Dict[str, Any]) -> Optional[InstallationMaterial]:
        """Обновление материала."""
        try:
            material = await self.get_material_by_id(material_id)
            if not material:
                return None
            
            for key, value in updates.items():
                if hasattr(material, key):
                    setattr(material, key, value)
            
            material.updated_at = datetime.utcnow()
            await self.session.flush()
            await self.session.refresh(material)
            return material
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating material {material_id}: {e}")
            return None
    
    async def delete_material(self, material_id: str) -> bool:
        """Удаление материала."""
        try:
            stmt = update(InstallationMaterial).where(
                InstallationMaterial.id == UUID(material_id)
            ).values(
                is_active=False,
                deleted_at=datetime.utcnow()
            )
            
            result = await self.session.execute(stmt)
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting material {material_id}: {e}")
            return False
    
    # ========== Разделы материалов ==========
    
    async def save_material_section(self, section: InstallationMaterialSection) -> InstallationMaterialSection:
        """Сохранение раздела материалов."""
        try:
            self.session.add(section)
            await self.session.flush()
            await self.session.refresh(section)
            return section
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error saving material section: {e}")
            raise
    
    async def get_material_section_by_id(self, section_id: str) -> Optional[InstallationMaterialSection]:
        """Получение раздела материалов по ID."""
        try:
            stmt = select(InstallationMaterialSection).where(
                InstallationMaterialSection.id == UUID(section_id),
                InstallationMaterialSection.is_active == True
            ).options(
                selectinload(InstallationMaterialSection.material_allocations)
            )
            
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting material section {section_id}: {e}")
            return None
    
    async def get_material_sections_by_object(self, object_id: str) -> List[InstallationMaterialSection]:
        """Получение разделов материалов объекта."""
        try:
            stmt = select(InstallationMaterialSection).where(
                InstallationMaterialSection.installation_object_id == UUID(object_id),
                InstallationMaterialSection.is_active == True
            ).options(
                selectinload(InstallationMaterialSection.material_allocations)
            ).order_by(InstallationMaterialSection.created_at)
            
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting material sections for object {object_id}: {e}")
            return []
    
    # ========== Распределение материалов по разделам ==========
    
    async def save_material_allocation(self, allocation: InstallationMaterialQuantity) -> InstallationMaterialQuantity:
        """Сохранение распределения материала по разделу."""
        try:
            self.session.add(allocation)
            await self.session.flush()
            await self.session.refresh(allocation)
            return allocation
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error saving material allocation: {e}")
            raise
    
    async def get_material_allocation(self, material_id: str, section_id: str) -> Optional[InstallationMaterialQuantity]:
        """Получение распределения материала в разделе."""
        try:
            stmt = select(InstallationMaterialQuantity).where(
                InstallationMaterialQuantity.material_id == UUID(material_id),
                InstallationMaterialQuantity.material_section_id == UUID(section_id),
                InstallationMaterialQuantity.is_active == True
            )
            
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting material allocation for material {material_id} in section {section_id}: {e}")
            return None
    
    async def get_material_allocation_by_id(self, allocation_id: str) -> Optional[InstallationMaterialQuantity]:
        """Получение распределения по ID."""
        try:
            stmt = select(InstallationMaterialQuantity).where(
                InstallationMaterialQuantity.id == UUID(allocation_id),
                InstallationMaterialQuantity.is_active == True
            )
            
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting material allocation {allocation_id}: {e}")
            return None
    
    async def get_material_allocations(self, material_id: str) -> List[InstallationMaterialQuantity]:
        """Получение всех распределений материала."""
        try:
            stmt = select(InstallationMaterialQuantity).where(
                InstallationMaterialQuantity.material_id == UUID(material_id),
                InstallationMaterialQuantity.is_active == True
            )
            
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting material allocations for material {material_id}: {e}")
            return []
    
    async def get_material_allocations_by_section(self, section_id: str) -> List[InstallationMaterialQuantity]:
        """Получение распределений материалов в разделе."""
        try:
            stmt = select(InstallationMaterialQuantity).where(
                InstallationMaterialQuantity.material_section_id == UUID(section_id),
                InstallationMaterialQuantity.is_active == True
            ).options(
                selectinload(InstallationMaterialQuantity.material)
            ).order_by(InstallationMaterialQuantity.created_at)
            
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting material allocations for section {section_id}: {e}")
            return []
    
    async def delete_material_allocation(self, allocation_id: str) -> bool:
        """Удаление распределения материала."""
        try:
            stmt = update(InstallationMaterialQuantity).where(
                InstallationMaterialQuantity.id == UUID(allocation_id)
            ).values(
                is_active=False,
                deleted_at=datetime.utcnow()
            )
            
            result = await self.session.execute(stmt)
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting material allocation {allocation_id}: {e}")
            return False
    
    # ========== Учет монтажа ==========
    
    async def save_montage(self, montage: InstallationMontage) -> InstallationMontage:
        """Сохранение учета монтажа."""
        try:
            self.session.add(montage)
            await self.session.flush()
            await self.session.refresh(montage)
            return montage
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error saving montage: {e}")
            raise
    
    async def get_montage_by_allocation(self, allocation_id: str) -> Optional[InstallationMontage]:
        """Получение учета монтажа по распределению."""
        try:
            stmt = select(InstallationMontage).where(
                InstallationMontage.material_allocation_id == UUID(allocation_id),
                InstallationMontage.is_active == True
            )
            
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting montage for allocation {allocation_id}: {e}")
            return None
    
    async def delete_montage(self, montage_id: str) -> bool:
        """Удаление учета монтажа."""
        try:
            stmt = update(InstallationMontage).where(
                InstallationMontage.id == UUID(montage_id)
            ).values(
                is_active=False,
                deleted_at=datetime.utcnow()
            )
            
            result = await self.session.execute(stmt)
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting montage {montage_id}: {e}")
            return False
    
    # ========== Поставки ==========
    
    async def save_supply(self, supply: InstallationSupply) -> InstallationSupply:
        """Сохранение поставки."""
        try:
            self.session.add(supply)
            await self.session.flush()
            await self.session.refresh(supply)
            return supply
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error saving supply: {e}")
            raise
    
    async def get_supply_by_id(self, supply_id: str) -> Optional[InstallationSupply]:
        """Получение поставки по ID."""
        try:
            stmt = select(InstallationSupply).where(
                InstallationSupply.id == UUID(supply_id),
                InstallationSupply.is_active == True
            )
            
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting supply {supply_id}: {e}")
            return None
    
    async def get_supplies_by_object(self, object_id: str) -> List[InstallationSupply]:
        """Получение поставок объекта."""
        try:
            stmt = select(InstallationSupply).where(
                InstallationSupply.installation_object_id == UUID(object_id),
                InstallationSupply.is_active == True
            ).order_by(InstallationSupply.delivery_date)
            
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting supplies for object {object_id}: {e}")
            return []
    
    async def get_supplies_by_date_range(self, object_id: str, start_date: date, end_date: date) -> List[InstallationSupply]:
        """Получение поставок в диапазоне дат."""
        try:
            stmt = select(InstallationSupply).where(
                InstallationSupply.installation_object_id == UUID(object_id),
                InstallationSupply.delivery_date.between(start_date, end_date),
                InstallationSupply.is_active == True
            ).order_by(InstallationSupply.delivery_date)
            
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting supplies by date range for object {object_id}: {e}")
            return []
    
    async def update_supply(self, supply_id: str, updates: Dict[str, Any]) -> Optional[InstallationSupply]:
        """Обновление поставки."""
        try:
            supply = await self.get_supply_by_id(supply_id)
            if not supply:
                return None
            
            for key, value in updates.items():
                if hasattr(supply, key):
                    setattr(supply, key, value)
            
            supply.updated_at = datetime.utcnow()
            await self.session.flush()
            await self.session.refresh(supply)
            return supply
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating supply {supply_id}: {e}")
            return None
    
    async def delete_supply(self, supply_id: str) -> bool:
        """Удаление поставки."""
        try:
            stmt = update(InstallationSupply).where(
                InstallationSupply.id == UUID(supply_id)
            ).values(
                is_active=False,
                deleted_at=datetime.utcnow()
            )
            
            result = await self.session.execute(stmt)
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting supply {supply_id}: {e}")
            return False
    
    # ========== Изменения ==========
    
    async def save_change(self, change: InstallationChange) -> InstallationChange:
        """Сохранение изменения."""
        try:
            self.session.add(change)
            await self.session.flush()
            await self.session.refresh(change)
            return change
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error saving change: {e}")
            raise
    
    async def get_change_by_id(self, change_id: str) -> Optional[InstallationChange]:
        """Получение изменения по ID."""
        try:
            stmt = select(InstallationChange).where(
                InstallationChange.id == UUID(change_id),
                InstallationChange.is_active == True
            )
            
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting change {change_id}: {e}")
            return None
    
    async def get_changes_by_object(self, object_id: str) -> List[InstallationChange]:
        """Получение изменений объекта."""
        try:
            stmt = select(InstallationChange).where(
                InstallationChange.installation_object_id == UUID(object_id),
                InstallationChange.is_active == True
            ).order_by(InstallationChange.created_at.desc())
            
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting changes for object {object_id}: {e}")
            return []
    
    async def update_change(self, change_id: str, updates: Dict[str, Any]) -> Optional[InstallationChange]:
        """Обновление изменения."""
        try:
            change = await self.get_change_by_id(change_id)
            if not change:
                return None
            
            for key, value in updates.items():
                if hasattr(change, key):
                    setattr(change, key, value)
            
            change.updated_at = datetime.utcnow()
            await self.session.flush()
            await self.session.refresh(change)
            return change
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating change {change_id}: {e}")
            return None
    
    async def delete_change(self, change_id: str) -> bool:
        """Удаление изменения."""
        try:
            stmt = update(InstallationChange).where(
                InstallationChange.id == UUID(change_id)
            ).values(
                is_active=False,
                deleted_at=datetime.utcnow()
            )
            
            result = await self.session.execute(stmt)
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting change {change_id}: {e}")
            return False
    
    # ========== Документы ==========
    
    async def save_document(self, document: InstallationDocument) -> InstallationDocument:
        """Сохранение документа."""
        try:
            self.session.add(document)
            await self.session.flush()
            await self.session.refresh(document)
            return document
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error saving document: {e}")
            raise
    
    async def get_document_by_id(self, document_id: str) -> Optional[InstallationDocument]:
        """Получение документа по ID."""
        try:
            stmt = select(InstallationDocument).where(
                InstallationDocument.id == UUID(document_id),
                InstallationDocument.is_active == True
            )
            
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting document {document_id}: {e}")
            return None
    
    async def get_documents_by_type(self, object_id: str, document_type: str) -> List[InstallationDocument]:
        """Получение документов определенного типа."""
        try:
            stmt = select(InstallationDocument).where(
                InstallationDocument.installation_object_id == UUID(object_id),
                InstallationDocument.document_type == document_type,
                InstallationDocument.is_active == True
            ).order_by(InstallationDocument.document_date.desc())
            
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting documents of type {document_type} for object {object_id}: {e}")
            return []
    
    async def update_document(self, document_id: str, updates: Dict[str, Any]) -> Optional[InstallationDocument]:
        """Обновление документа."""
        try:
            document = await self.get_document_by_id(document_id)
            if not document:
                return None
            
            for key, value in updates.items():
                if hasattr(document, key):
                    setattr(document, key, value)
            
            document.updated_at = datetime.utcnow()
            await self.session.flush()
            await self.session.refresh(document)
            return document
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating document {document_id}: {e}")
            return None
    
    async def delete_document(self, document_id: str) -> bool:
        """Удаление документа."""
        try:
            stmt = update(InstallationDocument).where(
                InstallationDocument.id == UUID(document_id)
            ).values(
                is_active=False,
                deleted_at=datetime.utcnow()
            )
            
            result = await self.session.execute(stmt)
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting document {document_id}: {e}")
            return False
    
    # ========== Привязки к группам ==========
    
    async def save_group_binding(self, binding: InstallationGroupBinding) -> InstallationGroupBinding:
        """Сохранение привязки к группе."""
        try:
            self.session.add(binding)
            await self.session.flush()
            await self.session.refresh(binding)
            return binding
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error saving group binding: {e}")
            raise
    
    async def delete_group_binding(self, object_id: str, chat_id: int) -> bool:
        """Удаление привязки к группе."""
        try:
            stmt = update(InstallationGroupBinding).where(
                InstallationGroupBinding.installation_object_id == UUID(object_id),
                InstallationGroupBinding.chat_id == chat_id
            ).values(
                is_active=False,
                deactivated_at=datetime.utcnow()
            )
            
            result = await self.session.execute(stmt)
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting group binding for object {object_id} in chat {chat_id}: {e}")
            return False