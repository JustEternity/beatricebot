from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from bot.models.states import RegistrationStates
from bot.handlers.common import show_filters_menu
from bot.services.city_validator import city_validator

router = Router()

@router.callback_query(F.data == "filter_city")
async def filter_city_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите город для поиска:")
    await state.set_state(RegistrationStates.SET_FILTER_CITY)
    await callback.answer()

@router.message(RegistrationStates.SET_FILTER_CITY)
async def process_city_filter(message: Message, state: FSMContext):
    is_valid, normalized_city = city_validator.validate_city(message.text)
    if not is_valid:
        await message.answer("⚠️ Город не найден. Введите существующий город.")
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
    except ValueError:
        await message.answer("⚠️ Неверный формат. Введите возрастной диапазон через дефис, например: 25-30")

