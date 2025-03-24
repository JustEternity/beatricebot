import logging
from typing import List, Optional, Union
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

async def delete_previous_messages(
    source: Union[Message, CallbackQuery],
    state: FSMContext
) -> None:
    """Удаляет предыдущие сообщения бота из чата"""
    try:
        data = await state.get_data()
        if 'last_menu_message_id' in data:
            await source.bot.delete_message(
                chat_id=source.from_user.id,
                message_id=data['last_menu_message_id']
            )
        if 'profile_photo_message_ids' in data:
            for msg_id in data['profile_photo_message_ids']:
                await source.bot.delete_message(
                    chat_id=source.from_user.id,
                    message_id=msg_id
                )
    except Exception as e:
        logger.error(f"Error deleting messages: {e}")

def validate_age(age_str: str) -> Optional[int]:
    """Проверяет валидность возраста"""
    try:
        age = int(age_str)
        return age if 18 <= age <= 100 else None
    except ValueError:
        return None

async def format_profile_text(user_data: dict, crypto) -> str:
    """Форматирует данные профиля в читаемый текст"""
    decrypted_data = {}
    for field in ['name', 'location', 'description']:
        if isinstance(user_data[field], bytes):
            decrypted_data[field] = crypto.decrypt(user_data[field])
        else:
            decrypted_data[field] = user_data[field]

    return (
        f"👤 *Имя:* {decrypted_data['name']}\n"
        f"🎂 *Возраст:* {user_data['age']}\n"
        f"🚻 *Пол:* {user_data['gender']}\n"
        f"📍 *Местоположение:* {decrypted_data['location']}\n"
        f"📝 *Описание:* {decrypted_data['description']}"
    )

def handle_errors(func):
    """Декоратор для обработки ошибок"""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            message = next((a for a in args if isinstance(a, (Message, CallbackQuery))), None)
            if message:
                await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")
    return wrapper

def create_media_group(photo_ids: List[str], caption: str) -> List[InputMediaPhoto]:
    """Создает медиагруппу для отправки фотографий"""
    if not photo_ids:
        return []

    return [
        InputMediaPhoto(
            media=photo_id,
            caption=caption if i == 0 else None,
            parse_mode="Markdown"
        ) for i, photo_id in enumerate(photo_ids)
    ]