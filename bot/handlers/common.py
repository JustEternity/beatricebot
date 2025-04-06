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
    await callback.answer()

    try:
        # Удаляем текущее сообщение
        await callback.message.delete()

        # Отправляем новое сообщение с главным меню
        await callback.message.answer(
            "🔹 Главное меню администратора🔹",
            reply_markup=admin_menu()
        )

        # Очищаем состояние
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка в back_to_admin_menu_handler: {e}")

        await callback.message.answer(
            "🔹 Главное меню администратора🔹",
            reply_markup=admin_menu()
        )

        # Очищаем состояние
        await state.clear()

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

    await state.update_data(last_menu_message_id=menu_message.message_id)
    await state.set_state(RegistrationStates.ADMIN_MENU)

# Обработчик команды /menu
@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext, db: Database):
    # Получаем количество непросмотренных лайков
    likes_count = await db.get_unviewed_likes_count(message.from_user.id)
    await show_main_menu(message, state, likes_count)

# Обработчик команды /cancel
@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, db: Database):
    await delete_previous_messages(message, state)
    await message.answer(
        "Действие отменено. Возврат в главное меню.",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()

    # Получаем количество непросмотренных лайков
    likes_count = await db.get_unviewed_likes_count(message.from_user.id)
    await show_main_menu(message, state, likes_count)

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_handler(callback: CallbackQuery, state: FSMContext, db: Database):
    """Универсальный обработчик возврата в меню"""
    await callback.answer()

    try:
        # Получаем количество непросмотренных лайков
        unviewed_likes = await db.get_unviewed_likes_count(callback.from_user.id)

        # Удаляем текущее сообщение
        await callback.message.delete()

        # Отправляем новое сообщение с главным меню
        await callback.message.answer(
            "🔹 Главное меню 🔹",
            reply_markup=main_menu(unviewed_likes)
        )

        # Очищаем состояние
        await state.clear()

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

        # Очищаем состояние
        await state.clear()

# Общая функция показа главного меню
async def show_main_menu(source: Message | CallbackQuery, state: FSMContext, likes_count: int = 0):
    await delete_previous_messages(source, state)
    menu_message = await source.answer(
        "🔹 Главное меню 🔹",
        reply_markup=main_menu(likes_count)
    )
    await state.update_data(last_menu_message_id=menu_message.message_id)
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

async def show_filters_menu(callback_or_message, state: FSMContext, db: Database, crypto: CryptoService = None):
    """Функция для показа меню фильтров"""
    # Получаем текущие фильтры из состояния
    filters = await state.get_data()
    
    # Определяем ID пользователя в зависимости от типа объекта
    if isinstance(callback_or_message, CallbackQuery):
        user_id = callback_or_message.from_user.id
    else:
        user_id = callback_or_message.from_user.id
    
    # Проверяем наличие подписки у пользователя
    has_subscription = await db.check_user_subscription(user_id)
    
    # Дешифруем город в фильтрах, если он зашифрован
    city = decrypt_city(crypto, filters.get('filter_city'))
    if city and city != filters.get('filter_city'):
        # Обновляем состояние только если город изменился после дешифрования
        await state.update_data(filter_city=city)
        filters = await state.get_data()  # Обновляем фильтры
    
    # Проверяем, есть ли хотя бы один установленный фильтр
    has_any_filter = any([
        filters.get('filter_city'),
        filters.get('filter_age_min') and filters.get('filter_age_max'),
        has_subscription and filters.get('filter_occupation'),
        has_subscription and filters.get('filter_goals')
    ])
    
    # Формируем текст с информацией о текущих фильтрах
    filter_info = []
    if filters.get('filter_city'):
        filter_info.append(f"📍 Город: {filters.get('filter_city')}")
    if filters.get('filter_age_min') and filters.get('filter_age_max'):
        filter_info.append(f"🔢 Возраст: {filters.get('filter_age_min')}-{filters.get('filter_age_max')}")
    if has_subscription:
        if filters.get('filter_occupation'):
            filter_info.append(f"💼 Род занятий: {filters.get('filter_occupation')}")
        if filters.get('filter_goals'):
            filter_info.append(f"🎯 Цели: {filters.get('filter_goals')}")
    
    # Создаем клавиатуру с фильтрами
    builder = InlineKeyboardBuilder()
    builder.button(text="📍 Город", callback_data="filter_city")
    builder.button(text="🔢 Возраст", callback_data="filter_age")
    
    # Дополнительные фильтры для подписчиков
    if has_subscription:
        builder.button(text="💼 Род занятий", callback_data="filter_occupation")
        builder.button(text="🎯 Цели знакомства", callback_data="filter_goals")
    
    # Кнопка сброса фильтров (только если есть хотя бы один фильтр)
    if has_any_filter:
        builder.button(text="🔄 Сбросить фильтры", callback_data="reset_filters")
    
    # Кнопка поиска для всех пользователей
    builder.button(text="🔍 Начать поиск", callback_data="start_search")
    builder.button(text="◀️ Назад", callback_data="back_to_menu")
    
    # Настраиваем расположение кнопок
    if has_subscription:
        builder.adjust(2, 2, 1, 1)  # Основные фильтры по 2 в ряд, доп. кнопки по 1
    else:
        builder.adjust(2, 1, 1)  # Основные фильтры по 2 в ряд, доп. кнопки по 1
    
    # Формируем основной текст сообщения
    base_text = "⚙️ Выберите фильтры для поиска:" if has_subscription else \
               "⚙️ Доступные фильтры (для подписки больше фильтров):"
    
    # Добавляем информацию о текущих фильтрах, если они есть
    if filter_info:
        text = f"{base_text}\n\n<b>Текущие фильтры:</b>\n" + "\n".join(filter_info)
    else:
        text = base_text
    
    # Проверяем тип объекта callback_or_message
    if isinstance(callback_or_message, CallbackQuery):
        # Это CallbackQuery
        await callback_or_message.message.edit_text(
            text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    else:
        # Это Message
        await callback_or_message.answer(
            text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )

@router.callback_query(F.data == "send_feedback")
async def send_feedback_handler(callback: CallbackQuery, state: FSMContext, crypto: CryptoService, db: Database, bot: Bot, s3: S3Service):
    await delete_previous_messages(callback.message, state)
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
    refresh_photos: bool = False
) -> dict:
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

        # Проверка и обновление фото
        if refresh_photos or not user_data.get('photos'):
            s3_urls = [photo['s3_url'] for photo in user_data.get('photos', [])]

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

        # Декодирование данных
        decrypted_fields = {
            'name': crypto.decrypt(user_data['name']),
            'location': crypto.decrypt(user_data['location']),
            'description': crypto.decrypt(user_data['description'])
        }

        # Преобразование пола
        gender_map = {
            '0': "👨 Мужской",
            '1': "👩 Женский",
            0: "👨 Мужской",
            1: "👩 Женский"
        }
        gender = gender_map.get(user_data['gender'], "Не указан")

        # Формирование текста
        profile_text = (
            f"👤 *Профиль пользователя:*\n\n"
            f"▪️ ID: `{user_id}`\n"
            f"▪️ Имя: {decrypted_fields['name']}\n"
            f"▪️ Возраст: {user_data['age']}\n"
            f"▪️ Пол: {gender}\n"
            f"▪️ Город: {decrypted_fields['location']}\n"
            f"▪️ Описание: {decrypted_fields['description']}"
        )

        # Сборка результата
        profile_data.update({
            'text': profile_text,
            'photos': [photo['file_id'] for photo in user_data.get('photos', [])]
        })

    except Exception as e:
        logger.error(f"Profile build error: {str(e)}")
        return None

    return profile_data

