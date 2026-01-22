from .data_managers import ServiceDataManagers
from .validators import (
    ServiceValidatorFactory,
    RegionCreateData,
    ServiceObjectCreateData,
    ProblemCreateData,
    MaintenanceCreateData,
    EquipmentCreateData,
    LetterCreateData,
    AdditionalDocumentData,
    AddressValidator,
    ContractValidator,
    DateRangeValidator,
    validate_object_name,
    validate_yes_no_answer,
    validate_note_text
)
from .region_manager import RegionManager
from .object_manager import ServiceObjectManager


class ServiceModule:
    def __init__(self, context):
        self.context = context
        self.data_managers = ServiceDataManagers(context)
        self.validators = ServiceValidatorFactory()
        self.region_manager = RegionManager(context)
        self.object_manager = ServiceObjectManager(context)
    
    async def initialize(self):
        await self.data_managers.initialize()
        return self
    
    def get_validator(self, data_type: str):
        """
        Получить валидатор для указанного типа данных.
        
        Args:
            data_type: Тип данных ('region', 'object', 'problem', etc.)
            
        Returns:
            Класс валидатора
        """
        return self.validators.get_validator(data_type)
    
    def validate_data(self, data_type: str, data: dict):
        """
        Валидировать данные для указанного типа.
        
        Args:
            data_type: Тип данных
            data: Словарь с данными
            
        Returns:
            Кортеж (успех, валидированные данные, сообщение об ошибке)
        """
        return ServiceValidatorFactory.validate(data_type, data)


# Экспорт для удобного импорта из других модулей
__all__ = [
    'ServiceModule',
    'ServiceValidatorFactory',
    'RegionCreateData',
    'ServiceObjectCreateData',
    'ProblemCreateData',
    'MaintenanceCreateData',
    'EquipmentCreateData',
    'LetterCreateData',
    'AdditionalDocumentData',
    'AddressValidator',
    'ContractValidator',
    'DateRangeValidator',
    'validate_object_name',
    'validate_yes_no_answer',
    'validate_note_text',
    'RegionManager',
    'ServiceObjectManager',
]