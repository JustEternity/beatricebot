from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from bot.services.database import Database
from bot.services.utils import format_profile_text
from bot.keyboards.menus import compatible_navigation_keyboard, back_to_menu_button, create_like_keyboard
import logging

logger = logging.getLogger(__name__)
router = Router()

# Общая функция для отображения профиля пользователя
async def show_profile(
    message: Message, 
    user_id: int, 
    profile_data: dict, 
    photos: list, 
    keyboard, 
    crypto=None, 
    additional_text=""
):
    try:
        # Форматируем профиль
        profile_text = await format_profile_text(profile_data, crypto)
        
        # Добавляем дополнительный текст, если он есть
        if additional_text:
            profile_text += additional_text
        
        # Отправляем сообщение с профилем
        if photos and len(photos) > 0:
            sent_message = await message.bot.send_photo(
                chat_id=user_id,
                photo=photos[0],
                caption=profile_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            sent_message = await message.bot.send_message(
                chat_id=user_id,
                text=profile_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        
        return sent_message
    except Exception as e:
        logger.error(f"Ошибка при показе профиля: {e}", exc_info=True)
        error_msg = await message.bot.send_message(
            chat_id=user_id,
            text="Произошла ошибка при загрузке профиля.",
            reply_markup=back_to_menu_button()
        )
        return error_msg

def decrypt_city(crypto, encrypted_city):
    """Дешифрует город, если он зашифрован"""
    if not encrypted_city or encrypted_city == 'Не задан' or not crypto:
        return encrypted_city
    
    try:
        # Проверяем, является ли город зашифрованным
        if isinstance(encrypted_city, bytes) or (
                isinstance(encrypted_city, str) and 
                (encrypted_city.startswith('b\'gAAAAA') or encrypted_city.startswith('gAAAAA'))):
            return crypto.decrypt(encrypted_city)
        return encrypted_city
    except Exception as e:
        logger.error(f"Ошибка при дешифровании города: {e}")
        return encrypted_city

# Показывает профиль пользователя, который поставил лайк
async def show_like_profile(message: Message, user_id: int, state: FSMContext, db: Database, crypto=None):
    try:
        # Получаем данные из состояния
        state_data = await state.get_data()
        current_index = state_data.get("current_like_index", 0)
        likes_list = state_data.get("likes_list", [])
        logger.debug(f"show_like_profile: index={current_index}, total likes={len(likes_list)}")
        
        # Если список лайков пуст
        if not likes_list:
            await message.bot.send_message(
                chat_id=user_id,
                text="У вас нет непросмотренных лайков.",
                reply_markup=back_to_menu_button()
            )
            return
        
        # Проверяем, не вышли ли за границы списка
        if current_index >= len(likes_list):
            current_index = 0
        
        # Получаем текущий лайк
        current_like = likes_list[current_index]
        logger.debug(f"Текущий лайк: {current_like}")
        
        # Определяем ID пользователя, который поставил лайк
        liker_id = current_like.get('from_user_id') or current_like.get('sendertelegramid')
        if not liker_id:
            # Логируем структуру для отладки
            logger.error(f"Неизвестная структура лайка: {current_like}")
            await message.bot.send_message(
                chat_id=user_id,
                text="Ошибка при загрузке профиля. Пожалуйста, попробуйте позже.",
                reply_markup=back_to_menu_button()
            )
            return
        
        logger.debug(f"ID пользователя, поставившего лайк: {liker_id}")
        
        # Получаем профиль пользователя
        user_profile = await db.get_user_profile(liker_id)
        user_photos = await db.get_user_photos(liker_id)
        
        if not user_profile:
            # Если профиль не найден, удаляем его из списка и показываем следующий
            likes_list.pop(current_index)
            await state.update_data(likes_list=likes_list)
            if not likes_list:
                await message.bot.send_message(
                    chat_id=user_id,
                    text="У вас больше нет непросмотренных лайков.",
                    reply_markup=back_to_menu_button()
                )
                return
            await show_like_profile(message, user_id, state, db, crypto)
            return
        
        # Логируем для отладки
        logger.debug(f"User profile keys: {list(user_profile.keys())}")
        logger.debug(f"is_verified in profile: {user_profile.get('is_verified')}")
        
        # Если по какой-то причине информация о верификации отсутствует, получаем ее отдельно
        if 'is_verified' not in user_profile:
            is_verified = await db.check_verify(liker_id)
            user_profile['is_verified'] = is_verified
            logger.debug(f"Added is_verified from check_verify: {is_verified}")
        
        # Создаем клавиатуру
        keyboard = create_like_keyboard(liker_id)
        
        # Отправляем сообщение с профилем
        sent_message = await show_profile(message, user_id, user_profile, user_photos, keyboard, crypto)
        
        # Сохраняем ID сообщения для возможного удаления в будущем
        await state.update_data(last_like_message_id=sent_message.message_id)
        
    except Exception as e:
        logger.error(f"Ошибка при показе профиля лайка: {e}", exc_info=True)
        await message.bot.send_message(
            chat_id=user_id,
            text="Произошла ошибка при загрузке профиля.",
            reply_markup=back_to_menu_button()
        )

# Функция для отображения совместимого пользователя
async def show_compatible_user(message: Message, state: FSMContext, db: Database, crypto=None):
    try:
        # Получаем данные из состояния
        state_data = await state.get_data()
        current_index = state_data.get("current_compatible_index", 0)
        compatible_users = state_data.get("compatible_users", [])
        last_messages = state_data.get("last_profile_messages", [])
        
        # Очищаем предыдущие сообщения
        for msg_id in last_messages:
            try:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=msg_id)
            except Exception as e:
                logger.error(f"Ошибка удаления сообщения {msg_id}: {e}")
        
        # Если список анкет пуст
        if not compatible_users:
            no_profiles_msg = await message.answer(
                "😔 Совместимых пользователей не найдено.\n"
                "Попробуйте изменить фильтры или проверьте позже.",
                reply_markup=back_to_menu_button()
            )
            await state.update_data(last_profile_messages=[no_profiles_msg.message_id])
            return
        
        # Корректируем индекс при выходе за границы
        if current_index >= len(compatible_users):
            current_index = 0
        elif current_index < 0:
            current_index = len(compatible_users) - 1
        
        # Получаем текущую анкету
        current_user = compatible_users[current_index]
        user_profile = current_user['profile']
        compatibility = current_user['compatibility']
        
        # Проверяем верификацию пользователя
        user_id = user_profile['telegramid']
        is_verified = await db.check_verify(user_id)
        user_profile['is_verified'] = is_verified
        
        # Дешифруем город в профиле, если он зашифрован
        if 'location' in user_profile:
            user_profile['city'] = decrypt_city(crypto, user_profile['location'])
        
        # Создаём адаптивную клавиатуру
        keyboard = compatible_navigation_keyboard(
            user_id=user_profile['telegramid'],
            is_first=current_index == 0,
            is_last=current_index == len(compatible_users) - 1,
            is_initial=False  # Всегда передаем False
        )
        
        # Добавляем информацию о совместимости
        additional_text = f"<b>Совместимость:</b> {compatibility}%"
        
        # Отправляем сообщение с профилем
        photos = user_profile.get('photos', [])
        sent_message = await show_profile(
            message, 
            message.chat.id,
            user_profile,
            photos,
            keyboard,
            crypto,
            additional_text
        )
        
        # Обновляем состояние
        await state.update_data(
            last_profile_messages=[sent_message.message_id],
            current_compatible_index=current_index,
            current_profile_id=user_profile['telegramid'],
            is_initial_view=False  # Сбрасываем флаг после первого показа
        )
    except Exception as e:
        logger.error(f"Критическая ошибка в show_compatible_user: {e}", exc_info=True)
        error_msg = await message.answer(
            "⚠️ Произошла непредвиденная ошибка при загрузке анкеты.",
            reply_markup=back_to_menu_button()
        )
        await state.update_data(last_profile_messages=[error_msg.message_id])