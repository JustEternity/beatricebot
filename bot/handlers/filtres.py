from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from bot.models.states import RegistrationStates
from bot.handlers.common import show_filters_menu
from bot.services.city_validator import city_validator
from bot.services.database import Database
from bot.services.encryption import CryptoService
from bot.keyboards.menus import back_to_menu_button

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
    
    await state.update_data(filter_city=normalized_city)
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

@router.callback_query(F.data == "filter_occupation")
async def filter_occupation_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Введите род занятий для поиска:",
        reply_markup=back_to_menu_button()
    )
    await state.set_state(RegistrationStates.SET_FILTER_OCCUPATION)
    await callback.answer()

@router.message(RegistrationStates.SET_FILTER_OCCUPATION)
async def process_occupation_filter(message: Message, state: FSMContext, db: Database, crypto: CryptoService):
    await state.update_data(filter_occupation=message.text)
    # Добавляем установку состояния FILTERS
    await state.set_state(RegistrationStates.FILTERS)
    await show_filters_menu(message, state, db, crypto)

@router.callback_query(F.data == "filter_goals")
async def filter_goals_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Введите цели знакомства для поиска:",
        reply_markup=back_to_menu_button()
    )
    await state.set_state(RegistrationStates.SET_FILTER_GOALS)
    await callback.answer()

@router.message(RegistrationStates.SET_FILTER_GOALS)
async def process_goals_filter(message: Message, state: FSMContext, db: Database, crypto: CryptoService):
    await state.update_data(filter_goals=message.text)
    # Добавляем установку состояния FILTERS
    await state.set_state(RegistrationStates.FILTERS)
    await show_filters_menu(message, state, db, crypto)

@router.callback_query(F.data == "reset_filters")
async def reset_filters_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto: CryptoService):
    await callback.answer("🔄 Фильтры сброшены")
    
    # Удаляем все фильтры из состояния
    await state.update_data(
        filter_city=None,
        filter_age_min=None,
        filter_age_max=None,
        filter_occupation=None,
        filter_goals=None
    )
    
    # Показываем обновленное меню фильтров
    await show_filters_menu(callback, state, db, crypto)

@router.callback_query(F.data == "back_to_filters")
async def back_to_filters_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto: CryptoService):
    """Обработчик для возврата в меню фильтров"""
    await callback.answer()
    await state.set_state(RegistrationStates.FILTERS)
    await show_filters_menu(callback, state, db, crypto)
