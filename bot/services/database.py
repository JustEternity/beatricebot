import asyncpg
import logging
from datetime import datetime
from typing import List, Optional, Dict, Union, Tuple
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
    
    async def get_answer_weights(self) -> Dict[int, Dict[int, float]]:
        """Получение весов ответов для расчета совместимости"""
        logger.debug("Fetching answer weights")
        async with self.pool.acquire() as conn:
            try:
                rows = await conn.fetch(
                    "SELECT questionid, answerid, answerweight FROM answers"
                )
                
                weights = {}
                for row in rows:
                    question_id = row['questionid']
                    answer_id = row['answerid']
                    weight = row['answerweight'] if 'answerweight' in row else 0.0
                    
                    if question_id not in weights:
                        weights[question_id] = {}
                    
                    weights[question_id][answer_id] = weight
                
                logger.debug(f"Loaded weights for {len(weights)} questions")
                return weights
            except Exception as e:
                logger.error(f"Error getting answer weights: {e}")
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
    """Получает профиль пользователя для отображения"""
    logger.debug(f"Getting profile for user {user_id}")
    async with self.pool.acquire() as conn:
        try:
            user = await conn.fetchrow(
                "SELECT telegramid, name, age, gender, city as location, profiledescription as description FROM users WHERE telegramid = $1",
                user_id
            )
            
            if not user:
                logger.warning(f"User {user_id} not found")
                return None
            
            return dict(user)
        except Exception as e:
            logger.error(f"Error getting profile for user {user_id}: {e}")
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

async def add_like(self, user_id: int, liked_user_id: int) -> bool:
    """Добавляет лайк от пользователя к другому пользователю"""
    logger.info(f"User {user_id} likes user {liked_user_id}")
    async with self.pool.acquire() as conn:
        try:
            # Проверяем, существует ли уже такой лайк
            existing = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM likes WHERE user_id = $1 AND liked_user_id = $2)",
                user_id, liked_user_id
            )
            
            if existing:
                logger.debug(f"Like from {user_id} to {liked_user_id} already exists")
                return True
            
            # Добавляем новый лайк
            await conn.execute(
                "INSERT INTO likes (user_id, liked_user_id, created_at) VALUES ($1, $2, $3)",
                user_id, liked_user_id, datetime.now()
            )
            
            logger.info(f"Added like from {user_id} to {liked_user_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding like from {user_id} to {liked_user_id}: {e}")
            return False

async def check_mutual_like(self, user1_id: int, user2_id: int) -> bool:
    """Проверяет наличие взаимных лайков между пользователями"""
    logger.debug(f"Checking mutual like between {user1_id} and {user2_id}")
    async with self.pool.acquire() as conn:
        try:
            # Проверяем лайк от user1 к user2
            like1 = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM likes WHERE user_id = $1 AND liked_user_id = $2)",
                user1_id, user2_id
            )
            
            # Проверяем лайк от user2 к user1
            like2 = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM likes WHERE user_id = $1 AND liked_user_id = $2)",
                user2_id, user1_id
            )
            
            # Взаимный лайк, если оба лайка существуют
            is_mutual = like1 and like2
            logger.debug(f"Mutual like between {user1_id} and {user2_id}: {is_mutual}")
            return is_mutual
        except Exception as e:
            logger.error(f"Error checking mutual like between {user1_id} and {user2_id}: {e}")
            return False
