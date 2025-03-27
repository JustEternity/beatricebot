import logging
from typing import List, Optional, Union, Dict
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

async def format_profile_text(user_data: Dict, crypto=None) -> str:
    """Форматирует текст профиля пользователя"""
    try:
        # Проверяем, что crypto не None
        if crypto is None:
            logger.warning("Crypto object is None in format_profile_text")
            decrypted_data = user_data.copy()  # Используем данные как есть
        else:
            # Расшифровываем данные
            decrypted_data = user_data.copy()
            encrypted_fields = ['name', 'about', 'interests', 'city']
            for field in encrypted_fields:
                if field in user_data and user_data[field] is not None:
                    try:
                        decrypted_data[field] = crypto.decrypt(user_data[field])
                    except Exception as e:
                        logger.error(f"Error decrypting field {field}: {e}")
                        decrypted_data[field] = user_data[field]  # Используем зашифрованные данные
        
        # Форматируем текст профиля
        profile_text = f"👤 <b>{decrypted_data.get('name', 'Без имени')}</b>, {decrypted_data.get('age', '?')} лет\n"
        profile_text += f"🏙️ {decrypted_data.get('city', 'Город не указан')}\n\n"
        
        if decrypted_data.get('about'):
            profile_text += f"<b>О себе:</b>\n{decrypted_data.get('about')}\n\n"
        
        if decrypted_data.get('interests'):
            profile_text += f"<b>Интересы:</b>\n{decrypted_data.get('interests')}\n\n"
        
        if decrypted_data.get('gender') is not None:
            gender = "Мужской" if decrypted_data.get('gender') == 0 else "Женский"
            profile_text += f"<b>Пол:</b> {gender}\n"
        
        if decrypted_data.get('looking_for') is not None:
            looking_for = "Мужчин" if decrypted_data.get('looking_for') == 0 else "Женщин"
            profile_text += f"<b>Ищет:</b> {looking_for}\n"
        
        return profile_text
    except Exception as e:
        logger.error(f"Error formatting profile text: {e}")
        return "Ошибка при отображении профиля"


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