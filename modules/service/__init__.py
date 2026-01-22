from .data_managers import ServiceDataManagers

class ServiceModule:
    def __init__(self, context):
        self.context = context
        self.data_managers = ServiceDataManagers(context)
    
    async def initialize(self):
        await self.data_managers.initialize()
        return self