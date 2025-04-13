from typing import List, Tuple, Dict
import logging
from bot.services.encryption import CryptoService
from bot.services import Database

logger = logging.getLogger(__name__)

class CompatibilityService:
    def __init__(self, db: Database):
        self.db = db

    async def get_user_answers(self, user_id: int) -> dict:
        """Получает ответы пользователя на вопросы теста"""
        query = "SELECT questionid, answerid FROM useranswers WHERE usertelegramid = $1"
        records = await self.db.pool.fetch(query, user_id)
        return {r['questionid']: r['answerid'] for r in records}

    async def get_all_users_with_answers(self, exclude_user_id: int) -> list:
        """Получает всех пользователей с ответами, кроме указанного"""
        query = """
            SELECT DISTINCT u.telegramid 
            FROM users u
            JOIN user_answers ua ON u.telegramid = ua.user_id
            WHERE u.telegramid != $1
        """
        return await self.db.pool.fetch(query, exclude_user_id)

    def calculate_compatibility(self, user1_answers: dict, user2_answers: dict) -> float:
        """Вычисляет процент совместимости"""
        if not user1_answers or not user2_answers:
            return 0.0

        total_score = 0
        max_score = len(user1_answers) * 3

        for q_id, a_id in user1_answers.items():
            if q_id in user2_answers:
                if user2_answers[q_id] == a_id:
                    total_score += 3
                elif abs(user2_answers[q_id] - a_id) == 1:
                    total_score += 1

        return (total_score / max_score) * 100 if max_score > 0 else 0

    async def find_compatible_users(
        self,
        user_id: int,
        city: str = None,
        age_min: int = None,
        age_max: int = None,
        gender: str = None,
        occupation: str = None,
        goals: str = None,
        filter_test_question: int = None,
        filter_test_answer: int = None,
        limit: int = 10,
        min_score: float = 50.0,
        crypto=None
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Поиск совместимых пользователей с учетом фильтров
        
        Args:
            user_id: ID пользователя, для которого ищем совместимость
            city: Фильтр по городу
            age_min: Минимальный возраст
            age_max: Максимальный возраст
            gender: Фильтр по полу
            occupation: Фильтр по роду занятий
            goals: Фильтр по целям знакомства
            filter_test_question: ID вопроса для фильтрации по интересам
            filter_test_answer: ID ответа для фильтрации по интересам (1 - первый вариант, 2 - второй вариант и т.д.)
            limit: Максимальное количество результатов
            min_score: Минимальный процент совместимости
            crypto: Сервис шифрования для дешифрования данных
            
        Returns:
            Tuple[List[Dict], List[Dict]]: Два списка пользователей -
            с высокой и низкой совместимостью
        """
        logger.debug(f"Finding compatible users for {user_id}, filters: city={city}, age={age_min}-{age_max}, gender={gender}, occupation={occupation}, goals={goals}, test_question={filter_test_question}, test_answer={filter_test_answer}")
        
        # Преобразуем параметры фильтрации в целые числа, если они не None
        if filter_test_question is not None:
            filter_test_question = int(filter_test_question)
        if filter_test_answer is not None:
            filter_test_answer = int(filter_test_answer)
        
        # Получаем ответы текущего пользователя
        user_answers = await self.get_user_answers(user_id)
        if not user_answers:
            logger.debug("User has no answers")
            return [], []
        
        logger.debug(f"Current user answers: {user_answers}")
        
        # Получаем профиль текущего пользователя для определения пола и предпочтений
        current_user_profile = await self.db.get_user_profile(user_id)
        if not current_user_profile:
            logger.debug("Could not get current user profile")
            return [], []
        
        # Определяем пол текущего пользователя и его предпочтения
        current_user_gender = current_user_profile.get('gender')
        
        # Если город не указан в фильтрах, используем город пользователя
        user_city = None
        if not city and current_user_profile.get('city'):
            encrypted_city = current_user_profile.get('city')
            # Пытаемся дешифровать город пользователя
            if crypto and encrypted_city:
                try:
                    # Проверяем, является ли город зашифрованным
                    if isinstance(encrypted_city, bytes) or (
                            isinstance(encrypted_city, str) and 
                            (encrypted_city.startswith('b\'gAAAAA') or encrypted_city.startswith('gAAAAA'))):
                        user_city = crypto.decrypt(encrypted_city)
                        logger.debug(f"Дешифрованный город пользователя: {user_city}")
                    else:
                        user_city = encrypted_city
                except Exception as e:
                    logger.error(f"Ошибка дешифрования города пользователя: {e}")
            else:
                user_city = encrypted_city
                
            logger.debug(f"Using user's city for filtering: {user_city}")
        else:
            user_city = city
        
        # Строим базовый запрос для получения пользователей
        query = """
            SELECT DISTINCT u.telegramid, u.name, u.age, u.gender, u.city as location,
                u.profiledescription as description
            FROM users u
            WHERE u.telegramid != $1
        """
        params = [user_id]
        param_index = 2
        
        # Добавляем фильтр по полу - показываем только противоположный пол
        if current_user_gender == '0':  # Мужчина ищет женщин
            query += f" AND u.gender = '1'"
        elif current_user_gender == '1':  # Женщина ищет мужчин
            query += f" AND u.gender = '0'"
        
        # Добавляем остальные фильтры (кроме города и интересов)
        if age_min is not None and age_max is not None:
            query += f" AND u.age BETWEEN ${param_index} AND ${param_index + 1}"
            params.extend([age_min, age_max])
            param_index += 2
        
        if gender is not None:
            query += f" AND u.gender = ${param_index}"
            params.append(gender)
            param_index += 1
        
        if occupation is not None:
            query += f" AND u.occupation = ${param_index}"
            params.append(occupation)
            param_index += 1
        
        if goals is not None:
            query += f" AND u.goals = ${param_index}"
            params.append(goals)
            param_index += 1
        
        # Если есть фильтр по интересам, добавляем JOIN с таблицей useranswers
        if filter_test_question is not None and filter_test_answer is not None:
            # Получаем реальный ID ответа из таблицы answers
            # filter_test_answer - это порядковый номер ответа (1, 2, 3...), 
            # а не его ID в таблице answers
            answers_query = """
                SELECT answerid FROM answers 
                WHERE questionid = $1
                ORDER BY answerid
            """
            answers = await self.db.pool.fetch(answers_query, filter_test_question)
            logger.debug(f"Available answers for question {filter_test_question}: {[a['answerid'] for a in answers]}")
            
            if answers and 0 <= filter_test_answer - 1 < len(answers):
                # Преобразуем порядковый номер ответа в его реальный ID
                real_answer_id = answers[filter_test_answer - 1]['answerid']
                logger.debug(f"Converted answer index {filter_test_answer} to real answer ID {real_answer_id}")
            else:
                # Если не можем найти ответ по индексу, используем первый доступный
                if answers:
                    real_answer_id = answers[0]['answerid']
                    logger.debug(f"Using first available answer ID: {real_answer_id}")
                else:
                    logger.debug(f"No answers found for question {filter_test_question}")
                    return [], []
            
            query = """
                SELECT DISTINCT u.telegramid, u.name, u.age, u.gender, u.city as location,
                    u.profiledescription as description
                FROM users u
                JOIN useranswers ua ON u.telegramid = ua.usertelegramid
                WHERE u.telegramid != $1
                AND ua.questionid = $2 AND ua.answerid = $3
            """
            params = [user_id, filter_test_question, real_answer_id]
            param_index = 4
            
            # Добавляем фильтр по полу
            if current_user_gender == '0':  # Мужчина ищет женщин
                query += f" AND u.gender = '1'"
            elif current_user_gender == '1':  # Женщина ищет мужчин
                query += f" AND u.gender = '0'"
            
            # Добавляем остальные фильтры
            if age_min is not None and age_max is not None:
                query += f" AND u.age BETWEEN ${param_index} AND ${param_index + 1}"
                params.extend([age_min, age_max])
                param_index += 2
            
            if gender is not None:
                query += f" AND u.gender = ${param_index}"
                params.append(gender)
                param_index += 1
            
            if occupation is not None:
                query += f" AND u.occupation = ${param_index}"
                params.append(occupation)
                param_index += 1
            
            if goals is not None:
                query += f" AND u.goals = ${param_index}"
                params.append(goals)
                param_index += 1
        
        # Выполняем запрос
        try:
            candidates = await self.db.pool.fetch(query, *params)
            logger.debug(f"Found {len(candidates)} candidates")
            
            if not candidates:
                return [], []
            
            # Выводим ID найденных кандидатов для отладки
            candidate_ids = [c['telegramid'] for c in candidates]
            logger.debug(f"Candidate IDs: {candidate_ids}")
            
            # Фильтруем по городу после получения результатов, если указан город
            filtered_candidates = []
            if user_city and crypto:
                logger.debug(f"Фильтрация по городу: {user_city}")
                for candidate in candidates:
                    encrypted_location = candidate['location']
                    if encrypted_location:
                        try:
                            # Проверяем, является ли город зашифрованным
                            if isinstance(encrypted_location, bytes) or (
                                    isinstance(encrypted_location, str) and 
                                    (encrypted_location.startswith('b\'gAAAAA') or encrypted_location.startswith('gAAAAA'))):
                                decrypted_location = crypto.decrypt(encrypted_location)
                                logger.debug(f"Сравниваем города: {decrypted_location.lower()} == {user_city.lower()}")
                                if decrypted_location.lower() == user_city.lower():
                                    filtered_candidates.append(candidate)
                            else:
                                # Если город не зашифрован, сравниваем напрямую
                                if encrypted_location.lower() == user_city.lower():
                                    filtered_candidates.append(candidate)
                        except Exception as e:
                            logger.error(f"Ошибка дешифрования города кандидата {candidate['telegramid']}: {e}")
                
                candidates = filtered_candidates
                logger.debug(f"После фильтрации по городу осталось {len(candidates)} кандидатов")
            
            if not candidates:
                return [], []
            
            # Вычисляем совместимость для каждого кандидата
            high_compatible = []
            low_compatible = []
            
            for candidate in candidates:
                # Получаем ответы кандидата
                candidate_answers = await self.get_user_answers(candidate['telegramid'])
                if not candidate_answers:
                    logger.debug(f"Candidate {candidate['telegramid']} has no answers, skipping")
                    continue
                
                # Вычисляем совместимость
                compatibility = self.calculate_compatibility(user_answers, candidate_answers)
                logger.debug(f"Compatibility with {candidate['telegramid']}: {compatibility}%")
                
                # Получаем фотографии пользователя
                photos = await self.db.get_user_photos(candidate['telegramid'])
                
                # Создаем полный профиль пользователя
                user_profile = dict(candidate)
                user_profile['photos'] = photos
                
                # Создаем результат с профилем и совместимостью
                result = {
                    'profile': user_profile,
                    'compatibility': round(compatibility, 1)
                }
                
                # Распределяем по категориям совместимости
                if compatibility >= min_score:
                    high_compatible.append(result)
                else:
                    low_compatible.append(result)
            
            # Сортируем по совместимости (от высокой к низкой)
            high_compatible.sort(key=lambda x: x['compatibility'], reverse=True)
            low_compatible.sort(key=lambda x: x['compatibility'], reverse=True)
            
            # Ограничиваем количество результатов
            return high_compatible[:limit], low_compatible[:limit]
        
        except Exception as e:
            logger.error(f"Error finding compatible users: {e}")
            logger.exception(e)
            return [], []

# неактивная функция, идея для доработки бота в будущем
    # async def get_compatibility_explanation(self, user1_id: int, user2_id: int) -> str: 
    #     """
    #     Генерирует объяснение совместимости между пользователями
        
    #     Args:
    #         user1_id: ID первого пользователя
    #         user2_id: ID второго пользователя
            
    #     Returns:
    #         str: Текстовое объяснение совместимости
    #     """
    #     # Получаем ответы обоих пользователей
    #     user1_answers = await self.db.get_user_answers(user1_id)
    #     user2_answers = await self.db.get_user_answers(user2_id)
        
    #     if not user1_answers or not user2_answers:
    #         return "Недостаточно данных для анализа совместимости."
        
    #     # Получаем вопросы
    #     questions = await self.db.get_all_questions()
        
    #     # Находим совпадения и различия
    #     matches = []
    #     differences = []
        
    #     for q_id, question in questions.items():
    #         if q_id in user1_answers and q_id in user2_answers:
    #             if user1_answers[q_id] == user2_answers[q_id]:
    #                 matches.append(question['text'])
    #             else:
    #                 differences.append(question['text'])
        
    #     # Формируем объяснение
    #     explanation = "Анализ совместимости:\n\n"
        
    #     if matches:
    #         explanation += "🟢 Совпадения во взглядах:\n"
    #         for i, match in enumerate(matches[:3], 1):  # Показываем только первые 3 совпадения
    #             explanation += f"{i}. {match}\n"
            
    #         if len(matches) > 3:
    #             explanation += f"...и еще {len(matches) - 3} совпадений\n"
        
    #     if differences:
    #         explanation += "\n🔴 Различия во взглядах:\n"
    #         for i, diff in enumerate(differences[:3], 1):  # Показываем только первые 3 различия
    #             explanation += f"{i}. {diff}\n"
            
    #         if len(differences) > 3:
    #             explanation += f"...и еще {len(differences) - 3} различий\n"
        
    #     return explanation
