from typing import Any, Callable, Dict, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from aiogram import Dispatcher

class DependencyInjectionMiddleware(BaseMiddleware):
    def __init__(self, dispatcher: Dispatcher):
        super().__init__()
        self.dispatcher = dispatcher

    async def __call__(self, handler, event, data):
        data.update(self.dispatcher.workflow_data)

        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id
            db = data.get('db')  # Предполагаем, что экземпляр БД доступен через DI

            if db and await db.is_user_blocked(user_id):
                # Отправляем сообщение о блокировке
                if isinstance(event, Message):
                    await event.answer("🚫 Вы заблокированы в этом боте!")
                elif isinstance(event, CallbackQuery):
                    await event.message.edit_text("🚫 Доступ запрещен!")
                    await event.answer()
                return

        return await handler(event, data)