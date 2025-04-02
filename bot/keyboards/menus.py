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


def main_menu(likes_count=0) -> InlineKeyboardMarkup:
    """Инлайн-клавиатура главного меню с количеством лайков"""
    likes_text = f"❤️ Лайки ({likes_count})" if likes_count > 0 else "❤️ Лайки"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Моя анкета", callback_data="view_profile")],
            [InlineKeyboardButton(text=likes_text, callback_data="view_likes")],
            [InlineKeyboardButton(text="📝 Пройти тест", callback_data="take_test")],
            [InlineKeyboardButton(text="🔍 Найти совместимых", callback_data="find_compatible")],
            [InlineKeyboardButton(text="💎 Подписка", callback_data="subscription_info")],
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
            [InlineKeyboardButton(text="📍 Локация", callback_data="edit_location"),
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

def subscription_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для активации подписки"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💎 Активировать подписку", callback_data="activate_subscription")],
            [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu")]
        ]
    )
