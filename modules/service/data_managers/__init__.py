"""
Пакет менеджеров подразделов обслуживания.
Содержит менеджеры для работы с проблемами, ТО, оборудованием и другими подразделами.
"""

from .problem_manager import ProblemManager
from .maintenance_manager import MaintenanceManager
from .equipment_manager import EquipmentManager
from .letter_manager import LetterManager
from .journal_manager import JournalManager
from .permit_manager import PermitManager
from .document_manager import DocumentManager


class ServiceDataManagers:
    """Фасад для менеджеров подразделов обслуживания."""
    
    def __init__(self, context):
        self.context = context
        self.problem_manager = ProblemManager(context)
        self.maintenance_manager = MaintenanceManager(context)
        self.equipment_manager = EquipmentManager(context)
        self.letter_manager = LetterManager(context)
        self.journal_manager = JournalManager(context)
        self.permit_manager = PermitManager(context)
        self.document_manager = DocumentManager(context)
    
    async def initialize(self):
        """Инициализирует все менеджеры подразделов."""
        # Инициализация при необходимости
        return self


__all__ = [
    'ServiceDataManagers',
    'ProblemManager',
    'MaintenanceManager',
    'EquipmentManager',
    'LetterManager',
    'JournalManager',
    'PermitManager',
    'DocumentManager'
]