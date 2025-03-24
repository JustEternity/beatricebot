import asyncpg
import logging
from datetime import datetime
from typing import List, Optional, Dict, Union
from bot.models.user import UserDB

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, config):
        self.config = config
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Установка пула подключений к базе данных"""
        logger.info("Connecting to database...")
        try:
            self.pool = await asyncpg.create_pool(
                user=self.config.db_user,
                password=self.config.db_pass,
                database=self.config.db_name,
                host=self.config.db_host,
                port=self.config.db_port
            )
            logger.info("✅ Successfully connected to database")
            logger.debug(f"Connection params: "
                        f"host={self.config.db_host}, "
                        f"port={self.config.db_port}, "
                        f"dbname={self.config.db_name}, "
                        f"user={self.config.db_user}")
        except Exception as e:
            logger.critical("❌ Database connection failed")
            logger.exception(e)
            raise

    async def is_user_registered(self, telegram_id: int) -> bool:
        """Проверка регистрации пользователя"""
        logger.debug(f"Checking registration for user {telegram_id}")
        async with self.pool.acquire() as conn:
            try:
                result = await conn.fetchrow(
                    "SELECT telegramid FROM users WHERE telegramid = $1",
                    telegram_id
                )
                logger.debug(f"User {telegram_id} registered: {bool(result)}")
                return result is not None
            except Exception as e:
                logger.error(f"Error checking registration for {telegram_id}")
                logger.exception(e)
                return False

    async def save_user(self, telegram_id: int, user_data: Dict) -> bool:
        """Сохранение нового пользователя"""
        logger.info(f"Saving user {telegram_id}")
        try:
            async with self.pool.acquire() as conn:
                # Логируем базовую информацию о пользователе
                logger.debug(f"User data: { {k: v for k, v in user_data.items() if k != 'photos'} }")
                logger.debug(f"Photos count: {len(user_data['photos'])}")

                # Сохранение основных данных
                await conn.execute("""
                    INSERT INTO users (
                        telegramid, name, age, gender, city,
                        profiledescription, registrationdate, lastactiondate
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """, telegram_id, user_data['name'], user_data['age'],
                    user_data['gender'], user_data['location'],
                    user_data['description'], datetime.now(), datetime.now())

                # Сохранение фотографий
                for index, photo_id in enumerate(user_data['photos']):
                    await conn.execute("""
                        INSERT INTO photos
                        (usertelegramid, photofileid, photodisplayorder)
                        VALUES ($1, $2, $3)
                    """, telegram_id, photo_id, index + 1)

                logger.info(f"✅ User {telegram_id} saved successfully")
                return True
        except Exception as e:
            logger.error(f"❌ Error saving user {telegram_id}")
            logger.exception(e)
            return False

    async def get_user_data(self, telegram_id: int) -> Optional[Dict]:
        """Получение данных пользователя"""
        logger.debug(f"Fetching data for user {telegram_id}")
        async with self.pool.acquire() as conn:
            try:
                user = await conn.fetchrow(
                    "SELECT * FROM users WHERE telegramid = $1",
                    telegram_id
                )
                photos = await conn.fetch(
                    "SELECT photofileid FROM photos WHERE usertelegramid = $1 "
                    "ORDER BY photodisplayorder",
                    telegram_id
                )

                if user:
                    logger.debug(f"Found user {telegram_id} with {len(photos)} photos")
                else:
                    logger.debug(f"User {telegram_id} not found")

                return {
                    'name': user['name'],
                    'age': user['age'],
                    'gender': user['gender'],
                    'location': user['city'],
                    'description': user['profiledescription'],
                    'photos': [p['photofileid'] for p in photos]
                } if user else None
            except Exception as e:
                logger.error(f"Error getting data for user {telegram_id}")
                logger.exception(e)
                return None

    async def update_user_field(self, telegram_id: int, **fields) -> bool:
        """Обновление полей пользователя"""
        logger.info(f"Updating user {telegram_id} fields: {', '.join(fields.keys())}")
        async with self.pool.acquire() as conn:
            try:
                updates = []
                values = [telegram_id, datetime.now()]  # Начинаем с этих двух значений

                for idx, (field, value) in enumerate(fields.items(), start=3):  # Начинаем с $3
                    updates.append(f"{field} = ${idx}")
                    values.append(value)
                    logger.debug(f"Setting {field} = {value}")

                query = f"""
                    UPDATE users
                    SET {', '.join(updates)}, lastactiondate = $2
                    WHERE telegramid = $1
                """

                result = await conn.execute(query, *values)  # Передаем все значения
                logger.info(f"✅ Updated user {telegram_id}. Result: {result}")
                return True
            except Exception as e:
                logger.error(f"❌ Error updating user {telegram_id}")
                logger.exception(e)
                return False

    async def update_user_photos(self, usertelegramid: str, photos: List[str]) -> bool:
        """Обновление фотографий пользователя"""
        logger.info(f"Updating photos for user {usertelegramid}")
        async with self.pool.acquire() as conn:
            try:
                # Удаляем старые фото
                delete_result = await conn.execute(
                    "DELETE FROM photos WHERE usertelegramid = $1",
                    usertelegramid
                )
                logger.debug(f"Deleted {delete_result.split()[-1]} old photos")

                # Добавляем новые
                for index, photofileid in enumerate(photos):
                    await conn.execute(
                        "INSERT INTO photos (usertelegramid, photofileid, photodisplayorder) VALUES ($1, $2, $3)",
                        usertelegramid, photofileid, index + 1
                    )
                logger.info(f"✅ Added {len(photos)} new photos for user {usertelegramid}")
                return True
            except Exception as e:
                logger.error(f"❌ Error updating photos for user {usertelegramid}")
                logger.exception(e)
                return False

    async def get_questions_and_answers(self) -> tuple[Dict, Dict]:
        """Получение вопросов и ответов для теста"""
        logger.info("Fetching questions and answers")
        async with self.pool.acquire() as conn:
            try:
                questions = await conn.fetch(
                    "SELECT questionid, questiontext FROM questions"
                )
                answers = await conn.fetch(
                    "SELECT answerid, questionid, answertext FROM answers"
                )

                logger.debug(f"Loaded {len(questions)} questions and {len(answers)} answers")

                # Словарь вопросов
                questions_dict = {
                    q['questionid']: q['questiontext'] for q in questions
                }

                # Словарь ответов с правильной группировкой
                answers_dict = {}
                for a in answers:
                    question_id = a['questionid']
                    answer_id = a['answerid']
                    answer_text = a['answertext']

                    if question_id not in answers_dict:
                        answers_dict[question_id] = {}

                    answers_dict[question_id][answer_id] = answer_text

                return questions_dict, answers_dict

            except Exception as e:
                logger.error("❌ Error loading questions and answers")
                logger.exception(e)
                return {}, {}

    async def save_user_answers(self, telegram_id: int, answers: Dict[int, int]) -> bool:
        """Сохранение результатов теста"""
        logger.info(f"Saving test answers for user {telegram_id}")
        async with self.pool.acquire() as conn:
            try:
                # Удаляем предыдущие ответы
                await conn.execute(
                    "DELETE FROM useranswers WHERE usertelegramid = $1",
                    telegram_id
                )
                logger.debug(f"Deleted previous answers for {telegram_id}")

                # Сохраняем новые
                for question_id, answer_id in answers.items():
                    await conn.execute("""
                        INSERT INTO useranswers
                        (usertelegramid, questionid, answerid)
                        VALUES ($1, $2, $3)
                    """, telegram_id, question_id, answer_id)

                logger.info(f"✅ Saved {len(answers)} answers for user {telegram_id}")
                return True
            except Exception as e:
                logger.error(f"❌ Error saving answers for user {telegram_id}")
                logger.exception(e)
                return False

    async def check_existing_answers(self, user_id: int) -> bool:
        logger.debug(f"Checking existing answers for user {user_id}")
        async with self.pool.acquire() as conn:
            try:
                result = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM useranswers WHERE usertelegramid = $1)",
                    user_id
                )
                logger.debug(f"User {user_id} has answers: {result}")
                return result
            except Exception as e:
                logger.error(f"Error checking answers for user {user_id}")
                logger.exception(e)
                return False

    async def get_user(self, telegram_id: int) -> Optional[UserDB]:
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM users WHERE telegramid = $1",
                telegram_id
            )

    async def update_profile_field(self, user_id: int, field: str, value: Union[str, int, bytes]) -> bool:
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        f"UPDATE users SET {field} = $1 WHERE telegramid = $2",
                        value, user_id
                    )
                    return True
            except Exception as e:
                logger.error(f"Ошибка обновления поля: {e}")
                return False

    async def del_user_answers(self, telegram_id: int) -> bool:
        async with self.pool.acquire() as conn:
            try:
                await conn.execute(
                    "DELETE FROM useranswers WHERE usertelegramid = $1",
                    telegram_id
                )
                return True
            except Exception as e:
                logger.error(f"Error deleting user answers: {e}")
                logger.exception(e)
                return False

