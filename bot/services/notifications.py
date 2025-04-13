from aiogram import Router
from aiogram.exceptions import TelegramAPIError
import logging
from bot.keyboards.menus import get_like_notification_keyboard
from bot.keyboards.menus import get_match_notification_keyboard

logger = logging.getLogger(__name__)
router = Router()

def decrypt_name(encrypted_name, crypto):
    """Дешифрует base64-строку"""
    logger.info(f"[decrypt_name] Входное значение: {repr(encrypted_name)}")
    
    if not crypto:
        logger.warning("[decrypt_name] crypto отсутствует, возвращаем имя по умолчанию")
        return "Пользователь"
    
    if not encrypted_name:
        logger.warning("[decrypt_name] encrypted_name отсутствует, возвращаем имя по умолчанию")
        return "Пользователь"
    
    try:
        # Обработка строки, которая может быть представлением байтов
        if isinstance(encrypted_name, str):
            # Если строка начинается с 'b', это может быть представление байтов
            if encrypted_name.startswith("b'") and encrypted_name.endswith("'"):
                encrypted_name = encrypted_name[2:-1]
            
            # Преобразуем строку в байты
            encrypted_name = encrypted_name.encode()
            logger.info(f"[decrypt_name] Преобразовано в байты: {encrypted_name!r}")
        
        # Расшифровываем
        decrypted = crypto.decrypt(encrypted_name)
        logger.info(f"[decrypt_name] Расшифрованное значение: {decrypted}")
        return decrypted
    except Exception as e:
        logger.error(f"[decrypt_name] Ошибка при дешифровании имени: {e}", exc_info=True)
        return "Пользователь"  # Возвращаем значение по умолчанию в случае ошибки

async def send_like_notification(bot, from_user_id, to_user_id, db, crypto=None):
    """Отправляет уведомление о лайке пользователю"""
    try:
        logger.info(f"Начинаем отправку уведомления о лайке от {from_user_id} к {to_user_id}")
        
        # Проверяем, есть ли взаимный лайк
        mutual_like = await db.check_mutual_like(from_user_id, to_user_id)
        
        # Если есть взаимный лайк, отправляем уведомление о взаимной симпатии
        if mutual_like:
            logger.info(f"Обнаружена взаимная симпатия между {from_user_id} и {to_user_id}")
            return await send_match_notification(bot, from_user_id, to_user_id, db, crypto)
        
        # Получаем информацию о пользователе, который поставил лайк
        sender = await db.get_user_profile(from_user_id)  
        if not sender:
            logger.error(f"Не удалось найти пользователя с ID {from_user_id}")
            return False
        
        logger.debug(f"Информация о отправителе лайка: {sender}")
        
        # Формируем текст уведомления
        notification_text = "❤️ <b>Кто-то проявил к вам симпатию!</b>\n\nХотите посмотреть профиль?"
        
        keyboard = get_like_notification_keyboard(from_user_id)
        
        # Отправляем уведомление
        try:
            logger.debug(f"Отправляем сообщение пользователю {to_user_id}")
            message = await bot.send_message(
                chat_id=to_user_id,
                text=notification_text,
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
                
        # Получаем и дешифруем имена пользователей
        user1_encrypted_name = user1_profile.get('name', user1_profile.get('username', 'Пользователь'))
        user2_encrypted_name = user2_profile.get('name', user2_profile.get('username', 'Пользователь'))
                
        user1_name = decrypt_name(user1_encrypted_name, crypto)
        user2_name = decrypt_name(user2_encrypted_name, crypto)
                
        logger.debug(f"Дешифрованные имена: user1={user1_name}, user2={user2_name}")
        
        # Получаем username пользователей (если есть)
        user1_username = user1_profile.get('username')
        user2_username = user2_profile.get('username')
        
        # Создаем ссылки на профили
        user1_link = f"<a href='tg://user?id={user1_id}'>{user1_name}</a>"
        user2_link = f"<a href='tg://user?id={user2_id}'>{user2_name}</a>"
        
        success = True
                
        # Отправляем уведомление первому пользователю
        try:
            keyboard1 = get_match_notification_keyboard(user2_id)
            await bot.send_message(
                chat_id=user1_id,
                text=f"✨ <b>У вас взаимная симпатия с {user2_link}!</b> ✨\n\n"
                     f"Теперь вы можете начать общение.",
                reply_markup=keyboard1,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления пользователю {user1_id}: {e}")
            success = False
                        
        # Отправляем уведомление второму пользователю
        try:
            keyboard2 = get_match_notification_keyboard(user1_id)
            await bot.send_message(
                chat_id=user2_id,
                text=f"✨ <b>У вас взаимная симпатия с {user1_link}!</b> ✨\n\n"
                     f"Теперь вы можете начать общение.",
                reply_markup=keyboard2,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления пользователю {user2_id}: {e}")
            success = False
                
        if success:
            logger.info(f"Уведомления о взаимной симпатии успешно отправлены")
            # Удаляем лайки после успешной отправки уведомлений
            await db.delete_mutual_likes(user1_id, user2_id)
                
        return success
    except TelegramAPIError as e:
        logger.error(f"Ошибка Telegram API при отправке уведомления о взаимной симпатии: {e}")
        return False
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о взаимной симпатии: {e}")
        return False