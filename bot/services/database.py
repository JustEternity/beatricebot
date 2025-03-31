import asyncpg
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Union, Tuple
from bot.models.user import UserDB
from bot.services.utils import standardize_gender

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

                # Получаем исходное значение пола
                gender_value = user_data['gender']
                logger.debug(f"Original gender value: {gender_value}, type: {type(gender_value)}")

                # Преобразуем к строчным буквам, если это строка
                if isinstance(gender_value, str):
                    gender_value = gender_value.lower()

                # Проверяем различные варианты мужского пола
                if gender_value in [0, '0', 'male', 'м', 'мужской', 'мужчина', '👨 мужской']:
                    standardized_gender = '0'  # Преобразуем в строку
                    logger.debug("Standardized to male ('0')")
                else:
                    standardized_gender = '1'  # Преобразуем в строку
                    logger.debug("Standardized to female ('1')")

                # Сохранение основных данных
                await conn.execute("""
                    INSERT INTO users (
                        telegramid, name, age, gender, city,
                        profiledescription, registrationdate, lastactiondate
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """, telegram_id, user_data['name'], user_data['age'],
                    standardized_gender, user_data['location'],
                    user_data['description'], datetime.now(), datetime.now())

                # Сохранение фотографий
                for index, photo_info in enumerate(user_data['photos']):
                    # Извлекаем file_id из словаря с информацией о фото
                    photo_id = photo_info['file_id'] if isinstance(photo_info, dict) else photo_info
                    logger.debug(f"Processing photo {index + 1}: {photo_info}")
                    logger.debug(f"Extracted file_id: {photo_id}")

                    await conn.execute("""
                        INSERT INTO photos
                        (usertelegramid, photourl, photofileid, photodisplayorder)
                         VALUES ($1, $2, $3, $4)
                     """,
                     telegram_id,
                     photo_info['s3_url'],   # URL фото
                     photo_info['file_id'],  # Telegram file ID
                     index)                  # Порядковый номер фото)

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

                if not user:
                    logger.warning(f"User {telegram_id} not found in database")
                    return None

                return {
                    'name': user['name'],
                    'age': user['age'],
                    'gender': user['gender'],
                    'location': user['city'],
                    'description': user['profiledescription'],
                    'photos': [p['photofileid'] for p in photos] if photos else []
                }
            except Exception as e:
                logger.error(f"Error getting data for user {telegram_id}: {e}")
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

    async def update_user_photos(
        self,
        usertelegramid: str,
        photos: List[dict]  # Принимаем список словарей вместо строк
    ) -> bool:
        """Обновление фотографий пользователя с поддержкой S3"""
        logger.info(f"Updating photos for user {usertelegramid}")

        async with self.pool.acquire() as conn:
            async with conn.transaction():  # Добавляем транзакцию
                try:
                    # Удаляем старые фото
                    delete_result = await conn.execute(
                        "DELETE FROM photos WHERE usertelegramid = $1",
                        usertelegramid
                    )
                    logger.debug(f"Deleted {delete_result.split()[-1]} old photos")

                    # Добавляем новые фото с S3 URL
                    for index, photo_data in enumerate(photos):
                        await conn.execute(
                            """INSERT INTO photos
                            (usertelegramid, photofileid, photourl, photodisplayorder)
                            VALUES ($1, $2, $3, $4)""",
                            usertelegramid,
                            photo_data["file_id"],
                            photo_data["s3_url"],
                            index + 1
                        )

                    logger.info(f"✅ Added {len(photos)} photos with S3 URLs for user {usertelegramid}")
                    return True

                except Exception as e:
                    logger.error(f"❌ Error updating photos for user {usertelegramid}: {str(e)}")
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

        # Проверяем, существует ли пользователь
        user_exists = await self.is_user_registered(telegram_id)
        if not user_exists:
            logger.error(f"Cannot save answers: User {telegram_id} is not registered")
            return False

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

    async def get_user_answers(self, user_id: int) -> Dict[int, int]:
        """Получение ответов пользователя на тест"""
        logger.debug(f"Fetching answers for user {user_id}")
        async with self.pool.acquire() as conn:
            try:
                rows = await conn.fetch(
                    "SELECT questionid, answerid FROM useranswers WHERE usertelegramid = $1",
                    user_id
                )

                answers = {row['questionid']: row['answerid'] for row in rows}
                logger.debug(f"Found {len(answers)} answers for user {user_id}")
                return answers
            except Exception as e:
                logger.error(f"Error getting answers for user {user_id}: {e}")
                return {}

    async def get_answer_weights(self):
        """Получает веса ответов для вопросов (использует веса по умолчанию)"""
        try:
            # Получаем все ID вопросов
            query = "SELECT questionid FROM questions"
            result = await self.execute_query(query)

            # Создаем словарь с весами по умолчанию (1.0) для всех вопросов
            weights = {row[0]: 1.0 for row in result} if result else {}

            logger.debug(f"Using default weights for {len(weights)} questions")
            return weights
        except Exception as e:
            logger.error(f"Error getting question IDs: {e}")
            return {}

    async def get_users_with_answers(self, exclude_user_id: int = None) -> List[int]:
        """Получение списка пользователей, прошедших тест"""
        logger.debug(f"Fetching users with test answers (excluding {exclude_user_id})")
        async with self.pool.acquire() as conn:
            try:
                query = """
                    SELECT DISTINCT usertelegramid
                    FROM useranswers
                """

                params = []
                if exclude_user_id is not None:
                    query += " WHERE usertelegramid != $1"
                    params.append(exclude_user_id)

                rows = await conn.fetch(query, *params)

                user_ids = [row['usertelegramid'] for row in rows]
                logger.debug(f"Found {len(user_ids)} users with answers")
                return user_ids
            except Exception as e:
                logger.error(f"Error getting users with answers: {e}")
                return []

    async def check_user_has_test(self, user_id: int) -> bool:
        """Проверяет, прошел ли пользователь тест совместимости"""
        logger.debug(f"Checking if user {user_id} has completed the test")
        async with self.pool.acquire() as conn:
            try:
                result = await conn.fetchval(
                    "SELECT COUNT(*) FROM useranswers WHERE usertelegramid = $1",
                    user_id
                )
                return result > 0
            except Exception as e:
                logger.error(f"Error checking test completion for user {user_id}: {e}")
                return False

    async def get_compatible_users(self, user_id: int, limit: int = 20) -> List[Tuple[int, float]]:
        """Получает список совместимых пользователей"""
        logger.debug(f"Finding compatible users for user {user_id}")
        try:
            # Получаем ответы текущего пользователя
            user_answers = await self.get_user_answers(user_id)
            if not user_answers:
                logger.warning(f"User {user_id} has no answers")
                return []

            # Получаем пользователей, прошедших тест
            other_users = await self.get_users_with_answers(exclude_user_id=user_id)
            logger.debug(f"Found {len(other_users)} other users with answers")
            if not other_users:
                logger.warning("No other users with answers found")
                return []

            # Получаем веса ответов
            weights = await self.get_answer_weights()

            # Рассчитываем совместимость с каждым пользователем
            compatible_users = []
            for other_id in other_users:
                # Получаем ответы другого пользователя
                other_answers = await self.get_user_answers(other_id)
                if not other_answers:
                    logger.warning(f"User {other_id} has no answers")
                    continue

                # Рассчитываем совместимость
                compatibility = self._calculate_compatibility(user_answers, other_answers, weights)

                # Добавляем пользователя в список, если совместимость выше порога
                if compatibility > 30:  # Минимальный порог совместимости
                    compatible_users.append((other_id, compatibility))

            # Сортируем по совместимости (от высокой к низкой)
            compatible_users.sort(key=lambda x: x[1], reverse=True)

            # Возвращаем ограниченное количество пользователей
            return compatible_users[:limit]

        except Exception as e:
            logger.error(f"Error finding compatible users: {e}")
            logger.exception(e)
            return []

    def _calculate_compatibility(self, user1_answers: Dict[int, int], user2_answers: Dict[int, int], weights: Dict[int, Dict[int, float]]) -> float:
        """Рассчитывает процент совместимости между двумя пользователями"""
        try:
            total_questions = len(set(user1_answers.keys()) & set(user2_answers.keys()))
            if total_questions == 0:
                return 0.0

            compatibility_score = 0.0

            for question_id in set(user1_answers.keys()) & set(user2_answers.keys()):
                answer1 = user1_answers[question_id]
                answer2 = user2_answers[question_id]

                # Если ответы совпадают, добавляем полный вес
                if answer1 == answer2:
                    weight = weights.get(question_id, {}).get(answer1, 1.0)
                    compatibility_score += weight
                else:
                    # Если ответы разные, можно добавить частичную совместимость
                    # в зависимости от близости ответов или других факторов
                    pass

            # Рассчитываем процент совместимости
            compatibility_percent = (compatibility_score / total_questions) * 100
            return compatibility_percent

        except Exception as e:
            logger.error(f"Error calculating compatibility: {e}")
            return 0.0

    async def get_user_profile(self, user_id: int) -> Optional[Dict]:
        """Получает профиль пользователя"""
        try:
            async with self.pool.acquire() as conn:
                query = """
                    SELECT telegramid, name, age, gender, city, profiledescription
                    FROM users
                    WHERE telegramid = $1
                """
                result = await conn.fetchrow(query, user_id)
                if result:
                    return dict(result)
                return None
        except Exception as e:
            logger.error(f"Error getting user profile for {user_id}: {e}")
            return None

    async def get_user_photos(self, user_id: int) -> List[str]:
        """Получает список ID фотографий пользователя"""
        logger.debug(f"Getting photos for user {user_id}")
        async with self.pool.acquire() as conn:
            try:
                rows = await conn.fetch(
                    "SELECT photofileid FROM photos WHERE usertelegramid = $1 ORDER BY photodisplayorder",
                    user_id
                )

                return [row['photofileid'] for row in rows]
            except Exception as e:
                logger.error(f"Error getting photos for user {user_id}: {e}")
                return []

    async def add_like(self, from_user_id: int, to_user_id: int) -> bool:
        """Добавляет лайк от одного пользователя к другому"""
        logger.info(f"User {from_user_id} likes user {to_user_id}")
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO likes (from_user_telegram_id, to_user_telegram_id, created_at)
                    VALUES ($1, $2, NOW())
                    ON CONFLICT (from_user_telegram_id, to_user_telegram_id)
                    DO NOTHING
                    """,
                    from_user_id, to_user_id
                )
                return True
        except Exception as e:
            logger.error(f"Error adding like from {from_user_id} to {to_user_id}: {e}")
            # Проверим структуру таблицы
            try:
                async with self.pool.acquire() as conn:
                    table_info = await conn.fetch(
                        """
                        SELECT column_name, data_type
                        FROM information_schema.columns
                        WHERE table_name = 'likes'
                        """
                    )
                    logger.info(f"Структура таблицы likes: {[dict(row) for row in table_info]}")
            except Exception as table_error:
                logger.error(f"Ошибка при получении структуры таблицы: {table_error}")
            return False

    async def check_mutual_like(self, user1_id: int, user2_id: int) -> bool:
        """Проверяет, есть ли взаимный лайк между пользователями"""
        logger.debug(f"Checking mutual like between {user1_id} and {user2_id}")
        try:
            async with self.pool.acquire() as conn:
                # Проверяем, лайкнул ли user1 пользователя user2
                like1 = await conn.fetchval(
                    """
                    SELECT EXISTS(
                        SELECT 1 FROM likes
                        WHERE from_user_telegram_id = $1 AND to_user_telegram_id = $2
                    )
                    """,
                    user1_id, user2_id
                )

                # Проверяем, лайкнул ли user2 пользователя user1
                like2 = await conn.fetchval(
                    """
                    SELECT EXISTS(
                        SELECT 1 FROM likes
                        WHERE from_user_telegram_id = $1 AND to_user_telegram_id = $2
                    )
                    """,
                    user2_id, user1_id
                )

                # Взаимный лайк есть, если оба пользователя лайкнули друг друга
                return like1 and like2
        except Exception as e:
            logger.error(f"Error checking mutual like between {user1_id} and {user2_id}: {e}")
            return False

    async def check_user_subscription(self, user_id: int) -> bool:
        """Проверяет, есть ли у пользователя активная подписка"""
        logger.debug(f"Checking subscription for user {user_id}")
        try:
            async with self.pool.acquire() as conn:
                # Проверяем наличие активной подписки
                result = await conn.fetchval(
                    """
                    SELECT EXISTS(
                        SELECT 1 FROM purchasedservices
                        WHERE usertelegramid = $1
                        AND serviceid = 1
                        AND serviceenddate > NOW()
                        AND paymentstatus = true
                    )
                    """,
                    user_id
                )

                if result:
                    logger.debug(f"User {user_id} has active subscription")
                    return True
                else:
                    logger.debug(f"User {user_id} has no active subscription")
                    return False
        except Exception as e:
            logger.error(f"Error checking subscription for user {user_id}: {e}")
            return False

    async def activate_subscription(self, user_id: int, days: int = 30) -> bool:
        """Активирует подписку для пользователя на указанное количество дней"""
        logger.info(f"Активация подписки для пользователя {user_id} на {days} дней")

        try:
            async with self.pool.acquire() as conn:
                # Проверяем, есть ли уже активная подписка
                has_active = await self.check_user_subscription(user_id)

                if has_active:
                    logger.info(f"У пользователя {user_id} уже есть активная подписка")
                    return True

                # Создаем новую запись
                payment_id = int(datetime.now().timestamp() * 1000)
                end_date = datetime.now() + timedelta(days=days)

                # Добавляем отладочный вывод
                logger.debug(f"Добавление записи: user_id={user_id}, service_id=1, end_date={end_date}, payment_id={payment_id}")

                try:
                    # Вставляем запись о подписке
                    await conn.execute(
                        """
                        INSERT INTO purchasedservices
                        (usertelegramid, serviceid, serviceenddate, paymentstatus, paymentid)
                        VALUES ($1, $2, $3, $4, $5)
                        """,
                        user_id, 1, end_date, True, payment_id
                    )

                except Exception as e:
                    logger.error(f"Ошибка SQL при активации подписки: {e}")
                return True

        except Exception as e:
            logger.error(f"❌ Ошибка активации подписки: {e}")
            logger.exception(e)
            return False
