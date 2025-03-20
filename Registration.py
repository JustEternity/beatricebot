import os
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InputMediaPhoto
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.enums import ParseMode
from dotenv import load_dotenv
import asyncpg
from cryptography.fernet import Fernet

# Загружаем переменные окружения из .env
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Текст политики конфиденциальности
POLICY_TEXT = """
📜 *Политика конфиденциальности:*

1. Мы собираем только необходимые данные для регистрации.
2. Ваши данные не будут переданы третьим лицам.
3. Вы можете запросить удаление ваших данных в любой момент.

Для продолжения регистрации, пожалуйста, подтвердите, что вы согласны с политикой конфиденциальности.
"""

# Определяем состояния для FSM
class RegistrationStates(StatesGroup):
    POLICY = State()
    NAME = State()
    AGE = State()
    GENDER = State()
    LOCATION = State()
    PHOTOS = State()
    DESCRIPTION = State()

# Функция для подключения к PostgreSQL
async def connect_to_db():
    try:
        conn = await asyncpg.connect(
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        )
        logging.info("Подключение к базе данных успешно установлено!")
        return conn
    except Exception as e:
        logging.error(f"Ошибка подключения к базе данных: {e}")
        return None

# Функция для сохранения данных пользователя в базу данных
async def save_user_to_db(user_data, telegram_id):
    conn = await connect_to_db()
    if conn:
        try:
            # Сохраняем данные в таблицу User
            await conn.execute("""
                INSERT INTO users (
                    TelegramID, Name, Age, Gender, City, ProfileDescription,
                    SubscriptionStatus, ModerationStatus, VerificationStatus,
                    RegistrationDate, LastActionDate, ProfilePriorityCoefficient,
                    AccountStatus, Mail
                ) VALUES (
                    $1, $2, $3, $4, $5, $6,
                    $7, $8, $9,
                    $10, $11, $12,
                    $13, $14
                )
            """, telegram_id, user_data['name'], user_data['age'], user_data['gender'],
                user_data['location'], user_data['description'], False, False, False,
                datetime.now(), datetime.now(), 0.00, 'active', None)

            # Сохраняем фотографии в таблицу Photos
            for index, photo_id in enumerate(user_data['photos']):
                await conn.execute("""
                    INSERT INTO Photos (
                        UserTelegramID, PhotoFileID, PhotoDisplayOrder
                    ) VALUES (
                        $1, $2, $3
                    )
                """, telegram_id, photo_id, index + 1)

            logging.info("Данные пользователя успешно сохранены в базу данных!")
            return True
        except Exception as e:
            logging.error(f"Ошибка при сохранении данных: {e}")
            return False
        finally:
            await conn.close()
    else:
        return False

# Функция для проверки регистрации пользователя
async def is_user_registered(telegram_id):
    conn = await connect_to_db()
    if conn:
        try:
            result = await conn.fetchrow("""
                SELECT telegramid FROM users WHERE telegramid = $1
            """, telegram_id)
            return result is not None
        except Exception as e:
            logging.error(f"Ошибка при проверке регистрации пользователя: {e}")
            return False
        finally:
            await conn.close()
    else:
        return False

# Функция для начала регистрации
async def start(message: types.Message, state: FSMContext):
    telegram_id = message.from_user.id

    if await is_user_registered(telegram_id):
        await message.answer("✅ Готово к использованию!")
        return

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Я согласен"), KeyboardButton(text="❌ Я не согласен")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(POLICY_TEXT, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    await state.set_state(RegistrationStates.POLICY)

# Функция для обработки согласия с политикой
async def confirm_policy(message: types.Message, state: FSMContext):
    user_response = message.text

    if user_response == "✅ Я согласен":
        await message.answer("🎉 Спасибо за согласие! Давайте начнем регистрацию. Как вас зовут?")
        await state.set_state(RegistrationStates.NAME)
    elif user_response == "❌ Я не согласен":
        await message.answer("🚫 Регистрация отменена. Если передумаете, нажмите /start.")
        await state.clear()
    else:
        await message.answer("Пожалуйста, используйте кнопки ниже.")

# Функция для обработки имени
async def get_name(message: types.Message, state: FSMContext):
    f = Fernet(os.getenv("cryptography_key"))
    encrypted_name = f.encrypt(message.text.encode())
    await state.update_data(name=encrypted_name)
    await message.answer(f"👋 Приятно познакомиться, {message.text}! Сколько вам лет?")
    await state.set_state(RegistrationStates.AGE)

# Функция для обработки возраста
async def get_age(message: types.Message, state: FSMContext):
    try:
        age = int(message.text)
        if age <= 18 or age > 100:
            await message.answer("Пожалуйста, введите допустимый возраст (от 18 до 100).")
        else:
            await state.update_data(age=age)
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="👨 Мужской"), KeyboardButton(text="👩 Женский")]
                ],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            await message.answer("🎂 Отлично! Теперь выберите ваш пол.", reply_markup=keyboard)
            await state.set_state(RegistrationStates.GENDER)
    except ValueError:
        await message.answer("Пожалуйста, введите число.")

# Функция для обработки пола
async def get_gender(message: types.Message, state: FSMContext):
    user_response = message.text

    if user_response in ["👨 Мужской", "👩 Женский"]:
        await state.update_data(gender=user_response)
        await message.answer("📍 Теперь напишите, где вы живете.")
        await state.set_state(RegistrationStates.LOCATION)
    else:
        await message.answer("Пожалуйста, выберите пол, используя кнопки ниже.")

# Функция для обработки местоположения
async def get_location(message: types.Message, state: FSMContext):
    f = Fernet(os.getenv("cryptography_key"))
    encrypted_location = f.encrypt(message.text.encode())
    await state.update_data(location=encrypted_location)
    await message.answer("📸 Теперь отправьте от 1 до 3 фотографий.")
    await state.set_state(RegistrationStates.PHOTOS)

# Функция для обработки фотографий
async def get_photos(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    photos = user_data.get('photos', [])

    if message.photo:
        photo = message.photo[-1]
        photos.append(photo.file_id)
        await state.update_data(photos=photos)

        if len(photos) >= 3:
            await message.answer("✅ Вы загрузили максимальное количество фото. Теперь напишите описание вашей анкеты.")
            await state.set_state(RegistrationStates.DESCRIPTION)
        else:
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="📷 Добавить еще фото"), KeyboardButton(text="➡️ Продолжить")]
                ],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            await message.answer(f"✅ Фото добавлено. Вы можете отправить еще {3 - len(photos)} фото.", reply_markup=keyboard)
    else:
        if message.text == "➡️ Продолжить":
            if len(photos) == 0:
                await message.answer("Пожалуйста, отправьте хотя бы одно фото.")
            else:
                await message.answer("Теперь напишите описание вашей анкеты.")
                await state.set_state(RegistrationStates.DESCRIPTION)
        else:
            await message.answer("Пожалуйста, отправьте фото или нажмите 'Продолжить'.")

# Функция для обработки описания анкеты
async def get_description(message: types.Message, state: FSMContext):
    f = Fernet(os.getenv("cryptography_key"))
    encrypted_description = f.encrypt(message.text.encode())
    await state.update_data(description=encrypted_description)
    user_data = await state.get_data()

    # Формируем текст анкеты
    profile_text = (
        f"🎉 *Спасибо за регистрацию!*\n\n"
        f"📝 *Ваша анкета:*\n"
        f"👤 *Имя:* {f.decrypt(user_data['name']).decode()}\n"
        f"📅 *Возраст:* {user_data['age']}\n"
        f"🚻 *Пол:* {user_data['gender']}\n"
        f"📍 *Местоположение:* {f.decrypt(user_data['location']).decode()}\n"
        f"📄 *Описание:* {f.decrypt(user_data['description']).decode()}\n\n"
        f"Если что-то не так, нажмите /start, чтобы начать заново."
    )

    # Создаем список медиафайлов для отправки
    media_group = []
    for index, photo_id in enumerate(user_data['photos']):
        if index == 0:
            media_group.append(InputMediaPhoto(media=photo_id, caption=profile_text, parse_mode=ParseMode.MARKDOWN))
        else:
            media_group.append(InputMediaPhoto(media=photo_id))

    # Отправляем медиагруппу
    if media_group:
        await message.answer_media_group(media=media_group)
    else:
        await message.answer(profile_text, parse_mode=ParseMode.MARKDOWN)

    # Сохраняем данные в базу данных
    telegram_id = message.from_user.id
    if await save_user_to_db(user_data, telegram_id):
        await message.answer("✅ Ваши данные успешно сохранены в базе данных!")
    else:
        await message.answer("❌ Произошла ошибка при сохранении данных. Пожалуйста, попробуйте позже.")

    await state.clear()

# Функция для отмены регистрации
async def cancel(message: types.Message, state: FSMContext):
    await message.answer("🚫 Регистрация отменена.")
    await state.clear()

# Запуск бота
async def main():
    bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
    dp = Dispatcher()

    # Регистрируем обработчики
    dp.message.register(start, Command("start"))
    dp.message.register(confirm_policy, RegistrationStates.POLICY)
    dp.message.register(get_name, RegistrationStates.NAME)
    dp.message.register(get_age, RegistrationStates.AGE)
    dp.message.register(get_gender, RegistrationStates.GENDER)
    dp.message.register(get_location, RegistrationStates.LOCATION)
    dp.message.register(get_photos, RegistrationStates.PHOTOS)
    dp.message.register(get_description, RegistrationStates.DESCRIPTION)
    dp.message.register(cancel, Command("cancel"))

    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())