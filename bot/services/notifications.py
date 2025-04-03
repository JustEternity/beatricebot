from aiogram import Router
from aiogram.exceptions import TelegramAPIError
import logging

from bot.keyboards.menus import get_like_notification_keyboard
from bot.keyboards.menus import get_match_notification_keyboard

logger = logging.getLogger(__name__)
router = Router()

async def send_like_notification(bot, from_user_id, to_user_id, db, crypto=None):
    """Отправляет уведомление о лайке пользователю"""
    try:
        logger.info(f"Начинаем отправку уведомления о лайке от {from_user_id} к {to_user_id}")

        mutual_like = await db.check_mutual_like(from_user_id, to_user_id)

        # Если есть взаимный лайк, отправляем уведомление о взаимной симпатии
        if mutual_like:
            logger.info(f"Обнаружена взаимная симпатия между {from_user_id} и {to_user_id}")
            return await send_match_notification(bot, from_user_id, to_user_id, db, crypto)

        keyboard = get_like_notification_keyboard(from_user_id)

        # Отправляем уведомление без указания конкретного пользователя
        try:
            message = await bot.send_message(
                chat_id=to_user_id,
                text=f"❤️ <b>Кто-то проявил к вам симпатию!</b>\n\n"
                     f"Хотите посмотреть профиль?",
                reply_markup=keyboard,
                parse_mode="HTML"
            )

            logger.info(f"Уведомление о лайке от {from_user_id} успешно отправлено пользователю {to_user_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения: {e}", exc_info=True)
            return False

    except TelegramAPIError as e:
        logger.error(f"Ошибка Telegram API при отправке уведомления о лайке: {e}")
        return False
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о лайке: {e}", exc_info=True)
        return False

async def send_match_notification(bot, user1_id, user2_id, db, crypto=None):
    """Отправляет уведомление о взаимной симпатии обоим пользователям"""
    logger.info(f"Отправка уведомлений о взаимной симпатии между {user1_id} и {user2_id}")

    try:
        # Получаем профили пользователей
        user1_profile = await db.get_user_profile(user1_id)
        user2_profile = await db.get_user_profile(user2_id)

        if not user1_profile or not user2_profile:
            logger.error(f"Не удалось получить профили пользователей {user1_id} и {user2_id}")
            return False

        # Получаем имена пользователей
        user1_name = user1_profile.get('name', user1_profile.get('username', 'Пользователь'))
        user2_name = user2_profile.get('name', user2_profile.get('username', 'Пользователь'))

        # Отправляем уведомление первому пользователю
        keyboard1 = get_match_notification_keyboard(user2_id)
        await bot.send_message(
            chat_id=user1_id,
            text=f"✨ <b>У вас взаимная симпатия с {user2_name}!</b> ✨\n\n"
                 f"Теперь вы можете начать общение.",
            reply_markup=keyboard1,
            parse_mode="HTML"
        )
        
        # Отправляем уведомление второму пользователю
        keyboard2 = get_match_notification_keyboard(user1_id)
        await bot.send_message(
            chat_id=user2_id,
            text=f"✨ <b>У вас взаимная симпатия с {user1_name}!</b> ✨\n\n"
                 f"Теперь вы можете начать общение.",
            reply_markup=keyboard2,
            parse_mode="HTML"
        )

        logger.info(f"Уведомления о взаимной симпатии успешно отправлены")
        return True

    except TelegramAPIError as e:
        logger.error(f"Ошибка Telegram API при отправке уведомления о взаимной симпатии: {e}")
        return False
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о взаимной симпатии: {e}")
        return False