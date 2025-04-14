from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.services.database import Database
from bot.handlers.algorithm import delete_message_safely
from bot.keyboards.menus import back_to_menu_button, main_menu, complaint_categories
from bot.services.profile_service import show_like_profile
from bot.services.notifications import send_like_notification, send_match_notification
import logging

logger = logging.getLogger(__name__)
router = Router()

# Обработчик жалобы на пользователя
@router.callback_query(F.data.startswith("compl_user_"))
async def complaint_user_handler(callback: CallbackQuery, state: FSMContext, db:Database):
    try:
        # Извлекаем ID пользователя из callback_data
        parts = callback.data.split("_")
        user_id = int(parts[2])
        current_user_id = callback.from_user.id
        logger.debug(f"Обработка жалобы от {current_user_id} к {user_id}")
        await state.update_data(reported_user=user_id)
        await callback.message.answer(text="Укажите причину жалобы:", reply_markup=complaint_categories())
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при обработке жалобы: {e}", exc_info=True)
        # В случае ошибки, пытаемся вернуть пользователя в главное меню
        try:
            await callback.message.answer(
                "Произошла ошибка при обработке вашего действия. Пожалуйста, вернитесь в главное меню.",
                reply_markup=back_to_menu_button()
            )
        except Exception:
            pass

@router.callback_query(F.data.startswith("incorrect_"))
async def complaint_user_handler(callback: CallbackQuery, state: FSMContext, db:Database, crypto=None):
    try:
        state_data = await state.get_data()
        compatible_users = state_data.get("compatible_users", [])
        current_index = state_data.get("current_compatible_index", 0)
        rep_user = state_data.get("reported_user")
        await db.save_complaint(sender=callback.from_user.id, reporteduser=rep_user, reason=callback.data.split("_")[1])
        await callback.message.answer(text="Спасибо, ваша жалоба принята")

        # ДОБАВЛЕНО: Переходим к следующей анкете, если она есть
        if compatible_users and current_index < len(compatible_users) - 1:
            # Увеличиваем индекс
            await state.update_data(current_compatible_index=current_index + 1)
            # Показываем следующую анкету
            from bot.services.profile_service import show_compatible_user
            await show_compatible_user(callback.message, state, db, crypto)
        else:
            # Если анкет больше нет, отправляем сообщение
            await callback.message.answer(
                "Вы просмотрели все доступные анкеты. Возвращайтесь позже!",
                reply_markup=back_to_menu_button()
            )

    except Exception as e:
        logger.error(f"Ошибка при обработке жалобы: {e}", exc_info=True)
        # В случае ошибки, пытаемся вернуть пользователя в главное меню
        try:
            await callback.message.answer(
                "Произошла ошибка при обработке вашего действия. Пожалуйста, вернитесь в главное меню.",
                reply_markup=back_to_menu_button()
            )
        except Exception:
            pass

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
        
        # Добавляем лайк (уведомления отправляются внутри add_like)
        like_id = await db.add_like(current_user_id, user_id, callback.bot, crypto)
        logger.debug(f"Результат добавления лайка: {like_id}")
        
        # ОТЛАДКА: Проверяем таблицу лайков после возможного добавления
        await db.debug_likes_table(current_user_id, user_id)
        
        # Удаляем текущее сообщение
        await delete_message_safely(callback.message)
        
        # ДОБАВЛЕНО: Получаем текущие данные из состояния
        state_data = await state.get_data()
        compatible_users = state_data.get("compatible_users", [])
        current_index = state_data.get("current_compatible_index", 0)
        
        # ДОБАВЛЕНО: Переходим к следующей анкете, если она есть
        if compatible_users and current_index < len(compatible_users) - 1:
            # Увеличиваем индекс
            await state.update_data(current_compatible_index=current_index + 1)
            # Показываем следующую анкету
            from bot.services.profile_service import show_compatible_user
            await show_compatible_user(callback.message, state, db, crypto)
        else:
            # Если анкет больше нет, отправляем сообщение
            await callback.message.answer(
                "Вы просмотрели все доступные анкеты. Возвращайтесь позже!",
                reply_markup=back_to_menu_button()
            )
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
        logger.debug(f"Обработка ответного лайка от {current_user_id} к {user_id}")
        
        # ОТЛАДКА: Проверяем таблицу лайков
        await db.debug_likes_table(current_user_id, user_id)
        
        # Проверяем, существует ли уже лайк
        like_exists = await db.check_like_exists(current_user_id, user_id)
        
        # Добавляем лайк (уведомления отправляются внутри add_like)
        like_result = await db.add_like(current_user_id, user_id, callback.bot, crypto)
        logger.debug(f"Результат добавления лайка: {like_result}")
        
        # ОТЛАДКА: Проверяем таблицу лайков после возможного добавления
        await db.debug_likes_table(current_user_id, user_id)
        
        # Удаляем текущее сообщение
        try:
            await callback.message.delete()
        except Exception as e:
            logger.error(f"Ошибка удаления сообщения: {e}")
        
        # ДОБАВЛЕНО: Получаем следующий лайк для просмотра
        likes = await db.get_user_likes(current_user_id, only_unviewed=True)
        if likes:
            # Сохраняем список лайков в состоянии
            await state.update_data(likes_list=likes, current_like_index=0)
            # Показываем следующий профиль
            await show_like_profile(callback.message, current_user_id, state, db, crypto)
        else:
            # Если лайков больше нет, возвращаемся в меню
            await callback.message.answer(
                "Вы просмотрели все лайки!",
                reply_markup=back_to_menu_button()
            )
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
# Обработчик дизлайка пользователя
@router.callback_query(F.data.startswith("dislike_user:"))
async def dislike_user_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    try:
        # Получаем ID пользователя из callback_data
        user_id = int(callback.data.split(':')[1])
        current_user_id = callback.from_user.id
        
        # Отмечаем лайк как просмотренный
        await db.mark_likes_as_viewed(user_id, current_user_id)
        
        # Удаляем лайки между пользователями
        await db.delete_mutual_likes(user_id, current_user_id)
        
        # ОТЛАДКА: Проверяем таблицу лайков после удаления
        await db.debug_likes_table(current_user_id, user_id)
        
        # Удаляем текущее сообщение
        await callback.message.delete()
        
        # Получаем оставшиеся непросмотренные лайки напрямую из базы данных
        likes = await db.get_user_likes(current_user_id, only_unviewed=True)
        
        # Обновляем состояние с новым списком лайков
        await state.update_data(likes_list=likes, current_like_index=0)
        
        # Проверяем, есть ли еще непросмотренные лайки
        if likes:
            # Если есть, показываем следующий профиль
            await show_like_profile(callback.message, current_user_id, state, db, crypto)
        else:
            # Если больше нет непросмотренных лайков, сообщаем об этом
            await callback.message.answer(
                "У вас больше нет непросмотренных лайков.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
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
    # await db.mark_like_as_viewed(liker_id, callback.from_user.id)
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
async def mutual_like_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
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
        sender_id = current_like.get("from_user_id") or current_like.get("sendertelegramid")
        
        if not sender_id:
            logger.error(f"Неизвестная структура лайка: {current_like}")
            await callback.answer("Ошибка при обработке лайка")
            return
        
        logger.debug(f"Обработка взаимной симпатии от {callback.from_user.id} к {sender_id}")
        
        # ОТЛАДКА: Проверяем таблицу лайков
        await db.debug_likes_table(callback.from_user.id, sender_id)
        
        # Добавляем лайк (уведомления отправляются внутри add_like)
        like_result = await db.add_like(callback.from_user.id, sender_id, callback.bot, crypto)
        logger.debug(f"Результат добавления лайка: {like_result}")
        
        # ОТЛАДКА: Проверяем таблицу лайков после возможного добавления
        await db.debug_likes_table(callback.from_user.id, sender_id)
        
        # Удаляем текущее сообщение
        await delete_message_safely(callback.message)
        
        # Удаляем просмотренную анкету из состояния
        await state.update_data(likes_list=likes_list)
        
        # Показываем следующую анкету или возвращаем в меню
        if likes_list:
            await state.update_data(current_like_index=0)
            await show_like_profile(callback.message, callback.from_user.id, state, db, crypto)
        else:
            # Получаем количество непросмотренных лайков
            likes_count = await db.get_unviewed_likes_count(callback.from_user.id)
            await callback.message.answer(
                "🔹 Главное меню 🔹",
                reply_markup=main_menu(likes_count)
            )
    except Exception as e:
        logger.error(f"Ошибка при обработке взаимной симпатии: {e}", exc_info=True)
        await callback.answer("Произошла ошибка. Пожалуйста, попробуйте еще раз.")
        try:
            await callback.message.answer(
                "Произошла ошибка при обработке вашего действия. Пожалуйста, вернитесь в главное меню.",
                reply_markup=back_to_menu_button()
            )
        except Exception:
            pass