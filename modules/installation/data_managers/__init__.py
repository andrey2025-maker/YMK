"""
Менеджеры подразделов модуля монтажа.
Реализует бизнес-логику работы с проектами, материалами, поставками и другими подразделами.
"""

from .material_manager import MaterialManager
from .montage_manager import MontageManager
from .supply_manager import SupplyManager
from .change_manager import ChangeManager
from .id_manager import IDManager
from .document_manager import InstallationDocumentManager
from .project_manager import ProjectManager


class InstallationDataManagers:
    """Контейнер менеджеров подразделов монтажа."""
    
    def __init__(self, context):
        self.context = context
        self.project_manager = ProjectManager(context)
        self.material_manager = MaterialManager(context)
        self.montage_manager = MontageManager(context)
        self.supply_manager = SupplyManager(context)
        self.change_manager = ChangeManager(context)
        self.id_manager = IDManager(context)
        self.document_manager = InstallationDocumentManager(context)
    
    async def initialize(self):
        """Инициализация всех менеджеров."""
        # При необходимости можно добавить инициализацию
        return self


# Экспорт для удобного импорта
__all__ = [
    'InstallationDataManagers',
    'ProjectManager',
    'MaterialManager',
    'MontageManager',
    'SupplyManager',
    'ChangeManager',
    'IDManager',
    'InstallationDocumentManager',
]