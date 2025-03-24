from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.models.states import RegistrationStates
from bot.services.database import Database
from bot.services.utils import handle_errors, delete_previous_messages
from bot.keyboards.menus import test_confirmation_keyboard, back_to_menu_button

router = Router()

@router.callback_query(F.data == "take_test")
@handle_errors
async def take_test(callback: CallbackQuery, state: FSMContext, db: Database):
    """Обработчик начала тестирования"""
    await delete_previous_messages(callback.message, state)

    # Проверка предыдущих попыток
    has_answers = await db.check_existing_answers(callback.from_user.id)

    if has_answers:
        await callback.message.edit_text(
            "Вы уже проходили тест. Хотите пройти снова?",
            reply_markup=test_confirmation_keyboard()
        )
        return

    await start_test(callback, state, db)

@router.callback_query(F.data == "confirm_test")
@handle_errors
async def confirm_test(callback: CallbackQuery, state: FSMContext, db: Database):
    """Подтверждение перепрохождения теста"""
    await callback.message.delete()
    await start_test(callback, state, db)

async def start_test(source: CallbackQuery, state: FSMContext, db: Database):
    """Запуск нового теста"""
    start_msg = await source.message.answer("🔄 Загрузка вопросов...")

    questions, answers = await db.get_questions_and_answers()
    if not questions or not answers:
        await start_msg.edit_text("❌ Ошибка загрузки вопросов")
        return

    await state.update_data(
        questions=questions,
        answers=answers,
        question_ids=list(questions.keys()),
        current_question=0,
        user_answers={},
        test_message_id=start_msg.message_id
    )
    await state.set_state(RegistrationStates.TEST_QUESTION)
    await show_question(start_msg, state)

@handle_errors
async def show_question(message: Message, state: FSMContext):
    """Отображение текущего вопроса"""
    data = await state.get_data()
    questions = data['questions']
    question_ids = data['question_ids']
    current_idx = data['current_question']

    if current_idx >= len(question_ids):
        await finish_test(message, state)
        return

    question_id = question_ids[current_idx]
    question_text = questions[question_id]
    answers = data['answers'][question_id]

    builder = InlineKeyboardBuilder()
    for answer_id, answer_text in answers.items():
        builder.button(
            text=answer_text,
            callback_data=f"answer_{question_id}_{answer_id}"
        )
    builder.adjust(1)

    try:
        await message.edit_text(
            f"Вопрос {current_idx + 1} из {len(question_ids)}:\n\n{question_text}",
            reply_markup=builder.as_markup()
        )
    except Exception:
        new_msg = await message.answer(
            f"Вопрос {current_idx + 1} из {len(question_ids)}:\n\n{question_text}",
            reply_markup=builder.as_markup()
        )
        await state.update_data(test_message_id=new_msg.message_id)

@router.callback_query(F.data.startswith("answer_"))
@handle_errors
async def process_test_answer(callback: CallbackQuery, state: FSMContext):
    """Обработка выбранного ответа"""
    _, question_id, answer_id = callback.data.split('_')
    question_id = int(question_id)
    answer_id = int(answer_id)

    data = await state.get_data()
    user_answers = data['user_answers']
    user_answers[question_id] = answer_id

    await state.update_data(
        user_answers=user_answers,
        current_question=data['current_question'] + 1
    )

    await callback.answer()
    await show_question(callback.message, state)

@handle_errors
async def finish_test(message: Message, state: FSMContext, db: Database):
    """Завершение теста и сохранение результатов"""
    data = await state.get_data()

    if await db.save_user_answers(
        user_id=message.from_user.id,
        answers=data['user_answers']
    ):
        await message.edit_text(
            "✅ Тест успешно завершен!",
            reply_markup=back_to_menu_button()
        )
    else:
        await message.edit_text(
            "❌ Ошибка сохранения результатов",
            reply_markup=back_to_menu_button()
        )

    await state.set_state(RegistrationStates.MAIN_MENU)