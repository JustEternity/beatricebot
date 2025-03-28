from typing import Any, Callable, Dict, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from aiogram import Dispatcher

class DependencyInjectionMiddleware(BaseMiddleware):
    def __init__(self, dispatcher: Dispatcher):
        super().__init__()
        self.dispatcher = dispatcher

    async def __call__(self, handler, event, data):
        for key, value in self.dispatcher.workflow_data.items():
            data[key] = value
        return await handler(event, data)