from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.models.states import RegistrationStates
from bot.services.city_validator import city_validator
from bot.services.database import Database
from bot.services.algorithm_sovmest import CompatibilityService
from bot.services.encryption import CryptoService
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from bot.services.utils import delete_previous_messages, format_profile_text, create_media_group
from bot.keyboards.menus import compatible_navigation_keyboard, back_to_menu_button, subscription_keyboard, main_menu, create_like_keyboard
from bot.handlers.filtres import show_filters_menu
import logging

logger = logging.getLogger(__name__)
router = Router()

# Функция для безопасного удаления сообщений
async def delete_message_safely(message):
    """Безопасно удаляет сообщение с обработкой ошибок"""
    try:
        await message.delete()
    except Exception as e:
        logger.debug(f"Не удалось удалить сообщение: {e}")

async def send_like_notification(bot, from_user_id, to_user_id, db, crypto=None):
    """Отправляет уведомление о лайке пользователю"""
    try:
        logger.info(f"Начинаем отправку уведомления о лайке от {from_user_id} к {to_user_id}")

        mutual_like = await db.check_mutual_like(from_user_id, to_user_id)

        # Если есть взаимный лайк, отправляем уведомление о взаимной симпатии
        if mutual_like:
            logger.info(f"Обнаружена взаимная симпатия между {from_user_id} и {to_user_id}")
            return await send_match_notification(bot, from_user_id, to_user_id, db, crypto)

        # Если нет взаимного лайка, отправляем обычное уведомление о лайке
        # Создаем клавиатуру с двумя кнопками: "Посмотреть" и "В меню"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="👁️ Посмотреть",
                callback_data=f"view_liker:{from_user_id}"
            )],
            [InlineKeyboardButton(
                text="◀️ В главное меню",
                callback_data="back_to_menu"
            )]
        ])

        # Отправляем уведомление без указания конкретного пользователя
        try:
            message = await bot.send_message(
                chat_id=to_user_id,
                text=f"❤️ <b>Кто-то проявил к вам симпатию!</b>\n\n"
                     f"Хотите посмотреть профиль?",
                reply_markup=keyboard,
                parse_mode="HTML"
            )

            logger.info(f"Уведомление о лайке от {from_user_id} успешно отправлено пользователю {to_user_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения: {e}", exc_info=True)
            return False

    except TelegramAPIError as e:
        logger.error(f"Ошибка Telegram API при отправке уведомления о лайке: {e}")
        return False
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о лайке: {e}", exc_info=True)
        return False

async def send_match_notification(bot, user1_id, user2_id, db, crypto=None):
    """Отправляет уведомление о взаимной симпатии обоим пользователям"""
    logger.info(f"Отправка уведомлений о взаимной симпатии между {user1_id} и {user2_id}")

    try:
        # Получаем профили пользователей
        user1_profile = await db.get_user_profile(user1_id)
        user2_profile = await db.get_user_profile(user2_id)

        if not user1_profile or not user2_profile:
            logger.error(f"Не удалось получить профили пользователей {user1_id} и {user2_id}")
            return False

        # Получаем имена пользователей
        user1_name = user1_profile.get('name', user1_profile.get('username', 'Пользователь'))
        user2_name = user2_profile.get('name', user2_profile.get('username', 'Пользователь'))

        # Отправляем уведомление первому пользователю
        keyboard1 = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="💬 Начать общение",
                url=f"tg://user?id={user2_id}"
            )],
            [InlineKeyboardButton(
                text="◀️ В меню",
                callback_data="back_to_menu"
            )]
        ])

        await bot.send_message(
            chat_id=user1_id,
            text=f"✨ <b>У вас взаимная симпатия с {user2_name}!</b> ✨\n\n"
                 f"Теперь вы можете начать общение.",
            reply_markup=keyboard1,
            parse_mode="HTML"
        )

        # Отправляем уведомление второму пользователю
        keyboard2 = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="💬 Начать общение",
                url=f"tg://user?id={user1_id}"
            )],
            [InlineKeyboardButton(
                text="◀️ В меню",
                callback_data="back_to_menu"
            )]
        ])

        await bot.send_message(
            chat_id=user2_id,
            text=f"✨ <b>У вас взаимная симпатия с {user1_name}!</b> ✨\n\n"
                 f"Теперь вы можете начать общение.",
            reply_markup=keyboard2,
            parse_mode="HTML"
        )

        logger.info(f"Уведомления о взаимной симпатии успешно отправлены")
        return True

    except TelegramAPIError as e:
        logger.error(f"Ошибка Telegram API при отправке уведомления о взаимной симпатии: {e}")
        return False
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о взаимной симпатии: {e}")
        return False

@router.callback_query(F.data == "view_likes")
async def view_likes_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    """Обработчик для просмотра лайков"""
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
        try:
            await callback.message.delete()
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение: {e}")

        # Показываем первый лайк
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

@router.callback_query(F.data.startswith("view_liker:"))
async def view_liker_profile_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    """Обработчик просмотра профиля пользователя, который поставил лайк"""
    await callback.answer()

    # Извлекаем ID пользователя из callback_data
    liker_id = int(callback.data.split(":")[1])

    # Отмечаем лайк как просмотренный
    await db.mark_likes_as_viewed(liker_id, callback.from_user.id)

    # Получаем данные пользователя
    user_profile = await db.get_user_profile(liker_id)
    user_photos = await db.get_user_photos(liker_id)

    if not user_profile:
        await callback.message.answer("Профиль пользователя не найден.")
        return

    # Форматируем профиль для отображения
    profile_text = await format_profile_text(user_profile, crypto)

    # Создаем клавиатуру с кнопками действий
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="❤️ Нравится",
                callback_data=f"like_back:{liker_id}"
            ),
            InlineKeyboardButton(
                text="👎 Не нравится",
                callback_data=f"dislike_user:{liker_id}"
            )
        ],
        [InlineKeyboardButton(
            text="◀️ Назад в главное меню",
            callback_data="back_to_menu"
        )]
    ])

    try:
        # Если есть фотографии, отправляем с фото
        if user_photos and len(user_photos) > 0:
            # Если текущее сообщение имеет фото, редактируем его
            if callback.message.photo:
                await callback.message.edit_caption(
                    caption=profile_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                # Иначе отправляем новое сообщение с фото
                await callback.message.delete()
                await callback.message.answer_photo(
                    photo=user_photos[0],
                    caption=profile_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
        else:
            # Если фото нет, отправляем только текст
            await callback.message.edit_text(
                profile_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
    except Exception as e:
        logger.warning(f"Не удалось отредактировать сообщение: {e}")

        # Если не удалось отредактировать, отправляем новое сообщение
        if user_photos and len(user_photos) > 0:
            await callback.message.answer_photo(
                photo=user_photos[0],
                caption=profile_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await callback.message.answer(
                profile_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

async def show_like_profile(message: Message, user_id: int, state: FSMContext, db: Database, crypto=None):
    """Показывает профиль пользователя, который поставил лайк"""
    try:
        # Получаем данные из состояния
        state_data = await state.get_data()
        current_index = state_data.get("current_like_index", 0)
        likes_list = state_data.get("likes_list", [])

        logger.debug(f"show_like_profile: index={current_index}, total likes={len(likes_list)}")

        # Если список лайков пуст
        if not likes_list:
            await message.answer(
                "У вас нет непросмотренных лайков.",
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
        if 'from_user_id' in current_like:
            liker_id = current_like['from_user_id']
        elif 'sendertelegramid' in current_like:
            liker_id = current_like['sendertelegramid']
        else:
            # Логируем структуру для отладки
            logger.error(f"Неизвестная структура лайка: {current_like}")
            await message.answer(
                "Ошибка при загрузке профиля. Пожалуйста, попробуйте позже.",
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
                await message.answer(
                    "У вас больше нет непросмотренных лайков.",
                    reply_markup=back_to_menu_button()
                )
                return

            await show_like_profile(message, user_id, state, db, crypto)
            return

        # Форматируем профиль
        profile_text = await format_profile_text(user_profile, crypto)

        # Создаем клавиатуру
        keyboard = create_like_keyboard(liker_id)

        # Отправляем сообщение с профилем
        if user_photos and len(user_photos) > 0:
            sent_message = await message.bot.send_photo(
                chat_id=user_id,
                photo=user_photos[0],
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

        # Сохраняем ID сообщения для возможного удаления в будущем
        await state.update_data(last_like_message_id=sent_message.message_id)

        # Отмечаем лайк как просмотренный
        await db.mark_likes_as_viewed(liker_id, user_id)

    except Exception as e:
        logger.error(f"Ошибка при показе профиля лайка: {e}", exc_info=True)
        await message.bot.send_message(
            chat_id=user_id,
            text="Произошла ошибка при загрузке профиля.",
            reply_markup=back_to_menu_button()
        )

async def handle_error(message: Message, text: str):
    try:
        await message.answer(text, reply_markup=back_to_menu_button())
    except Exception as e:
        logger.error(f"Не удалось отправить сообщение об ошибке: {e}")

@router.callback_query(F.data.startswith("skip_like:"))
async def skip_like_handler(callback: CallbackQuery, state: FSMContext, db: Database):
    """Обработчик пропуска лайка"""
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

@router.callback_query(F.data == "mutual_like")
async def mutual_like_handler(callback: CallbackQuery, state: FSMContext, db: Database):
    """Обработчик кнопки 'Взаимная симпатия'."""
    logger.debug("Пользователь выбрал 'Взаимная симпатия'")

    state_data = await state.get_data()
    likes_list = state_data.get("likes_list", [])

    # Если список пустой — ничего не делаем
    if not likes_list:
        await callback.answer("Нет доступных лайков")
        return

    # Берем первый лайк из списка
    current_like = likes_list.pop(0)
    sender_id = current_like["sendertelegramid"]

    # Проверяем, ставил ли он тоже лайк пользователю
    mutual_like = await db.fetchval("""
        SELECT COUNT(*) FROM likes
        WHERE sendertelegramid = $1 AND receivertelegramid = $2
        AND likeviewedstatus = TRUE
    """, callback.from_user.id, sender_id)

    if mutual_like:
        await callback.answer("✨ У вас взаимная симпатия! ✨", show_alert=True)
    else:
        await callback.answer("Лайк отправлен! Ждем ответа 😊")

    # Удаляем просмотренную анкету из состояния
    await state.update_data(likes_list=likes_list)

    # Показываем следующую анкету или возвращаем в меню
    if likes_list:
        await show_like_profile(callback.message, state, db)
    else:
        likes_count = await db.fetchval(
            "SELECT COUNT(*) FROM likes WHERE receivertelegramid = $1 AND likeviewedstatus = FALSE",
            callback.from_user.id
        )
        await callback.message.edit_text(
            "🔹 Главное меню 🔹",
            reply_markup=main_menu(likes_count)
        )

@router.callback_query(F.data.startswith("like_user_"))
async def like_user_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    """Обработчик для лайка пользователя"""
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
            # Обычный лайк
            await callback.message.answer(
                "👍 Вы отметили этого пользователя. Если он также отметит вас, вы сможете начать общение.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
                ])
            )

            # Отправляем уведомление о лайке другому пользователю
            try:
                # Создаем клавиатуру с кнопками
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="👁️ Посмотреть",
                        callback_data=f"view_liker:{current_user_id}"
                    )],
                    [InlineKeyboardButton(
                        text="◀️ В главное меню",
                        callback_data="back_to_menu"
                    )]
                ])

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
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu")]
                ])
            )
        except Exception:
            pass

@router.callback_query(F.data.startswith("like_back:"))
async def like_back_handler(callback: CallbackQuery, state: FSMContext, db: Database):
    """Обработчик для ответного лайка"""
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

        # Отправляем сообщение о успешном лайке и предлагаем продолжить просмотр лайков
        await callback.message.answer(
            "Вы поставили лайк этому пользователю! Это взаимная симпатия! 🎉",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="Продолжить просмотр лайков",
                    callback_data="view_likes"
                )],
                [InlineKeyboardButton(
                    text="◀️ Назад в главное меню",
                    callback_data="back_to_menu"
                )]
            ])
        )

    except Exception as e:
        logger.error(f"Ошибка при обработке ответного лайка: {e}", exc_info=True)
        await callback.answer("Произошла ошибка. Пожалуйста, попробуйте еще раз.")

@router.callback_query(F.data.startswith("dislike_user:"))
async def dislike_user_handler(callback: CallbackQuery, state: FSMContext, db: Database):
    """Обработчик для дизлайка пользователя"""
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

# Обработчик для поиска совместимых пользователей
@router.callback_query(F.data == "find_compatible")
async def find_compatible_handler(callback: CallbackQuery, state: FSMContext, db: Database):
    """Обработчик поиска совместимых пользователей"""
    try:
        await callback.answer()

        # Проверяем, прошел ли пользователь тест
        has_answers = await db.check_existing_answers(callback.from_user.id)
        if not has_answers:
            msg = await callback.message.answer(
                "⚠️ Для поиска совместимых пользователей необходимо пройти тест.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📝 Пройти тест", callback_data="take_test")],
                    [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu")]
                ])
            )
            await state.update_data(last_message_id=msg.message_id)
            return

        await show_filters_menu(callback, state, db)

    except Exception as e:
        logger.error(f"Ошибка в find_compatible_handler: {e}")
        await callback.message.answer("⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.")

async def find_compatible_users(self, user_id: int, **filters):
    """Поиск совместимых пользователей с учетом приоритета"""
    try:
        # Получаем коэффициент приоритета текущего пользователя
        user_priority = await self.get_user_priority(user_id)

        # Базовый запрос
        query = """
            SELECT u.*,
                   (u.profileprioritycoefficient * $1) as search_priority
            FROM users u
            WHERE u.telegramid != $2
            AND u.accountstatus = 'active'
            AND u.moderationstatus = TRUE
        """

        params = [user_priority, user_id]

        # Добавляем фильтры
        if filters.get('city'):
            query += " AND u.city = $3"
            params.append(filters['city'])

        if filters.get('age_min') and filters.get('age_max'):
            query += " AND u.age BETWEEN $4 AND $5"
            params.extend([filters['age_min'], filters['age_max']])

        # Сортируем по приоритету
        query += " ORDER BY search_priority DESC, u.lastactiondate DESC"

        if filters.get('limit'):
            query += " LIMIT $6"
            params.append(filters['limit'])

        async with self.pool.acquire() as conn:
            users = await conn.fetch(query, *params)

        return [dict(user) for user in users]

    except Exception as e:
        logger.error(f"Error finding compatible users: {e}")
        return []

async def check_expired_services(self):
    """Проверяет и деактивирует просроченные услуги"""
    try:
        async with self.pool.acquire() as conn:
            # Находим просроченные услуги
            expired = await conn.fetch(
                "SELECT usertelegramid FROM purchasedservices "
                "WHERE serviceenddate <= NOW() AND paymentstatus = TRUE"
            )

            if not expired:
                return 0

            # Деактивируем их
            await conn.execute(
                "UPDATE purchasedservices SET paymentstatus = FALSE "
                "WHERE serviceenddate <= NOW() AND paymentstatus = TRUE"
            )

            # Обновляем приоритеты для затронутых пользователей
            for record in expired:
                await self.update_user_priority(record['usertelegramid'])

            return len(expired)

    except Exception as e:
        logger.error(f"Error checking expired services: {e}")
        return 0

# Функция для отображения совместимого пользователя
async def show_compatible_user(message: Message, state: FSMContext, db: Database, crypto=None):
    """Показывает совместимого пользователя с очисткой предыдущих сообщений и правильными кнопками"""
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

        # Форматируем текст профиля
        profile_text = await format_profile_text(user_profile, crypto)
        profile_text += f"<b>Совместимость:</b> {compatibility}%"

        # Создаём адаптивную клавиатуру - всегда передаем False для is_initial
        keyboard = compatible_navigation_keyboard(
            user_id=user_profile['telegramid'],
            is_first=current_index == 0,
            is_last=current_index == len(compatible_users) - 1,
            is_initial=False  # Всегда передаем False
        )

        # Отправляем новое сообщение
        photos = user_profile.get('photos', [])
        sent_message = None
        if photos:
            sent_message = await message.answer_photo(
                photo=photos[0],
                caption=profile_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            sent_message = await message.answer(
                text=profile_text,
                reply_markup=keyboard,
                parse_mode="HTML"
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
    # Показываем следующего пользователя - ВАЖНО: передаем crypto
    await show_compatible_user(callback.message, state, db, crypto)

# Обработчик начала поиска
@router.callback_query(F.data == "start_search")
async def start_search_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    await callback.answer()
    await callback.message.edit_text("🔍 Ищем совместимых пользователей...")
    # Получаем фильтры из состояния
    filters = await state.get_data()
    # Создаем сервис совместимости
    compatibility_service = CompatibilityService(db)
    # Ищем пользователей с учетом фильтров
    high_compatible_users, low_compatible_users = await compatibility_service.find_compatible_users(
        user_id=callback.from_user.id,
        city=filters.get('filter_city'),
        age_min=filters.get('filter_age_min'),
        age_max=filters.get('filter_age_max'),
        gender=filters.get('filter_gender'),
        occupation=filters.get('filter_occupation'),
        goals=filters.get('filter_goals'),
        limit=10,
        min_score=50.0
    )
    # Объединяем результаты
    all_compatible_users = high_compatible_users + low_compatible_users
    if not all_compatible_users:
        await callback.message.edit_text(
            "😔 По вашим фильтрам совместимых пользователей не найдено.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu")]
            ])
        )
        return
    # Сохраняем результаты поиска
    await state.update_data(
        compatible_users=all_compatible_users,
        current_compatible_index=0
    )
    # Показываем первого пользователя - ВАЖНО: передаем crypto
    await show_compatible_user(callback.message, state, db, crypto)

'''Обработчик кнопки назад на одну анкету'''
@router.callback_query(F.data == "prev_compatible")
async def prev_compatible_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    await callback.answer()
    # Получаем текущий индекс
    state_data = await state.get_data()
    current_index = state_data.get("current_compatible_index", 0) - 1  # Уменьшаем индекс
    compatible_users = state_data.get("compatible_users", [])
    # Если ушли в минус, переходим к последней анкете
    if current_index < 0:
        current_index = len(compatible_users) - 1
    # Обновляем индекс в состоянии
    await state.update_data(current_compatible_index=current_index)
    # Удаляем предыдущее сообщение
    await delete_message_safely(callback.message)
    # Показываем предыдущего пользователя
    await show_compatible_user(callback.message, state, db, crypto)

    # Добавьте этот обработчик в конец файла

@router.callback_query(F.data == "next_like")
async def next_like_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    """Обработчик перехода к следующему лайку"""
    await callback.answer()

    try:
        # Получаем данные из состояния
        data = await state.get_data()
        likes_list = data.get("likes_list", [])
        current_index = data.get("current_like_index", 0)

        if current_index >= len(likes_list):
            # Больше лайков нет
            await callback.message.answer(
                "Больше лайков нет.",
                reply_markup=back_to_menu_button()
            )
            return

        # Удаляем текущее сообщение
        await delete_message_safely(callback.message)

        # Показываем следующий профиль
        await show_like_profile(callback.message, callback.from_user.id, state, db, crypto)

    except Exception as e:
        logger.error(f"Ошибка при переходе к следующему лайку: {e}", exc_info=True)
        await callback.message.answer(
            "Произошла ошибка. Пожалуйста, попробуйте позже.",
            reply_markup=back_to_menu_button()
        )

@router.callback_query(F.data == "prev_like")
async def prev_like_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    """Обработчик кнопки 'Назад' при просмотре лайков"""
    # Получаем текущие данные из состояния
    state_data = await state.get_data()
    current_index = state_data.get("current_like_index", 0)

    # Проверяем, есть ли предыдущий лайк
    if current_index > 0:
        # Уменьшаем индекс
        current_index -= 1
        await state.update_data(current_like_index=current_index)

        # Показываем предыдущий профиль
        await show_like_profile(callback.message, callback.from_user.id, state, db, crypto)
    else:
        await callback.answer("Это первый лайк в списке", show_alert=True)

@router.callback_query(F.data == "my_likes")
async def show_my_likes(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    """Показывает список непросмотренных лайков"""
    try:
        # Получаем только НЕпросмотренные лайки
        likes = await db.fetch(
            "SELECT likeid, sendertelegramid FROM likes WHERE receivertelegramid = $1 AND likeviewedstatus = FALSE",
            callback.from_user.id
        )

        if not likes:
            await callback.message.edit_text(
                "У вас пока нет новых лайков.",
                reply_markup=back_to_menu_button()
            )
            await callback.answer()
            return

        # Сохраняем список лайков в состоянии
        await state.update_data(likes_list=likes, current_like_index=0)

        # Показываем первый профиль
        await show_like_profile(callback.message, state, db, crypto)

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при получении лайков: {e}")
        await callback.message.edit_text(
            "Произошла ошибка при загрузке лайков. Попробуйте позже.",
            reply_markup=back_to_menu_button()
        )
        await callback.answer("Произошла ошибка", show_alert=True)