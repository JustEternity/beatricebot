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
from bot.services.s3storage import S3Service
from bot.services.image_moderator import EnhancedContentDetector
from bot.services.text_moderator import TextModerator  # Импортируем новый класс

from io import BytesIO
import logging
import os

logger = logging.getLogger(__name__)
router = Router()

# Инициализация модератора текста
text_moderator = TextModerator()

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, db: Database):
    policyid, POLICY_TEXT = await db.get_actual_policy_id()
    await state.update_data(idpolicy=policyid)
    user_id = message.from_user.id
    if await db.is_user_registered(user_id):
        policy_accept = await db.check_actual_policy(user_id, policyid)
        likes_count = await db.get_unviewed_likes_count(user_id)
        if policy_accept:
            await show_main_menu(message, state, likes_count)
        else:
            await message.answer(POLICY_TEXT, reply_markup=policy_keyboard())
            await state.set_state(RegistrationStates.POLICY_SECOND_TIME)
        return
    await message.answer(POLICY_TEXT, reply_markup=policy_keyboard())
    await state.set_state(RegistrationStates.POLICY)


@router.message(RegistrationStates.POLICY_SECOND_TIME, F.text.in_(["✅ Я согласен", "❌ Я не согласен"]))
async def policy_second_handler(message: Message, state: FSMContext, db: Database):
    if message.text == "✅ Я согласен":
        await state.update_data(policy=True)
        user_data = await state.get_data()
        res = await db.save_policy_acception(message.from_user.id, user_data)
        if res:
            await message.answer("🎉 Спасибо! Вы можете продолжить использование бота",
                                 reply_markup=ReplyKeyboardRemove())
            await show_main_menu(message, state)
        else:
            await message.answer("🚫 Произошла ошибка, попробуйте позже", reply_markup=ReplyKeyboardRemove())
    else:
        await message.answer("🚫 Вы не можете использовать бот, без согласия на ОПД. /start - начать заново")
        await state.clear()


@router.message(RegistrationStates.POLICY, F.text.in_(["✅ Я согласен", "❌ Я не согласен"]))
async def policy_handler(message: Message, state: FSMContext):
    if message.text == "✅ Я согласен":
        await state.update_data(policy=True)
        await message.answer("🎉 Спасибо! Как вас зовут?", reply_markup=ReplyKeyboardRemove())
        await state.set_state(RegistrationStates.NAME)
    else:
        await message.answer("🚫 Регистрация отменена. /start - начать заново")
        await state.clear()


@router.message(RegistrationStates.NAME)
async def name_handler(message: Message, state: FSMContext, crypto: CryptoService):
    # Используем text_moderator вместо локальной функции validate_text
    is_valid, error_msg = text_moderator.validate_text(message.text)
    if not is_valid:
        await message.answer(error_msg)
        return
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

    # Проверяем текст города через модератор
    is_valid, error_msg = text_moderator.validate_text(normalized_city)
    if not is_valid:
        await message.answer(error_msg)
        return

    await state.update_data(location=crypto.encrypt(normalized_city))
    await message.answer("📸 Отправьте 1-3 фотографии")
    await state.set_state(RegistrationStates.PHOTOS)


@router.message(RegistrationStates.PHOTOS, F.photo | F.text)
async def photos_handler(message: Message, state: FSMContext, s3: S3Service, bot: Bot):
    data = await state.get_data()
    photos = data.get("photos", [])

    if message.photo:
        if len(photos) >= 3:
            await message.answer("⚠️ Максимум 3 фотографии")
            return

        try:
            file_id = message.photo[-1].file_id
            file = await bot.get_file(file_id)

            file_data = BytesIO()
            await bot.download_file(file.file_path, file_data)

            # Сохраняем временный файл для анализа
            temp_path = f"temp_{message.from_user.id}.jpg"
            with open(temp_path, "wb") as f:
                f.write(file_data.getbuffer())

            # Анализируем фото
            detector = EnhancedContentDetector()
            result = detector.analyze_image(temp_path)

            # Удаляем временный файл
            try:
                os.remove(temp_path)
            except:
                pass

            # Проверяем результат модерации
            if result.get('verdict') == '🔴 BANNED':
                violations = []
                if result['violations'].get('nudity'):
                    violations.append("🔞 обнаженные тела/эротика")
                if result['violations'].get('drugs'):
                    violations.append("💊 наркотики/наркотические средства")
                if result['violations'].get('weapons'):
                    violations.append("🔫 оружие/опасные предметы")
                if result['violations'].get('violence'):
                    violations.append("💢 насилие/кровь")

                await message.answer(
                    "⚠️ Фото отклонено модерацией. Причины:\n" +
                    "\n".join(violations) +
                    "\nПожалуйста, отправьте другое фото."
                )
                return

            # Если фото прошло модерацию, загружаем его в S3
            file_data.seek(0)
            s3_url = await s3.upload_photo(file_data, message.from_user.id)

            if not s3_url:
                await message.answer("⚠️ Ошибка загрузки фото. Попробуйте еще раз")
                return

            photos.append({
                "file_id": file_id,
                "s3_url": s3_url,
                "moderation_result": result
            })

            await state.update_data(photos=photos)

            builder = ReplyKeyboardBuilder()
            builder.add(KeyboardButton(text="📷 Добавить еще"))
            if len(photos) >= 1:
                builder.add(KeyboardButton(text="✅ Продолжить"))

            await message.answer(
                f"✅ Добавлено {len(photos)}/3 фото",
                reply_markup=builder.as_markup(resize_keyboard=True)
            )

        except Exception as e:
            logger.error(f"Photo upload error: {str(e)}")
            await message.answer("⚠️ Ошибка при обработке фото. Попробуйте еще раз")

    elif message.text == "✅ Продолжить":
        if not photos:
            await message.answer("⚠️ Нужно добавить хотя бы 1 фото")
        else:
            await message.answer("✏️ Напишите описание вашего профиля:", reply_markup=ReplyKeyboardRemove())
            await state.set_state(RegistrationStates.DESCRIPTION)


@router.message(RegistrationStates.DESCRIPTION)
async def description_handler(message: Message, state: FSMContext, db: Database, crypto: CryptoService):
    # Используем text_moderator вместо локальной функции validate_text
    is_valid, error_msg = text_moderator.validate_text(message.text)
    if not is_valid:
        await message.answer(error_msg)
        return

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