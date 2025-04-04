from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.services.database import Database
from bot.handlers.algorithm import delete_message_safely
from bot.keyboards.menus import back_to_menu_button, main_menu
from bot.services.profile_service import show_like_profile
from bot.services.notifications import send_like_notification, send_match_notification
import logging

logger = logging.getLogger(__name__)
router = Router()

# Обработчик лайка пользователя
@router.callback_query(F.data.startswith("like_user_"))
async def like_user_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    try:
        # Извлекаем ID пользователя из callback_data
        parts = callback.data.split("_")
        user_id = int(parts[2])
        current_user_id = callback.from_user.id
        logger.debug(f"Обработка лайка от {current_user_id} к {user_id}")
        
        # ОТЛАДКА: Проверяем таблицу лайков
        await db.debug_likes_table(current_user_id, user_id)
        
        # Проверяем, существует ли уже лайк от текущего пользователя к другому
        like_exists = await db.check_like_exists(current_user_id, user_id)
        
        # Если лайк не существует, добавляем его
        if not like_exists:
            # ВАЖНО: передаем объект бота в метод add_like
            like_id = await db.add_like(current_user_id, user_id, callback.bot)
            logger.debug(f"Добавлен новый лайк с ID: {like_id}")
            
            # Проверяем, лайкнул ли другой пользователь текущего пользователя
            reverse_like_exists = await db.check_like_exists(user_id, current_user_id)
            logger.debug(f"Обратный лайк существует: {reverse_like_exists}")
        else:
            logger.debug(f"Лайк уже существует")
            
        # ОТЛАДКА: Проверяем таблицу лайков после возможного добавления
        await db.debug_likes_table(current_user_id, user_id)
        
        # Проверяем, есть ли взаимный лайк
        is_mutual = await db.check_mutual_like(current_user_id, user_id)
        logger.debug(f"Взаимный лайк: {is_mutual}")
        
        # Удаляем текущее сообщение
        await delete_message_safely(callback.message)
        
        if is_mutual:
            # Создаем матч, если его еще нет
            match_exists = await db.check_match_exists(current_user_id, user_id)
            if not match_exists:
                match_id = await db.create_match(current_user_id, user_id)
                logger.info(f"Создан новый матч с ID: {match_id}")
            
            # Отправляем уведомление о взаимной симпатии обоим пользователям через notifications.py
            await send_match_notification(callback.bot, current_user_id, user_id, db, crypto)
            
        else:
            # Отправляем уведомление о лайке другому пользователю через функцию из notifications.py
            await send_like_notification(callback.bot, current_user_id, user_id, db, crypto)
            
    except Exception as e:
        logger.error(f"Ошибка при обработке лайка: {e}", exc_info=True)
        await callback.answer("Произошла ошибка. Пожалуйста, попробуйте еще раз.")
        # В случае ошибки, пытаемся вернуть пользователя в главное меню
        try:
            await callback.message.answer(
                "Произошла ошибка при обработке вашего действия. Пожалуйста, вернитесь в главное меню.",
                reply_markup=back_to_menu_button()
            )
        except Exception:
            pass

# Обработчик ответного лайка (мэтча)
@router.callback_query(F.data.startswith("like_back:"))
async def like_back_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    try:
        # Получаем ID пользователя из callback_data
        user_id = int(callback.data.split(':')[1])
        current_user_id = callback.from_user.id
        
        # Добавляем лайк в базу данных
        like_result = await db.add_like(current_user_id, user_id)
        
        # Удаляем текущее сообщение
        try:
            await callback.message.delete()
        except Exception as e:
            logger.error(f"Ошибка удаления сообщения: {e}")
        
        # Проверяем, есть ли взаимные лайки (должны быть, так как это ответный лайк)
        mutual_like = await db.check_mutual_like(current_user_id, user_id)
        
        # Отправляем уведомления о взаимной симпатии через функцию из notifications.py
        if mutual_like:
            # Создаем матч, если его еще нет
            match_exists = await db.check_match_exists(current_user_id, user_id)
            if not match_exists:
                match_id = await db.create_match(current_user_id, user_id)
                logger.info(f"Создан новый матч с ID: {match_id}")
            
            # Отправляем уведомления обоим пользователям через notifications.py
            await send_match_notification(callback.bot, current_user_id, user_id, db, crypto)
            
    except Exception as e:
        logger.error(f"Ошибка при обработке ответного лайка: {e}", exc_info=True)
        await callback.answer("Произошла ошибка. Пожалуйста, попробуйте еще раз.")
        try:
            await callback.message.answer(
                "Произошла ошибка при обработке вашего действия. Пожалуйста, вернитесь в главное меню.",
                reply_markup=back_to_menu_button()
            )
        except Exception:
            pass

# Обработчик дизлайка пользователя
@router.callback_query(F.data.startswith("dislike_user:"))
async def dislike_user_handler(callback: CallbackQuery, state: FSMContext, db: Database):
    try:
        # Получаем ID пользователя из callback_data
        user_id = int(callback.data.split(':')[1])

        # Отмечаем лайк как просмотренный
        await db.mark_likes_as_viewed(user_id, callback.from_user.id)

        # Удаляем текущее сообщение
        await callback.message.delete()

        # Отправляем новое сообщение вместо редактирования
        await callback.message.answer(
            "Вы отклонили этого пользователя.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="Вернуться к просмотру лайков",
                    callback_data="view_likes"
                )],
                [InlineKeyboardButton(
                    text="◀️ Назад в главное меню",
                    callback_data="back_to_menu"
                )]
            ])
        )

    except Exception as e:
        logger.error(f"Ошибка при обработке дизлайка: {e}", exc_info=True)
        await callback.answer("Произошла ошибка. Пожалуйста, попробуйте еще раз.")

# Обработчик пропуска (просмотр) анкеты
@router.callback_query(F.data.startswith("skip_like:"))
async def skip_like_handler(callback: CallbackQuery, state: FSMContext, db: Database):
    liker_id = int(callback.data.split(":")[1])

    # Помечаем лайк как просмотренный
    await db.mark_like_as_viewed(liker_id, callback.from_user.id)

    # Получаем обновленный список лайков
    likes = await db.get_user_likes(callback.from_user.id)

    if likes:
        await state.update_data(likes_list=likes, current_like_index=0)
        await show_like_profile(callback.message, state, db)
    else:
        await callback.message.edit_text(
            "Вы просмотрели все лайки!",
            reply_markup=back_to_menu_button()
        )

    await callback.answer("Лайк пропущен")

# Обработчик кнопки 'Взаимная симпатия'
@router.callback_query(F.data == "mutual_like")
async def mutual_like_handler(callback: CallbackQuery, state: FSMContext, db: Database):
    try:
        logger.debug("Пользователь выбрал 'Взаимная симпатия'")
        state_data = await state.get_data()
        likes_list = state_data.get("likes_list", [])
        
        # Если список пустой — ничего не делаем
        if not likes_list:
            await callback.answer("Нет доступных лайков")
            return
        
        # Берем первый лайк из списка
        current_like = likes_list.pop(0)
        sender_id = current_like["from_user_id"]  # Используем правильное имя поля
        
        # Добавляем лайк и проверяем взаимность
        await db.add_like(callback.from_user.id, sender_id, callback.bot)
        
        # Удаляем просмотренную анкету из состояния
        await state.update_data(likes_list=likes_list)
        
        # Показываем следующую анкету или возвращаем в меню
        if likes_list:
            await show_like_profile(callback.message, callback.from_user.id, state, db)
        else:
            # Получаем количество непросмотренных лайков
            likes_count = await db.get_unviewed_likes_count(callback.from_user.id)
            
            await callback.message.edit_text(
                "🔹 Главное меню 🔹",
                reply_markup=main_menu(likes_count)
            )
    except Exception as e:
        logger.error(f"Ошибка при обработке взаимной симпатии: {e}", exc_info=True)
        await callback.answer("Произошла ошибка. Пожалуйста, попробуйте еще раз.")
