from decimal import Decimal

import json
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

                # Сохранение политики согласия с ПК
                await conn.execute("""
                    INSERT INTO consenttopdp (usertelegramid, policyversionid, consentstatus)
                    VALUES ($1, $2, $3)
                """, telegram_id, user_data['idpolicy'], user_data['policy'])

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

    async def save_policy_acception(self, telegram_id: int, user_data: Dict):
        """Сохранение согласия с ПК (при обновлении)"""
        logger.info(f"Updating user {telegram_id} policy acception")
        async with self.pool.acquire() as conn:
            try:
                await conn.execute("""
                            INSERT INTO consenttopdp (usertelegramid, policyversionid, consentstatus)
                            VALUES ($1, $2, $3)
                        """, telegram_id, user_data['idpolicy'], user_data['policy'])
                return True
            except Exception as e:
                logger.error(f"❌ Error saving user {telegram_id} policy acception")
                logger.exception(e)
                return False

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

    async def get_user_photos(self, user_id):
        """Получает фотографии пользователя"""
        try:
            async with self.pool.acquire() as conn:
                query = """
                SELECT photofileid, photourl
                FROM photos
                WHERE usertelegramid = $1
                ORDER BY photodisplayorder
                """
                rows = await conn.fetch(query, user_id)

                # Логируем для отладки
                photos = [row['photofileid'] for row in rows] if rows else []
                logger.debug(f"Получено {len(photos)} фотографий для пользователя {user_id}")
                for i, photo in enumerate(photos):
                    logger.debug(f"Фото {i+1}: {photo[:30]}...")

                return photos
        except Exception as e:
            logger.error(f"Ошибка при получении фотографий пользователя {user_id}: {e}")
            return []

    async def add_like(self, user_id: int, liked_user_id: int, bot=None) -> int:
        """Добавляет лайк от пользователя к другому пользователю"""
        try:
            # Проверяем, существует ли уже такой лайк
            like_exists = await self.check_like_exists(user_id, liked_user_id)
            if like_exists:
                logger.info(f"Лайк от {user_id} к {liked_user_id} уже существует")
                return 0

            async with self.pool.acquire() as conn:
                # Добавляем запись о лайке в базу данных
                like_id = await conn.fetchval("""
                    INSERT INTO likes (sendertelegramid, receivertelegramid, likeviewedstatus)
                    VALUES ($1, $2, FALSE)
                    RETURNING likeid
                """, user_id, liked_user_id)
                logger.info(f"Добавлен лайк от {user_id} к {liked_user_id}, ID: {like_id}")

                # Проверяем на взаимный лайк
                is_mutual = await self.check_mutual_like(user_id, liked_user_id)
                logger.info(f"Взаимный лайк между {user_id} и {liked_user_id}: {is_mutual}")

                # Если это взаимный лайк, помечаем оба лайка как просмотренные
                if is_mutual:
                    # Помечаем оба лайка как просмотренные
                    await conn.execute("""
                        UPDATE likes
                        SET likeviewedstatus = TRUE
                        WHERE (sendertelegramid = $1 AND receivertelegramid = $2)
                        OR (sendertelegramid = $2 AND receivertelegramid = $1)
                    """, user_id, liked_user_id)
                    logger.info(f"Оба лайка между {user_id} и {liked_user_id} помечены как просмотренные")

                # Если передан объект бота, отправляем уведомление
                if bot:
                    logger.info(f"Отправляем уведомление о лайке от {user_id} к {liked_user_id}")
                    # Импортируем функцию здесь, чтобы избежать циклических импортов
                    from bot.services.notifications import send_like_notification
                    await send_like_notification(bot, user_id, liked_user_id, self)
                else:
                    logger.warning(f"Объект бота не передан при добавлении лайка от {user_id} к {liked_user_id}")

                return like_id
        except Exception as e:
            logger.error(f"Ошибка при добавлении лайка: {e}", exc_info=True)
            return 0

    async def check_mutual_like(self, user_id: int, liked_user_id: int) -> bool:
        """Проверяет, есть ли взаимный лайк между двумя пользователями"""
        try:
            logger.debug(f"Проверка взаимных лайков между {user_id} и {liked_user_id}")
            async with self.pool.acquire() as conn:
                # Проверяем наличие взаимных лайков, где хотя бы один из лайков не просмотрен
                result = await conn.fetchval("""
                    SELECT EXISTS(
                        SELECT 1 FROM likes l1
                        JOIN likes l2 ON l1.sendertelegramid = l2.receivertelegramid
                                    AND l1.receivertelegramid = l2.sendertelegramid
                        WHERE (l1.sendertelegramid = $1 AND l1.receivertelegramid = $2)
                        AND (l1.likeviewedstatus = FALSE OR l2.likeviewedstatus = FALSE)
                    )
                """, user_id, liked_user_id)
                return bool(result)
        except Exception as e:
            logger.error(f"Ошибка при проверке взаимного лайка: {e}")
            return False

    async def get_mutual_likes(self, user_id):
        """Получает список пользователей, с которыми есть взаимные лайки"""
        try:
            async with self.pool.acquire() as conn:
                query = """
                SELECT u.* FROM users u
                WHERE u.telegramid IN (
                    SELECT l1.sendertelegramid FROM likes l1
                    JOIN likes l2 ON l1.sendertelegramid = l2.receivertelegramid
                                AND l1.receivertelegramid = l2.sendertelegramid
                    WHERE l1.receivertelegramid = $1
                )
                """
                rows = await conn.fetch(query, user_id)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка при получении взаимных лайков: {str(e)}")
            return []

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

    async def save_feedback(self, user_id: int, text: str) -> bool:
        try:
            async with self.pool.acquire() as conn:
                res = await conn.execute(
                    "INSERT INTO feedback (sendertelegramid, messagetext) "
                    "VALUES ($1, $2)",
                    user_id,
                    text
                )

                if res == "INSERT 0 1":
                    return True

                logger.error(f"Unexpected insert result: {res}")
                return False
        except Exception as e:
            logger.error(f"Feedback save error: {str(e)}")
            return False

    async def get_user_likes(self, user_id, only_unviewed=False):
        try:
            async with self.pool.acquire() as conn:
                if only_unviewed:
                    query = """
                        SELECT likeid, sendertelegramid as from_user_id, receivertelegramid as to_user_id,
                            likeviewedstatus
                        FROM likes
                        WHERE receivertelegramid = $1 AND likeviewedstatus = FALSE
                        ORDER BY likeid DESC
                    """
                else:
                    query = """
                        SELECT likeid, sendertelegramid as from_user_id, receivertelegramid as to_user_id,
                            likeviewedstatus
                        FROM likes
                        WHERE receivertelegramid = $1
                        ORDER BY likeid DESC
                    """

                likes = await conn.fetch(query, user_id)
                return [dict(like) for like in likes]
        except Exception as e:
            logging.error(f"Ошибка при получении лайков пользователя {user_id}: {e}")
            return []

    async def get_user_likes_count(self, user_id):
        """Получает количество лайков пользователя"""
        try:
            async with self.pool.acquire() as conn:
                query = """
                SELECT COUNT(*) as count
                FROM likes
                WHERE receivertelegramid = $1
                """
                result = await conn.fetchval(query, user_id)

            return result or 0
        except Exception as e:
            logger.error(f"Ошибка при получении количества лайков пользователя {user_id}: {e}")
            return 0

    async def get_unviewed_likes_count(self, user_id):
        """Получает количество непросмотренных лайков пользователя"""
        try:
            async with self.pool.acquire() as conn:
                query = """
                SELECT COUNT(*) as count
                FROM likes
                WHERE receivertelegramid = $1
                AND likeviewedstatus = false
                """
                result = await conn.fetchval(query, user_id)

                return result or 0
        except Exception as e:
            logger.error(f"Ошибка при получении количества непросмотренных лайков пользователя {user_id}: {e}")
            return 0

    async def mark_likes_as_viewed(self, sender_id: int, receiver_id: int = None, only_unviewed: bool = True) -> bool:
        """
        Отмечает лайки как просмотренные.

        Args:
            sender_id: ID отправителя лайка или получателя (зависит от наличия receiver_id)
            receiver_id: ID получателя лайка (если None, то sender_id считается получателем)
            only_unviewed: Обновлять только непросмотренные лайки

        Returns:
            bool: True в случае успеха, False в случае ошибки
        """
        try:
            async with self.pool.acquire() as conn:
                if receiver_id is None:
                    # Отмечаем все лайки, полученные пользователем
                    query = """
                        UPDATE likes
                        SET likeviewedstatus = TRUE
                        WHERE receivertelegramid = $1
                    """
                    if only_unviewed:
                        query += " AND likeviewedstatus = FALSE"

                    await conn.execute(query, sender_id)
                    logger.info(f"Все лайки пользователя {sender_id} отмечены как просмотренные")
                else:
                    # Отмечаем только лайки от sender_id к receiver_id
                    query = """
                        UPDATE likes
                        SET likeviewedstatus = TRUE
                        WHERE sendertelegramid = $1 AND receivertelegramid = $2
                    """
                    if only_unviewed:
                        query += " AND likeviewedstatus = FALSE"

                    await conn.execute(query, sender_id, receiver_id)
                    logger.info(f"Лайки от {sender_id} к {receiver_id} отмечены как просмотренные")

                return True
        except Exception as e:
            logger.error(f"Ошибка при обновлении статуса просмотра лайков: {e}")
            return False

    async def check_like_exists(self, user_id: int, liked_user_id: int) -> bool:
        """Проверяет, существует ли уже лайк от пользователя к другому пользователю"""
        try:
            async with self.pool.acquire() as conn:
                # Проверяем существование лайка в базе данных
                result = await conn.fetchval("""
                    SELECT EXISTS(
                        SELECT 1 FROM likes
                        WHERE sendertelegramid = $1 AND receivertelegramid = $2
                    )
                """, user_id, liked_user_id)

                # Логируем результат для отладки
                logger.debug(f"Проверка лайка от {user_id} к {liked_user_id}: {bool(result)}")

                return bool(result)
        except Exception as e:
            logger.error(f"Ошибка при проверке существования лайка: {e}")
            return False

    async def check_match_exists(self, user1_id: int, user2_id: int) -> bool:
        """Проверяет, существует ли уже запись о взаимной симпатии между пользователями"""
        try:
            async with self.pool.acquire() as conn:
                # Проверяем в обоих направлениях
                result = await conn.fetchval("""
                    SELECT EXISTS(
                        SELECT 1 FROM matches
                        WHERE (usertelegramid = $1 AND matchedusertelegramid = $2)
                        OR (usertelegramid = $2 AND matchedusertelegramid = $1)
                    )
                """, user1_id, user2_id)

                return bool(result)
        except Exception as e:
            logger.error(f"Ошибка при проверке существования записи о взаимной симпатии: {e}")
            return False

    async def debug_likes_table(self, user_id: int = None, liked_user_id: int = None):
        """Отладочный метод для проверки таблицы лайков"""
        try:
            async with self.pool.acquire() as conn:
                if user_id and liked_user_id:
                    # Проверяем конкретную пару пользователей
                    query = """
                        SELECT * FROM likes
                        WHERE (sendertelegramid = $1 AND receivertelegramid = $2)
                        OR (sendertelegramid = $2 AND receivertelegramid = $1)
                    """
                    rows = await conn.fetch(query, user_id, liked_user_id)
                elif user_id:
                    # Проверяем все лайки, связанные с конкретным пользователем
                    query = """
                        SELECT * FROM likes
                        WHERE sendertelegramid = $1 OR receivertelegramid = $1
                    """
                    rows = await conn.fetch(query, user_id)
                else:
                    # Получаем все лайки
                    query = "SELECT * FROM likes LIMIT 100"
                    rows = await conn.fetch(query)

                # Выводим результаты
                logger.info(f"Результаты запроса к таблице лайков ({len(rows)} записей):")
                for row in rows:
                    logger.info(f"Лайк: от {row['sendertelegramid']} к {row['receivertelegramid']}, ID: {row['likeid']}")

                return rows
        except Exception as e:
            logger.error(f"Ошибка при отладке таблицы лайков: {e}")
            return []

    async def get_all_services(self):
        """Получает список всех доступных услуг"""
        logger.debug("Fetching all services")
        try:
            async with self.pool.acquire() as conn:
                query = """
                    SELECT
                        serviceid,
                        cost,
                        serviceduration,
                        description,
                        priorityboostvalue,
                        availabilitystatus
                    FROM servicetypes
                    ORDER BY cost ASC
                """
                rows = await conn.fetch(query)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching services: {e}")
            return []

    async def get_service_by_id(self, service_id: int):
        """Получает информацию об услуге по ID"""
        logger.debug(f"Fetching service with ID {service_id}")
        try:
            async with self.pool.acquire() as conn:
                query = """
                    SELECT
                        serviceid,
                        cost,
                        serviceduration,
                        description,
                        priorityboostvalue,
                        availabilitystatus
                    FROM servicetypes
                    WHERE serviceid = $1
                """
                row = await conn.fetchrow(query, service_id)
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error fetching service {service_id}: {e}")
            return None

    async def get_user_services(self, user_id: int) -> List[Dict]:
        """Получает список активных услуг пользователя"""
        logger.debug(f"Fetching active services for user {user_id}")
        try:
            async with self.pool.acquire() as conn:
                query = """
                    SELECT
                        ps.recordid,
                        ps.serviceid,
                        ps.serviceenddate,
                        ps.paymentstatus,
                        st.description,
                        st.cost,
                        st.priorityboostvalue
                    FROM purchasedservices ps
                    JOIN servicetypes st ON ps.serviceid = st.serviceid
                    WHERE
                        ps.usertelegramid = $1 AND
                        ps.serviceenddate > NOW() AND
                        ps.paymentstatus = TRUE
                    ORDER BY ps.serviceenddate DESC
                """
                rows = await conn.fetch(query, user_id)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching active services for user {user_id}: {e}")
            return []

    async def get_active_services(self, user_id: int) -> List[Dict]:
        """Обертка для обратной совместимости"""
        logger.warning("Method get_active_services is deprecated, use get_user_services instead")
        return await self.get_user_services(user_id)

    async def calculate_priority_coefficient(self, user_id: int) -> float:
        """Рассчитывает общий коэффициент приоритета пользователя"""
        from decimal import Decimal

        base_coefficient = Decimal('1.0')
        try:
            async with self.pool.acquire() as conn:
                # Получаем активные услуги пользователя
                query = """
                    SELECT st.priorityboostvalue
                    FROM purchasedservices ps
                    JOIN servicetypes st ON ps.serviceid = st.serviceid
                    WHERE ps.usertelegramid = $1
                    AND ps.serviceenddate > NOW()
                    AND ps.paymentstatus = TRUE
                """
                rows = await conn.fetch(query, user_id)

                # Суммируем бонусы от всех активных услуг
                total_boost = sum(
                    Decimal(str(row['priorityboostvalue'])) / Decimal('100.0')
                    for row in rows
                )

                # Проверяем наличие активной подписки
                has_subscription = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM purchasedservices "
                    "WHERE usertelegramid = $1 AND serviceid = 1 "
                    "AND serviceenddate > NOW() AND paymentstatus = TRUE)",
                    user_id
                )

                # Добавляем бонус за подписку
                if has_subscription:
                    total_boost += Decimal('0.5')

                final_coefficient = base_coefficient + total_boost
                final_coefficient = min(final_coefficient, Decimal('999.99'))  # Ограничение максимума
                return float(final_coefficient.quantize(Decimal('0.01')))

        except Exception as e:
            logger.error(f"Error calculating priority for user {user_id}: {e}")
            return 1.0

    async def update_user_priority(self, user_id: int) -> bool:
        """Обновляет коэффициент приоритета пользователя в БД"""
        try:
            new_coefficient = await self.calculate_priority_coefficient(user_id)
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE users SET profileprioritycoefficient = $1 WHERE telegramid = $2",
                    new_coefficient, user_id
                )
            return True
        except Exception as e:
            logger.error(f"Error updating priority for user {user_id}: {e}")
            return False

    async def activate_service(self, user_id: int, service_id: int) -> bool:
        """Активирует услугу для пользователя, если она еще не активна"""
        try:
            async with self.pool.acquire() as conn:
                # Проверяем, есть ли уже активная такая же услуга
                existing_service = await conn.fetchval(
                    """
                    SELECT EXISTS(
                        SELECT 1 FROM purchasedservices
                        WHERE usertelegramid = $1
                        AND serviceid = $2
                        AND serviceenddate > NOW()
                        AND paymentstatus = TRUE
                    )
                    """,
                    user_id, service_id
                )

                if existing_service:
                    logger.info(f"User {user_id} tried to buy service {service_id} which is already active")
                    return False

                # Добавляем запись о покупке услуги
                await conn.execute(
                    """
                    INSERT INTO purchasedservices 
                    (usertelegramid, serviceid, serviceenddate, paymentstatus, paymentid)
                    VALUES ($1, $2, 
                        NOW() + (SELECT serviceduration FROM servicetypes WHERE serviceid = $2), 
                        TRUE, $3)
                    """,
                    user_id, service_id, user_id
                )

                # Если это подписка (service_id=1), обновляем статус подписки
                if service_id == 1:
                    await conn.execute(
                        "UPDATE users SET subscriptionstatus = TRUE WHERE telegramid = $1",
                        user_id
                    )

                # Обновляем коэффициент приоритета
                await self.update_user_priority(user_id)

                logger.info(f"Successfully activated service {service_id} for user {user_id}")
                return True

        except Exception as e:
            logger.error(f"Error activating service {service_id} for user {user_id}: {e}")
            return False

    async def update_subscription_status(self, user_id: int) -> bool:
        """Обновляет статус подписки пользователя"""
        try:
            async with self.pool.acquire() as conn:
                has_subscription = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM purchasedservices "
                    "WHERE usertelegramid = $1 AND serviceid = 1 "
                    "AND serviceenddate > NOW() AND paymentstatus = TRUE)",
                    user_id
                )

                await conn.execute(
                    "UPDATE users SET subscriptionstatus = $1 WHERE telegramid = $2",
                    has_subscription, user_id
                )
            return True
        except Exception as e:
            logger.error(f"Error updating subscription status for user {user_id}: {e}")
            return False

    async def fix_priority_coefficient(self, user_id: int) -> bool:
        """Исправляет коэффициент приоритета (альтернативный метод)"""
        return await self.update_user_priority(user_id)

    async def update_all_users_priority(self):
        """Обновляет коэффициенты приоритета для всех пользователей"""
        logger.info("Updating priority coefficients for all users")
        try:
            async with self.pool.acquire() as conn:
                # Получаем всех пользователей
                users = await conn.fetch("SELECT telegramid FROM users")

                updated_count = 0
                for user in users:
                    user_id = user['telegramid']
                    success = await self.fix_priority_coefficient(user_id)
                    if success:
                        updated_count += 1

                logger.info(f"Updated priority coefficients for {updated_count}/{len(users)} users")
                return updated_count
        except Exception as e:
            logger.error(f"Error updating all users priority: {e}")
            logger.exception(e)
            return 0

    async def check_actual_policy(self, user_id: int, policyid: int):
        """Проверяет принял ли пользователь актуальную политику конфиденциальности"""
        logger.info("Проверка согласия на обработку персональных данных")
        try:
            async with self.pool.acquire() as conn:
                res = await conn.fetchval("""SELECT EXISTS (SELECT 1
                FROM consenttopdp
                WHERE usertelegramid = $1 AND policyversionid = $2 AND consentstatus = true)""", user_id, policyid)
                logger.info(f'Пользователь {user_id} согласен с актуальной ПК {res}')
                return bool(res)
        except Exception as e:
            logger.error(f"Ошибка при проверке согласия на ОПД пользователя {user_id}: {e}")
            logger.exception(e)
            return False

    async def get_actual_policy_id(self):
        """ Возвращает самую актуальную версию ПК"""
        logger.info('Поиск актуальной версии ПК')
        try:
            async with self.pool.acquire() as conn:
                vers, text = await conn.fetchrow("""SELECT policyversionid, consenttext
                    FROM privacypolicy
                    ORDER BY effectivedate DESC, policyversionid DESC
                    LIMIT 1;""")
                logger.info(f'Актуальная ПК {vers}')
                return int(vers), text
        except Exception as e:
            logger.error(f"Ошибка при проверке актуальной версии ПК: {e}")
            logger.exception(e)
            return False

    async def get_admin_pass(self, user_id):
        """ Возвращает пароль для активации режима админа"""
        logger.info('Получение пароля админа')
        try:
            async with self.pool.acquire() as conn:
                password = await conn.fetchval("""SELECT password
                    FROM administrators
                    WHERE telegramid = $1;""", user_id)
                return password
        except Exception as e:
            logger.error(f"Ошибка при получении пароля админа для пользователя {user_id}: {e}")
            logger.exception(e)
            return False

    async def get_reports(self):
        """ Возвращает все доступные отчеты"""
        logger.info('Запрос доступных отчетов')
        try:
            async with self.pool.acquire() as conn:
                reports = await conn.fetch("""
                    SELECT reporttypeid, reportsqlquery
                    FROM reports
                    ORDER BY reporttypeid;
                """)
                return {record['reporttypeid']: record['reportsqlquery'] for record in reports}
        except Exception as e:
            logger.error(f"Ошибка при получении доступных отчетов {e}")
            logger.exception(e)
            return None

    async def exec_report(self, admin_id: int, report_id: int,  query: str, *args) -> dict:
        """
        Выполняет SQL-запрос и возвращает результат в формате словаря
        :param query: SQL-запрос
        :param args: Параметры для запроса (опционально)
        :return: Словарь с результатами или ошибкой
        """
        result = []
        try:
            async with self.pool.acquire() as conn:
                records = await conn.fetch(query, *args)
                result = [dict(record) for record in records]

                json_data = json.dumps(result, ensure_ascii=False)

                q = "INSERT INTO statistics (admintelegramid, reporttypeid, reportdata) VALUES ($1, $2, $3)"
                await conn.execute(q, admin_id, report_id, json_data)

        except Exception as e:
            result.append({"error": str(e)})
            logger.error(f"Query execution failed: {e}\nQuery: {query}")

        return result

    async def get_feedback(self):
        """Возвращает словарь {feedbackid: messageid} для необработанных обращений"""
        logger.info('Запрос необработанных обращений')
        try:
            async with self.pool.acquire() as conn:
                records = await conn.fetch("""
                    SELECT feedbackid, messagetext
                    FROM feedback
                    WHERE processingstatus = false
                    ORDER BY feedbackid;
                """)

                return {record['feedbackid']: record['messagetext'] for record in records}

        except Exception as e:
            logger.error(f"Ошибка при получении обращений: {e}")
            logger.exception(e)
            return None

    async def update_feedback_status(self, feedback_id, category, status, admin_id):
        """Обновляет статус и категорию обращения"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE feedback
                    SET
                        category = $1,
                        processingstatus = $2,
                        admintelegramid = $3
                    WHERE feedbackid = $4
                    """,
                    category, status, admin_id, feedback_id
                )
                logger.info(f"Обновлен статус обращения ID {feedback_id}")
        except Exception as e:
            logger.error(f"Ошибка обновления статуса обращения: {e}")
            logger.exception(e)

    async def get_complaints(self):
        """Возвращает словарь необработанных жалоб"""
        logger.info('Запрос необработанных жалоб')
        try:
            async with self.pool.acquire() as conn:
                records = await conn.fetch("""
                    SELECT complaintid, reportedusertelegramid, complaintreason
                    FROM complaints
                    WHERE processingstatus = false
                    ORDER BY complaintid;
                """)

                return {
                record['complaintid']: (
                    record['reportedusertelegramid'],
                    record['complaintreason']
                )
                for record in records
            }

        except Exception as e:
            logger.error(f"Ошибка при получении жалоб: {e}")
            logger.exception(e)
            return None

    async def update_complaint_status(self, complaint_id, category, status, admin_id):
        """Обновляет статус и категорию жалобы"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE complaints
                    SET
                        category = $1,
                        processingstatus = $2,
                        admintelegramid = $3
                    WHERE complaintid = $4
                    """,
                    category, status, admin_id, complaint_id
                )
                logger.info(f"Обновлен статус жалобы ID {complaint_id}")
        except Exception as e:
            logger.error(f"Ошибка обновления статуса жалобы: {e}")
            logger.exception(e)

    async def get_verifications(self):
        """Возвращает словарь необработанных верификаций"""
        logger.info('Запрос необработанных верификаций')
        try:
            async with self.pool.acquire() as conn:
                records = await conn.fetch("""
                    SELECT verificationid, verificationvideofileid, usertelegramid
                    FROM verifications
                    WHERE processingstatus = 'open'
                    ORDER BY verificationid;
                """)

                return {
                record['verificationid']: (record['verificationvideofileid'], record['usertelegramid']) for record in records
            }

        except Exception as e:
            logger.error(f"Ошибка при получении необработанных верификаций: {e}")
            logger.exception(e)
            return None

    async def update_verification(
        self,
        admin_id: int,
        verification_id: int,
        status: str,  # 'approved' или 'rejected'
        rejection_reason: str = None
    ):
        """Обновляет статус верификации и причину отказа"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    UPDATE verifications
                    SET processingstatus = $1,
                        rejectionreason = $2,
                        verificationdate = NOW(),
                        admintelegramid = $4
                    WHERE verificationid = $3
                """, status, rejection_reason, verification_id, admin_id)
        except Exception as e:
            logger.error(f"Ошибка обновления верификации: {e}")

    async def get_moderations(self):
        """Возвращает словарь необработанных модераций"""
        logger.info('Запрос необработанных модераций')
        try:
            async with self.pool.acquire() as conn:
                records = await conn.fetch("""
                    SELECT moderationid, usertelegramid
                    FROM moderations
                    WHERE processingstatus = 'open'
                    ORDER BY moderationid;
                """)

                return {
                record['moderationid']: record['usertelegramid'] for record in records
            }

        except Exception as e:
            logger.error(f"Ошибка при получении необработанных верификаций: {e}")
            logger.exception(e)
            return None

    async def update_moderation_status(
        self,
        moderationid: int,
        status: str,  # 'approved' или 'blocked'
        admin_id: int,
        rejection_reason: str = None
    ):
        """Обновляет статус модерации"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE moderations
                SET admintelegramid = $1,
                    processingstatus = $2,
                    rejectionreason = $3,
                    moderationdate = CURRENT_TIMESTAMP
                WHERE moderationid = $4
            """, admin_id, status, rejection_reason, moderationid)

    async def save_verification_video(self, user_id: int, video_file_id: str):
        """Сохраняет в БД file_id видео для верификации пользователя"""
        logger.info(f'Сохранение в БД file_id видео для верификации пользователя {user_id}')
        try:
            async with self.pool.acquire() as conn:
                query = "INSERT INTO verifications (usertelegramid, verificationvideofileid) VALUES ($1, $2)"
                return await conn.execute(query, user_id, video_file_id)
        except Exception as e:
            logger.error(f"Ошибка при сохранении видео для верификации пользователя {user_id}: {e}")
            logger.exception(e)
            return None

    async def check_verify(self, user_id: int):
        """Проверяет, проходил ли пользователь верификацию"""
        logger.info(f'Проверка активной верификации для пользователя {user_id}')
        try:
            async with self.pool.acquire() as conn:
                query = """
                    SELECT EXISTS(
                        SELECT 1
                        FROM verifications
                        WHERE
                            usertelegramid = $1
                            AND processingstatus != 'rejected'
                            AND processingstatus IS NOT NULL
                    )
                """
                result = await conn.fetchval(query, user_id)
                return bool(result)

        except Exception as e:
            logger.error(f"Ошибка при проверке верификации пользователя {user_id}: {e}")
            logger.exception(e)
            return False

    async def del_user(self, user_id: int):
        """Удаляет всю информацию о пользователе"""
        logger.info(f'Удаление данных о пользователе {user_id}')
        try:
            async with self.pool.acquire() as conn:
                query = """
                    DELETE FROM users WHERE telegramid=$1;
                """
                result = await conn.execute(query, user_id)
                return bool(result)

        except Exception as e:
            logger.error(f"Ошибка при удалении пользователя {user_id}: {e}")
            logger.exception(e)
            return False

    async def is_user_blocked(self, user_id: int) -> bool:
        """Проверяет, заблокирован ли пользователь"""
        async with self.pool.acquire() as conn:
            query = "SELECT EXISTS(SELECT 1 FROM users WHERE telegramid = $1 and accountstatus='blocked')"
            return await conn.fetchval(query, user_id)
