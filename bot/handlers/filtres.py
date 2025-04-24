from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from bot.models.states import RegistrationStates
from bot.services.database import Database
from bot.services.city_validator import city_validator
from bot.services.encryption import CryptoService
from bot.keyboards.menus import back_to_menu_button
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
import logging
from bot.handlers.common import show_filters_menu

logger = logging.getLogger(__name__)
router = Router()

# Обработчик для кнопки "Город"
@router.callback_query(F.data == "filter_city")
async def filter_city_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()  # Важно: сначала отвечаем на callback
    await callback.message.edit_text(
        "Введите город для поиска:",
        reply_markup=back_to_menu_button()
    )
    await state.set_state(RegistrationStates.SET_FILTER_CITY)

@router.message(RegistrationStates.SET_FILTER_CITY)
async def process_city_filter(message: Message, state: FSMContext, db: Database, crypto: CryptoService):
    is_valid, normalized_city = city_validator.validate_city(message.text)
    if not is_valid:
        await message.answer(
            "⚠️ Город не найден. Введите существующий город.",
            reply_markup=back_to_menu_button()
        )
        return
        
    # Шифруем город перед сохранением
    encrypted_city = crypto.encrypt(normalized_city) if crypto else normalized_city
    await state.update_data(filter_city=encrypted_city)
    
    # Устанавливаем состояние FILTERS перед вызовом show_filters_menu
    await state.set_state(RegistrationStates.FILTERS)
    await show_filters_menu(message, state, db, crypto)

# Обработчик для кнопки "Возраст"
@router.callback_query(F.data == "filter_age")
async def filter_age_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()  # Важно: сначала отвечаем на callback
    await callback.message.edit_text(
        "Введите возрастной диапазон (например, 25-30):",
        reply_markup=back_to_menu_button()
    )
    await state.set_state(RegistrationStates.SET_FILTER_AGE)

@router.message(RegistrationStates.SET_FILTER_AGE)
async def process_age_filter(message: Message, state: FSMContext, db: Database, crypto: CryptoService):
    try:
        age_min, age_max = map(int, message.text.split('-'))
        if 18 <= age_min <= age_max <= 100:
            await state.update_data(filter_age_min=age_min, filter_age_max=age_max)
            # Добавляем установку состояния FILTERS
            await state.set_state(RegistrationStates.FILTERS)
            await show_filters_menu(message, state, db, crypto)
        else:
            await message.answer(
                "⚠️ Возраст должен быть от 18 до 100 лет",
                reply_markup=back_to_menu_button()
            )
    except ValueError:
        await message.answer(
            "⚠️ Неверный формат. Введите возрастной диапазон через дефис, например: 25-30",
            reply_markup=back_to_menu_button()
        )

# Обработчик для кнопки "Интересы" (на основе теста)
@router.callback_query(F.data == "filter_interests")
async def filter_interests_handler(callback: CallbackQuery, state: FSMContext, db: Database):
    await callback.answer()
    
    # Проверяем наличие подписки
    has_subscription = await db.check_user_subscription(callback.from_user.id)
    if not has_subscription:
        await callback.message.answer(
            "⚠️ Фильтрация по интересам доступна только для пользователей с подпиской",
            reply_markup=back_to_menu_button()
        )
        return
    
    # Проверяем, прошел ли пользователь тест
    has_test = await db.check_existing_answers(callback.from_user.id)
    if not has_test:
        await callback.message.answer(
            "⚠️ Для использования этого фильтра необходимо пройти тест совместимости",
            reply_markup=back_to_menu_button()
        )
        return
    
    # Получаем текущие выбранные интересы
    data = await state.get_data()
    selected_interests = data.get('filter_interests', [])
    
    # Создаем клавиатуру с категориями интересов
    builder = InlineKeyboardBuilder()
    
    # Словарь интересов для отображения статуса выбора
    interests = {
        "active": {"name": "🏃 Активный отдых", "question": 2, "answer": 1},
        "travel": {"name": "✈️ Путешествия", "question": 3, "answer": 1},
        "sport": {"name": "🏋️ Спорт", "question": 4, "answer": 1},
        "animals": {"name": "🐶 Животные", "question": 5, "answer": 1},
        "art": {"name": "🎨 Творчество", "question": 6, "answer": 1},
        "parties": {"name": "🎭 Вечеринки", "question": 8, "answer": 2},
        "space": {"name": "🚀 Космос", "question": 9, "answer": 1},
        "serious": {"name": "💑 Серьезные отношения", "question": 1, "answer": 1}
    }
    
    # Добавляем кнопки для разных категорий интересов с отметкой выбранных
    for interest_key, interest_info in interests.items():
        # Добавляем отметку, если интерес выбран
        button_text = f"✅ {interest_info['name']}" if interest_key in selected_interests else interest_info['name']
        builder.button(text=button_text, callback_data=f"toggle_interest_{interest_key}")
    
    # Добавляем кнопку "Применить"
    builder.button(text="✅ Применить", callback_data="apply_interests")
    
    # Добавляем кнопку "Назад"
    builder.button(text="◀️ Назад", callback_data="back_to_filters")
    
    # Настраиваем расположение кнопок (по 2 в ряд, последние две кнопки отдельно)
    builder.adjust(2, 2, 2, 2, 1, 1)
    
    # Отправляем сообщение с клавиатурой
    await callback.message.edit_text(
        "🔍 Выберите интересы для поиска совместимых пользователей:\n"
        "Вы можете выбрать несколько интересов.",
        reply_markup=builder.as_markup()
    )

# Обработчик переключения интересов
@router.callback_query(F.data.startswith("toggle_interest_"))
async def toggle_interest_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    # Извлекаем выбранный интерес из callback_data
    interest_type = callback.data.replace("toggle_interest_", "")
    
    # Получаем текущие выбранные интересы
    data = await state.get_data()
    selected_interests = data.get('filter_interests', [])
    
    # Переключаем состояние интереса (добавляем/удаляем)
    if interest_type in selected_interests:
        selected_interests.remove(interest_type)
    else:
        selected_interests.append(interest_type)
    
    # Сохраняем обновленный список интересов
    await state.update_data(filter_interests=selected_interests)
    
    # Обновляем клавиатуру с отметками выбранных интересов
    builder = InlineKeyboardBuilder()
    
    # Словарь интересов для отображения статуса выбора
    interests = {
        "active": {"name": "🏃 Активный отдых", "question": 2, "answer": 1},
        "travel": {"name": "✈️ Путешествия", "question": 3, "answer": 1},
        "sport": {"name": "🏋️ Спорт", "question": 4, "answer": 1},
        "animals": {"name": "🐶 Животные", "question": 5, "answer": 1},
        "art": {"name": "🎨 Творчество", "question": 6, "answer": 1},
        "parties": {"name": "🎭 Вечеринки", "question": 8, "answer": 2},
        "space": {"name": "🚀 Космос", "question": 9, "answer": 1},
        "serious": {"name": "💑 Серьезные отношения", "question": 1, "answer": 1}
    }
    
    # Добавляем кнопки для разных категорий интересов с отметкой выбранных
    for interest_key, interest_info in interests.items():
        # Добавляем отметку, если интерес выбран
        button_text = f"✅ {interest_info['name']}" if interest_key in selected_interests else interest_info['name']
        builder.button(text=button_text, callback_data=f"toggle_interest_{interest_key}")
    
    # Добавляем кнопку "Применить"
    builder.button(text="✅ Применить", callback_data="apply_interests")
    
    # Добавляем кнопку "Назад"
    builder.button(text="◀️ Назад", callback_data="back_to_filters")
    
    # Настраиваем расположение кнопок (по 2 в ряд, последние две кнопки отдельно)
    builder.adjust(2, 2, 2, 2, 1, 1)
    
    # Обновляем сообщение с клавиатурой
    await callback.message.edit_text(
        "🔍 Выберите интересы для поиска совместимых пользователей:\n"
        "Вы можете выбрать несколько интересов.",
        reply_markup=builder.as_markup()
    )

# Обработчик применения выбранных интересов
@router.callback_query(F.data == "apply_interests")
async def apply_interests_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto: CryptoService):
    await callback.answer("✅ Фильтры по интересам применены")
    
    # Устанавливаем состояние FILTERS
    await state.set_state(RegistrationStates.FILTERS)
    
    # Показываем обновленное меню фильтров
    await show_filters_menu(callback, state, db, crypto)

# Обработчик сброса фильтров
@router.callback_query(F.data == "reset_filters")
async def reset_filters_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto: CryptoService):
    await callback.answer("🔄 Фильтры сброшены")
        
    # Удаляем все фильтры из состояния
    await state.update_data(
        filter_city='Не задан',  # 'Не задан' вместо None
        filter_age_min=None,
        filter_age_max=None,
        filter_interests=[],  # Сбрасываем список интересов
        filter_test_question=None,
        filter_test_answer=None
    )
        
    # Показываем обновленное меню фильтров
    try:
        await show_filters_menu(callback, state, db, crypto)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            # Если сообщение не изменилось, просто игнорируем ошибку
            pass
        else:
            # Если другая ошибка, пробрасываем её дальше
            raise

# Обработчик для возврата в меню фильтров
@router.callback_query(F.data == "back_to_filters")
async def back_to_filters_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto: CryptoService):
    try:
        await callback.answer()
        await show_filters_menu(callback, state, db, crypto)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            # Если сообщение не изменилось, просто игнорируем ошибку
            pass
        else:
            # Если другая ошибка, пробрасываем её дальше
            raise