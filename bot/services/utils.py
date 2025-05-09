import logging
from datetime import datetime, timedelta
from typing import List, Optional, Union, Dict
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

async def delete_previous_messages(message, state):
    """Удаляет предыдущие сообщения бота"""
    try:
        data = await state.get_data()
        
        # Проверяем все возможные ключи, где могут храниться ID сообщений
        message_keys = ['message_ids', 'last_profile_messages', 'last_like_message_ids']
        all_message_ids = []
        
        # Собираем все ID сообщений из разных ключей
        for key in message_keys:
            ids = data.get(key, [])
            if ids:
                all_message_ids.extend(ids)
                # Очищаем список сообщений в состоянии
                await state.update_data({key: []})
        
        logger.debug(f"Найдено сообщений для удаления: {len(all_message_ids)}")
        print(f"Сообщения для удаления: {all_message_ids}")
        
        if not all_message_ids:
            return
            
        # Удаляем сообщения
        deleted_count = 0
        for msg_id in all_message_ids:
            try:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=msg_id)
                deleted_count += 1
            except Exception as e:
                # Логируем ошибку только на уровне DEBUG
                logger.debug(f"Не удалось удалить сообщение {msg_id}: {e}")
                
        logger.debug(f"Удалено {deleted_count}/{len(all_message_ids)} сообщений")
        
    except Exception as e:
        logger.debug(f"Ошибка в delete_previous_messages: {e}")


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
        # Логируем только базовую информацию без полных данных
        logger.debug(f"Formatting profile with keys: {list(user_data.keys())}")
        logger.debug(f"is_verified value: {user_data.get('is_verified')}")

        # Проверяем, что crypto не None
        if crypto is None:
            logger.warning("Crypto object is None in format_profile_text")
            decrypted_data = user_data.copy()  # Используем данные как есть
        else:
            # Расшифровываем данные
            decrypted_data = user_data.copy()

            # Определяем поля, которые могут быть зашифрованы
            encrypted_fields = ['name', 'about', 'interests', 'city', 'location', 'profiledescription', 'description']

            for field in encrypted_fields:
                if field in user_data and user_data[field] is not None:
                    try:
                        # Проверяем, является ли значение байтами (зашифрованными данными)
                        if isinstance(user_data[field], bytes):
                            decrypted_data[field] = crypto.decrypt(user_data[field])
                        else:
                            # Если это не байты, используем как есть
                            decrypted_data[field] = user_data[field]
                    except Exception as e:
                        logger.error(f"Error decrypting field {field}: {e}")
                        decrypted_data[field] = user_data[field]  # Используем исходные данные

        # Проверяем статус верификации
        is_verified = decrypted_data.get('is_verified', False)
        logger.debug(f"is_verified after decryption: {is_verified}")

        # Начинаем с информации о верификации
        profile_text = ""
        if is_verified:
            profile_text = "✅ Подтвержден\n"
        else:
            profile_text = "✖️ Не подтвержден\n"

        # Добавляем основную информацию о пользователе
        profile_text += f"👤 <b>{decrypted_data.get('name', 'Без имени')}</b>, {decrypted_data.get('age', '?')} лет\n"

        # Используем 'location' или 'city' в зависимости от того, что доступно
        location = decrypted_data.get('location') or decrypted_data.get('city', 'Город не указан')
        profile_text += f"🏙️ {location}\n\n"

        # Используем 'description' или 'about' в зависимости от того, что доступно
        description = decrypted_data.get('profiledescription') or decrypted_data.get('description')
        if description:
            profile_text += f"<b>О себе:</b>\n{description}\n\n"

        if decrypted_data.get('interests'):
            profile_text += f"<b>Интересы:</b>\n{decrypted_data.get('interests')}\n\n"

        # Преобразуем значение пола в читаемый формат
        gender_value = decrypted_data.get('gender')

        # Определяем отображаемый пол
        if gender_value == '0' or gender_value == 0:
            gender_display = "👨 Мужской"
        elif gender_value == '1' or gender_value == 1:
            gender_display = "👩 Женский"
        else:
            gender_display = "Не указан"

        profile_text += f"<b>Пол:</b> {gender_display}\n"

        # Преобразуем предпочтения в читаемый формат
        looking_for = decrypted_data.get('looking_for')
        if looking_for is not None:
            # Определяем предпочтения в читаемом формате
            if str(looking_for) == '0' or looking_for == 0:
                looking_for_display = "👨 Мужчин"
            else:
                looking_for_display = "👩 Женщин"

            profile_text += f"<b>Ищет:</b> {looking_for_display}\n"

        return profile_text
    except Exception as e:
        logger.error(f"Error formatting profile text: {e}")
        logger.exception(e)
        return "Ошибка при отображении профиля"

def standardize_gender(gender_value):
    """Стандартизирует значение пола к строковому формату: '0' - мужской, '1' - женский"""
    logger.debug(f"Standardizing gender value: {gender_value}, type: {type(gender_value)}")

    # Преобразуем к строчным буквам, если это строка
    if isinstance(gender_value, str):
        gender_value = gender_value.lower()

    # Проверяем различные варианты мужского пола
    if gender_value in [0, '0', 'male', 'м', 'мужской', 'мужчина', '👨 мужской']:
        return '0'  # Возвращаем строку
    else:
        return '1'  # Возвращаем строку

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

def utc_to_local(utc_dt: datetime) -> datetime:
    """Конвертирует UTC время в локальное (MSK, UTC+3)"""
    if utc_dt is None:
        return None
    return utc_dt + timedelta(hours=3)