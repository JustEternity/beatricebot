from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.models.states import RegistrationStates
from bot.services.city_validator import city_validator
from bot.services.database import Database
from bot.services.algorithm_sovmest import CompatibilityService
from bot.services.encryption import CryptoService
from bot.services.utils import delete_previous_messages, format_profile_text, create_media_group
from bot.keyboards.menus import compatible_navigation_keyboard, back_to_menu_button, subscription_keyboard

import logging

logger = logging.getLogger(__name__)

router = Router()


# Обработчик для поиска совместимых пользователей
@router.callback_query(F.data == "find_compatible")
async def find_compatible_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
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

        # Проверяем наличие подписки
        has_subscription = await db.check_user_subscription(callback.from_user.id)

        # Создаем клавиатуру с фильтрами
        builder = InlineKeyboardBuilder()

        # Базовые фильтры (доступны всем)
        builder.button(text="📍 Город", callback_data="filter_city")
        builder.button(text="🔢 Возраст", callback_data="filter_age")

        # Дополнительные фильтры (только для подписчиков)
        if has_subscription:
            builder.button(text="👫 Пол", callback_data="filter_gender")
            builder.button(text="💼 Род занятий", callback_data="filter_occupation")
            builder.button(text="🎯 Цели знакомства", callback_data="filter_goals")

        builder.button(text="🔍 Начать поиск", callback_data="start_search")
        builder.button(text="◀️ Назад", callback_data="back_to_menu")

        builder.adjust(2)  # По 2 кнопки в ряду

        text = "⚙️ Выберите фильтры для поиска:" if has_subscription else "⚙️ Доступные фильтры (для подписки больше фильтров):"

        # Удаляем предыдущее сообщение если есть
        data = await state.get_data()
        if 'last_message_id' in data:
            try:
                await callback.bot.delete_message(callback.message.chat.id, data['last_message_id'])
            except:
                pass

        msg = await callback.message.answer(
            text,
            reply_markup=builder.as_markup()
        )
        await state.update_data(last_message_id=msg.message_id)

    except Exception as e:
        logger.error(f"Error in find_compatible_handler: {e}")
        await callback.message.answer("⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.")

# Функция для отображения совместимого пользователя
async def show_compatible_user(message: Message, state: FSMContext, db: Database, crypto=None):
    """Показывает совместимого пользователя"""
    try:
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

        # Получаем профиль и совместимость
        user_profile = current_user['profile']
        compatibility = current_user['compatibility']

        # Форматируем текст профиля - ВАЖНО: передаем crypto
        profile_text = await format_profile_text(user_profile, crypto)

        # Добавляем информацию о совместимости
        profile_text += f"<b>Совместимость:</b> {compatibility}%"

        # Получаем фото пользователя
        photos = user_profile.get('photos', [])

        # Создаем клавиатуру навигации
        keyboard = compatible_navigation_keyboard(user_profile['telegramid'])

        # Отправляем сообщение с фото или без
        if photos:
            await message.answer_photo(
                photo=photos[0],
                caption=profile_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await message.answer(
                profile_text,
                reply_markup=keyboard,
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

    # Показываем следующего пользователя - ВАЖНО: передаем crypto
    await show_compatible_user(callback.message, state, db, crypto)

# Обработчик для лайка пользователя
@router.callback_query(F.data.startswith("like_user_"))
async def like_user_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
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
        await callback.answer("👍 Вы отметили этого пользователя. Если он также отметит вас, вы получите уведомление.",
                              show_alert=True)

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

    # Показываем следующего пользователя - ВАЖНО: передаем crypto
    await show_compatible_user(callback.message, state, db, crypto)

# Обработчики фильтров
@router.callback_query(F.data == "filter_city")
async def filter_city_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите город для поиска:")
    await state.set_state(RegistrationStates.SET_FILTER_CITY)
    await callback.answer()

@router.message(RegistrationStates.SET_FILTER_CITY)
async def process_city_filter(message: Message, state: FSMContext):
    is_valid, normalized_city = city_validator.validate_city(message.text)

    if not is_valid:
        await message.answer("⚠️ Город не найден. Пожалуйста, введите существующий российский город")
        return

    await state.update_data(filter_city=normalized_city)
    await show_filters_menu(message, state)

@router.callback_query(F.data == "filter_age")
async def filter_age_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите возрастной диапазон (например, 25-30):")
    await state.set_state(RegistrationStates.SET_FILTER_AGE)
    await callback.answer()

@router.message(RegistrationStates.SET_FILTER_AGE)
async def process_age_filter(message: Message, state: FSMContext):
    try:
        age_min, age_max = map(int, message.text.split('-'))
        if 18 <= age_min <= age_max <= 100:
            await state.update_data(filter_age_min=age_min, filter_age_max=age_max)
            await show_filters_menu(message, state)
        else:
            await message.answer("⚠️ Возраст должен быть от 18 до 100 лет")
    except:
        await message.answer("⚠️ Неверный формат. Введите например: 25-30")

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

async def show_filters_menu(message: Message, state: FSMContext, db=None):
    """Показывает меню фильтров с текущими настройками"""
    data = await state.get_data()
    has_subscription = await db.check_user_subscription(message.from_user.id)

    builder = InlineKeyboardBuilder()

    # Добавляем кнопки фильтров с текущими значениями
    city_text = f"📍 Город: {data.get('filter_city', 'любой')}"
    age_text = f"🔢 Возраст: {data.get('filter_age_min', '18')}-{data.get('filter_age_max', '100')}"

    builder.button(text=city_text, callback_data="filter_city")
    builder.button(text=age_text, callback_data="filter_age")

    if has_subscription:
        # Доп фильтры для подписчиков
        gender_text = f"👫 Пол: {data.get('filter_gender', 'любой')}"
        builder.button(text=gender_text, callback_data="filter_gender")

    builder.button(text="🔍 Начать поиск", callback_data="start_search")
    builder.button(text="◀️ Назад", callback_data="back_to_menu")

    builder.adjust(2)

    await message.answer(
        "⚙️ Текущие фильтры поиска:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data == "filter_city")
async def filter_city_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите город для поиска:")
    await state.set_state(RegistrationStates.SET_FILTER_CITY)
    await callback.answer()

@router.callback_query(F.data == "filter_age")
async def filter_age_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите возрастной диапазон (например, 25-30):")
    await state.set_state(RegistrationStates.SET_FILTER_AGE)
    await callback.answer()