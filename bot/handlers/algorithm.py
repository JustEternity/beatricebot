from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.services.database import Database
from bot.services.algorithm_sovmest import CompatibilityService
from bot.keyboards.menus import back_to_menu_button
from bot.handlers.filtres import show_filters_menu
from bot.services.profile_service import show_compatible_user, decrypt_city
from bot.services.encryption import CryptoService
import logging

logger = logging.getLogger(__name__)
router = Router()

# Функция для безопасного удаления сообщений
async def delete_message_safely(message):
    """Безопасно удаляет сообщение с обработкой ошибок"""
    try:
        await message.delete()
    except Exception as e:
        logger.debug(f"Не удалось удалить сообщение: {e}")

# Обработка ошибок
async def handle_error(message: Message, text: str):
    try:
        await message.answer(text, reply_markup=back_to_menu_button())
    except Exception as e:
        logger.error(f"Не удалось отправить сообщение об ошибке: {e}")

# Обработчик для поиска совместимых пользователей
@router.callback_query(F.data == "find_compatible")
async def find_compatible_handler(callback: CallbackQuery, state: FSMContext, db: Database):
    """Обработчик поиска совместимых пользователей"""
    try:
        await callback.answer()

        # Проверяем, прошел ли пользователь тест
        has_answers = await db.check_existing_answers(callback.from_user.id)
        if not has_answers:
            msg = await callback.message.answer(
                "⚠️ Для поиска совместимых пользователей необходимо пройти тест.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📝 Пройти тест", callback_data="take_test")],
                    [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu")]
                ])
            )
            await state.update_data(last_message_id=msg.message_id)
            return

        await show_filters_menu(callback, state, db)

    except Exception as e:
        logger.error(f"Ошибка в find_compatible_handler: {e}")
        await callback.message.answer("⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик для перехода к следующему совместимому пользователю
@router.callback_query(F.data == "next_compatible")
async def next_compatible_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    await callback.answer()
    # Получаем текущий индекс
    state_data = await state.get_data()
    current_index = state_data.get("current_compatible_index", 0) + 1
    compatible_users = state_data.get("compatible_users", [])
    # Если дошли до конца списка, начинаем сначала
    if current_index >= len(compatible_users):
        current_index = 0
    # Обновляем индекс в состоянии
    await state.update_data(current_compatible_index=current_index)
    # Показываем следующего пользователя - ВАЖНО: передаем crypto
    await show_compatible_user(callback.message, state, db, crypto)

# Обработчик начала поиска
@router.callback_query(F.data == "start_search")
async def start_search_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto: CryptoService):
    await callback.answer()
    await callback.message.edit_text("🔍 Ищем совместимых пользователей...")
    
    # Получаем фильтры из состояния
    filters = await state.get_data()
    
    # Используем утилиту для дешифрования города
    city = decrypt_city(crypto, filters.get('filter_city'))
    
    # Создаем сервис совместимости
    compatibility_service = CompatibilityService(db)
    
    # Ищем пользователей с учетом фильтров
    high_compatible_users, low_compatible_users = await compatibility_service.find_compatible_users(
        user_id=callback.from_user.id,
        city=city,
        age_min=filters.get('filter_age_min'),
        age_max=filters.get('filter_age_max'),
        gender=filters.get('filter_gender'),
        occupation=filters.get('filter_occupation'),
        goals=filters.get('filter_goals'),
        limit=10,
        min_score=50.0,
        crypto=crypto  # Передаем объект crypto для шифрования города
    )
    
    # Объединяем результаты
    all_compatible_users = high_compatible_users + low_compatible_users
    
    if not all_compatible_users:
        await callback.message.edit_text(
            "😔 По вашим фильтрам совместимых пользователей не найдено.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu")]
            ])
        )
        return
    
    # Сохраняем результаты поиска
    await state.update_data(
        compatible_users=all_compatible_users,
        current_compatible_index=0
    )
    
    # Показываем первого пользователя
    await show_compatible_user(callback.message, state, db, crypto)

# Обработчик кнопки назад на одну анкету в ленте анкет
@router.callback_query(F.data == "prev_compatible")
async def prev_compatible_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    await callback.answer()
    # Получаем текущий индекс
    state_data = await state.get_data()
    current_index = state_data.get("current_compatible_index", 0) - 1  # Уменьшаем индекс
    compatible_users = state_data.get("compatible_users", [])
    # Если ушли в минус, переходим к последней анкете
    if current_index < 0:
        current_index = len(compatible_users) - 1
    # Обновляем индекс в состоянии
    await state.update_data(current_compatible_index=current_index)
    # Удаляем предыдущее сообщение
    await delete_message_safely(callback.message)
    # Показываем предыдущего пользователя
    await show_compatible_user(callback.message, state, db, crypto)