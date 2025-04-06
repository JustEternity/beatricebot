from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

def policy_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для согласия с политикой конфиденциальности"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Я согласен"), KeyboardButton(text="❌ Я не согласен")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def services_keyboard(services=None) -> InlineKeyboardMarkup:
    """Клавиатура для просмотра услуг"""
    buttons = []

    # Если есть услуги, добавляем кнопки для каждой услуги
    if services:
        for service in services:
            buttons.append([
                InlineKeyboardButton(
                    text=f"{service['description']} - {service['cost']} руб.",
                    callback_data=f"service_info_{service['serviceid']}"
                )
            ])

    # Добавляем кнопку возврата в меню
    buttons.append([InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_menu() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура админского меню"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Модерации", callback_data="admin_moderations")],
            [InlineKeyboardButton(text="Верификации", callback_data="admin_verifications")],
            [InlineKeyboardButton(text="Жалобы", callback_data="admin_complaints")],
            [InlineKeyboardButton(text="Обратная связь", callback_data="admin_feedback")],
            [InlineKeyboardButton(text="Отчеты", callback_data="admin_reports")],
            [InlineKeyboardButton(text="В режим пользователя", callback_data="back_to_menu")]
        ]
    )

def back_to_admin_menu_button() -> InlineKeyboardMarkup:
    """Кнопка возврата в меню админа"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_admin_menu")]
        ]
    )

def reports_menu() -> InlineKeyboardMarkup:
    """ Инлайн-клавиатура доступных отчетов"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Активность за месяц", callback_data="get_active_users")],
            [InlineKeyboardButton(text="Регистрации за год", callback_data="get_count_of_regs")],
            [InlineKeyboardButton(text="Мои результаты", callback_data="admin_results")],
            [InlineKeyboardButton(text="Купленные услуги за год", callback_data="get_purchased_services")],
            [InlineKeyboardButton(text="В меню", callback_data="back_to_admin_menu")]
        ]
    )

def back_to_reports_menu() -> InlineKeyboardMarkup:
    """ Кнопка назад к отчетам и в меню"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="К отчетам", callback_data="admin_reports")],
            [InlineKeyboardButton(text="В меню", callback_data="back_to_admin_menu")]
        ]
    )

def feedback_categories() -> InlineKeyboardMarkup:
    """Категории обращений обратной связи"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Баги", callback_data="feedback_bags")],
            [InlineKeyboardButton(text="Пожелания", callback_data="feedback_wishes")],
            [InlineKeyboardButton(text="Спам", callback_data="feedback_spam")],
            [InlineKeyboardButton(text="Сотрудничество", callback_data="feedback_collab")],
            [InlineKeyboardButton(text="Другое", callback_data="feedback_other")],
            [InlineKeyboardButton(text="Назад в меню", callback_data="back_to_admin_menu")]
        ]
    )

def complaint_decisions() -> InlineKeyboardMarkup:
    """Решения для жалоб"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data="complaint_skip")],
            [InlineKeyboardButton(text="Блокировать", callback_data="complaint_block")],
            [InlineKeyboardButton(text="Назад в меню", callback_data="back_to_admin_menu")]
        ]
    )

def verify_decisions() -> InlineKeyboardMarkup:
    """Решения для верификации"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data="verify_skip")],
            [InlineKeyboardButton(text="Блокировать", callback_data="verify_block")],
            [InlineKeyboardButton(text="Назад в меню", callback_data="back_to_admin_menu")]
        ]
    )

def moder_decisions() -> InlineKeyboardMarkup:
    """Решения для модерации"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data="moder_skip")],
            [InlineKeyboardButton(text="Блокировать", callback_data="moder_block")],
            [InlineKeyboardButton(text="Назад в меню", callback_data="back_to_admin_menu")]
        ]
    )

def main_menu(likes_count=0) -> InlineKeyboardMarkup:
    """Инлайн-клавиатура главного меню с количеством лайков"""
    likes_text = f"❤️ Лайки ({likes_count})" if likes_count > 0 else "❤️ Лайки"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Моя анкета", callback_data="view_profile")],
            [InlineKeyboardButton(text=likes_text, callback_data="view_likes")],
            [InlineKeyboardButton(text="📝 Пройти тест", callback_data="take_test")],
            [InlineKeyboardButton(text="🔍 Найти совместимых", callback_data="find_compatible")],
            [InlineKeyboardButton(text="🛒 Услуги", callback_data="view_services")],
            [InlineKeyboardButton(text="Обратная связь", callback_data="send_feedback")]
        ]
    )

def back_to_menu_button() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu")]
        ]
    )

def edit_profile_keyboard() -> InlineKeyboardMarkup:
    """Меню редактирования профиля"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Имя", callback_data="edit_name"),
             InlineKeyboardButton(text="🔢 Возраст", callback_data="edit_age")],
            [InlineKeyboardButton(text="📍 Город", callback_data="edit_location"),
             InlineKeyboardButton(text="📸 Фото", callback_data="edit_photos")],
            [InlineKeyboardButton(text="📄 Описание", callback_data="edit_description")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
        ]
    )

def photos_edit_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура при редактировании фотографий"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📷 Добавить еще"),
             KeyboardButton(text="✅ Сохранить")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

def test_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Подтверждение повторного прохождения теста"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Пройти заново", callback_data="confirm_test")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_menu")]
        ]
    )

def view_profile() -> InlineKeyboardMarkup:
    """Меню просмотра профиля"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu"),
             InlineKeyboardButton(text="✏️ Изменить анкету", callback_data="edit_profile")],
        ]
    )

def has_answers_keyboard() -> InlineKeyboardMarkup:
    """Меню при наличии ответов на тест"""
    return InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Да, хочу пройти заново", callback_data="confirm_test")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_menu")]
            ])

def compatible_navigation_keyboard(
    user_id: int = None,
    is_first: bool = False,
    is_last: bool = False,
    is_initial: bool = False
) -> InlineKeyboardMarkup:
    """Клавиатура с обязательными кнопками 'Лайк' и 'Пропустить'"""
    buttons = []

    # Основной ряд
    main_buttons = []

    # Кнопка "Назад" (показываем всегда, кроме первой анкеты)
    if not is_first:
        main_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data="prev_compatible"))

    # Кнопка "Лайк" - всегда показываем
    if user_id:
        main_buttons.append(InlineKeyboardButton(text="❤️ Лайк", callback_data=f"like_user_{user_id}"))

    # Кнопка "Пропустить" - всегда показываем, независимо от позиции анкеты
    main_buttons.append(InlineKeyboardButton(text="👎 Пропустить", callback_data="next_compatible"))

    if main_buttons:
        buttons.append(main_buttons)

    # Кнопка возврата в меню (всегда)
    buttons.append([InlineKeyboardButton(text="◀️ В меню", callback_data="back_to_menu")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def create_like_keyboard(liker_id):
    """Создает стандартную клавиатуру для просмотра лайков"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️ Нравится", callback_data=f"like_back:{liker_id}"),
            InlineKeyboardButton(text="👎 Не нравится", callback_data=f"dislike_user:{liker_id}")
        ],
        [InlineKeyboardButton(text="◀️ Назад в главное меню", callback_data="back_to_menu")]
    ])

def get_like_notification_keyboard(liker_id: int) -> InlineKeyboardMarkup:
    # Создает клавиатуру для уведомления о лайке

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="👁️ Посмотреть",
            callback_data=f"view_liker:{liker_id}"
        )],
        [InlineKeyboardButton(
            text="◀️ В главное меню",
            callback_data="back_to_menu"
        )]
    ])

def get_match_notification_keyboard(user_id: int) -> InlineKeyboardMarkup:
    # Создает клавиатуру для уведомления о взаимной симпатии

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💬 Начать общение",
            url=f"tg://user?id={user_id}"
        )],
        [InlineKeyboardButton(
            text="◀️ В меню",
            callback_data="back_to_menu"
        )]
    ])

def subscription_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для активации подписки"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💎 Активировать подписку", callback_data="activate_subscription")],
            [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu")]
        ]
    )
