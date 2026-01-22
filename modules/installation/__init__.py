"""
Модуль монтажа - управление объектами монтажа, проектами, материалами и поставками.
"""

from .object_manager import InstallationObjectManager
from .validators import InstallationValidatorFactory
from .data_managers import InstallationDataManagers


class InstallationModule:
    def __init__(self, context):
        self.context = context
        self.object_manager = InstallationObjectManager(context)
        self.validators = InstallationValidatorFactory()
        self.data_managers = InstallationDataManagers(context)
    
    async def initialize(self):
        """Инициализация модуля монтажа."""
        await self.data_managers.initialize()
        return self
    
    def get_validator(self, data_type: str):
        """
        Получить валидатор для указанного типа данных.
        
        Args:
            data_type: Тип данных ('installation_object', 'project', 'material', etc.)
            
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
        return InstallationValidatorFactory.validate(data_type, data)


# Экспорт для удобного импорта из других модулей
__all__ = [
    'InstallationModule',
    'InstallationObjectManager',
    'InstallationValidatorFactory',
    'InstallationDataManagers',
]