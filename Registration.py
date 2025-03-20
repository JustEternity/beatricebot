import os
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.enums import ParseMode
from dotenv import load_dotenv
import asyncpg
import asyncio
from cryptography.fernet import Fernet

load_dotenv()

# настройка логирования
logging.basicConfig(level=logging.INFO)

# опд
POLICY_TEXT = """
📜 *Политика конфиденциальности:*

1. Мы собираем только необходимые данные для регистрации.
2. Ваши данные не будут переданы третьим лицам.
3. Вы можете запросить удаление ваших данных в любой момент.

Для продолжения регистрации, пожалуйста, подтвердите, что вы согласны с политикой конфиденциальности.
"""

# состояния для FSM (диалоги с пользователем)
class RegistrationStates(StatesGroup):
    POLICY = State()
    NAME = State()
    AGE = State()
    GENDER = State()
    LOCATION = State()
    PHOTOS = State()
    DESCRIPTION = State()
    MAIN_MENU = State()
    EDIT_NAME = State() 
    EDIT_AGE = State()
    EDIT_LOCATION = State()
    EDIT_PHOTOS = State()
    EDIT_DESCRIPTION = State()

    TEST_IN_PROGRESS = State()
    TEST_QUESTION = State()

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

# сохранения данных пользователя в бд
async def save_user_to_db(user_data, telegram_id):
    conn = await connect_to_db()
    if conn:
        try:
            # сохр данные в таблицу users
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

            # сохр фотки в таблицу Photos
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

# валидация проверки регистрации пользователя
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

# начало регистрации
async def start(message: types.Message, state: FSMContext):
    telegram_id = message.from_user.id

    if await is_user_registered(telegram_id):
        # вместо простого сообщения вызываем функцию показа меню
        await show_main_menu(message, state)
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

# обработка согласия с опд
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

# обработка имени
async def get_name(message: types.Message, state: FSMContext):
    f = Fernet(os.getenv("cryptography_key"))
    encrypted_name = f.encrypt(message.text.encode())
    await state.update_data(name=encrypted_name)
    await message.answer(f"👋 Приятно познакомиться, {message.text}! Сколько вам лет?")
    await state.set_state(RegistrationStates.AGE)

# обработка возраста
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

# обработка пола
async def get_gender(message: types.Message, state: FSMContext):
    user_response = message.text

    if user_response in ["👨 Мужской", "👩 Женский"]:
        await state.update_data(gender=user_response)
        await message.answer("📍 Теперь напишите, где вы живете.")
        await state.set_state(RegistrationStates.LOCATION)
    else:
        await message.answer("Пожалуйста, выберите пол, используя кнопки ниже.")

# обработка местоположения
async def get_location(message: types.Message, state: FSMContext):
    f = Fernet(os.getenv("cryptography_key"))
    encrypted_location = f.encrypt(message.text.encode())
    await state.update_data(location=encrypted_location)
    await message.answer("📸 Теперь отправьте от 1 до 3 фотографий.")
    await state.set_state(RegistrationStates.PHOTOS)

# обработка фотографий
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

# обработка описания анкеты
async def get_description(message: types.Message, state: FSMContext):
    f = Fernet(os.getenv("cryptography_key").encode())
    encrypted_description = f.encrypt(message.text.encode())
    await state.update_data(description=encrypted_description)
    user_data = await state.get_data()

    profile_text = (
        f"🎉 *Спасибо за регистрацию!*\n\n"
        f"📝 *Ваша анкета:*\n"
        f"👤 *Имя:* {f.decrypt(user_data['name']).decode()}\n"
        f"📅 *Возраст:* {user_data['age']}\n"
        f"🚻 *Пол:* {user_data['gender']}\n"
        f"📍 *Местоположение:* {f.decrypt(user_data['location']).decode()}\n"
        f"📄 *Описание:* {f.decrypt(user_data['description']).decode()}\n\n"
    )

    # создание списка медиафайлов для отправки
    media_group = []
    for index, photo_id in enumerate(user_data['photos']):
        if index == 0:
            media_group.append(InputMediaPhoto(media=photo_id, caption=profile_text, parse_mode=ParseMode.MARKDOWN))
        else:
            media_group.append(InputMediaPhoto(media=photo_id))

    if media_group:
        await message.answer_media_group(media=media_group)
    else:
        await message.answer(profile_text, parse_mode=ParseMode.MARKDOWN)

    telegram_id = message.from_user.id
    if await save_user_to_db(user_data, telegram_id):
        await message.answer("✅ Ваши данные успешно сохранены в базе данных!")
    else:
        await message.answer("❌ Произошла ошибка при сохранении данных. Пожалуйста, попробуйте позже.")

    await show_main_menu(message, state)

# отмена регистрации
async def cancel(message: types.Message, state: FSMContext):
    await message.answer("🚫 Регистрация отменена.")
    await state.clear()

# получение данных пользователя из БД
async def get_user_data(telegram_id):
    conn = await connect_to_db()
    if conn:
        try:
            user_data = await conn.fetchrow("""
                SELECT * FROM users WHERE telegramid = $1
            """, telegram_id)
            
            photos = await conn.fetch("""
                SELECT photofileid FROM photos 
                WHERE usertelegramid = $1 
                ORDER BY photodisplayorder
            """, telegram_id)
            
            photo_ids = [photo['photofileid'] for photo in photos]
            
            # создание словаря с данными пользователя
            result = {
                'name': user_data['name'],
                'age': user_data['age'],
                'gender': user_data['gender'],
                'location': user_data['city'],
                'description': user_data['profiledescription'],
                'photos': photo_ids
            }
            
            return result
        except Exception as e:
            logging.error(f"Ошибка при получении данных пользователя: {e}")
            return None
        finally:
            await conn.close()
    else:
        return None

# отображение главного меню
async def show_main_menu(message: types.Message, state: FSMContext):
    telegram_id = message.from_user.id
    
    # валидация проверки, зарегистрирован ли пользователь
    if not await is_user_registered(telegram_id):
        await message.answer("Вы еще не зарегистрированы. Нажмите /start для регистрации.")
        return
    
    user_data = await get_user_data(telegram_id)
    if not user_data:
        await message.answer("Не удалось загрузить ваши данные. Попробуйте позже.")
        return
    
    # инлайн-клавиатура для меню
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Моя анкета", callback_data="view_profile")],
        [InlineKeyboardButton(text="✏️ Изменить анкету", callback_data="edit_profile")],
        [InlineKeyboardButton(text="📝 Пройти тест", callback_data="take_test")]
    ])
    
    menu_message = await message.answer("🔹 Главное меню 🔹", reply_markup=keyboard)
    
    # сохр ID сообщения в состоянии
    await state.update_data(last_menu_message_id=menu_message.message_id)
    await state.set_state(RegistrationStates.MAIN_MENU)

# обработка нажатия на кнопку "Моя анкета"
async def view_profile(callback: types.CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    
    user_data = await get_user_data(telegram_id)
    if not user_data:
        await callback.answer("Не удалось загрузить ваши данные. Попробуйте позже.")
        return
    
    # дешифрование
    f = Fernet(os.getenv("cryptography_key").encode())
    name = f.decrypt(user_data['name']).decode() if isinstance(user_data['name'], bytes) else user_data['name']
    location = f.decrypt(user_data['location']).decode() if isinstance(user_data['location'], bytes) else user_data['location']
    description = f.decrypt(user_data['description']).decode() if isinstance(user_data['description'], bytes) else user_data['description']
    
    profile_text = (
        f"👤 *Ваша анкета:*\n\n"
        f"*Имя:* {name}\n"
        f"*Возраст:* {user_data['age']}\n"
        f"*Пол:* {user_data['gender']}\n"
        f"*Местоположение:* {location}\n"
        f"*Описание:* {description}"
    )
    
    # кнопка для возврата в меню
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu")]
    ])
    
    # если есть фотки, отправляем их с текстом анкеты
    if user_data['photos']:
        # сначала удаляем текущее сообщение с меню
        await callback.message.delete()
        
        # создаем медиагруппу с фотками
        media_group = []
        for i, photo_id in enumerate(user_data['photos']):
            # добавляем подпись только к первой фотке
            if i == 0:
                media_group.append(InputMediaPhoto(media=photo_id, caption=profile_text, parse_mode=ParseMode.MARKDOWN))
            else:
                media_group.append(InputMediaPhoto(media=photo_id))
        
        # отправляем медиагруппу и сохраняем ID сообщений
        sent_messages = await callback.message.answer_media_group(media=media_group)
        
        # сохраняем ID сообщений с фотографиями в состоянии
        photo_message_ids = [msg.message_id for msg in sent_messages]
        await state.update_data(profile_photo_message_ids=photo_message_ids)
        
        # отправляем кнопку возврата отдельным сообщением
        menu_msg = await callback.message.answer("Выберите действие:", reply_markup=keyboard)
        await state.update_data(profile_menu_message_id=menu_msg.message_id)
    else:
        # если фоток нет, просто редактируем текущее сообщение
        await callback.message.edit_text(profile_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
    
    await callback.answer()

# обработка нажатия на кнопку "Изменить анкету"
async def edit_profile(callback_or_message, state: FSMContext):
    # получаем данные состояния
    user_data = await state.get_data()
    
    # удаляем сообщения с фотками (если они есть)
    if isinstance(callback_or_message, types.CallbackQuery) and 'profile_photo_message_ids' in user_data and user_data['profile_photo_message_ids']:
        for msg_id in user_data['profile_photo_message_ids']:
            try:
                await callback_or_message.bot.delete_message(callback_or_message.from_user.id, msg_id)
            except Exception as e:
                logging.error(f"Ошибка при удалении сообщения с фото: {e}")
        
        # удаляяем ID сообщений из состояния
        await state.update_data(profile_photo_message_ids=None)
    
    # создаем клавиатуру с параметрами для редактирования
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Изменить имя", callback_data="edit_name")],
        [InlineKeyboardButton(text="🔢 Изменить возраст", callback_data="edit_age")],
        [InlineKeyboardButton(text="📍 Изменить местоположение", callback_data="edit_location")],
        [InlineKeyboardButton(text="📸 Изменить фото", callback_data="edit_photos")],
        [InlineKeyboardButton(text="📄 Изменить описание", callback_data="edit_description")],
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu")]
    ])
    
    # проверяем тип объекта и отправляем сообщение соответственно
    if isinstance(callback_or_message, types.CallbackQuery):
        await callback_or_message.message.edit_text("Выберите, что хотите изменить:", reply_markup=keyboard)
        await callback_or_message.answer()
    elif isinstance(callback_or_message, types.Message):
        # если это сообщение, отправляем новое сообщение с клавиатурой
        await callback_or_message.answer("Выберите, что хотите изменить:", reply_markup=keyboard)
    else:
        logging.error(f"Неподдерживаемый тип объекта в функции edit_profile: {type(callback_or_message)}")

# получение вопросов и ответов из бдшки
async def get_questions_and_answers(conn):
    questions_dict = {}
    answers_dict = {}

    try:
        # получаем все вопросы
        questions = await conn.fetch("SELECT questionid, questiontext FROM questions ORDER BY questionid;")
        for question in questions:
            question_id, question_text = question['questionid'], question['questiontext']
            questions_dict[question_id] = question_text

        # получаем все ответы
        answers = await conn.fetch("SELECT answerid, questionid, answertext FROM answers ORDER BY questionid, answerid;")
        for answer in answers:
            answer_id, question_id, answer_text = answer['answerid'], answer['questionid'], answer['answertext']
            if question_id not in answers_dict:
                answers_dict[question_id] = {}
            answers_dict[question_id][answer_id] = answer_text

        return questions_dict, answers_dict
    except Exception as e:
        logging.error(f"Ошибка при получении данных: {e}")
        return {}, {}

# сохр ответов пользователя
async def save_user_answers(conn, telegramid, user_answers):
    try:
        # сначала удаляем предыдущие ответы пользователя, если они есть
        await conn.execute('DELETE FROM useranswers WHERE usertelegramid = $1;', telegramid)
        
        # сохр новые ответы
        for question_id, answer_id in user_answers.items():
            await conn.execute('INSERT INTO useranswers (usertelegramid, questionid, answerid) VALUES ($1, $2, $3);',
                              telegramid, question_id, answer_id)
        return True
    except Exception as e:
        logging.error(f"Ошибка при сохранении ответов: {e}")
        return False

# обработка нажатия на кнопку "Пройти тест"
async def take_test(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()  # отвечаем на callback
    
    # получаем данные состояния
    user_data = await state.get_data()
    
    # удаляем сообщения с фотками, если они есть
    if 'profile_photo_message_ids' in user_data and user_data['profile_photo_message_ids']:
        for msg_id in user_data['profile_photo_message_ids']:
            try:
                await callback.bot.delete_message(callback.from_user.id, msg_id)
            except Exception as e:
                logging.error(f"Ошибка при удалении сообщения с фото: {e}")
        
        # удаляем ID сообщений из состояния
        await state.update_data(profile_photo_message_ids=None)
    
    if 'profile_menu_message_id' in user_data and user_data['profile_menu_message_id']:
        try:
            await callback.bot.delete_message(callback.from_user.id, user_data['profile_menu_message_id'])
        except Exception as e:
            logging.error(f"Ошибка при удалении сообщения с меню: {e}")
        
        # удаляем ID сообщения из состояния
        await state.update_data(profile_menu_message_id=None)
    
    # проходил ли пользователь тест ранее
    conn = await connect_to_db()
    if not conn:
        try:
            await callback.message.edit_text("❌ Не удалось подключиться к базе данных. Попробуйте позже.",
                                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                                [InlineKeyboardButton(text="◀️ Вернуться в меню", callback_data="back_to_menu")]
                                            ]))
        except Exception as e:
            logging.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.message.answer("❌ Не удалось подключиться к базе данных. Попробуйте позже.",
                                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                             [InlineKeyboardButton(text="◀️ Вернуться в меню", callback_data="back_to_menu")]
                                         ]))
        return
    
    try:
        # проверяем наличие ответов пользователя в бдшке
        has_answers = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM useranswers WHERE usertelegramid = $1)",
            callback.from_user.id
        )
        
        if has_answers:
            # если пользователь уже проходил тест, спрашиваем о повторном прохождении
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Да, хочу пройти заново", callback_data="confirm_test")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_menu")]
            ])
            
            try:
                await callback.message.edit_text(
                    "Вы уже проходили тест ранее. Хотите пройти его снова?\n\n"
                    "⚠️ Ваши предыдущие ответы будут удалены.",
                    reply_markup=keyboard
                )
            except Exception as e:
                logging.error(f"Ошибка при редактировании сообщения: {e}")
                await callback.message.answer(
                    "Вы уже проходили тест ранее. Хотите пройти его снова?\n\n"
                    "⚠️ Ваши предыдущие ответы будут удалены.",
                    reply_markup=keyboard
                )
            return
    except Exception as e:
        logging.error(f"Ошибка при проверке предыдущих ответов: {e}")
    finally:
        await conn.close()
    
    # если пользователь не проходил тест ранее, начинаем тест
    await start_test(callback, state)

# функция для подтверждения повторного прохождения теста
async def confirm_test(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await start_test(callback, state)

# начало теста
async def start_test(callback: types.CallbackQuery, state: FSMContext):
    # удаляем текущее сообщение с кнопкой "Пройти тест"
    try:
        await callback.message.delete()
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")
    
    # отправляем сообщение о начале теста
    start_message = await callback.message.answer("🔄 Загрузка теста...")
    
    # подключаемся к бдшке
    conn = await connect_to_db()
    if not conn:
        await start_message.edit_text("❌ Не удалось подключиться к базе данных. Попробуйте позже.",
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                         [InlineKeyboardButton(text="◀️ Вернуться в меню", callback_data="back_to_menu")]
                                     ]))
        return
    
    try:
        # удаляем предыдущие ответы пользователя, если они есть
        await conn.execute('DELETE FROM useranswers WHERE usertelegramid = $1;', callback.from_user.id)
        
        # получаем вопросы и ответы
        questions_dict, answers_dict = await get_questions_and_answers(conn)
        if not questions_dict or not answers_dict:
            await start_message.edit_text("❌ Не удалось загрузить вопросы и ответы. Попробуйте позже.",
                                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                             [InlineKeyboardButton(text="◀️ Вернуться в меню", callback_data="back_to_menu")]
                                         ]))
            return
        
        # сохр вопросы и ответы в состоянии
        await state.update_data(
            questions=questions_dict,
            answers=answers_dict,
            current_question_index=0,
            question_ids=list(questions_dict.keys()),
            user_answers={},
            test_message_id=start_message.message_id
        )
        
        # переходим к первому вопросу
        await state.set_state(RegistrationStates.TEST_QUESTION)
        await show_question(start_message, state)
        
    except Exception as e:
        logging.error(f"Ошибка при запуске теста: {e}")
        await start_message.edit_text("❌ Произошла ошибка при запуске теста. Попробуйте позже.",
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                         [InlineKeyboardButton(text="◀️ Вернуться в меню", callback_data="back_to_menu")]
                                     ]))
    finally:
        await conn.close()

# отображение текущего вопроса
async def show_question(message: types.Message, state: FSMContext):
    # получаем данные из состояния
    data = await state.get_data()
    questions = data.get('questions', {})
    answers = data.get('answers', {})
    question_ids = data.get('question_ids', [])
    current_index = data.get('current_question_index', 0)
    
    # проверяем, есть ли еще вопросы
    if current_index >= len(question_ids):
        # сохраняем результаты
        await finish_test(message, state)
        return
    
    # получаем текущий вопрос
    question_id = question_ids[current_index]
    question_text = questions[question_id]
    
    # создаем клавиатуру с вариантами ответов
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    # добавляем кнопки с вариантами ответов
    for answer_id, answer_text in answers[question_id].items():
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=answer_text, callback_data=f"answer_{question_id}_{answer_id}")
        ])
    
    # отображаем вопрос и варианты ответов
    try:
        await message.edit_text(
            f"Вопрос {current_index + 1} из {len(question_ids)}:\n\n{question_text}",
            reply_markup=keyboard
        )
    except Exception as e:
        logging.error(f"Ошибка при отображении вопроса: {e}")
        # если не удалось отредактировать сообщение, отправляем новое
        new_message = await message.answer(
            f"Вопрос {current_index + 1} из {len(question_ids)}:\n\n{question_text}",
            reply_markup=keyboard
        )
        await state.update_data(test_message_id=new_message.message_id)

# обработчик ответов на вопросы теста
async def process_test_answer(callback: types.CallbackQuery, state: FSMContext):
    # получаем данные из callback_data
    _, question_id, answer_id = callback.data.split('_')
    question_id, answer_id = int(question_id), int(answer_id)
    
    # получаем данные из состояния
    data = await state.get_data()
    user_answers = data.get('user_answers', {})
    current_index = data.get('current_question_index', 0)
    
    # сохраняем ответ пользователя
    user_answers[question_id] = answer_id
    
    # обновляем индекс текущего вопроса
    current_index += 1
    
    # обновляем данные в состоянии
    await state.update_data(
        user_answers=user_answers,
        current_question_index=current_index
    )
    
    # переходим к следующему вопросу
    await show_question(callback.message, state)
    await callback.answer()

# завершение теста и сохр результатов
async def finish_test(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_answers = data.get('user_answers', {})
    
    conn = await connect_to_db()
    if not conn:
        await message.edit_text("❌ Не удалось подключиться к базе данных для сохранения результатов. Попробуйте позже.",
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                   [InlineKeyboardButton(text="◀️ Вернуться в меню", callback_data="back_to_menu")]
                               ]))
        return
    
    try:
        # сохр ответы пользователя
        success = await save_user_answers(conn, message.chat.id, user_answers)
        
        if success:
            # создаем кнопку для возврата в меню
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Вернуться в меню", callback_data="back_to_menu")]
            ])
            
            # отобрж сообщение об успешном завершении теста
            try:
                await message.edit_text("✅ Тест успешно пройден! Спасибо за ваши ответы.", reply_markup=keyboard)
            except Exception as e:
                logging.error(f"Ошибка при отображении результатов: {e}")
                await message.answer("✅ Тест успешно пройден! Спасибо за ваши ответы.", reply_markup=keyboard)
        else:
            try:
                await message.edit_text("❌ Произошла ошибка при сохранении результатов теста.", 
                                       reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                           [InlineKeyboardButton(text="◀️ Вернуться в меню", callback_data="back_to_menu")]
                                       ]))
            except Exception as e:
                logging.error(f"Ошибка при отображении сообщения об ошибке: {e}")
                await message.answer("❌ Произошла ошибка при сохранении результатов теста.", 
                                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                        [InlineKeyboardButton(text="◀️ Вернуться в меню", callback_data="back_to_menu")]
                                    ]))
    except Exception as e:
        logging.error(f"Ошибка при завершении теста: {e}")
        try:
            await message.edit_text("❌ Произошла ошибка при обработке результатов теста.", 
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                       [InlineKeyboardButton(text="◀️ Вернуться в меню", callback_data="back_to_menu")]
                                   ]))
        except Exception as e2:
            logging.error(f"Ошибка при отображении сообщения об ошибке: {e2}")
            await message.answer("❌ Произошла ошибка при обработке результатов теста.", 
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                   [InlineKeyboardButton(text="◀️ Вернуться в меню", callback_data="back_to_menu")]
                               ]))
    finally:
        await conn.close()
    
    # возвращаемся в главное меню
    await state.set_state(RegistrationStates.MAIN_MENU)

# возврат в главное меню
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    
    # создаем клавиатуру главного меню с кнопкой "Изменить анкету"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Моя анкета", callback_data="view_profile")],
        [InlineKeyboardButton(text="✏️ Изменить анкету", callback_data="edit_profile")],
        [InlineKeyboardButton(text="📝 Пройти тест", callback_data="take_test")]
    ])
    
    try:
        menu_message = await callback.message.edit_text("🔹 Главное меню 🔹", reply_markup=keyboard)
        await state.update_data(profile_menu_message_id=menu_message.message_id)
    except Exception as e:
        logging.error(f"Ошибка при редактировании сообщения: {e}")
        menu_message = await callback.message.answer("🔹 Главное меню 🔹", reply_markup=keyboard)
        await state.update_data(profile_menu_message_id=menu_message.message_id)
    
    # устанавливаем состояние MAIN_MENU
    await state.set_state(RegistrationStates.MAIN_MENU)
    await callback.answer()

# обработчик кнопки "Изменить имя"
async def edit_name_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите новое имя:")
    await state.set_state(RegistrationStates.EDIT_NAME)
    await callback.answer()

# обработчик ввода нового имени
async def process_edit_name(message: types.Message, state: FSMContext):
    f = Fernet(os.getenv("cryptography_key").encode())
    encrypted_name = f.encrypt(message.text.encode())
    
    # обновляем имя в бдшке
    conn = await connect_to_db()
    if conn:
        try:
            await conn.execute("""
                UPDATE users SET name = $1 WHERE telegramid = $2
            """, encrypted_name, message.from_user.id)
            await message.answer(f"✅ Имя успешно изменено на {message.text}!")
        except Exception as e:
            logging.error(f"Ошибка при обновлении имени: {e}")
            await message.answer("❌ Произошла ошибка при обновлении имени.")
        finally:
            await conn.close()
    
    # создаем клавиатуру для редактирования
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Изменить имя", callback_data="edit_name")],
        [InlineKeyboardButton(text="🔢 Изменить возраст", callback_data="edit_age")],
        [InlineKeyboardButton(text="📍 Изменить местоположение", callback_data="edit_location")],
        [InlineKeyboardButton(text="📸 Изменить фото", callback_data="edit_photos")],
        [InlineKeyboardButton(text="📄 Изменить описание", callback_data="edit_description")],
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu")]
    ])
    
    # отправляем новое меню редактирования
    await message.answer("Выберите, что еще хотите изменить:", reply_markup=keyboard)

# обработчик кнопки "Изменить возраст"
async def edit_age_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите новый возраст:")
    await state.set_state(RegistrationStates.EDIT_AGE)
    await callback.answer()

# обработчик ввода нового возраста
async def process_edit_age(message: types.Message, state: FSMContext):
    try:
        age = int(message.text)
        if age <= 18 or age > 100:
            await message.answer("Пожалуйста, введите допустимый возраст (от 18 до 100).")
            return
        
        # обновляем возраст в бдшке
        conn = await connect_to_db()
        if conn:
            try:
                await conn.execute("""
                    UPDATE users SET age = $1 WHERE telegramid = $2
                """, age, message.from_user.id)
                await message.answer(f"✅ Возраст успешно изменен на {age}!")
            except Exception as e:
                logging.error(f"Ошибка при обновлении возраста: {e}")
                await message.answer("❌ Произошла ошибка при обновлении возраста.")
            finally:
                await conn.close()
        
        # возвращаемся в меню редактирования
        await edit_profile(await message.answer("Выберите, что еще хотите изменить:"), state)
    except ValueError:
        await message.answer("Пожалуйста, введите число.")

# обработчик кнопки "Изменить местоположение"
async def edit_location_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите новое местоположение:")
    await state.set_state(RegistrationStates.EDIT_LOCATION)
    await callback.answer()

# обработчик ввода нового местоположения
async def process_edit_location(message: types.Message, state: FSMContext):
    f = Fernet(os.getenv("cryptography_key").encode())
    encrypted_location = f.encrypt(message.text.encode())
    
    # обновляем местоположение в базе данных
    conn = await connect_to_db()
    if conn:
        try:
            await conn.execute("""
                UPDATE users SET city = $1 WHERE telegramid = $2
            """, encrypted_location, message.from_user.id)
            await message.answer(f"✅ Местоположение успешно изменено на {message.text}!")
        except Exception as e:
            logging.error(f"Ошибка при обновлении местоположения: {e}")
            await message.answer("❌ Произошла ошибка при обновлении местоположения.")
        finally:
            await conn.close()
    
    # возвращаемся в меню редактирования
    await edit_profile(await message.answer("Выберите, что еще хотите изменить:"), state)

# обработчик кнопки "Изменить описание"
async def edit_description_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите новое описание анкеты:")
    await state.set_state(RegistrationStates.EDIT_DESCRIPTION)
    await callback.answer()

# обработчик ввода нового описания
async def process_edit_description(message: types.Message, state: FSMContext):
    f = Fernet(os.getenv("cryptography_key").encode())
    encrypted_description = f.encrypt(message.text.encode())
    
    # обновляем описание в бдшке
    conn = await connect_to_db()
    if conn:
        try:
            await conn.execute("""
                UPDATE users SET profiledescription = $1 WHERE telegramid = $2
            """, encrypted_description, message.from_user.id)
            await message.answer("✅ Описание анкеты успешно обновлено!")
        except Exception as e:
            logging.error(f"Ошибка при обновлении описания: {e}")
            await message.answer("❌ Произошла ошибка при обновлении описания.")
        finally:
            await conn.close()
    
    # возвращаемся в меню редактирования
    await edit_profile(await message.answer("Выберите, что еще хотите изменить:"), state)

# обработчик кнопки "Изменить фото"
async def edit_photos_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Отправьте новые фотографии (до 3 штук). Старые фотографии будут заменены.")
    await state.set_state(RegistrationStates.EDIT_PHOTOS)
    # очищаем список фотографий в состоянии
    await state.update_data(edit_photos=[])
    await callback.answer()

# обработчик загрузки новых фоток
async def process_edit_photos(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    photos = user_data.get('edit_photos', [])
    
    if message.photo:
        photo = message.photo[-1]
        photos.append(photo.file_id)
        await state.update_data(edit_photos=photos)
        
        if len(photos) >= 3:
            # если загружено максимальное количество фоток, сохраняем их
            await save_edited_photos(message, photos, state)
        else:
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="📷 Добавить еще фото"), KeyboardButton(text="➡️ Сохранить фото")]
                ],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            await message.answer(f"✅ Фото добавлено. Вы можете отправить еще {3 - len(photos)} фото или сохранить текущие.", reply_markup=keyboard)
    elif message.text == "➡️ Сохранить фото":
        if len(photos) == 0:
            await message.answer("Пожалуйста, отправьте хотя бы одно фото.")
        else:
            await save_edited_photos(message, photos, state)
    else:
        await message.answer("Пожалуйста, отправьте фото или нажмите 'Сохранить фото'.")

# сохр отредактированных фотографий
async def save_edited_photos(message: types.Message, photos, state: FSMContext):
    conn = await connect_to_db()
    if conn:
        try:
            # удаляем старые фотографии
            await conn.execute("""
                DELETE FROM photos WHERE usertelegramid = $1
            """, message.from_user.id)
            
            # добавляем новые фотографии
            for index, photo_id in enumerate(photos):
                await conn.execute("""
                    INSERT INTO photos (usertelegramid, photofileid, photodisplayorder)
                    VALUES ($1, $2, $3)
                """, message.from_user.id, photo_id, index + 1)
            
            await message.answer("✅ Фотографии успешно обновлены!")
        except Exception as e:
            logging.error(f"Ошибка при обновлении фотографий: {e}")
            await message.answer("❌ Произошла ошибка при обновлении фотографий.")
        finally:
            await conn.close()
    
    # возвращаемся в меню редактирования
    await edit_profile(await message.answer("Выберите, что еще хотите изменить:"), state)

# обработчик команды /menu
async def menu_command(message: types.Message, state: FSMContext):
    await show_main_menu(message, state)

# запуск бота
async def main():
    bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
    dp = Dispatcher()

    # регистрируем обработчики сообщений
    dp.message.register(start, Command("start"))
    dp.message.register(menu_command, Command("menu"))
    dp.message.register(confirm_policy, RegistrationStates.POLICY)
    dp.message.register(get_name, RegistrationStates.NAME)
    dp.message.register(get_age, RegistrationStates.AGE)
    dp.message.register(get_gender, RegistrationStates.GENDER)
    dp.message.register(get_location, RegistrationStates.LOCATION)
    dp.message.register(get_photos, RegistrationStates.PHOTOS)
    dp.message.register(get_description, RegistrationStates.DESCRIPTION)
    dp.message.register(cancel, Command("cancel"))
    
    # регистрируем обработчики для редактирования анкеты
    dp.message.register(process_edit_name, RegistrationStates.EDIT_NAME)
    dp.message.register(process_edit_age, RegistrationStates.EDIT_AGE)
    dp.message.register(process_edit_location, RegistrationStates.EDIT_LOCATION)
    dp.message.register(process_edit_photos, RegistrationStates.EDIT_PHOTOS)
    dp.message.register(process_edit_description, RegistrationStates.EDIT_DESCRIPTION)
    
    # регистрируем обработчики callback-запросов
    dp.callback_query.register(view_profile, F.data == "view_profile")
    dp.callback_query.register(edit_profile, F.data == "edit_profile")
    dp.callback_query.register(take_test, F.data == "take_test")
    dp.callback_query.register(back_to_menu, F.data == "back_to_menu")
    
    # регистрируем обработчики для кнопок редактирования
    dp.callback_query.register(edit_name_handler, F.data == "edit_name")
    dp.callback_query.register(edit_age_handler, F.data == "edit_age")
    dp.callback_query.register(edit_location_handler, F.data == "edit_location")
    dp.callback_query.register(edit_photos_handler, F.data == "edit_photos")
    dp.callback_query.register(edit_description_handler, F.data == "edit_description")

    # регистрация обработчиков для теста
    dp.callback_query.register(take_test, F.data == "take_test")
    dp.callback_query.register(confirm_test, F.data == "confirm_test")
    dp.callback_query.register(process_test_answer, F.data.startswith("answer_"))

    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())