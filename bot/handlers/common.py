from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from bot.models.states import RegistrationStates
from bot.services.database import Database
from bot.keyboards.menus import main_menu, back_to_menu_button as back
from bot.services.utils import delete_previous_messages
from bot.services.encryption import CryptoService
from bot.texts.textforbot import POLICY_TEXT
from bot.services.s3storage import S3Service

import logging
logger = logging.getLogger(__name__)
router = Router()

# Обработчик команды /start
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, db: Database):
    user_id = message.from_user.id

    if await db.is_user_registered(user_id):
        await show_main_menu(message, state)
        return

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Я согласен")],
            [KeyboardButton(text="❌ Я не согласен")]
        ],
        resize_keyboard=True
    )

    await message.answer(POLICY_TEXT, reply_markup=keyboard)
    await state.set_state(RegistrationStates.POLICY)

# Обработчик команды /menu
@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    await show_main_menu(message, state)

# Обработчик команды /cancel
@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await delete_previous_messages(message, state)
    await message.answer(
        "Действие отменено. Возврат в главное меню.",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()
    await show_main_menu(message, state)

# Обработчик возврата в меню
@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    await delete_previous_messages(callback.message, state)
    await callback.message.edit_reply_markup()
    await show_main_menu(callback.message, state)
    await callback.answer()

# Общая функция показа главного меню
async def show_main_menu(source: Message | CallbackQuery, state: FSMContext):
    await delete_previous_messages(source, state)

    menu_message = await source.answer(
        "🔹 Главное меню 🔹",
        reply_markup=main_menu()
    )

    await state.update_data(last_menu_message_id=menu_message.message_id)
    await state.set_state(RegistrationStates.MAIN_MENU)

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

        # Отправляем подтверждение
        if success:
            await message.answer(
                "✅ Спасибо за ваше сообщение! Мы рассмотрим его в ближайшее время.",
                reply_markup=main_menu()
            )
        else:
            await message.answer(
                "❌ Приносим свои извинения, произошла ошибка.\nПопробуйте позже",
                reply_markup=main_menu()
            )

    except Exception as e:
        logger.error(f"Feedback save error: {str(e)}")
        await message.answer("❌ Произошла ошибка при сохранении отзыва")

    await state.clear()

# Обработчик любых неожиданных сообщений
@router.message()
async def unexpected_messages_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    logger.debug(f"Received policy response: {message.text}")
    if current_state is None:
        await message.answer(
            "Пожалуйста, используйте команды из меню.",
            reply_markup=main_menu()
        )
    else:
        await message.answer(
            "Пожалуйста, завершите текущее действие "
            "или нажмите /cancel для отмены."
        )