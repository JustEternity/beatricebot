from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import (
    KeyboardButton,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup
)

def build_main_menu() -> InlineKeyboardBuilder:
    """Строит инлайн-клавиатуру главного меню"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👤 Профиль", callback_data="view_profile"),
        InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_profile"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="📝 Тест", callback_data="take_test"),
        width=1
    )
    return builder

def build_gender_select() -> ReplyKeyboardBuilder:
    """Клавиатура выбора пола"""
    builder = ReplyKeyboardBuilder()
    builder.add(
        KeyboardButton(text="👨 Мужской"),
        KeyboardButton(text="👩 Женский")
    )
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

def build_photos_upload(current_count: int = 0) -> ReplyKeyboardMarkup:
    """Динамическая клавиатура для загрузки фото"""
    builder = ReplyKeyboardBuilder()

    if current_count < 3:
        builder.add(KeyboardButton(text="📷 Добавить фото"))

    builder.add(KeyboardButton(text="✅ Завершить"))

    return builder.as_markup(
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder=f"Добавлено {current_count}/3 фото"
    )

def build_yes_no_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура Да/Нет"""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="✅ Да"),
        KeyboardButton(text="❌ Нет"),
        width=2
    )
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

def build_edit_profile_kb() -> InlineKeyboardBuilder:
    """Инлайн-клавиатура редактирования профиля"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Имя", callback_data="edit_name"),
        InlineKeyboardButton(text="Возраст", callback_data="edit_age"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="Город", callback_data="edit_location"),
        InlineKeyboardButton(text="Описание", callback_data="edit_description"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="Фото", callback_data="edit_photos"),
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu"),
        width=2
    )
    return builder

def build_test_answers(answers: dict[int, str]) -> InlineKeyboardMarkup:
    """Строит клавиатуру с вариантами ответов для теста"""
    builder = InlineKeyboardBuilder()
    for answer_id, answer_text in answers.items():
        builder.button(
            text=answer_text,
            callback_data=f"answer_{answer_id}"
        )
    builder.adjust(1)  # По одному варианту в строке
    return builder.as_markup()