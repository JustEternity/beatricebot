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

def main_menu() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура главного меню"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Моя анкета", callback_data="view_profile")],
            [InlineKeyboardButton(text="📝 Пройти тест", callback_data="take_test")]
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

