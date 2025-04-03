from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from bot.models.states import RegistrationStates
from bot.services.database import Database
from bot.keyboards.menus import main_menu, back_to_menu_button as back, policy_keyboard
from bot.services.utils import delete_previous_messages
from bot.services.encryption import CryptoService
from bot.texts.textforbot import POLICY_TEXT
from bot.services.s3storage import S3Service
import logging

logger = logging.getLogger(__name__)
router = Router()

# Обработчик команды /menu
@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext, db: Database):
    # Получаем количество непросмотренных лайков
    likes_count = await db.get_unviewed_likes_count(message.from_user.id)
    await show_main_menu(message, state, likes_count)

# Обработчик команды /cancel
@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, db: Database):
    await delete_previous_messages(message, state)
    await message.answer(
        "Действие отменено. Возврат в главное меню.",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()

    # Получаем количество непросмотренных лайков
    likes_count = await db.get_unviewed_likes_count(message.from_user.id)
    await show_main_menu(message, state, likes_count)

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_handler(callback: CallbackQuery, state: FSMContext, db: Database):
    """Универсальный обработчик возврата в меню"""
    await callback.answer()

    try:
        # Получаем количество непросмотренных лайков
        unviewed_likes = await db.get_unviewed_likes_count(callback.from_user.id)

        # Удаляем текущее сообщение
        await callback.message.delete()

        # Отправляем новое сообщение с главным меню
        await callback.message.answer(
            "🔹 Главное меню 🔹",
            reply_markup=main_menu(unviewed_likes)
        )

        # Очищаем состояние
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка в back_to_menu_handler: {e}")
        # Если не получилось удалить сообщение, отправляем новое
        try:
            unviewed_likes = await db.get_unviewed_likes_count(callback.from_user.id)
        except:
            unviewed_likes = 0

        await callback.message.answer(
            "🔹 Главное меню 🔹",
            reply_markup=main_menu(unviewed_likes)
        )

        # Очищаем состояние
        await state.clear()

# Общая функция показа главного меню
async def show_main_menu(source: Message | CallbackQuery, state: FSMContext, likes_count: int = 0):
    await delete_previous_messages(source, state)
    menu_message = await source.answer(
        "🔹 Главное меню 🔹",
        reply_markup=main_menu(likes_count)
    )
    await state.update_data(last_menu_message_id=menu_message.message_id)
    await state.set_state(RegistrationStates.MAIN_MENU)

async def update_main_menu(message, state: FSMContext, db: Database):
    """Обновляет главное меню с актуальным количеством лайков"""
    # Получаем актуальное количество непросмотренных лайков
    likes_count = await db.get_unviewed_likes_count(message.chat.id)

    # Обновляем меню
    await message.edit_text(
        "🔹 Главное меню 🔹",
        reply_markup=main_menu(likes_count)
    )

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

        # Получаем количество непросмотренных лайков
        likes_count = await db.get_unviewed_likes_count(message.from_user.id)

        # Отправляем подтверждение
        if success:
            await message.answer(
                "✅ Спасибо за ваше сообщение! Мы рассмотрим его в ближайшее время.",
                reply_markup=main_menu(likes_count)
            )
        else:
            await message.answer(
                "❌ Приносим свои извинения, произошла ошибка.\nПопробуйте позже",
                reply_markup=main_menu(likes_count)
            )
    except Exception as e:
        logger.error(f"Feedback save error: {str(e)}")
        await message.answer("❌ Произошла ошибка при сохранении отзыва")
    await state.clear()

# Обработчик любых неожиданных сообщений
@router.message()
async def unexpected_messages_handler(message: Message, state: FSMContext, db: Database):
    current_state = await state.get_state()
    logger.debug(f"Received policy response: {message.text}")
    if current_state is None:
        # Получаем количество непросмотренных лайков
        likes_count = await db.get_unviewed_likes_count(message.from_user.id)
        await message.answer(
            "Пожалуйста, используйте команды из меню.",
            reply_markup=main_menu(likes_count)
        )
    else:
        await message.answer(
            "Пожалуйста, завершите текущее действие "
            "или нажмите /cancel для отмены."
        )
