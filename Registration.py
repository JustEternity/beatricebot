from telegram import Update, ReplyKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import psycopg2
from psycopg2 import sql
from datetime import datetime

# Определяем состояния для ConversationHandler
POLICY, NAME, AGE, GENDER, LOCATION, PHOTOS, DESCRIPTION = range(7)

# Текст политики конфиденциальности
POLICY_TEXT = """
📜 *Политика конфиденциальности:*

1. Мы собираем только необходимые данные для регистрации.
2. Ваши данные не будут переданы третьим лицам.
3. Вы можете запросить удаление ваших данных в любой момент.

Для продолжения регистрации, пожалуйста, подтвердите, что вы согласны с политикой конфиденциальности.
"""

# Функция для подключения к PostgreSQL
def connect_to_db():
    try:
        conn = psycopg2.connect(
            dbname="beatrice",  # Имя вашей базы данных
            user="postgres",  # Имя пользователя PostgreSQL
            password="12345qwerty",  # Пароль пользователя
            host="localhost",  # Хост (обычно localhost)
            port="5432"  # Порт (по умолчанию 5432)
        )
        print("Подключение к базе данных успешно установлено!")
        return conn
    except Exception as e:
        print(f"Ошибка подключения к базе данных: {e}")
        return None

# Функция для сохранения данных пользователя в базу данных
def save_user_to_db(user_data, telegram_id):
    conn = connect_to_db()
    if conn:
        try:
            cur = conn.cursor()

            # Сохраняем данные в таблицу User
            query_user = sql.SQL("""
                INSERT INTO "Users" (
                    TelegramID, Name, Age, Gender, City, ProfileDescription,
                    SubscriptionStatus, ModerationStatus, VerificationStatus,
                    RegistrationDate, LastActionDate, ProfilePriorityCoefficient,
                    AccountStatus, Mail
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s
                )
            """)
            cur.execute(query_user, (
                telegram_id,
                user_data['name'].encode('utf-8'),  # Преобразуем в BYTEA
                user_data['age'],
                user_data['gender'],
                user_data['location'].encode('utf-8'),  # Преобразуем в BYTEA
                user_data['description'].encode('utf-8'),  # Преобразуем в BYTEA
                False,  # SubscriptionStatus
                False,  # ModerationStatus
                False,  # VerificationStatus
                datetime.now(),  # RegistrationDate
                datetime.now(),  # LastActionDate
                0.00,  # ProfilePriorityCoefficient
                'active',  # AccountStatus
                None  # Mail (можно оставить пустым или добавить позже)
            ))

            # Сохраняем фотографии в таблицу Photos
            for index, photo_id in enumerate(user_data['photos']):
                query_photo = sql.SQL("""
                    INSERT INTO Photos (
                        UserTelegramID, PhotoFileID, PhotoDisplayOrder
                    ) VALUES (
                        %s, %s, %s
                    )
                """)
                cur.execute(query_photo, (
                    telegram_id,
                    photo_id,
                    index + 1  # Порядок отображения фото
                ))

            conn.commit()
            cur.close()
            conn.close()
            print("Данные пользователя успешно сохранены в базу данных!")
            return True
        except Exception as e:
            print(f"Ошибка при сохранении данных: {e}")
            return False
    else:
        return False

# Функция для начала регистрации
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [["✅ Я согласен", "❌ Я не согласен"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(POLICY_TEXT, reply_markup=reply_markup, parse_mode="Markdown")
    return POLICY

# Функция для обработки согласия с политикой
async def confirm_policy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_response = update.message.text

    if user_response == "✅ Я согласен":
        await update.message.reply_text("🎉 Спасибо за согласие! Давайте начнем регистрацию. Как вас зовут?", reply_markup=None)
        return NAME
    elif user_response == "❌ Я не согласен":
        await update.message.reply_text("🚫 Регистрация отменена. Если передумаете, нажмите /start.", reply_markup=None)
        return ConversationHandler.END
    else:
        await update.message.reply_text("Пожалуйста, используйте кнопки ниже.")
        return POLICY

# Функция для обработки имени
async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['name'] = update.message.text
    await update.message.reply_text(f"👋 Приятно познакомиться, {context.user_data['name']}! Сколько вам лет?")
    return AGE

# Функция для обработки возраста
async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        age = int(update.message.text)
        if age <= 18 or age > 100:
            await update.message.reply_text("Пожалуйста, введите корректный возраст (от 18 до 100).")
            return AGE
        else:
            context.user_data['age'] = age
            keyboard = [["👨 Мужской", "👩 Женский"]]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            await update.message.reply_text("🎂 Отлично! Теперь выберите ваш пол.", reply_markup=reply_markup)
            return GENDER
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите число.")
        return AGE

# Функция для обработки пола
async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_response = update.message.text

    if user_response in ["👨 Мужской", "👩 Женский"]:
        context.user_data['gender'] = user_response
        await update.message.reply_text("📍 Теперь напишите, где вы живете.", reply_markup=None)
        return LOCATION
    else:
        await update.message.reply_text("Пожалуйста, выберите пол, используя кнопки ниже.")
        return GENDER

# Функция для обработки местоположения
async def get_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['location'] = update.message.text
    await update.message.reply_text("📸 Теперь отправьте от 1 до 3 фотографий.")
    return PHOTOS

# Функция для обработки фотографий
async def get_photos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if 'photos' not in context.user_data:
        context.user_data['photos'] = []

    if update.message.photo:
        photo = update.message.photo[-1]
        context.user_data['photos'].append(photo.file_id)

        keyboard = [["📷 Добавить еще фото", "➡️ Продолжить"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

        if len(context.user_data['photos']) >= 3:
            await update.message.reply_text("✅ Вы загрузили максимальное количество фото. Теперь напишите описание вашей анкеты.", reply_markup=None)
            return DESCRIPTION
        else:
            await update.message.reply_text(f"✅ Фото добавлено. Вы можете отправить еще {3 - len(context.user_data['photos'])} фото.", reply_markup=reply_markup)
            return PHOTOS
    else:
        if update.message.text == "➡️ Продолжить":
            if len(context.user_data['photos']) == 0:
                await update.message.reply_text("Пожалуйста, отправьте хотя бы одно фото.")
                return PHOTOS
            else:
                await update.message.reply_text("Теперь напишите описание вашей анкеты.", reply_markup=None)
                return DESCRIPTION
        else:
            await update.message.reply_text("Пожалуйста, отправьте фото или нажмите 'Продолжить'.")
            return PHOTOS

# Функция для обработки описания анкеты
async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['description'] = update.message.text

    # Формируем текст анкеты
    profile_text = (
        f"🎉 *Спасибо за регистрацию!*\n\n"
        f"📝 *Ваша анкета:*\n"
        f"👤 *Имя:* {context.user_data['name']}\n"
        f"📅 *Возраст:* {context.user_data['age']}\n"
        f"🚻 *Пол:* {context.user_data['gender']}\n"
        f"📍 *Местоположение:* {context.user_data['location']}\n"
        f"📄 *Описание:* {context.user_data['description']}\n\n"
        f"Если что-то не так, нажмите /start, чтобы начать заново."
    )

    # Создаем список медиафайлов для отправки
    media_group = []
    for index, photo_id in enumerate(context.user_data['photos']):
        if index == 0:
            # Первое фото будет содержать текст анкеты
            media_group.append(InputMediaPhoto(media=photo_id, caption=profile_text, parse_mode="Markdown"))
        else:
            # Остальные фото без подписи
            media_group.append(InputMediaPhoto(media=photo_id))

    # Отправляем медиагруппу
    if media_group:
        await update.message.reply_media_group(media=media_group)
    else:
        await update.message.reply_text(profile_text, parse_mode="Markdown")

    # Сохраняем данные в базу данных
    telegram_id = update.message.from_user.id  # Получаем Telegram ID пользователя
    if save_user_to_db(context.user_data, telegram_id):
        await update.message.reply_text("✅ Ваши данные успешно сохранены в базе данных!")
    else:
        await update.message.reply_text("❌ Произошла ошибка при сохранении данных. Пожалуйста, попробуйте позже.")

    return ConversationHandler.END

# Функция для отмены регистрации
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("🚫 Регистрация отменена.")
    return ConversationHandler.END

def main() -> None:
    token = '7646103564:AAGvbxZL8MAs52kK3NJVSrY3JPDRyIt2m4s'  # Замените на ваш токен
    application = Application.builder().token(token).build()

    # Определяем ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            POLICY: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_policy)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_gender)],
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_location)],
            PHOTOS: [MessageHandler(filters.PHOTO | filters.TEXT, get_photos)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_description)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == '__main__':
    main()