"""
Модуль фильтров для работы с состояниями FSM.
Позволяет проверять текущее состояние пользователя.
"""
from typing import Any, Dict, Optional, Union
from aiogram.filters import BaseFilter, StateFilter as AiogramStateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from core.context import AppContext


class StateFilter(BaseFilter):
    """
    Базовый фильтр для проверки состояния FSM.
    
    Args:
        state: Состояние или список состояний для проверки
        negate: Если True, проверяет что состояние НЕ равно указанному
    """
    
    def __init__(self, state: Union[State, list[State], None] = None, negate: bool = False):
        self.state = state
        self.negate = negate
    
    async def __call__(self, update: Message | CallbackQuery, context: AppContext) -> bool:
        """
        Проверяет состояние пользователя.
        
        Args:
            update: Объект сообщения или callback query
            context: Контекст приложения
            
        Returns:
            bool: True если состояние соответствует условию
        """
        from aiogram import Bot
        from aiogram.fsm.storage.base import StorageKey
        
        user_id = update.from_user.id
        chat_id = update.chat.id if isinstance(update, Message) else update.message.chat.id
        
        # Создаем ключ для хранилища состояний
        storage_key = StorageKey(
            chat_id=chat_id,
            user_id=user_id,
            bot_id=context.bot.id
        )
        
        # Получаем текущее состояние из хранилища
        state_data = await context.bot.session.storage.get_data(storage_key)
        current_state = state_data.get('state') if state_data else None
        
        if not self.state:
            # Если состояние не указано, проверяем любое состояние
            result = current_state is not None
        else:
            # Проверяем конкретное состояние
            if isinstance(self.state, list):
                # Проверяем список состояний
                result = current_state in [s.state if hasattr(s, 'state') else s for s in self.state]
            else:
                # Проверяем одно состояние
                state_value = self.state.state if hasattr(self.state, 'state') else self.state
                result = current_state == state_value
        
        # Инвертируем результат если требуется negate
        if self.negate:
            result = not result
        
        return result


class InState(StateFilter):
    """
    Фильтр для проверки, что пользователь находится в указанном состоянии.
    
    Args:
        state: Состояние или список состояний
    """
    
    def __init__(self, state: Union[State, list[State]]):
        super().__init__(state=state, negate=False)


class NotInState(StateFilter):
    """
    Фильтр для проверки, что пользователь НЕ находится в указанном состоянии.
    
    Args:
        state: Состояние или список состояний
    """
    
    def __init__(self, state: Union[State, list[State]]):
        super().__init__(state=state, negate=True)


class FSMNotActive(StateFilter):
    """
    Фильтр для проверки, что у пользователя нет активного FSM состояния.
    Используется для блокировки команд во время активных сценариев.
    """
    
    def __init__(self):
        super().__init__(state=None, negate=True)


class FSMActive(StateFilter):
    """
    Фильтр для проверки, что у пользователя есть активное FSM состояние.
    """
    
    def __init__(self):
        super().__init__(state=None, negate=False)


class InAnyState(StateFilter):
    """
    Фильтр для проверки, что пользователь находится в любом состоянии.
    """
    
    def __init__(self):
        super().__init__(state=None, negate=False)