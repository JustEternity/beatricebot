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
from bot.handlers.profile_edit import remove_keyboard_if_exists
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
async def find_compatible_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto: CryptoService):
    """Обработчик поиска совместимых пользователей"""
    await remove_keyboard_if_exists(callback.message)

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
        
        # Добавляем параметр crypto при вызове show_filters_menu
        await show_filters_menu(callback, state, db, crypto)
    except Exception as e:
        logger.error(f"Ошибка в find_compatible_handler: {e}")
        await callback.message.answer("⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик для перехода к следующему совместимому пользователю
@router.callback_query(F.data == "next_compatible")
async def next_compatible_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    await callback.answer()
    
    # Получаем текущий индекс и данные
    state_data = await state.get_data()
    current_index = state_data.get("current_compatible_index", 0)
    compatible_users = state_data.get("compatible_users", [])
    
    # Получаем историю просмотров (если её нет, создаем пустой список)
    view_history = state_data.get("view_history", [])
    
    # Логируем текущее состояние перед изменениями
    logger.info(f"NEXT: История до: {view_history}, текущий индекс: {current_index}")
    
    # Добавляем текущий индекс в историю просмотров, если его там еще нет
    if current_index not in view_history:
        view_history.append(current_index)
    
    # Удаляем предыдущее сообщение для избежания ошибок
    await delete_message_safely(callback.message)
    
    # ИЗМЕНЕНО: Проверяем, есть ли еще анкеты
    if current_index < len(compatible_users) - 1:
        # Увеличиваем индекс
        next_index = current_index + 1
        
        # Обновляем индекс в состоянии и историю просмотров
        await state.update_data(
            current_compatible_index=next_index,
            view_history=view_history,
            already_went_back=False  # Сбрасываем флаг при движении вперед
        )
        
        # Логируем обновленное состояние
        logger.info(f"NEXT: История после: {view_history}, новый индекс: {next_index}, сброшен флаг возврата")
        
        # Показываем следующего пользователя
        await show_compatible_user(callback.message, state, db, crypto)
    else:
        # ДОБАВЛЕНО: Если анкет больше нет, отправляем сообщение
        await callback.message.answer(
            "Вы просмотрели все доступные анкеты. Возвращайтесь позже!",
            reply_markup=back_to_menu_button()
        )

# Обработчик начала поиска
@router.callback_query(F.data == "start_search")
async def start_search_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto: CryptoService):
    try:
        await callback.answer()
        search_msg = await callback.message.edit_text("🔍 Ищем пользователей...")
        
        # Получаем фильтры из состояния
        filters = await state.get_data()
        logger.info(f"Поиск пользователей для {callback.from_user.id} с фильтрами: {filters}")
        
        # Дешифруем город
        city = decrypt_city(crypto, filters.get('filter_city'))
        logger.info(f"Дешифрованный город для поиска: {city}")
        
        compatibility_service = CompatibilityService(db)
        
        # Получаем список интересов для фильтрации
        selected_interests = filters.get('filter_interests', [])
        logger.info(f"Выбранные интересы: {selected_interests}")
        
        interests_mapping = {
            "active": {"question": 2, "answer": 1},
            "travel": {"question": 3, "answer": 1},
            "sport": {"question": 4, "answer": 1},
            "animals": {"question": 5, "answer": 1},
            "art": {"question": 6, "answer": 1},
            "parties": {"question": 8, "answer": 2},
            "space": {"question": 9, "answer": 1},
            "serious": {"question": 1, "answer": 1}
        }
        
        filter_test_question = None
        filter_test_answer = None
        
        if selected_interests:
            first_interest = selected_interests[0]
            if first_interest in interests_mapping:
                filter_test_question = interests_mapping[first_interest]["question"]
                filter_test_answer = interests_mapping[first_interest]["answer"]
                logger.info(f"Фильтр по интересу: вопрос {filter_test_question}, ответ {filter_test_answer}")
        
        # Проверяем, есть ли у пользователя ответы на тест
        has_answers = await db.check_existing_answers(callback.from_user.id)
        logger.info(f"Пользователь {callback.from_user.id} имеет ответы на тест: {has_answers}")
        
        # Проверяем профиль пользователя
        user_profile = await db.get_user_profile(callback.from_user.id)
        if user_profile:
            logger.info(f"Профиль пользователя: возраст={user_profile.get('age')}, пол={user_profile.get('gender')}")
        else:
            logger.warning(f"Профиль пользователя {callback.from_user.id} не найден")
        
        # Ищем пользователей - убираем параметр limit, чтобы получить всех пользователей
        logger.info("Начинаем поиск совместимых пользователей...")
        high_compatible_users, low_compatible_users = await compatibility_service.find_compatible_users(
            user_id=callback.from_user.id,
            city=city,
            age_min=filters.get('filter_age_min'),
            age_max=filters.get('filter_age_max'),
            gender=filters.get('filter_gender'),
            occupation=filters.get('filter_occupation'),
            goals=filters.get('filter_goals'),
            filter_test_question=filter_test_question,
            filter_test_answer=filter_test_answer,
            limit=None,  # Изменено с 10 на None, чтобы получить всех пользователей
            min_score=50.0,
            crypto=crypto
        )
        
        logger.info(f"Найдено пользователей: {len(high_compatible_users)} с высокой совместимостью, {len(low_compatible_users)} с низкой")
        
        all_compatible_users = high_compatible_users + low_compatible_users
        
        # Пытаемся удалить сообщение о поиске
        try:
            await search_msg.delete()
        except Exception as e:
            logger.debug(f"Не удалось удалить сообщение о поиске: {e}")
        
        if not all_compatible_users:
            logger.warning(f"По фильтрам пользователей не найдено для {callback.from_user.id}")
            await callback.message.answer(
                "😔 По вашим фильтрам пользователей не найдено.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu")]
                ])
            )
            return
        
        # Сохраняем результаты поиска
        await state.update_data(
            compatible_users=all_compatible_users,
            current_compatible_index=0,
            view_history=[],
            already_went_back=False,
            last_profile_messages=[]  # Очищаем предыдущие сообщения
        )
        
        logger.info(f"START: Инициализирована пустая история просмотров, найдено {len(all_compatible_users)} пользователей")
        
        # Показываем первого пользователя
        await show_compatible_user(callback.message, state, db, crypto)
    except Exception as e:
        logger.error(f"Ошибка в start_search_handler: {e}", exc_info=True)
        await callback.message.answer(
            "⚠️ Произошла ошибка при поиске. Пожалуйста, попробуйте позже.",
            reply_markup=back_to_menu_button()
        )

# Обработчик кнопки назад на одну анкету в ленте анкет
@router.callback_query(F.data == "prev_compatible")
async def prev_compatible_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    await callback.answer()
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    current_index = state_data.get("current_compatible_index", 0)
    view_history = state_data.get("view_history", [])
    
    # Получаем флаг, который показывает, использовал ли пользователь уже кнопку "Назад"
    already_went_back = state_data.get("already_went_back", False)
    
    # Логируем текущее состояние
    logger.info(f"PREV: История до: {view_history}, текущий индекс: {current_index}, уже возвращался: {already_went_back}")
    
    # Если пользователь уже использовал кнопку "Назад", не позволяем ему вернуться еще раз
    if already_went_back:
        await callback.answer("Вы можете вернуться только на одну анкету назад", show_alert=True)
        return
    
    # Проверяем, есть ли предыдущая анкета в истории просмотров
    if not view_history:
        await callback.answer("Это первая анкета в вашей ленте", show_alert=True)
        return
    
    # Определяем предыдущий индекс
    prev_index = None
    
    # Если текущий индекс находится в истории, берем предыдущий элемент
    if current_index in view_history:
        current_position = view_history.index(current_index)
        if current_position > 0:
            prev_index = view_history[current_position - 1]
    
    # Если предыдущий индекс не определен, но история не пуста, берем последний элемент
    if prev_index is None and view_history:
        prev_index = view_history[-1]
    
    # Если предыдущий индекс все еще не определен, нельзя вернуться назад
    if prev_index is None:
        await callback.answer("Невозможно вернуться назад", show_alert=True)
        return
    
    # Обновляем индекс в состоянии и устанавливаем флаг, что пользователь уже вернулся назад
    await state.update_data(
        current_compatible_index=prev_index,
        already_went_back=True
    )
    
    # Логируем обновленное состояние
    logger.info(f"PREV: История после: {view_history}, новый индекс: {prev_index}, установлен флаг возврата")
    
    # Удаляем предыдущее сообщение
    await delete_message_safely(callback.message)
    
    # Показываем предыдущего пользователя
    await show_compatible_user(callback.message, state, db, crypto)