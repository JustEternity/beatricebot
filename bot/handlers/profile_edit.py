from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InputMediaPhoto, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.enums import ParseMode

from bot.models.states import RegistrationStates
from bot.services.database import Database
from bot.services.encryption import CryptoService
from bot.keyboards.menus import edit_profile_keyboard, view_profile, has_answers_keyboard, back_to_menu_button
from bot.services.utils import delete_previous_messages

import logging
logger = logging.getLogger(__name__)
router = Router()

# Просмотр профиля - главное меню
@router.callback_query(F.data == "view_profile")
async def view_profile_handler(callback: CallbackQuery, state: FSMContext, crypto: CryptoService, db: Database):
    await delete_previous_messages(callback.message, state)

    # Получаем данные пользователя
    user_data = await db.get_user_data(callback.from_user.id)

    # Декодируем зашифрованные данные
    name = crypto.decrypt(user_data['name']).decode() if isinstance(crypto.decrypt(user_data['name']), bytes) else crypto.decrypt(user_data['name'])
    location = crypto.decrypt(user_data['location']).decode() if isinstance(crypto.decrypt(user_data['location']), bytes) else crypto.decrypt(user_data['location'])
    description = crypto.decrypt(user_data['description']).decode() if isinstance(crypto.decrypt(user_data['description']), bytes) else crypto.decrypt(user_data['description'])


    # Формируем текст анкеты
    profile_text = (
        f"👤 *Ваша анкета:*\n\n"
        f"*Имя:* {name}\n"
        f"*Возраст:* {user_data['age']}\n"
        f"*Пол:* {user_data['gender']}\n"
        f"*Местоположение:* {location}\n"
        f"*Описание:* {description}"
    )

    # Если есть фото
    if user_data['photos']:
        # Создаем медиагруппу
        media_group = [
            InputMediaPhoto(
                media=photo_id,
                caption=profile_text if i == 0 else None,
                parse_mode=ParseMode.MARKDOWN
            )
            for i, photo_id in enumerate(user_data['photos'])
        ]

        # Отправляем медиагруппу и сохраняем ID сообщений
        sent_messages = await callback.message.answer_media_group(media=media_group)
        photo_message_ids = [msg.message_id for msg in sent_messages]
        await state.update_data(profile_photo_message_ids=photo_message_ids)

        # Отправляем кнопки управления
        await callback.message.answer("Выберите действие:", reply_markup=view_profile())

    # Если фото нет
    else:
        # Редактируем исходное сообщение с кнопкой
        await callback.message.edit_text(
            text=profile_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=view_profile()  # Ваша клавиатура для управления
        )

    await callback.answer()
    await state.set_state(RegistrationStates.VIEW_PROFILE)

# Редактирование профиля - главное меню
@router.callback_query(F.data == "edit_profile")
async def edit_profile_handler(callback: CallbackQuery, state: FSMContext):
    await delete_previous_messages(callback.message, state)
    await callback.message.edit_text(
        "✏️ Выберите что хотите изменить:",
        reply_markup=edit_profile_keyboard()
    )
    await callback.answer()

async def show_edit_menu(message: Message, state: FSMContext):
    await delete_previous_messages(message, state)
    await message.answer(
        "✏️ Выберите что хотите изменить:",
        reply_markup=edit_profile_keyboard()
    )

# Редактирование имени
@router.callback_query(F.data == "edit_name")
async def edit_name_handler(callback: CallbackQuery, state: FSMContext):
    msg = await callback.message.answer("Введите новое имя:")
    await state.update_data(edit_message_id=msg.message_id)
    await state.set_state(RegistrationStates.EDIT_NAME)
    await callback.answer()

@router.message(RegistrationStates.EDIT_NAME)
async def process_edit_name(message: Message, state: FSMContext, crypto: CryptoService, db: Database):
    encrypted_name = crypto.encrypt(message.text)

    if await db.update_user_field(message.from_user.id, name=encrypted_name):
        await message.answer(f"✅ Имя успешно изменено на {message.text}!")
    else:
        await message.answer("❌ Ошибка при обновлении имени")

    await show_edit_menu(message, state)

# Редактирование возраста
@router.callback_query(F.data == "edit_age")
async def edit_age_handler(callback: CallbackQuery, state: FSMContext):
    msg = await callback.message.answer("Введите новый возраст:")
    await state.update_data(edit_message_id=msg.message_id)
    await state.set_state(RegistrationStates.EDIT_AGE)
    await callback.answer()

@router.message(RegistrationStates.EDIT_AGE)
async def process_edit_age(message: Message, state: FSMContext, db: Database):
    try:
        age = int(message.text)
        if 18 <= age <= 100:
            if await db.update_user_field(message.from_user.id, age=age):
                await message.answer(f"✅ Возраст успешно изменен на {age}!")
            else:
                await message.answer("❌ Ошибка при обновлении возраста")
        else:
            await message.answer("⚠️ Возраст должен быть от 18 до 100 лет")
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введите число")

    await show_edit_menu(message, state)

# Редактирование местоположения
@router.callback_query(F.data == "edit_location")
async def edit_location_handler(callback: CallbackQuery, state: FSMContext):
    msg = await callback.message.answer("Введите новое местоположение:")
    await state.update_data(edit_message_id=msg.message_id)
    await state.set_state(RegistrationStates.EDIT_LOCATION)
    await callback.answer()

@router.message(RegistrationStates.EDIT_LOCATION)
async def process_edit_location(message: Message, state: FSMContext, crypto: CryptoService, db: Database):
    encrypted_location = crypto.encrypt(message.text)

    if await db.update_user_field(message.from_user.id, city=encrypted_location):
        await message.answer(f"✅ Местоположение изменено на {message.text}!")
    else:
        await message.answer("❌ Ошибка при обновлении местоположения")

    await show_edit_menu(message, state)

# Редактирование описания
@router.callback_query(F.data == "edit_description")
async def edit_description_handler(callback: CallbackQuery, state: FSMContext):
    msg = await callback.message.answer("Введите новое описание:")
    await state.update_data(edit_message_id=msg.message_id)
    await state.set_state(RegistrationStates.EDIT_DESCRIPTION)
    await callback.answer()

@router.message(RegistrationStates.EDIT_DESCRIPTION)
async def process_edit_description(message: Message, state: FSMContext, crypto: CryptoService, db: Database):
    encrypted_description = crypto.encrypt(message.text)

    if await db.update_user_field(message.from_user.id, profiledescription=encrypted_description):
        await message.answer("✅ Описание успешно обновлено!")
    else:
        await message.answer("❌ Ошибка при обновлении описания")

    await show_edit_menu(message, state)

# Редактирование фото
@router.callback_query(F.data == "edit_photos")
async def edit_photos_handler(callback: CallbackQuery, state: FSMContext):
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="📷 Добавить фото"))
    builder.add(KeyboardButton(text="✅ Завершить"))
    msg = await callback.message.answer(
        "Отправьте новые фотографии (максимум 3):",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )
    await state.update_data(
        edit_message_id=msg.message_id,
        temp_photos=[]
    )
    await state.set_state(RegistrationStates.EDIT_PHOTOS)
    await callback.answer()

@router.message(RegistrationStates.EDIT_PHOTOS, F.photo)
async def process_edit_photos_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    temp_photos = data.get('temp_photos', [])

    if len(temp_photos) >= 3:
        await message.answer("⚠️ Достигнут лимит в 3 фотографии")
        return

    temp_photos.append(message.photo[-1].file_id)
    await state.update_data(temp_photos=temp_photos)

    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="📷 Добавить еще"))
    builder.add(KeyboardButton(text="✅ Завершить"))

    await message.answer(
        f"✅ Добавлено фото ({len(temp_photos)}/3)",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@router.message(RegistrationStates.EDIT_PHOTOS, F.text == "✅ Завершить")
async def process_edit_photos_finish(message: Message, state: FSMContext, db: Database):
    data = await state.get_data()
    temp_photos = data.get('temp_photos', [])

    if not temp_photos:
        await message.answer("⚠️ Вы не добавили ни одной фотографии")
        return

    if await db.update_user_photos(message.from_user.id, temp_photos):
        await message.answer("✅ Фотографии успешно обновлены!", reply_markup=ReplyKeyboardRemove())
    else:
        await message.answer("❌ Ошибка при обновлении фотографий", reply_markup=ReplyKeyboardRemove())

    await show_edit_menu(message, state)

# Пройти тест - главное меню
@router.callback_query(F.data == "take_test")
async def take_test_handler(callback: CallbackQuery, state: FSMContext, db: Database):
    await delete_previous_messages(callback.message, state)

    user_data = await state.get_data()

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

    has_answers = await db.check_existing_answers(user_id=callback.from_user.id)

    if has_answers:
        try:
            await callback.message.edit_text(
                "Вы уже проходили тест ранее. Хотите пройти его снова?\n\n"
                "⚠️ Ваши предыдущие ответы будут удалены.",
                reply_markup=has_answers_keyboard()
                )
        except Exception as e:
            logging.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.message.answer(
                "Вы уже проходили тест ранее. Хотите пройти его снова?\n\n"
                "⚠️ Ваши предыдущие ответы будут удалены.",
                reply_markup=has_answers_keyboard()
            )
        return

    # если пользователь не проходил тест ранее, начинаем тест
    await start_test(callback, state, db)

# функция для подтверждения повторного прохождения теста
@router.callback_query(F.data == "confirm_test")
async def confirm_test(callback: CallbackQuery, state: FSMContext, db: Database):
    await callback.answer()
    await start_test(callback, state, db)

@router.callback_query(lambda c: c.data.startswith("answer_"))
async def handle_test_answer(callback: CallbackQuery, state: FSMContext, db: Database):
    await process_test_answer(callback, state, db)

# начало теста
async def start_test(callback: CallbackQuery, state: FSMContext, db: Database):
    # удаляем текущее сообщение с кнопкой "Пройти тест"
    try:
        await callback.message.delete()
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")

    # отправляем сообщение о начале теста
    start_message = await callback.message.answer("🔄 Загрузка теста...")

    try:
        # удаляем предыдущие ответы пользователя, если они есть
        await db.del_user_answers(callback.from_user.id)

        # получаем вопросы и ответы
        questions_dict, answers_dict = await db.get_questions_and_answers()
        if not questions_dict or not answers_dict:
            await start_message.edit_text("❌ Не удалось загрузить вопросы и ответы. Попробуйте позже.",
                                         reply_markup=back_to_menu_button())
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
        await show_question(start_message, state, db)

    except Exception as e:
        logging.error(f"Ошибка при запуске теста: {e}")
        await start_message.edit_text("❌ Произошла ошибка при запуске теста. Попробуйте позже.",
                                     reply_markup=back_to_menu_button())

# отображение текущего вопроса
async def show_question(message: Message, state: FSMContext, db: Database = None):
    # получаем данные из состояния
    data = await state.get_data()
    questions = data.get('questions', {})
    answers = data.get('answers', {})
    question_ids = data.get('question_ids', [])
    current_index = data.get('current_question_index', 0)

    # проверяем, есть ли еще вопросы
    if current_index >= len(question_ids):
        # сохраняем результаты
        await finish_test(message, state, db)
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

async def process_test_answer(callback: CallbackQuery, state: FSMContext, db: Database = None):
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
    await show_question(callback.message, state, db)
    await callback.answer()

# завершение теста и сохр результатов
async def finish_test(message: Message, state: FSMContext, db: Database):
    data = await state.get_data()
    user_answers = data.get('user_answers', {})

    try:
        # сохр ответы пользователя
        success = await db.save_user_answers(message.chat.id, user_answers)

        if success:
            # отобрж сообщение об успешном завершении теста
            try:
                await message.edit_text("✅ Тест успешно пройден! Спасибо за ваши ответы.", reply_markup=back_to_menu_button())
            except Exception as e:
                logging.error(f"Ошибка при отображении результатов: {e}")
                await message.answer("✅ Тест успешно пройден! Спасибо за ваши ответы.", reply_markup=back_to_menu_button())
        else:
            try:
                await message.edit_text("❌ Произошла ошибка при сохранении результатов теста.",
                                       reply_markup=back_to_menu_button())
            except Exception as e:
                logging.error(f"Ошибка при отображении сообщения об ошибке: {e}")
                await message.answer("❌ Произошла ошибка при сохранении результатов теста.",
                                    reply_markup=back_to_menu_button())
    except Exception as e:
        logging.error(f"Ошибка при завершении теста: {e}")
        try:
            await message.edit_text("❌ Произошла ошибка при обработке результатов теста.",
                                   reply_markup=back_to_menu_button())
        except Exception as e2:
            logging.error(f"Ошибка при отображении сообщения об ошибке: {e2}")
            await message.answer("❌ Произошла ошибка при обработке результатов теста.",
                               reply_markup=back_to_menu_button())

    # возвращаемся в главное меню
    await state.set_state(RegistrationStates.MAIN_MENU)



