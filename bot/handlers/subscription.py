from aiogram import Router, F
from aiogram.types import CallbackQuery
from bot.services.database import Database
from bot.services.utils import handle_errors
from bot.keyboards.menus import main_menu, subscription_keyboard, back_to_menu_button
import logging

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "activate_subscription")
@handle_errors
async def activate_subscription_handler(callback: CallbackQuery, db: Database, **kwargs):
    """Обработчик активации подписки"""
    user_id = callback.from_user.id
    logger.info(f"Запрос на активацию подписки для пользователя {user_id}")

    # Проверяем, есть ли уже активная подписка
    has_subscription = await db.check_user_subscription(user_id)
    logger.info(f"Текущий статус подписки пользователя {user_id}: {has_subscription}")

    if has_subscription:
        # Если подписка уже активна, сообщаем об этом
        await callback.answer("У вас уже есть активная подписка!", show_alert=True)
        await callback.message.edit_text(
            "💎 Ваша подписка уже активирована!\n\n"
            "Вам доступны все функции бота, включая расширенные параметры поиска.",
            reply_markup=main_menu()
        )
        return

    # Активируем подписку на 30 дней
    success = await db.activate_subscription(user_id, days=30)
    logger.info(f"Результат активации: {success}")

    # Проверяем, активировалась ли подписка
    new_status = await db.check_user_subscription(user_id)
    logger.info(f"Новый статус подписки после активации: {new_status}")

    if success and new_status:
        await callback.answer("✅ Подписка успешно активирована на 30 дней!", show_alert=True)
        await callback.message.edit_text(
            "💎 Ваша подписка активирована!\n\n"
            "Теперь вам доступны все функции приложения, включая расширенные параметры поиска.",
            reply_markup=main_menu()
        )
    else:
        await callback.answer("❌ Произошла ошибка при активации подписки", show_alert=True)
        logger.error(f"Не удалось активировать подписку: success={success}, new_status={new_status}")

@router.callback_query(F.data == "subscription_info")
@handle_errors
async def subscription_info_handler(callback: CallbackQuery, db: Database, **kwargs):
    """Обработчик информации о подписке"""
    user_id = callback.from_user.id

    # Проверяем наличие подписки
    has_subscription = await db.check_user_subscription(user_id)

    if has_subscription:
        await callback.message.edit_text(
            "💎 У вас активирована подписка!\n\n"
            "Вам доступны все функции приложения, включая расширенные параметры поиска.",
            reply_markup=back_to_menu_button()
        )
    else:
        await callback.message.edit_text(
            "🔒 У вас нет активной подписки\n\n"
            "Активируйте подписку, чтобы получить доступ к расширенным параметрам поиска "
            "и другим премиум-функциям.",
            reply_markup=subscription_keyboard()
        )