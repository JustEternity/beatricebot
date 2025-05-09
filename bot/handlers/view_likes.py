from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.services.database import Database
from bot.services.utils import format_profile_text
from bot.keyboards.menus import back_to_menu_button
from bot.handlers.algorithm import delete_message_safely
from bot.keyboards.menus import create_like_keyboard
from bot.services.profile_service import show_like_profile, show_profile
from bot.handlers.profile_edit import remove_keyboard_if_exists
import logging

logger = logging.getLogger(__name__)
router = Router()

# Обработчик для просмотра лайков
@router.callback_query(F.data == "view_likes")
async def view_likes_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    await remove_keyboard_if_exists(callback.message)
    try:
        # Получаем только непросмотренные лайки
        likes = await db.get_user_likes(callback.from_user.id, only_unviewed=True)
        logger.debug(f"Получено {len(likes)} непросмотренных лайков для пользователя {callback.from_user.id}")
        
        if not likes:
            # Если нет непросмотренных лайков, сообщаем об этом
            await callback.message.edit_text(
                "У вас нет непросмотренных лайков.",
                reply_markup=back_to_menu_button()
            )
            return
        
        # Сохраняем список лайков в состоянии
        await state.update_data(likes_list=likes, current_like_index=0)
        
        # Удаляем текущее сообщение, чтобы избежать ошибок при редактировании
        await delete_message_safely(callback.message)
        
        # Показываем первый лайк - исправленный вызов
        await show_like_profile(callback.message, callback.from_user.id, state, db, crypto)
    except Exception as e:
        logger.error(f"Ошибка в view_likes_handler: {e}", exc_info=True)
        # Пробуем отправить новое сообщение вместо редактирования
        try:
            await callback.message.answer(
                "Произошла ошибка при загрузке лайков.",
                reply_markup=back_to_menu_button()
            )
        except Exception:
            await callback.answer("Произошла ошибка. Вернитесь в главное меню.")

# Обработчик просмотра профиля пользователя, который поставил лайк
@router.callback_query(F.data.startswith("view_liker:"))
async def view_liker_profile_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    await callback.answer()
    # Извлекаем ID пользователя из callback_data
    liker_id = int(callback.data.split(":")[1])
    
    # Получаем данные пользователя
    user_profile = await db.get_user_profile(liker_id)
    user_photos = await db.get_user_photos(liker_id)
    
    if not user_profile:
        await callback.message.answer("Профиль пользователя не найден.")
        return
    
    # Проверяем наличие фотографий
    if not user_photos or len(user_photos) == 0:
        await callback.message.answer("У этого пользователя нет фотографий в профиле.")
        return
    
    # Логируем для отладки
    logger.debug(f"User profile keys: {list(user_profile.keys())}")
    
    # Всегда получаем актуальный статус верификации
    is_verified, _, _ = await db.check_verify(liker_id)
    user_profile['is_verified'] = is_verified
    logger.debug(f"Updated is_verified status: {is_verified}")
    
    # Создаем клавиатуру с кнопками действий
    keyboard = create_like_keyboard(liker_id)
    
    try:
        # Удаляем текущее сообщение
        await delete_message_safely(callback.message)
        
        # Используем общую функцию для отображения профиля
        await show_profile(
            callback.message,
            callback.from_user.id,
            user_profile,
            user_photos,
            keyboard,
            crypto
        )
    except Exception as e:
        logger.error(f"Ошибка при показе профиля лайка: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка при загрузке профиля.",
            reply_markup=back_to_menu_button()
        )

# Показывает список не просмотренных лайков
@router.callback_query(F.data == "my_likes")
async def show_my_likes(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    try:
        # Получаем только НЕпросмотренные лайки
        likes = await db.get_user_likes(callback.from_user.id, only_unviewed=True)
        
        if not likes:
            await callback.message.edit_text(
                "У вас пока нет новых лайков.",
                reply_markup=back_to_menu_button()
            )
            await callback.answer()
            return
        
        # Сохраняем список лайков в состоянии
        await state.update_data(likes_list=likes, current_like_index=0)
        
        # Показываем первый профиль - исправленный вызов
        await show_like_profile(callback.message, callback.from_user.id, state, db, crypto)
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при получении лайков: {e}")
        await callback.message.edit_text(
            "Произошла ошибка при загрузке лайков. Попробуйте позже.",
            reply_markup=back_to_menu_button()
        )
        await callback.answer("Произошла ошибка", show_alert=True)

# Обработчик перехода к следующему лайку
@router.callback_query(F.data == "next_like")
async def next_like_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    await callback.answer()
    try:
        # Получаем данные из состояния
        data = await state.get_data()
        likes_list = data.get("likes_list", [])
        current_index = data.get("current_like_index", 0)
        
        if current_index >= len(likes_list) - 1:
            # Больше лайков нет
            await callback.message.answer(
                "Больше лайков нет.",
                reply_markup=back_to_menu_button()
            )
            return
        
        # Увеличиваем индекс
        await state.update_data(current_like_index=current_index + 1)
        
        # Удаляем текущее сообщение
        await delete_message_safely(callback.message)
        
        # Показываем следующий профиль - исправленный вызов
        await show_like_profile(callback.message, callback.from_user.id, state, db, crypto)
    except Exception as e:
        logger.error(f"Ошибка при переходе к следующему лайку: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка. Пожалуйста, попробуйте позже.",
            reply_markup=back_to_menu_button()
        )

# Обработчик кнопки "Назад" при просмотре лайков из раздела 'Лайки'
@router.callback_query(F.data == "prev_like")
async def prev_like_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    await callback.answer()
    # Получаем текущие данные из состояния
    state_data = await state.get_data()
    current_index = state_data.get("current_like_index", 0)
    
    # Проверяем, есть ли предыдущий лайк
    if current_index > 0:
        # Уменьшаем индекс
        await state.update_data(current_like_index=current_index - 1)
        
        # Удаляем текущее сообщение
        await delete_message_safely(callback.message)
        
        # Показываем предыдущий профиль - исправленный вызов
        await show_like_profile(callback.message, callback.from_user.id, state, db, crypto)
    else:
        await callback.answer("Это первый лайк в списке", show_alert=True)
