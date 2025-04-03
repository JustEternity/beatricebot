from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.services.database import Database
from bot.handlers.algorithm import delete_message_safely, show_like_profile
from bot.keyboards.menus import get_like_notification_keyboard, back_to_menu_button, main_menu

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
            # Получаем информацию о пользователе, которого лайкнули
            user_profile = await db.get_user_profile(user_id)

            # Используем имя по умолчанию
            user_name = "пользователь"

            # Если профиль найден, пытаемся получить имя
            if user_profile and 'name' in user_profile:
                encrypted_name = user_profile['name']
                logger.debug(f"Зашифрованное имя: {encrypted_name}, тип: {type(encrypted_name)}")

                if crypto:
                    try:
                        if isinstance(encrypted_name, bytes):
                            decrypted_name = crypto.decrypt(encrypted_name)
                            logger.debug(f"Расшифрованное имя (bytes): {decrypted_name}")

                            # Проверяем тип расшифрованного имени
                            if isinstance(decrypted_name, bytes):
                                user_name = decrypted_name.decode('utf-8')
                            else:
                                # Если уже строка, используем как есть
                                user_name = decrypted_name
                        else:
                            logger.warning(f"Неизвестный тип имени: {type(encrypted_name)}")
                            user_name = str(encrypted_name)
                    except Exception as e:
                        logger.error(f"Ошибка при расшифровке имени: {e}", exc_info=True)
                        user_name = "пользователь"
                else:
                    logger.warning("Объект crypto не доступен")
                    user_name = str(encrypted_name)

            # Логируем для отладки
            logger.debug(f"Расшифрованное имя пользователя: {user_name}")

            # Создаем матч, если его еще нет
            match_exists = await db.check_match_exists(current_user_id, user_id)
            if not match_exists:
                match_id = await db.create_match(current_user_id, user_id)
                logger.info(f"Создан новый матч с ID: {match_id}")

            # Это взаимный лайк - отправляем уведомление с именем пользователя
            await callback.message.answer(
                f"❤️ У вас взаимная симпатия с {user_name}! Теперь вы можете начать общение.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=f"💬 Начать чат с {user_name}", url=f"tg://user?id={user_id}")],
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
                ])
            )

            # Отправляем уведомление другому пользователю, если это новый матч
            if not match_exists:
                try:
                    # Получаем информацию о текущем пользователе
                    current_user_profile = await db.get_user_profile(current_user_id)
                    current_user_name = "пользователь"

                    if current_user_profile and 'name' in current_user_profile and crypto:
                        try:
                            encrypted_name = current_user_profile['name']
                            if isinstance(encrypted_name, bytes):
                                decrypted_name = crypto.decrypt(encrypted_name)
                                if isinstance(decrypted_name, bytes):
                                    current_user_name = decrypted_name.decode('utf-8')
                                else:
                                    current_user_name = decrypted_name
                        except Exception as e:
                            logger.error(f"Ошибка при расшифровке имени текущего пользователя: {e}")

                    # Отправляем уведомление другому пользователю
                    await callback.bot.send_message(
                        chat_id=user_id,
                        text=f"❤️ У вас новая взаимная симпатия с {current_user_name}! Теперь вы можете начать общение.",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text=f"💬 Начать чат с {current_user_name}", url=f"tg://user?id={current_user_id}")],
                            [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu")]
                        ])
                    )
                    logger.info(f"Отправлено уведомление о матче пользователю {user_id}")
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления о матче: {e}", exc_info=True)
        else:
            # Отправляем уведомление о лайке другому пользователю
            try:
                # Создаем клавиатуру с кнопками
                keyboard = keyboard = get_like_notification_keyboard(current_user_id)

                # Отправляем уведомление
                await callback.bot.send_message(
                    chat_id=user_id,
                    text=f"❤️ <b>Кто-то проявил к вам симпатию!</b>\n\n"
                         f"Хотите посмотреть профиль?",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                logger.info(f"Отправлено уведомление о лайке пользователю {user_id}")
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления о лайке: {e}", exc_info=True)

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
async def like_back_handler(callback: CallbackQuery, state: FSMContext, db: Database):
    try:
        # Получаем ID пользователя из callback_data
        user_id = int(callback.data.split(':')[1])

        # Добавляем лайк в базу данных
        like_result = await db.add_like(callback.from_user.id, user_id)

        # Проверяем, есть ли взаимные лайки (должны быть, так как это ответный лайк)
        mutual_like = await db.check_mutual_like(callback.from_user.id, user_id)

        # Удаляем текущее сообщение
        try:
            await callback.message.delete()
        except Exception as e:
            logger.error(f"Ошибка удаления сообщения: {e}")

        # Отправляем уведомления о взаимной симпатии
        if mutual_like:
            logger.info(f"Отправка уведомлений о взаимной симпатии между {callback.from_user.id} и {user_id}")

            # Получаем профили пользователей
            user1_profile = await db.get_user_profile(callback.from_user.id)
            user2_profile = await db.get_user_profile(user_id)

            if user1_profile and user2_profile:
                # Отправляем уведомление первому пользователю
                await callback.message.answer(
                    f"🎉 У вас взаимная симпатия с {user2_profile['name']}!\n"
                    f"Теперь вы можете начать общение: @{user2_profile.get('username', 'пользователь')}"
                )

                # Отправляем уведомление второму пользователю
                try:
                    await callback.bot.send_message(
                        user_id,
                        f"🎉 У вас взаимная симпатия с {user1_profile['name']}!\n"
                        f"Теперь вы можете начать общение: @{user1_profile.get('username', 'пользователь')}"
                    )
                    logger.info("Уведомления о взаимной симпатии успешно отправлены")
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления о взаимной симпатии: {e}")

    except Exception as e:
        logger.error(f"Ошибка при обработке ответного лайка: {e}", exc_info=True)
        await callback.answer("Произошла ошибка. Пожалуйста, попробуйте еще раз.")

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
        
        # Проверяем, есть ли взаимный лайк
        is_mutual = await db.check_mutual_like(callback.from_user.id, sender_id)
        
        if is_mutual:
            await callback.answer("✨ У вас взаимная симпатия! ✨", show_alert=True)
        else:
            await callback.answer("Лайк отправлен! Ждем ответа 😊")
        
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
