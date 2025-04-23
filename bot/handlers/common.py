from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from bot.models.states import RegistrationStates
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.services.database import Database
from bot.keyboards.menus import main_menu, back_to_menu_button as back, policy_keyboard, admin_menu
from bot.services.utils import delete_previous_messages
from bot.services.profile_service import decrypt_city
from bot.handlers.profile_edit import remove_keyboard_if_exists
from bot.services.encryption import CryptoService
from bot.texts.textforbot import POLICY_TEXT
from bot.services.s3storage import S3Service
import logging
import os

logger = logging.getLogger(__name__)
router = Router()

# Обработчик /admin для перехода в админское меню
@router.message(Command("admin"))
async def admin_menu_handler(message: Message, state: FSMContext, db: Database):
    # Проверяем, является ли пользователь администратором
    admin_password = await db.get_admin_pass(message.from_user.id)

    if not admin_password:
        await message.answer("❌ Вы не администратор.")
        await show_main_menu(message, state)
        return

    # Если пользователь админ, запрашиваем пароль
    auth_message = await message.answer("Введите пароль администратора:")

    # Сохраняем ID сообщения с запросом пароля и пароль админа в state
    await state.update_data(
        auth_message_id=auth_message.message_id,
        admin_password=admin_password
    )

    # Переходим в состояние ожидания ввода пароля
    await state.set_state(RegistrationStates.ADMIN_AUTH)

@router.message(RegistrationStates.ADMIN_AUTH)
async def check_admin_password(message: Message, state: FSMContext, db: Database):
    # Получаем введенный пароль
    password = message.text

    # Получаем данные из state
    data = await state.get_data()
    auth_message_id = data.get("auth_message_id")
    admin_password = data.get("admin_password")  # Получаем пароль из state

    # Пытаемся удалить сообщение с паролем
    try:
        await message.delete()
    except Exception as e:
        logger.error(f"Не удалось удалить сообщение с паролем: {e}")

    # Пытаемся удалить сообщение с запросом пароля
    if auth_message_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=auth_message_id)
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение с запросом пароля: {e}")

    # Проверяем пароль
    if password == admin_password:
        # Если пароль верный, показываем админское меню
        await show_admin_menu(message, state)
    else:
        # Если пароль неверный, отправляем сообщение об ошибке
        error_message = await message.answer("❌ Неверный пароль. Доступ запрещен.")

        # Возвращаемся в обычное меню
        await show_main_menu(message, state)

@router.callback_query(F.data == "back_to_admin_menu")
async def back_to_admin_menu_handler(callback: CallbackQuery, state: FSMContext, db: Database):
    """Универсальный обработчик возврата в меню админа"""
    await delete_previous_messages(callback, state)
    await callback.answer()

    try:
        # Удаляем текущее сообщение
        await callback.message.delete()

        # Отправляем новое сообщение с главным меню
        res = await callback.message.answer(
            "🔹 Главное меню администратора🔹",
            reply_markup=admin_menu()
        )
        await state.update_data(message_ids=[res.message_id])

    except Exception as e:
        logger.error(f"Ошибка в back_to_admin_menu_handler: {e}")

        res = await callback.message.answer(
            "🔹 Главное меню администратора🔹",
            reply_markup=admin_menu()
        )
        await state.update_data(message_ids=[res.message_id])



# Общая функция показа главного меню админа
async def show_admin_menu(source: Message | CallbackQuery, state: FSMContext):
    await delete_previous_messages(source, state)

    # Определяем, как отправить сообщение в зависимости от типа source
    if isinstance(source, Message):
        menu_message = await source.answer(
            "🔹Главное меню администратора🔹",
            reply_markup=admin_menu()
        )
    else:  # CallbackQuery
        menu_message = await source.message.answer(
            "🔹Главное меню администратора🔹",
            reply_markup=admin_menu()
        )
        await source.answer()  # Закрываем callback query

    await state.update_data(message_ids=[menu_message.message_id])
    await state.set_state(RegistrationStates.ADMIN_MENU)

# Обработчик команды /cancel
@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, db: Database):
    await delete_previous_messages(message, state)

    # Проверяем, зарегистрирован ли пользователь
    user_data = await db.get_user_data(message.from_user.id)
    if not user_data:
        # Если пользователь не зарегистрирован, отправляем сообщение и не показываем главное меню
        await message.answer(
            "Действие отменено. Пожалуйста, завершите регистрацию (/start).",
            reply_markup=ReplyKeyboardRemove()
        )
        # Возвращаем пользователя к началу регистрации
        await state.set_state(RegistrationStates.NAME)
        return

    await message.answer(
        "Действие отменено. Возврат в главное меню.",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()

    # Получаем количество непросмотренных лайков
    likes_count = await db.get_unviewed_likes_count(message.from_user.id)
    await show_main_menu(message, state, likes_count, db)

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_handler(callback: CallbackQuery, state: FSMContext, db: Database):
    """Универсальный обработчик возврата в меню"""
    await delete_previous_messages(callback.message, state)
    await callback.answer()

    try:
        # Получаем количество непросмотренных лайков
        unviewed_likes = await db.get_unviewed_likes_count(callback.from_user.id)

        # Удаляем текущее сообщение
        await callback.message.delete()

        # Отправляем новое сообщение с главным меню
        res = await callback.message.answer(
            "🔹 Главное меню 🔹",
            reply_markup=main_menu(unviewed_likes)
        )
        await state.update_data(message_ids=[res.message_id])

    except Exception as e:
        logger.error(f"Ошибка в back_to_menu_handler: {e}")
        # Если не получилось удалить сообщение, отправляем новое
        try:
            unviewed_likes = await db.get_unviewed_likes_count(callback.from_user.id)
        except:
            unviewed_likes = 0

        await callback.message.answer(
            "🔹 Главное меню 🔹",
            reply_markup=main_menu(unviewed_likes)
        )

# Общая функция показа главного меню
async def show_main_menu(source: Message | CallbackQuery, state: FSMContext, likes_count: int = 0, db: Database = None):
    await delete_previous_messages(source, state)

    # Определяем ID пользователя в зависимости от типа source
    user_id = source.from_user.id if isinstance(source, Message) else source.from_user.id

    # Проверяем, зарегистрирован ли пользователь, только если db передан
    if db:
        user_data = await db.get_user_data(user_id)
        if not user_data:
            # Если пользователь не зарегистрирован, отправляем сообщение
            if isinstance(source, Message):
                await source.answer(
                    "Пожалуйста, сначала завершите регистрацию.",
                    reply_markup=ReplyKeyboardRemove()
                )
            else:  # CallbackQuery
                await source.message.answer(
                    "Пожалуйста, сначала завершите регистрацию.",
                    reply_markup=ReplyKeyboardRemove()
                )
                await source.answer()

            # Возвращаем пользователя к началу регистрации
            await state.set_state(RegistrationStates.NAME)
            return

    # Если пользователь зарегистрирован или db не передан, показываем главное меню
    if isinstance(source, Message):
        menu_message = await source.answer(
            "🔹 Главное меню 🔹",
            reply_markup=main_menu(likes_count)
        )
    else:  # CallbackQuery
        menu_message = await source.message.answer(
            "🔹 Главное меню 🔹",
            reply_markup=main_menu(likes_count)
        )
        await source.answer()  # Закрываем callback query

    await state.update_data(message_ids=[menu_message.message_id])
    await state.set_state(RegistrationStates.MAIN_MENU)

async def update_main_menu(message, state: FSMContext, db: Database):
    """Обновляет главное меню с актуальным количеством лайков"""
    # Получаем актуальное количество непросмотренных лайков
    likes_count = await db.get_unviewed_likes_count(message.chat.id)

    # Обновляем меню
    await message.edit_text(
        "🔹 Главное меню 🔹",
        reply_markup=main_menu(likes_count)
    )

async def show_filters_menu(source, state: FSMContext, db: Database, crypto: CryptoService):
    """Показывает меню фильтров"""
    data = await state.get_data()

    # Получаем текущие значения фильтров
    filter_city = data.get('filter_city', 'Не задан')
    filter_age_min = data.get('filter_age_min')
    filter_age_max = data.get('filter_age_max')

    # Получаем информацию о фильтрах по интересам
    filter_interests = data.get('filter_interests', [])

    # Формируем текст с текущими фильтрами
    filters_text = "🔍 Текущие фильтры поиска:\n\n"

    # Город
    if filter_city != 'Не задан' and crypto:
        try:
            decrypted_city = decrypt_city(crypto, filter_city)
            filters_text += f"🏙️ Город: {decrypted_city}\n"
        except:
            filters_text += f"🏙️ Город: {filter_city}\n"
    else:
        filters_text += f"🏙️ Город: {filter_city}\n"

    # Возраст
    if filter_age_min is not None and filter_age_max is not None:
        filters_text += f"🔢 Возраст: {filter_age_min}-{filter_age_max} лет\n"
    else:
        filters_text += "🔢 Возраст: Не задан\n"

    # Интересы (на основе теста)
    if filter_interests:
        # Словарь соответствия интересов понятным названиям
        interest_names = {
            "active": "Активный отдых",
            "travel": "Путешествия",
            "sport": "Спорт",
            "animals": "Животные",
            "art": "Творчество",
            "parties": "Шумные вечеринки",
            "space": "Интерес к космосу",
            "serious": "Серьезные отношения"
        }

        # Формируем список названий выбранных интересов
        interest_list = [interest_names.get(interest, interest) for interest in filter_interests]
        filters_text += f"🧩 Интересы: {', '.join(interest_list)}\n"
    else:
        filters_text += "🧩 Интересы: Не заданы\n"

    # Создаем клавиатуру с кнопками фильтров
    builder = InlineKeyboardBuilder()

    # Кнопки для установки фильтров
    builder.button(text="🏙️ Город", callback_data="filter_city")
    builder.button(text="🔢 Возраст", callback_data="filter_age")
    builder.button(text="🧩 Интересы", callback_data="filter_interests")

    # Кнопка сброса фильтров
    builder.button(text="🔄 Сбросить фильтры", callback_data="reset_filters")

    # Кнопка начала поиска
    builder.button(text="🔍 Начать поиск", callback_data="start_search")

    # Кнопка возврата в меню
    builder.button(text="◀️ Назад в меню", callback_data="back_to_menu")

    # Настраиваем расположение кнопок (по 2 в ряд, последние три отдельно)
    builder.adjust(2, 1, 1, 1)

    # Проверяем тип источника сообщения (CallbackQuery или Message)
    if hasattr(source, 'message'):
        # Если это CallbackQuery
        await source.message.edit_text(
            filters_text,
            reply_markup=builder.as_markup()
        )
    else:
        # Если это Message
        await source.answer(
            filters_text,
            reply_markup=builder.as_markup()
        )

@router.callback_query(F.data == "send_feedback")
async def send_feedback_handler(callback: CallbackQuery, state: FSMContext, crypto: CryptoService, db: Database, bot: Bot, s3: S3Service):
    await delete_previous_messages(callback.message, state)
    await remove_keyboard_if_exists(callback.message)
    await state.clear()
    msg = await callback.message.answer(
        "📝 Напишите ваше сообщение для обратной связи (максимум 500 символов):",
        reply_markup=back()
    )
    await state.update_data(edit_message_id=msg.message_id)
    await state.set_state(RegistrationStates.SEND_FEEDBACK)
    await callback.answer()

# Обработчик текста обратной связи
@router.message(RegistrationStates.SEND_FEEDBACK, F.text)
async def feedback_text_handler(message: Message, state: FSMContext, db: Database):
    feedback_text = message.text.strip()
    if len(feedback_text) > 500:
        await message.answer("⚠️ Сообщение слишком длинное (максимум 500 символов)")
        return
    try:
        # Сохраняем в базу данных
        success = await db.save_feedback(
            user_id=message.from_user.id,
            text=feedback_text,
        )

        # Получаем количество непросмотренных лайков
        likes_count = await db.get_unviewed_likes_count(message.from_user.id)

        # Отправляем подтверждение
        if success:
            await message.answer(
                "✅ Спасибо за ваше сообщение! Мы рассмотрим его в ближайшее время.",
                reply_markup=main_menu(likes_count)
            )
        else:
            await message.answer(
                "❌ Приносим свои извинения, произошла ошибка.\nПопробуйте позже",
                reply_markup=main_menu(likes_count)
            )
    except Exception as e:
        logger.error(f"Feedback save error: {str(e)}")
        await message.answer("❌ Произошла ошибка при сохранении отзыва")
    await state.clear()

@router.callback_query(F.data == "start_verification")
async def start_verification_handler(callback: CallbackQuery, state: FSMContext, db: Database):
    await delete_previous_messages(callback.message, state)
    await remove_keyboard_if_exists(callback.message)
    await state.clear()
    user_id = callback.from_user.id
    have_sub = await db.check_user_subscription(user_id)
    is_verified, verification_status, rejection_reason = await db.check_verify(user_id)

    if not have_sub:
        msg = await callback.message.answer(
            "Прохождение верификации доступно только пользователям с подпиской",
            reply_markup=back()
        )
        await state.set_state(RegistrationStates.MAIN_MENU)
    elif is_verified:
        # Если верификация уже пройдена успешно
        likes_count = await db.get_unviewed_likes_count(user_id)
        msg = await callback.message.answer(
            "✅ Вы уже успешно прошли верификацию!",
            reply_markup=back()
        )
        await state.set_state(RegistrationStates.MAIN_MENU)
    elif verification_status == 'rejected':
        # Если верификация была отклонена
        reason_text = f"\n\nПричина отклонения: {rejection_reason}" if rejection_reason else ""

        msg = await callback.message.answer(
            f"❌ Ваша предыдущая верификация была отклонена.{reason_text}\n\n"
            "Вы можете отправить новое видеосообщение для верификации:",
            reply_markup=back()
        )
        await state.set_state(RegistrationStates.VERIFICATION)
        await state.update_data(edit_message_id=msg.message_id)
    elif verification_status == 'open':
        # Если верификация находится на рассмотрении
        msg = await callback.message.answer(
            "Вы уже отправили видео для верификации,\nесли вам не пришел ответ о результате,\n"
            "отправьте сообщение обратной связи:",
            reply_markup=back()
        )
        await state.set_state(RegistrationStates.MAIN_MENU)
    else:
        # Если записи о верификации нет
        msg = await callback.message.answer(
            "Отправьте видеосообщение для верификации:",
            reply_markup=back()
        )
        await state.set_state(RegistrationStates.VERIFICATION)
        await state.update_data(edit_message_id=msg.message_id)

    await callback.answer()

@router.message(RegistrationStates.VERIFICATION, F.video_note)
async def virification_handler(message: Message, state: FSMContext, db: Database):
    video_note = message.video_note
    video_file_id = video_note.file_id
    user_id = message.from_user.id

    try:
        # Сохраняем file_id видеосообщения в базу данных
        success = await db.save_verification_video(
            user_id=user_id,
            video_file_id=video_file_id
        )

        # Получаем количество непросмотренных лайков
        likes_count = await db.get_unviewed_likes_count(user_id)

        # Отправляем подтверждение
        if success:
            await message.answer(
                "✅ Спасибо за ваше видеосообщение! Мы рассмотрим его в ближайшее время.",
                reply_markup=main_menu(likes_count)
            )
        else:
            await message.answer(
                "❌ Приносим свои извинения, произошла ошибка.\nПопробуйте позже",
                reply_markup=main_menu(likes_count)
            )
    except Exception as e:
        logger.error(f"Ошибка сохранения видеосообщения: {str(e)}")
        likes_count = await db.get_unviewed_likes_count(user_id)
        await message.answer(
            "❌ Произошла ошибка при сохранении видеосообщения",
            reply_markup=main_menu(likes_count)
        )

    await state.clear()

# Обработчик любых неожиданных сообщений
@router.message()
async def unexpected_messages_handler(message: Message, state: FSMContext, db: Database):
    current_state = await state.get_state()
    logger.debug(f"Received message in state {current_state}: {message.text}")

    # Проверяем, не находится ли пользователь в состоянии установки фильтров
    filter_states = [
        RegistrationStates.SET_FILTER_CITY.state,
        RegistrationStates.SET_FILTER_AGE.state,
        RegistrationStates.SET_FILTER_GENDER.state,
        RegistrationStates.SET_FILTER_OCCUPATION.state,
        RegistrationStates.SET_FILTER_GOALS.state
    ]

    if current_state in filter_states:
        # Пропускаем обработку, чтобы сообщение обработали соответствующие обработчики
        return

    if current_state is None:
        # Получаем количество непросмотренных лайков
        likes_count = await db.get_unviewed_likes_count(message.from_user.id)
        await message.answer(
            "Пожалуйста, используйте команды из меню.",
            reply_markup=main_menu(likes_count)
        )
    else:
        await message.answer(
            "Пожалуйста, завершите текущее действие "
            "или нажмите /cancel для отмены."
        )

async def get_user_profile(
    user_id: int,
    db: Database,
    crypto: CryptoService,
    bot: Bot,
    s3: S3Service,
    refresh_photos: bool = False) -> dict:
    """
    Получает и подготавливает данные профиля пользователя
    :param user_id: ID целевого пользователя
    :param refresh_photos: Принудительное обновление фото
    :return: Словарь с данными профиля или None
    """
    profile_data = {
        'text': None,
        'photos': [],
        'user_id': user_id
    }

    try:
        # Получаем сырые данные из БД
        user_data = await db.get_user_data(user_id)
        if not user_data:
            return None

        # Добавим отладочную информацию
        logger.debug(f"User data: {user_data}")

        # Проверка и обновление фото
        if refresh_photos or not user_data.get('photos'):
            # Проверяем, что photos - это список словарей с ключом 's3_url'
            photos = user_data.get('photos', [])
            if isinstance(photos, list) and all(isinstance(p, dict) and 's3_url' in p for p in photos):
                s3_urls = [photo['s3_url'] for photo in photos]
                # Логика обновления фото
                new_photos = []
                if s3_urls:
                    local_paths = await s3.download_photos_by_urls(s3_urls)
                    for path in local_paths:
                        try:
                            with open(path, 'rb') as f:
                                msg = await bot.send_photo(user_id, f)
                                new_photos.append({
                                    'file_id': msg.photo[-1].file_id,
                                    's3_url': next(url for url in s3_urls if url.split('/')[-1] in path)
                                })
                            os.remove(path)
                        except Exception as e:
                            logger.error(f"Photo reload error: {str(e)}")
                    if new_photos:
                        await db.update_user_photos(user_id, new_photos)
                        user_data['photos'] = new_photos
            else:
                logger.warning(f"Invalid photos format: {photos}")

        # Декодирование данных с проверкой на None
        try:
            # Проверяем, что crypto - это экземпляр класса
            if not isinstance(crypto, CryptoService):
                logger.error(f"crypto is not an instance of CryptoService: {type(crypto)}")
                raise TypeError("crypto должен быть экземпляром CryptoService")

            decrypted_fields = {
                'name': crypto.decrypt(user_data['name']) if user_data.get('name') else "Не указано",
                'location': crypto.decrypt(user_data['location']) if user_data.get('location') else "Не указано",
                'description': crypto.decrypt(user_data['description']) if user_data.get('description') else "Не указано"
            }
        except Exception as e:
            logger.error(f"Decryption failed. Data: {user_data}", exc_info=True)
            logger.error(f"Error details: {e}", exc_info=True)
            logger.error(f"Type of crypto: {type(crypto)}")
            raise

        # Преобразование пола
        gender_map = {
            '0': "👨 Мужской",
            '1': "👩 Женский",
            0: "👨 Мужской",
            1: "👩 Женский"
        }
        gender = gender_map.get(user_data.get('gender', 'Не указан'), "Не указан")

        # Формирование текста
        profile_text = (
            f"👤 *Профиль пользователя:*\n\n"
            f"▪️ ID: `{user_id}`\n"
            f"▪️ Имя: {decrypted_fields['name']}\n"
            f"▪️ Возраст: {user_data.get('age', 'Не указан')}\n"
            f"▪️ Пол: {gender}\n"
            f"▪️ Город: {decrypted_fields['location']}\n"
            f"▪️ Описание: {decrypted_fields['description']}"
        )

        # Сборка результата
        photos_list = []
        photos = user_data.get('photos', [])

        # Добавим отладочную информацию
        logger.debug(f"Photos data: {photos}")

        # Проверяем формат photos
        if isinstance(photos, list):
            if len(photos) > 0:
                if all(isinstance(p, dict) and 'file_id' in p for p in photos):
                    # Если photos - список словарей с ключом 'file_id'
                    photos_list = [photo['file_id'] for photo in photos]
                    logger.debug(f"Extracted file_ids from dict: {photos_list}")
                elif all(isinstance(p, str) for p in photos):
                    # Если photos - просто список строк (file_id)
                    photos_list = photos
                    logger.debug(f"Using photos as is: {photos_list}")
                else:
                    logger.warning(f"Unexpected photos format: {photos}")
            else:
                logger.debug("Photos list is empty")
        else:
            logger.warning(f"Photos is not a list: {photos}")

        profile_data.update({
            'text': profile_text,
            'photos': photos_list
        })
    except Exception as e:
        logger.error(f"Profile build error: {str(e)}")
        # Добавляем отладочную информацию
        print(f"Отладка для {user_data}")
        return None

    return profile_data
