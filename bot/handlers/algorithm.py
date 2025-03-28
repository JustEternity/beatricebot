from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.models.states import RegistrationStates
from bot.services.database import Database
from bot.services.algorithm_sovmest import CompatibilityService
from bot.services.encryption import CryptoService
from bot.services.utils import delete_previous_messages, format_profile_text, create_media_group
from bot.keyboards.menus import compatible_navigation_keyboard, back_to_menu_button

import logging
logger = logging.getLogger(__name__)

router = Router()

# Обработчик для поиска совместимых пользователей
@router.callback_query(F.data == "find_compatible")
async def find_compatible_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    await delete_previous_messages(callback.message, state)
    
    # Проверяем, прошел ли пользователь тест
    has_answers = await db.check_existing_answers(callback.from_user.id)
    
    if not has_answers:
        await callback.message.edit_text(
            "⚠️ Для поиска совместимых пользователей необходимо пройти тест.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📝 Пройти тест", callback_data="take_test")],
                [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu")]
            ])
        )
        await callback.answer()
        return
    
    # Сообщаем о начале поиска
    await callback.message.edit_text("🔍 Ищем совместимых пользователей...")
    
    # Создаем сервис совместимости
    compatibility_service = CompatibilityService(db)
    
    # Ищем совместимых пользователей
    high_compatible_users, low_compatible_users = await compatibility_service.find_compatible_users(
        user_id=callback.from_user.id,
        limit=5,  # Ограничиваем количество результатов
        min_score=50.0  # Минимальный порог совместимости
    )
    
    # Объединяем списки - сначала высокая совместимость, потом низкая
    all_compatible_users = high_compatible_users + low_compatible_users
    
    if not all_compatible_users:
        await callback.message.edit_text(
            "😔 К сожалению, совместимых пользователей не найдено.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu")]
            ])
        )
        await callback.answer()
        return
    
    # Сохраняем результаты в состоянии
    await state.update_data(compatible_users=all_compatible_users, current_compatible_index=0)
    
    # Показываем первого совместимого пользователя
    await show_compatible_user(callback.message, state, db, crypto)
    await callback.answer()

# Функция для отображения совместимого пользователя
async def show_compatible_user(message: Message, state: FSMContext, db: Database, crypto=None):
    """Показывает совместимого пользователя"""
    try:
        # Получаем данные текущего пользователя
        user_id = message.chat.id
        
        # Получаем данные о состоянии
        state_data = await state.get_data()
        current_index = state_data.get("current_compatible_index", 0)
        compatible_users = state_data.get("compatible_users", [])
        
        # Если список пуст, сообщаем об этом
        if not compatible_users:
            await message.answer(
                "К сожалению, совместимых пользователей не найдено. "
                "Попробуйте позже или измените свои ответы в тесте.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
                ])
            )
            return
        
        # Проверяем, не вышли ли мы за пределы списка
        if current_index >= len(compatible_users):
            current_index = 0
            await state.update_data(current_compatible_index=current_index)
        
        # Получаем данные текущего совместимого пользователя
        current_user = compatible_users[current_index]
        
        # Логируем тип и структуру данных для отладки
        logger.debug(f"Compatible user data type: {type(current_user)}")
        logger.debug(f"Compatible user data: {current_user}")
        
        # Обрабатываем данные в зависимости от их типа
        if isinstance(current_user, tuple):
            # Если это кортеж, предполагаем структуру (user_id, compatibility)
            user_id_compatible = current_user[0]
            compatibility = current_user[1]
            # Получаем профиль пользователя из базы данных
            user_data = await db.get_user_data(user_id_compatible)
        elif isinstance(current_user, dict):
            # Если это словарь, используем ключи
            user_data = current_user.get("profile", {})
            compatibility = current_user.get("compatibility", 0)
            user_id_compatible = user_data.get("telegramid", 0)
        else:
            # Неизвестный формат данных
            logger.error(f"Unknown format of compatible user data: {type(current_user)}")
            await message.answer(
                "Произошла ошибка при обработке данных пользователя. Пожалуйста, попробуйте позже.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
                ])
            )
            return
        
        # Форматируем текст профиля
        profile_text = await format_profile_text(user_data, crypto)
        
        logger.debug(f"User gender in profile: {user_data.get('gender')}, type: {type(user_data.get('gender'))}")

        # Добавляем информацию о совместимости
        profile_text += f"<b>Совместимость:</b> {compatibility}%"
        
        # Получаем фото пользователя
        photo_data = user_data.get("photos", [])
        
        # Исправляем обработку фото - проверяем тип данных
        if photo_data and isinstance(photo_data, list):
            # Если это список строк (file_id)
            if photo_data and isinstance(photo_data[0], str):
                photo_id = photo_data[0]
            # Если это список словарей
            elif photo_data and isinstance(photo_data[0], dict) and "photo_id" in photo_data[0]:
                photo_id = photo_data[0]["photo_id"]
            else:
                photo_id = None
        else:
            photo_id = None
        
        # Создаем клавиатуру
        keyboard = [
            [
                InlineKeyboardButton(text="👎 Пропустить", callback_data="next_compatible"),
                InlineKeyboardButton(text="👍 Лайк", callback_data=f"write_to_{user_id_compatible}")
            ],
            [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu")]
        ]
        
        # Отправляем сообщение с фото или без
        if photo_id:
            await message.answer_photo(
                photo=photo_id,
                caption=profile_text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
                parse_mode="HTML"
            )
        else:
            await message.answer(
                profile_text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
                parse_mode="HTML"
            )
        
    except Exception as e:
        logger.error(f"Error showing compatible user: {e}")
        logger.exception(e)
        await message.answer(
            "Произошла ошибка при поиске совместимых пользователей. Пожалуйста, попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
            ])
        )

# Обработчик для перехода к следующему совместимому пользователю
@router.callback_query(F.data == "next_compatible")
async def next_compatible_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    await callback.answer()
    
    # Получаем текущий индекс
    state_data = await state.get_data()
    current_index = state_data.get("current_compatible_index", 0) + 1
    compatible_users = state_data.get("compatible_users", [])
    
    # Если дошли до конца списка, начинаем сначала
    if current_index >= len(compatible_users):
        current_index = 0
    
    # Обновляем индекс в состоянии
    await state.update_data(current_compatible_index=current_index)
    
    # Показываем следующего пользователя
    await show_compatible_user(callback.message, state, db, crypto)

# Обработчик для лайка пользователя
@router.callback_query(F.data.startswith("like_user_"))
async def like_user_handler(callback: CallbackQuery, state: FSMContext, db: Database):
    # Извлекаем ID пользователя из callback_data
    liked_user_id = int(callback.data.split("_")[2])
    
    # Сохраняем лайк в базе данных
    await db.add_like(callback.from_user.id, liked_user_id)
    
    # Проверяем взаимность
    is_mutual = await db.check_mutual_like(callback.from_user.id, liked_user_id)
    
    if is_mutual:
        # Если лайк взаимный, сообщаем об этом
        await callback.answer("❤️ Взаимная симпатия! Теперь вы можете начать общение.", show_alert=True)
        
        # Можно добавить логику для создания чата или отправки контактов
        # ...
    else:
        await callback.answer("👍 Вы отметили этого пользователя. Если он также отметит вас, вы получите уведомление.", show_alert=True)
    
    # Переходим к следующему пользователю
    data = await state.get_data()
    current_index = data.get('current_compatible_index', 0)
    
    # Удаляем предыдущие сообщения с фотографиями
    photo_message_ids = data.get('compatible_photo_message_ids', [])
    keyboard_message_id = data.get('compatible_keyboard_message_id')
    
    for msg_id in photo_message_ids:
        try:
            await callback.bot.delete_message(callback.message.chat.id, msg_id)
        except Exception as e:
            logger.error(f"Ошибка при удалении сообщения: {e}")
    
    if keyboard_message_id:
        try:
            await callback.bot.delete_message(callback.message.chat.id, keyboard_message_id)
        except Exception as e:
            logger.error(f"Ошибка при удалении сообщения с клавиатурой: {e}")
    
    # Увеличиваем индекс
    await state.update_data(current_compatible_index=current_index + 1)
    
    # Показываем следующего пользователя
    await show_compatible_user(callback.message, state, db)