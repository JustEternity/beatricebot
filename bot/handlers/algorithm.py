from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.models.states import RegistrationStates
from bot.services.city_validator import city_validator
from bot.services.database import Database
from bot.services.algorithm_sovmest import CompatibilityService
from bot.services.encryption import CryptoService
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from bot.services.utils import delete_previous_messages, format_profile_text, create_media_group
from bot.keyboards.menus import compatible_navigation_keyboard, back_to_menu_button, subscription_keyboard, main_menu
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "view_services")
async def view_services_handler(callback: CallbackQuery, db, state: FSMContext):
    """Обработчик для просмотра доступных услуг"""
    user_id = callback.from_user.id
    logger.debug(f"Получен callback_data: {callback.data}")

    # Обновляем статус подписки и приоритет пользователя
    await db.update_subscription_status(user_id)
    await db.update_user_priority(user_id)

    # Создаем клавиатуру с тремя конкретными услугами
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💎 Подписка на месяц", callback_data="service_1")],
            [InlineKeyboardButton(text="🚀 Буст видимости на 24 часа", callback_data="service_2")],
            [InlineKeyboardButton(text="🔥 Буст видимости на 7 дней", callback_data="service_3")],
            [InlineKeyboardButton(text="📋 Мои активные услуги", callback_data="my_services")],
            [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu")]
        ]
    )

    # Отправляем сообщение с клавиатурой
    await callback.message.edit_text(
        "📋 <b>Доступные услуги:</b>\n\n"
        "Выберите интересующую вас услугу для получения подробной информации:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data in ["service_1", "service_2", "service_3"])
async def service_details_handler(callback: CallbackQuery, db, state: FSMContext):
    """Обработчик для просмотра детальной информации об услуге"""
    logger.debug(f"Получен callback_data: {callback.data}")
    try:
        service_id = int(callback.data.split("_")[1])
        user_id = callback.from_user.id

        # Исправляем коэффициент приоритета перед показом услуг
        await db.fix_priority_coefficient(user_id)

        # Получаем информацию об услуге из предопределенных данных
        service_info = {
            1: {
                "id": 1,
                "description": "Подписка на месяц",
                "cost": 299,
                "serviceduration": "30 дней",
                "priorityboostvalue": 50,
                "availabilitystatus": True,
                "details": "Премиум подписка на месяц дает вам приоритет в поиске и доступ ко всем функциям приложения."
            },
            2: {
                "id": 2,
                "description": "Буст видимости на 24 часа",
                "cost": 99,
                "serviceduration": "24 часа",
                "priorityboostvalue": 100,
                "availabilitystatus": True,
                "details": "Максимальное повышение видимости вашего профиля в течение 24 часов."
            },
            3: {
                "id": 3,
                "description": "Буст видимости на 7 дней",
                "cost": 499,
                "serviceduration": "7 дней",
                "priorityboostvalue": 75,
                "availabilitystatus": True,
                "details": "Значительное повышение видимости вашего профиля в течение недели."
            }
        }

        # Проверяем, есть ли такая услуга
        if service_id not in service_info:
            logger.warning(f"Service {service_id} not found")
            await callback.answer("Услуга не найдена", show_alert=True)
            return

        service = service_info[service_id]

        # Формируем детальное сообщение об услуге
        message_text = (
            f"<b>🔍 {service['description']}</b>\n\n"
            f"{service['details']}\n\n"
            f"💰 <b>Стоимость:</b> {service['cost']} руб.\n"
            f"⏱ <b>Длительность:</b> {service['serviceduration']}\n"
            f"🔝 <b>Повышение приоритета:</b> +{service['priorityboostvalue']}%\n\n"
            f"Чтобы приобрести услугу, нажмите кнопку ниже."
        )

        # Создаем клавиатуру с кнопкой покупки и возврата
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💳 Приобрести", callback_data=f"buy_service_{service_id}")],
                [InlineKeyboardButton(text="◀️ К списку услуг", callback_data="view_services")],
                [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu")]
            ]
        )

        await callback.message.edit_text(
            message_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in service_details handler: {e}", exc_info=True)
        await callback.answer("Произошла ошибка при обработке запроса", show_alert=True)


@router.callback_query(lambda c: c.data.startswith("buy_service_"))
async def buy_service_handler(callback: CallbackQuery, db: Database, state: FSMContext):
    """Обработчик покупки услуги"""
    try:
        service_id = int(callback.data.split("_")[-1])
        user_id = callback.from_user.id

        # Активируем услугу
        success = await db.activate_service(user_id, service_id)

        if success:
            # Дополнительно исправляем коэффициент для надежности
            await db.fix_priority_coefficient(user_id)
            # Получаем информацию об услуге для сообщения
            service = await db.get_service_by_id(service_id)
            service_name = service['description'] if service else "услуга"

            # Получаем обновленную информацию о пользователе
            user_data = await db.get_user(user_id)
            priority_coefficient = user_data['profileprioritycoefficient'] if user_data else 1.0
            subscription_status = user_data['subscriptionstatus'] if user_data else False

            # Формируем сообщение с информацией о статусе
            status_text = (
                f"✅ Услуга «{service_name}» успешно активирована!\n\n"
                f"📊 Ваш текущий приоритет: {priority_coefficient:.2f}\n"
                f"🔑 Статус подписки: {'Активна ✅' if subscription_status else 'Неактивна ❌'}"
            )

            await callback.answer("✅ Услуга успешно активирована!", show_alert=True)

            # Показываем сообщение с обновленным статусом
            await callback.message.edit_text(
                status_text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📋 Мои услуги", callback_data="my_services")],
                    [InlineKeyboardButton(text="◀️ К списку услуг", callback_data="view_services")]
                ])
            )
        else:
            await callback.answer(
                "⚠️ Не удалось активировать услугу. Попробуйте позже.",
                show_alert=True
            )
    except Exception as e:
        logger.error(f"Error in buy_service handler: {e}")
        await callback.answer(
            "Произошла ошибка при активации услуги",
            show_alert=True
        )



async def update_all_users_priority(self):
    """Обновляет коэффициенты приоритета для всех пользователей"""
    logger.info("Updating priority coefficients for all users")
    try:
        async with self.pool.acquire() as conn:
            # Получаем всех пользователей
            users = await conn.fetch("SELECT telegramid FROM users")

            updated_count = 0
            for user in users:
                user_id = user['telegramid']
                success = await self.fix_priority_coefficient(user_id)
                if success:
                    updated_count += 1

            logger.info(f"Updated priority coefficients for {updated_count}/{len(users)} users")
            return updated_count
    except Exception as e:
        logger.error(f"Error updating all users priority: {e}")
        logger.exception(e)
        return 0


@router.callback_query(F.data == "my_services")
async def view_my_services(callback: CallbackQuery, db: Database):
    """Показывает активные услуги пользователя"""
    try:
        services = await db.get_active_services(callback.from_user.id)

        if not services:
            text = "У вас нет активных услуг"
        else:
            text = "🎁 Ваши активные услуги:\n\n"
            for service in services:
                end_date = service['serviceenddate'].strftime("%d.%m.%Y %H:%M")
                text += (
                    f"🔹 {service['description']}\n"
                    f"   Приоритет: +{service['priorityboostvalue']}%\n"
                    f"   Действует до: {end_date}\n\n"
                )

        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="view_services")]
            ])
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Error showing services: {e}")
        await callback.answer("Ошибка при загрузке услуг", show_alert=True)

# Функция для безопасного удаления сообщений
async def delete_message_safely(message):
    """Безопасно удаляет сообщение с обработкой ошибок"""
    try:
        await message.delete()
    except Exception as e:
        logger.debug(f"Не удалось удалить сообщение: {e}")

async def send_like_notification(bot, from_user_id, to_user_id, db, crypto=None):
    """Отправляет уведомление пользователю о том, что его лайкнули"""
    logger.debug(f"Отправка уведомления о лайке от {from_user_id} пользователю {to_user_id}")
    
    try:
        # Создаем клавиатуру с кнопками для просмотра лайков или возврата в меню
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="👀 Посмотреть лайки", 
                callback_data="view_likes"
            )],
            [InlineKeyboardButton(
                text="◀️ В меню", 
                callback_data="back_to_menu"
            )]
        ])
        
        # Отправляем уведомление без информации о пользователе
        await bot.send_message(
            chat_id=to_user_id,
            text=f"❤️ *Вас лайкнули!*\n\n"
                 f"Кто-то оценил ваш профиль. Хотите узнать, кто это?",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return True
    except TelegramAPIError as e:
        if "bot was blocked by the user" in str(e).lower():
            logger.warning(f"Бот заблокирован пользователем {to_user_id}")
        elif "chat not found" in str(e).lower():
            logger.warning(f"Чат с пользователем {to_user_id} не найден")
        else:
            logger.error(f"Ошибка Telegram API при отправке уведомления: {e}")
        return False
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о лайке: {e}")
        return False

@router.callback_query(F.data == "view_likes")
async def view_likes_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    """Обработчик просмотра лайков"""
    await callback.answer()
    
    try:
        # Получаем только непросмотренные лайки
        likes = await db.get_user_likes(callback.from_user.id)
        
        if not likes:
            await callback.message.edit_text(
                "У вас пока нет новых лайков.",
                reply_markup=back_to_menu_button()
            )
            return
        
        # Сохраняем в состоянии
        await state.update_data(
            likes_list=likes,
            current_like_index=0
        )
        
        # Показываем первый профиль
        await show_like_profile(callback.message, state, db, crypto)
        
    except Exception as e:
        logger.error(f"Ошибка в view_likes_handler: {e}")
        await callback.message.edit_text(
            "Ошибка при загрузке лайков",
            reply_markup=back_to_menu_button()
        )

@router.callback_query(F.data.startswith("view_liker:"))
async def view_liker_profile_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    """Обработчик просмотра профиля пользователя, который поставил лайк"""
    await callback.answer()
    
    # Извлекаем ID пользователя из callback_data
    liker_id = int(callback.data.split(":")[1])
    
    # Получаем данные пользователя
    user_profile = await db.get_user_profile(liker_id)
    user_photos = await db.get_user_photos(liker_id)
    
    if not user_profile:
        await callback.message.answer("Профиль пользователя не найден.")
        return
    
    # Форматируем профиль для отображения
    profile_text = await format_profile_text(user_profile, crypto)
    
    # Создаем клавиатуру с кнопками действий
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="❤️ Лайкнуть в ответ", 
            callback_data=f"like_back:{liker_id}"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад", 
            callback_data="back_to_menu"
        )]
    ])
    
    # Отправляем профиль
    await callback.message.edit_text(
        profile_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
async def show_like_profile(message: Message, state: FSMContext, db: Database, crypto=None):
    try:
        state_data = await state.get_data()
        current_index = state_data.get("current_like_index", 0)
        likes_list = state_data.get("likes_list", [])
        
        if not likes_list or current_index >= len(likes_list):
            # Универсальный способ вернуться в меню
            try:
                if hasattr(message, 'photo') and message.photo:
                    await message.edit_caption(
                        caption="Вы просмотрели все лайки!",
                        reply_markup=back_to_menu_button()
                    )
                else:
                    await message.edit_text(
                        "Вы просмотрели все лайки!",
                        reply_markup=back_to_menu_button()
                    )
            except Exception as e:
                logger.warning(f"Не удалось отредактировать сообщение: {e}")
                await message.answer(
                    "Вы просмотрели все лайки!",
                    reply_markup=back_to_menu_button()
                )
            return

        current_like = likes_list[current_index]
        liker_id = current_like['from_user_id']
        
        # Проверяем, не пытаемся ли показать тот же профиль
        if state_data.get('last_shown_profile') == liker_id:
            return

        user_profile = await db.get_user_profile(liker_id)
        if not user_profile:
            await handle_error(message, "Профиль пользователя не найден")
            return

        profile_text = await format_profile_text(user_profile, crypto)
        keyboard = create_like_keyboard(liker_id)

        photos = await db.get_user_photos(liker_id)
        
        try:
            if hasattr(message, 'photo') and message.photo:
                if photos:
                    await message.edit_media(
                        InputMediaPhoto(media=photos[0], caption=profile_text, parse_mode="HTML"),
                        reply_markup=keyboard
                    )
                else:
                    await message.edit_caption(
                        caption=profile_text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
            else:
                if photos:
                    await message.answer_photo(
                        photos[0],
                        caption=profile_text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                else:
                    await message.answer(
                        profile_text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
            
            await db.mark_like_as_viewed(liker_id, message.from_user.id)
            await state.update_data(last_shown_profile=liker_id)
            
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                logger.debug("Пропускаем дублирующее обновление")
            else:
                raise
                
    except Exception as e:
        logger.error(f"Ошибка в show_like_profile: {e}")
        await handle_error(message, "Ошибка при загрузке профиля")

def create_like_keyboard(liker_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️ Ответить", callback_data=f"like_back:{liker_id}"),
            InlineKeyboardButton(text="👎 Пропустить", callback_data="next_like")
        ],
        [InlineKeyboardButton(text="◀️ В меню", callback_data="back_to_menu")]
    ])

async def handle_error(message: Message, text: str):
    try:
        await message.answer(text, reply_markup=back_to_menu_button())
    except Exception as e:
        logger.error(f"Не удалось отправить сообщение об ошибке: {e}")

@router.callback_query(F.data.startswith("skip_like:"))
async def skip_like_handler(callback: CallbackQuery, state: FSMContext, db: Database):
    """Обработчик пропуска лайка"""
    liker_id = int(callback.data.split(":")[1])
    
    # Помечаем лайк как просмотренный
    await db.mark_like_as_viewed(liker_id, callback.from_user.id)
    
    # Получаем обновленный список лайков
    likes = await db.get_user_likes(callback.from_user.id)
    
    if likes:
        await state.update_data(likes_list=likes, current_like_index=0)
        await show_like_profile(callback.message, state, db)
    else:
        await callback.message.edit_text(
            "Вы просмотрели все лайки!",
            reply_markup=back_to_menu_button()
        )
    
    await callback.answer("Лайк пропущен")

@router.callback_query(F.data == "mutual_like")
async def mutual_like_handler(callback: CallbackQuery, state: FSMContext, db: Database):
    """Обработчик кнопки 'Взаимная симпатия'."""
    logger.debug("Пользователь выбрал 'Взаимная симпатия'")

    state_data = await state.get_data()
    likes_list = state_data.get("likes_list", [])

    # Если список пустой — ничего не делаем
    if not likes_list:
        await callback.answer("Нет доступных лайков")
        return

    # Берем первый лайк из списка
    current_like = likes_list.pop(0)
    sender_id = current_like["sendertelegramid"]

    # Проверяем, ставил ли он тоже лайк пользователю
    mutual_like = await db.fetchval("""
        SELECT COUNT(*) FROM likes
        WHERE sendertelegramid = $1 AND receivertelegramid = $2
        AND likeviewedstatus = TRUE
    """, callback.from_user.id, sender_id)

    if mutual_like:
        await callback.answer("✨ У вас взаимная симпатия! ✨", show_alert=True)
    else:
        await callback.answer("Лайк отправлен! Ждем ответа 😊")

    # Удаляем просмотренную анкету из состояния
    await state.update_data(likes_list=likes_list)

    # Показываем следующую анкету или возвращаем в меню
    if likes_list:
        await show_like_profile(callback.message, state, db)
    else:
        likes_count = await db.fetchval(
            "SELECT COUNT(*) FROM likes WHERE receivertelegramid = $1 AND likeviewedstatus = FALSE",
            callback.from_user.id
        )
        await callback.message.edit_text(
            "🔹 Главное меню 🔹",
            reply_markup=main_menu(likes_count)
        )

@router.callback_query(lambda c: c.data.startswith("dislike_user:"))
async def handle_dislike(callback: CallbackQuery, state: FSMContext, db: Database):
    """Обрабатывает дизлайк"""
    try:
        liker_id = int(callback.data.split(":")[1])  # Получаем ID лайкнувшего

        # Получаем список лайков и текущий индекс
        state_data = await state.get_data()
        likes_list = state_data.get("likes_list", [])
        current_index = state_data.get("current_like_index", 0)

        # Удаляем лайкнутого пользователя из списка
        new_likes_list = [like for like in likes_list if like['from_user_id'] != liker_id]

        if new_likes_list:
            # Обновляем состояние с новым списком лайков
            await state.update_data(likes_list=new_likes_list, current_like_index=min(current_index, len(new_likes_list) - 1))

            # Показываем следующий профиль
            await show_like_profile(callback.message, state, db)
        else:
            # Если больше нет лайков, отправляем сообщение
            await callback.message.edit_text("У вас больше нет лайков от пользователей.", reply_markup=back_to_menu_button())

        # Уведомляем пользователя, что дизлайк обработан
        await callback.answer("Профиль удалён из списка.", show_alert=True)

    except Exception as e:
        logger.error(f"Ошибка при обработке дизлайка: {e}")
        await callback.answer("Произошла ошибка, попробуйте позже.", show_alert=True)

@router.callback_query(F.data.startswith("like_back:"))
async def like_back_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    """Обработчик лайка в ответ"""
    await callback.answer("❤️")
    
    # Извлекаем ID пользователя из callback_data
    liked_user_id = int(callback.data.split(":")[1])
    
    try:
        # Добавляем лайк в базу данных
        like_id = await db.add_like(callback.from_user.id, liked_user_id)
        
        if like_id:
            logger.info(f"Пользователь {callback.from_user.id} лайкнул {liked_user_id} в ответ")
            
            # Проверяем на взаимный лайк (должен быть True, так как это ответный лайк)
            is_mutual = await db.check_mutual_like(callback.from_user.id, liked_user_id)
            
            # Отправляем уведомление о лайке
            await send_like_notification(
                callback.bot, 
                callback.from_user.id,
                liked_user_id,
                db,
                crypto
            )
            
            # Показываем сообщение о взаимной симпатии
            if is_mutual:
                await callback.message.answer(
                    "❤️ У вас взаимная симпатия! Теперь вы можете продолжить общение."
                )
        
        # Обновляем текущий профиль, чтобы показать взаимную симпатию
        await show_like_profile(callback.message, state, db, crypto)
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении лайка в ответ: {e}")
        await callback.answer("Произошла ошибка. Попробуйте позже.", show_alert=True)

# Обработчик для поиска совместимых пользователей
@router.callback_query(F.data == "find_compatible")
async def find_compatible_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
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

        # Проверяем наличие подписки
        has_subscription = await db.check_user_subscription(callback.from_user.id)
        # Создаем клавиатуру с фильтрами
        builder = InlineKeyboardBuilder()
        # Базовые фильтры (доступны всем)
        builder.button(text="📍 Город", callback_data="filter_city")
        builder.button(text="🔢 Возраст", callback_data="filter_age")
        # Дополнительные фильтры (только для подписчиков)
        if has_subscription:
            builder.button(text="👫 Пол", callback_data="filter_gender")
            builder.button(text="💼 Род занятий", callback_data="filter_occupation")
            builder.button(text="🎯 Цели знакомства", callback_data="filter_goals")
        builder.button(text="🔍 Начать поиск", callback_data="start_search")
        builder.button(text="◀️ Назад", callback_data="back_to_menu")
        builder.adjust(2)  # По 2 кнопки в ряду
        text = "⚙️ Выберите фильтры для поиска:" if has_subscription else "⚙️ Доступные фильтры (для подписки больше фильтров):"
        
        # Удаляем предыдущее сообщение если есть
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
    except Exception as e:
        logger.error(f"Error in find_compatible_handler: {e}")
        await callback.message.answer("⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.")


async def find_compatible_users(self, user_id: int, **filters):
    """Поиск совместимых пользователей с учетом приоритета"""
    try:
        # Получаем коэффициент приоритета текущего пользователя
        user_priority = await self.get_user_priority(user_id)

        # Базовый запрос
        query = """
            SELECT u.*, 
                   (u.profileprioritycoefficient * $1) as search_priority
            FROM users u
            WHERE u.telegramid != $2
            AND u.accountstatus = 'active'
            AND u.moderationstatus = TRUE
        """

        params = [user_priority, user_id]

        # Добавляем фильтры
        if filters.get('city'):
            query += " AND u.city = $3"
            params.append(filters['city'])

        if filters.get('age_min') and filters.get('age_max'):
            query += " AND u.age BETWEEN $4 AND $5"
            params.extend([filters['age_min'], filters['age_max']])

        # Сортируем по приоритету
        query += " ORDER BY search_priority DESC, u.lastactiondate DESC"

        if filters.get('limit'):
            query += " LIMIT $6"
            params.append(filters['limit'])

        async with self.pool.acquire() as conn:
            users = await conn.fetch(query, *params)

        return [dict(user) for user in users]

    except Exception as e:
        logger.error(f"Error finding compatible users: {e}")
        return []


async def check_expired_services(self):
    """Проверяет и деактивирует просроченные услуги"""
    try:
        async with self.pool.acquire() as conn:
            # Находим просроченные услуги
            expired = await conn.fetch(
                "SELECT usertelegramid FROM purchasedservices "
                "WHERE serviceenddate <= NOW() AND paymentstatus = TRUE"
            )

            if not expired:
                return 0

            # Деактивируем их
            await conn.execute(
                "UPDATE purchasedservices SET paymentstatus = FALSE "
                "WHERE serviceenddate <= NOW() AND paymentstatus = TRUE"
            )

            # Обновляем приоритеты для затронутых пользователей
            for record in expired:
                await self.update_user_priority(record['usertelegramid'])

            return len(expired)

    except Exception as e:
        logger.error(f"Error checking expired services: {e}")
        return 0

# Функция для отображения совместимого пользователя
async def show_compatible_user(message: Message, state: FSMContext, db: Database, crypto=None):
    """Показывает совместимого пользователя с очисткой предыдущих сообщений и правильными кнопками"""
    try:
        # Получаем данные из состояния
        state_data = await state.get_data()
        current_index = state_data.get("current_compatible_index", 0)
        compatible_users = state_data.get("compatible_users", [])
        last_messages = state_data.get("last_profile_messages", [])
        
        # Очищаем предыдущие сообщения
        for msg_id in last_messages:
            try:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=msg_id)
            except Exception as e:
                logger.error(f"Ошибка удаления сообщения {msg_id}: {e}")
        
        # Если список анкет пуст
        if not compatible_users:
            no_profiles_msg = await message.answer(
                "😔 Совместимых пользователей не найдено.\n"
                "Попробуйте изменить фильтры или проверьте позже.",
                reply_markup=back_to_menu_button()
            )
            await state.update_data(last_profile_messages=[no_profiles_msg.message_id])
            return
        
        # Корректируем индекс при выходе за границы
        if current_index >= len(compatible_users):
            current_index = 0
        elif current_index < 0:
            current_index = len(compatible_users) - 1
        
        # Получаем текущую анкету
        current_user = compatible_users[current_index]
        user_profile = current_user['profile']
        compatibility = current_user['compatibility']
        
        # Форматируем текст профиля
        profile_text = await format_profile_text(user_profile, crypto)
        profile_text += f"<b>Совместимость:</b> {compatibility}%"
        
        # Создаём адаптивную клавиатуру - всегда передаем False для is_initial
        keyboard = compatible_navigation_keyboard(
            user_id=user_profile['telegramid'],
            is_first=current_index == 0,
            is_last=current_index == len(compatible_users) - 1,
            is_initial=False  # Всегда передаем False
        )
        
        # Отправляем новое сообщение
        photos = user_profile.get('photos', [])
        sent_message = None
        if photos:
            sent_message = await message.answer_photo(
                photo=photos[0],
                caption=profile_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            sent_message = await message.answer(
                text=profile_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        
        # Обновляем состояние
        await state.update_data(
            last_profile_messages=[sent_message.message_id],
            current_compatible_index=current_index,
            current_profile_id=user_profile['telegramid'],
            is_initial_view=False  # Сбрасываем флаг после первого показа
        )
    except Exception as e:
        logger.error(f"Критическая ошибка в show_compatible_user: {e}", exc_info=True)
        error_msg = await message.answer(
            "⚠️ Произошла непредвиденная ошибка при загрузке анкеты.",
            reply_markup=back_to_menu_button()
        )
        await state.update_data(last_profile_messages=[error_msg.message_id])

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

# Обработчик для лайка пользователя
@router.callback_query(F.data.startswith("like_user_"))
async def like_user_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    """Обработчик лайка пользователя"""
    await callback.answer("❤️")
    
    # Извлекаем ID пользователя из callback_data
    liked_user_id = int(callback.data.split("_")[2])
    
    try:
        # Добавляем лайк в базу данных
        like_id = await db.add_like(callback.from_user.id, liked_user_id)
        
        if like_id:
            logger.info(f"Пользователь {callback.from_user.id} лайкнул {liked_user_id}")
            
            # Проверяем на взаимный лайк
            is_mutual = await db.check_mutual_like(callback.from_user.id, liked_user_id)
            
            # Отправляем уведомление о лайке
            await send_like_notification(
                callback.bot, 
                callback.from_user.id,
                liked_user_id,
                db,
                crypto
            )
            
            # Если это взаимный лайк, показываем особое сообщение
            if is_mutual:
                await callback.message.answer(
                    "❤️ У вас взаимная симпатия! Теперь вы можете начать общение.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="💬 Написать сообщение", 
                            url=f"tg://user?id={liked_user_id}"
                        )]
                    ])
                )
    except Exception as e:
        logger.error(f"Ошибка при добавлении лайка: {e}")
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    current_index = state_data.get("current_compatible_index", 0)
    compatible_users = state_data.get("compatible_users", [])
    
    # Увеличиваем индекс для перехода к следующей анкете
    current_index += 1
    
    # Если дошли до конца списка, начинаем сначала
    if current_index >= len(compatible_users):
        current_index = 0
    
    # Обновляем индекс в состоянии
    await state.update_data(current_compatible_index=current_index)
    
    # Удаляем предыдущее сообщение
    await delete_message_safely(callback.message)
    
    # Показываем следующего пользователя
    await show_compatible_user(callback.message, state, db, crypto)

# Обработчики фильтров
@router.callback_query(F.data == "filter_city")
async def filter_city_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите город для поиска:")
    await state.set_state(RegistrationStates.SET_FILTER_CITY)
    await callback.answer()

@router.message(RegistrationStates.SET_FILTER_CITY)
async def process_city_filter(message: Message, state: FSMContext):
    is_valid, normalized_city = city_validator.validate_city(message.text)
    if not is_valid:
        await message.answer("⚠️ Город не найден. Пожалуйста, введите существующий российский город")
        return
    await state.update_data(filter_city=normalized_city)
    await show_filters_menu(message, state)

@router.callback_query(F.data == "filter_age")
async def filter_age_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите возрастной диапазон (например, 25-30):")
    await state.set_state(RegistrationStates.SET_FILTER_AGE)
    await callback.answer()

@router.message(RegistrationStates.SET_FILTER_AGE)
async def process_age_filter(message: Message, state: FSMContext):
    try:
        age_min, age_max = map(int, message.text.split('-'))
        if 18 <= age_min <= age_max <= 100:
            await state.update_data(filter_age_min=age_min, filter_age_max=age_max)
            await show_filters_menu(message, state)
        else:
            await message.answer("⚠️ Возраст должен быть от 18 до 100 лет")
    except:
        await message.answer("⚠️ Неверный формат. Введите например: 25-30")

# Обработчик начала поиска
@router.callback_query(F.data == "start_search")
async def start_search_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    await callback.answer()
    await callback.message.edit_text("🔍 Ищем совместимых пользователей...")
    # Получаем фильтры из состояния
    filters = await state.get_data()
    # Создаем сервис совместимости
    compatibility_service = CompatibilityService(db)
    # Ищем пользователей с учетом фильтров
    high_compatible_users, low_compatible_users = await compatibility_service.find_compatible_users(
        user_id=callback.from_user.id,
        city=filters.get('filter_city'),
        age_min=filters.get('filter_age_min'),
        age_max=filters.get('filter_age_max'),
        gender=filters.get('filter_gender'),
        occupation=filters.get('filter_occupation'),
        goals=filters.get('filter_goals'),
        limit=10,
        min_score=50.0
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
    # Показываем первого пользователя - ВАЖНО: передаем crypto
    await show_compatible_user(callback.message, state, db, crypto)

async def show_filters_menu(message: Message, state: FSMContext, db=None):
    """Показывает меню фильтров с текущими настройками"""
    data = await state.get_data()
    has_subscription = await db.check_user_subscription(message.from_user.id)
    builder = InlineKeyboardBuilder()
    # Добавляем кнопки фильтров с текущими значениями
    city_text = f"📍 Город: {data.get('filter_city', 'любой')}"
    age_text = f"🔢 Возраст: {data.get('filter_age_min', '18')}-{data.get('filter_age_max', '100')}"
    builder.button(text=city_text, callback_data="filter_city")
    builder.button(text=age_text, callback_data="filter_age")
    if has_subscription:
        # Доп фильтры для подписчиков
        gender_text = f"👫 Пол: {data.get('filter_gender', 'любой')}"
        builder.button(text=gender_text, callback_data="filter_gender")
    builder.button(text="🔍 Начать поиск", callback_data="start_search")
    builder.button(text="◀️ Назад", callback_data="back_to_menu")
    builder.adjust(2)
    await message.answer(
        "⚙️ Текущие фильтры поиска:",
        reply_markup=builder.as_markup()
    )

'''Обработчик кнопки назад на одну анкету'''
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

    # Добавьте этот обработчик в конец файла

@router.callback_query()
async def debug_callback(callback: CallbackQuery):
    """Отладочный обработчик для всех callback_query"""
    logger.debug(f"Получен callback_data: {callback.data}")
    await callback.answer()

@router.callback_query(F.data == "next_like")
async def next_like_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    """Обработчик перехода к следующему лайку"""
    await callback.answer()
    
    state_data = await state.get_data()
    current_index = state_data.get("current_like_index", 0) + 1
    likes_list = state_data.get("likes_list", [])
    
    if current_index >= len(likes_list):
        await callback.message.edit_text(
            "Вы просмотрели все лайки!",
            reply_markup=back_to_menu_button()
        )
        return
    
    await state.update_data(current_like_index=current_index)
    await show_like_profile(callback.message, state, db, crypto)

@router.callback_query(F.data == "prev_like")
async def prev_like_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    """Обработчик кнопки 'Назад' при просмотре лайков"""
    # Получаем текущие данные из состояния
    state_data = await state.get_data()
    current_index = state_data.get("current_like_index", 0)
    
    # Проверяем, есть ли предыдущий лайк
    if current_index > 0:
        # Уменьшаем индекс
        current_index -= 1
        await state.update_data(current_like_index=current_index)
        
        # Показываем предыдущий профиль
        await show_like_profile(callback.message, state, db, crypto)
    else:
        await callback.answer("Это первый лайк в списке", show_alert=True)

@router.callback_query(F.data == "my_likes")
async def show_my_likes(callback: CallbackQuery, state: FSMContext, db: Database, crypto=None):
    """Показывает список непросмотренных лайков"""
    try:
        # Получаем только НЕпросмотренные лайки
        likes = await db.fetch(
            "SELECT likeid, sendertelegramid FROM likes WHERE receivertelegramid = $1 AND likeviewedstatus = FALSE",
            callback.from_user.id
        )

        if not likes:
            await callback.message.edit_text(
                "У вас пока нет новых лайков.",
                reply_markup=back_to_menu_button()
            )
            await callback.answer()
            return

        # Сохраняем список лайков в состоянии
        await state.update_data(likes_list=likes, current_like_index=0)

        # Показываем первый профиль
        await show_like_profile(callback.message, state, db, crypto)

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при получении лайков: {e}")
        await callback.message.edit_text(
            "Произошла ошибка при загрузке лайков. Попробуйте позже.",
            reply_markup=back_to_menu_button()
        )
        await callback.answer("Произошла ошибка", show_alert=True)
