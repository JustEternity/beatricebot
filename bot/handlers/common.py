from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from bot.models.states import RegistrationStates
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.services.database import Database
from bot.keyboards.menus import main_menu, back_to_menu_button as back, policy_keyboard, admin_menu
from bot.services.utils import delete_previous_messages
from bot.services.encryption import CryptoService
from bot.texts.textforbot import POLICY_TEXT
from bot.services.s3storage import S3Service
import logging

logger = logging.getLogger(__name__)
router = Router()

# Обработчик /admin для перехода в админское меню
@router.message(Command("admin"))
async def admin_menu_handler(message: Message, state: FSMContext, db: Database):
    # Проверяем, является ли пользователь администратором
    admin_password = await db.get_admin_pass(message.from_user.id)

    if not admin_password:
        await message.answer("❌ Вы не администратор.")
        await show_main_menu(message, state)
        return

    # Если пользователь админ, запрашиваем пароль
    auth_message = await message.answer("Введите пароль администратора:")

    # Сохраняем ID сообщения с запросом пароля и пароль админа в state
    await state.update_data(
        auth_message_id=auth_message.message_id,
        admin_password=admin_password
    )

    # Переходим в состояние ожидания ввода пароля
    await state.set_state(RegistrationStates.ADMIN_AUTH)

@router.message(RegistrationStates.ADMIN_AUTH)
async def check_admin_password(message: Message, state: FSMContext, db: Database):
    # Получаем введенный пароль
    password = message.text

    # Получаем данные из state
    data = await state.get_data()
    auth_message_id = data.get("auth_message_id")
    admin_password = data.get("admin_password")  # Получаем пароль из state

    # Пытаемся удалить сообщение с паролем
    try:
        await message.delete()
    except Exception as e:
        logger.error(f"Не удалось удалить сообщение с паролем: {e}")

    # Пытаемся удалить сообщение с запросом пароля
    if auth_message_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=auth_message_id)
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение с запросом пароля: {e}")

    # Проверяем пароль
    if password == admin_password:
        # Если пароль верный, показываем админское меню
        await show_admin_menu(message, state)
    else:
        # Если пароль неверный, отправляем сообщение об ошибке
        error_message = await message.answer("❌ Неверный пароль. Доступ запрещен.")

        # Возвращаемся в обычное меню
        await show_main_menu(message, state)

# Общая функция показа главного меню админа
async def show_admin_menu(source: Message | CallbackQuery, state: FSMContext):
    await delete_previous_messages(source, state)

    # Определяем, как отправить сообщение в зависимости от типа source
    if isinstance(source, Message):
        menu_message = await source.answer(
            "🔹Главное меню администратора🔹",
            reply_markup=admin_menu()
        )
    else:  # CallbackQuery
        menu_message = await source.message.answer(
            "🔹Главное меню администратора🔹",
            reply_markup=admin_menu()
        )
        await source.answer()  # Закрываем callback query

    await state.update_data(last_menu_message_id=menu_message.message_id)
    await state.set_state(RegistrationStates.ADMIN_MENU)

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

async def show_filters_menu(callback: CallbackQuery, state: FSMContext, db: Database):
    """Функция для показа меню фильтров"""
    # Проверяем наличие подписки у пользователя
    has_subscription = await db.check_user_subscription(callback.from_user.id)

    # Создаем клавиатуру с фильтрами
    builder = InlineKeyboardBuilder()
    builder.button(text="📍 Город", callback_data="filter_city")
    builder.button(text="🔢 Возраст", callback_data="filter_age")

    # Дополнительные фильтры для подписчиков
    if has_subscription:
        builder.button(text="💼 Род занятий", callback_data="filter_occupation")
        builder.button(text="🎯 Цели знакомства", callback_data="filter_goals")

    builder.button(text="🔍 Начать поиск", callback_data="start_search")
    builder.button(text="◀️ Назад", callback_data="back_to_menu")
    builder.adjust(2)  # По 2 кнопки в ряду

    text = "⚙️ Выберите фильтры для поиска:" if has_subscription else \
           "⚙️ Доступные фильтры (для подписки больше фильтров):"

    # Удаляем предыдущее сообщение, если есть
    data = await state.get_data()
    if 'last_message_id' in data:
        try:
            await callback.bot.delete_message(callback.message.chat.id, data['last_message_id'])
        except:
            pass

    msg = await callback.message.answer(
        text,
        reply_markup=builder.as_markup()
    )
    await state.update_data(last_message_id=msg.message_id)

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
