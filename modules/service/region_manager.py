import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models.service import ServiceRegion
from storage.repositories.service_repository import ServiceRepository
from modules.file.archive_manager import ArchiveManager
from core.context import AppContext


class RegionManager:
    """Менеджер регионов обслуживания"""
    
    def __init__(self, context: AppContext):
        self.context = context
        self.repo = ServiceRepository(context.db)
        self.archive_manager = ArchiveManager(context)
    
    async def create_region(
        self,
        short_name: str,
        full_name: str,
        created_by: int
    ) -> ServiceRegion:
        """Создание нового региона обслуживания"""
        
        # Проверка на существование региона с таким short_name
        existing = await self.repo.get_region_by_short_name(short_name)
        if existing:
            raise ValueError(f"Регион с сокращением '{short_name}' уже существует")
        
        region = ServiceRegion(
            short_name=short_name.strip(),
            full_name=full_name.strip()
        )
        
        await self.repo.add_region(region)
        
        # Логирование создания
        await self._log_region_creation(region, created_by)
        
        return region
    
    async def get_all_regions(self) -> List[ServiceRegion]:
        """Получение всех регионов"""
        return await self.repo.get_all_regions()
    
    async def get_region_by_id(self, region_id: uuid.UUID) -> Optional[ServiceRegion]:
        """Получение региона по ID"""
        return await self.repo.get_region_by_id(region_id)
    
    async def get_region_by_short_name(self, short_name: str) -> Optional[ServiceRegion]:
        """Получение региона по короткому имени"""
        return await self.repo.get_region_by_short_name(short_name)
    
    async def update_region(
        self,
        region_id: uuid.UUID,
        updates: Dict[str, Any],
        updated_by: int
    ) -> ServiceRegion:
        """Обновление данных региона"""
        
        region = await self.get_region_by_id(region_id)
        if not region:
            raise ValueError(f"Регион с ID {region_id} не найден")
        
        old_data = {
            'short_name': region.short_name,
            'full_name': region.full_name
        }
        
        # Применяем обновления
        for key, value in updates.items():
            if hasattr(region, key):
                setattr(region, key, value)
        
        region.updated_at = datetime.utcnow()
        await self.repo.session.commit()
        
        # Логирование изменений
        await self._log_region_update(region, old_data, updated_by)
        
        return region
    
    async def delete_region(self, region_id: uuid.UUID, deleted_by: int) -> bool:
        """Удаление региона с архивацией"""
        
        region = await self.get_region_by_id(region_id)
        if not region:
            return False
        
        # Архивирование данных региона
        archive_data = {
            'region': region.to_dict(),
            'objects': [obj.to_dict() for obj in region.objects],
            'deleted_at': datetime.utcnow().isoformat(),
            'deleted_by': deleted_by
        }
        
        await self.archive_manager.archive_data(
            data=archive_data,
            category='service_region_deleted',
            description=f"Удален регион {region.short_name}"
        )
        
        # Удаление из БД
        await self.repo.delete_region(region_id)
        
        # Логирование удаления
        await self._log_region_deletion(region, deleted_by)
        
        return True
    
    async def _log_region_creation(self, region: ServiceRegion, created_by: int):
        """Логирование создания региона"""
        log_data = {
            'action': 'create_region',
            'region_id': str(region.id),
            'short_name': region.short_name,
            'full_name': region.full_name,
            'created_by': created_by,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        await self.archive_manager.send_to_log_channel(
            message=f"Создан регион: {region.short_name} - {region.full_name}",
            data=log_data
        )
    
    async def _log_region_update(self, region: ServiceRegion, old_data: Dict, updated_by: int):
        """Логирование обновления региона"""
        changes = []
        for key, old_value in old_data.items():
            new_value = getattr(region, key)
            if old_value != new_value:
                changes.append(f"{key}: {old_value} -> {new_value}")
        
        if changes:
            log_data = {
                'action': 'update_region',
                'region_id': str(region.id),
                'changes': changes,
                'updated_by': updated_by,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            await self.archive_manager.send_to_log_channel(
                message=f"Обновлен регион {region.short_name}: {', '.join(changes)}",
                data=log_data
            )
    
    async def _log_region_deletion(self, region: ServiceRegion, deleted_by: int):
        """Логирование удаления региона"""
        log_data = {
            'action': 'delete_region',
            'region_short_name': region.short_name,
            'region_full_name': region.full_name,
            'deleted_by': deleted_by,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        await self.archive_manager.send_to_log_channel(
            message=f"Удален регион: {region.short_name} - {region.full_name}",
            data=log_data
        )