from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from bot.handlers.common import show_main_menu
from bot.models.states import RegistrationStates
from bot.services.city_validator import city_validator
from bot.services.database import Database
from bot.services.encryption import CryptoService
from bot.services.utils import delete_previous_messages
from bot.keyboards.menus import policy_keyboard
from bot.texts.textforbot import POLICY_TEXT
# from bot.services.s3storage import S3Service

from io import BytesIO
import logging
logger = logging.getLogger(__name__)
router = Router()

@router.message(Command("start"))
async def start_handler(message: Message, state: FSMContext, db: Database):
    await delete_previous_messages(message, state)

    if await db.is_user_registered(message.from_user.id):
        await show_main_menu(message, state)
        return

    await message.answer(
        POLICY_TEXT,
        reply_markup=policy_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(RegistrationStates.POLICY)

@router.message(RegistrationStates.POLICY, F.text.in_(["✅ Я согласен", "❌ Я не согласен"]))
async def policy_handler(message: Message, state: FSMContext):
    if message.text == "✅ Я согласен":
        await message.answer("🎉 Спасибо! Как вас зовут?", reply_markup=ReplyKeyboardRemove())
        await state.set_state(RegistrationStates.NAME)
        logger.debug(f"User {message.from_user.id} accepted policy")
    else:
        await message.answer("🚫 Регистрация отменена. /start - начать заново")
        await state.clear()

@router.message(RegistrationStates.NAME)
async def name_handler(message: Message, state: FSMContext, crypto: CryptoService):
    await state.update_data(name=crypto.encrypt(message.text))
    await message.answer(f"👋 Привет, {message.text}! Сколько вам лет?")
    await state.set_state(RegistrationStates.AGE)

@router.message(RegistrationStates.AGE)
async def age_handler(message: Message, state: FSMContext):
    try:
        age = int(message.text)
        if 18 <= age <= 100:
            await state.update_data(age=age)
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="👨 Мужской"), KeyboardButton(text="👩 Женский")]
                ],
                resize_keyboard=True
            )
            await message.answer("🎂 Отлично! Выберите ваш пол:", reply_markup=keyboard)
            await state.set_state(RegistrationStates.GENDER)
        else:
            await message.answer("⚠️ Возраст должен быть от 18 до 100 лет")
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введите число")

@router.message(RegistrationStates.GENDER, F.text.in_(["👨 Мужской", "👩 Женский"]))
async def gender_handler(message: Message, state: FSMContext):
    await state.update_data(gender=message.text)
    await message.answer("📍 Введите ваше местоположение:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(RegistrationStates.LOCATION)

@router.message(RegistrationStates.LOCATION)
async def location_handler(message: Message, state: FSMContext, crypto: CryptoService):
    is_valid, normalized_city = city_validator.validate_city(message.text)

    if not is_valid:
        await message.answer("⚠️ Город не найден. Пожалуйста, введите существующий российский город")
        return

    await state.update_data(location=crypto.encrypt(normalized_city))
    await message.answer("📸 Отправьте 1-3 фотографии")
    await state.set_state(RegistrationStates.PHOTOS)

@router.message(RegistrationStates.PHOTOS, F.photo | F.text)
async def photos_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])

    if message.photo:
        if len(photos) >= 3:
            await message.answer("⚠️ Максимум 3 фотографии")
            return

@router.message(RegistrationStates.PHOTOS, F.photo | F.text)
async def photos_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])

    if message.photo:
        if len(photos) >= 3:
            await message.answer("⚠️ Максимум 3 фотографии")
            return

        photos.append(message.photo[-1].file_id)
        await state.update_data(photos=photos)

        builder = ReplyKeyboardBuilder()
        builder.add(KeyboardButton(text="📷 Добавить еще"))
        builder.add(KeyboardButton(text="✅ Продолжить"))

        await message.answer(
            f"✅ Добавлено {len(photos)}/3 фото",
            reply_markup=builder.as_markup(resize_keyboard=True)
        )
    elif message.text == "✅ Продолжить":
        if not photos:
            await message.answer("⚠️ Нужно добавить хотя бы 1 фото")
        else:
            await message.answer("✏️ Напишите описание вашего профиля:", reply_markup=ReplyKeyboardRemove())
            await state.set_state(RegistrationStates.DESCRIPTION)

@router.message(RegistrationStates.DESCRIPTION)
async def description_handler(
    message: Message,
    state: FSMContext,
    db: Database,
    crypto: CryptoService
):
    user_data = await state.get_data()
    user_data["description"] = crypto.encrypt(message.text)

    if await db.save_user(
        telegram_id=message.from_user.id,
        user_data=user_data
    ):
        await message.answer("✅ Регистрация завершена!")
        await show_main_menu(message, state)
    else:
        await message.answer("❌ Ошибка сохранения данных. Попробуйте позже.")

    await state.clear()