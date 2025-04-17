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
        limit: int = None,
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
            limit: Максимальное количество результатов (None - без ограничений)
            min_score: Минимальный процент совместимости
            crypto: Сервис шифрования для дешифрования данных
            
        Returns:
            Tuple[List[Dict], List[Dict]]: Два списка пользователей -
            с высокой и низкой совместимостью
        """
        logger.info(f"Поиск пользователей для {user_id} с фильтрами: {{'city': {city}, 'age': {age_min}-{age_max}, 'gender': {gender}, 'occupation': {occupation}, 'goals': {goals}, 'test_question': {filter_test_question}, 'test_answer': {filter_test_answer}}}")
        
        # Преобразуем параметры фильтрации в целые числа, если они не None
        if filter_test_question is not None:
            filter_test_question = int(filter_test_question)
        if filter_test_answer is not None:
            filter_test_answer = int(filter_test_answer)
        
        # Получаем ответы текущего пользователя
        user_answers = await self.get_user_answers(user_id)
        if not user_answers:
            logger.info(f"Пользователь {user_id} не имеет ответов на тест")
            return [], []
        
        # Получаем профиль текущего пользователя для определения пола и предпочтений
        current_user_profile = await self.db.get_user_profile(user_id)
        if not current_user_profile:
            logger.warning(f"Не удалось получить профиль пользователя {user_id}")
            return [], []
        
        # Определяем пол текущего пользователя
        current_user_gender = current_user_profile.get('gender')
        logger.info(f"Профиль пользователя: возраст={current_user_profile.get('age')}, пол={current_user_gender}")
        
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
                    else:
                        user_city = encrypted_city
                except Exception as e:
                    logger.error(f"Ошибка дешифрования города пользователя: {e}")
            else:
                user_city = encrypted_city
        else:
            user_city = city
        
        logger.info(f"Дешифрованный город для поиска: {user_city}")
        
        # Вспомогательная функция для добавления фильтров к запросу
        def add_filters_to_query(query, params, param_index):
            # Добавляем фильтр по полу - показываем только противоположный пол
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
            
            return query, params, param_index
        
        # Строим базовый запрос для получения пользователей
        query = """
            SELECT DISTINCT u.telegramid, u.name, u.age, u.gender, u.city as location,
                u.profiledescription as description, u.profileprioritycoefficient
            FROM users u
            WHERE u.telegramid != $1
            AND (u.accountstatus IS NULL OR u.accountstatus != 'blocked')
        """
        params = [user_id]
        param_index = 2
        
        # Если есть фильтр по интересам, модифицируем запрос
        if filter_test_question is not None and filter_test_answer is not None:
            # Получаем реальный ID ответа из таблицы answers
            answers_query = """
                SELECT answerid FROM answers 
                WHERE questionid = $1
                ORDER BY answerid
            """
            answers = await self.db.pool.fetch(answers_query, filter_test_question)
            
            if answers and 0 <= filter_test_answer - 1 < len(answers):
                # Преобразуем порядковый номер ответа в его реальный ID
                real_answer_id = answers[filter_test_answer - 1]['answerid']
            else:
                # Если не можем найти ответ по индексу, используем первый доступный
                if answers:
                    real_answer_id = answers[0]['answerid']
                else:
                    logger.warning(f"Не найдены ответы для вопроса {filter_test_question}")
                    return [], []
            
            # Модифицируем запрос для фильтрации по интересам
            query = """
                SELECT DISTINCT u.telegramid, u.name, u.age, u.gender, u.city as location,
                    u.profiledescription as description, u.profileprioritycoefficient
                FROM users u
                JOIN useranswers ua ON u.telegramid = ua.usertelegramid
                WHERE u.telegramid != $1
                AND (u.accountstatus IS NULL OR u.accountstatus != 'blocked')
                AND ua.questionid = $2 AND ua.answerid = $3
            """
            params = [user_id, filter_test_question, real_answer_id]
            param_index = 4
        
        # Добавляем фильтры к запросу
        query, params, param_index = add_filters_to_query(query, params, param_index)
        
        # Выполняем запрос
        try:
            candidates = await self.db.pool.fetch(query, *params)
            logger.info(f"Найдено кандидатов: {len(candidates)}")
            
            if not candidates:
                logger.warning(f"По фильтрам пользователей не найдено для {user_id}")
                return [], []
            
            # Фильтруем по городу после получения результатов, если указан город
            filtered_candidates = []
            if user_city and crypto:
                for candidate in candidates:
                    encrypted_location = candidate['location']
                    if encrypted_location:
                        try:
                            # Проверяем, является ли город зашифрованным
                            if isinstance(encrypted_location, bytes) or (
                                    isinstance(encrypted_location, str) and 
                                    (encrypted_location.startswith('b\'gAAAAA') or encrypted_location.startswith('gAAAAA'))):
                                decrypted_location = crypto.decrypt(encrypted_location)
                                if decrypted_location.lower() == user_city.lower():
                                    filtered_candidates.append(candidate)
                            else:
                                # Если город не зашифрован, сравниваем напрямую
                                if encrypted_location.lower() == user_city.lower():
                                    filtered_candidates.append(candidate)
                        except Exception as e:
                            logger.error(f"Ошибка дешифрования города кандидата {candidate['telegramid']}: {e}")
                
                candidates = filtered_candidates
            else:
                # Если город не указан, используем всех кандидатов
                filtered_candidates = candidates
            
            if not candidates:
                logger.warning(f"После фильтрации по городу не осталось кандидатов для {user_id}")
                return [], []
            
            # Вычисляем совместимость для каждого кандидата
            high_compatible = []
            low_compatible = []
            
            # Счетчики для статистики
            skipped_no_answers = 0
            high_compat_count = 0
            low_compat_count = 0
            
            for candidate in candidates:
                # Получаем ответы кандидата
                candidate_answers = await self.get_user_answers(candidate['telegramid'])
                if not candidate_answers:
                    skipped_no_answers += 1
                    continue
                
                # Вычисляем совместимость
                compatibility = self.calculate_compatibility(user_answers, candidate_answers)
                
                # Получаем фотографии пользователя
                photos = await self.db.get_user_photos(candidate['telegramid'])
                
                # Создаем полный профиль пользователя
                user_profile = dict(candidate)
                user_profile['photos'] = photos
                
                # Проверяем верификацию пользователя
                is_verified, _, _ = await self.db.check_verify(candidate['telegramid'])
                
                # Получаем коэффициент приоритета (если не указан в профиле)
                priority_coefficient = candidate.get('profileprioritycoefficient', 1.0)
                
                # Создаем результат с профилем и совместимостью
                result = {
                    'profile': user_profile,
                    'compatibility': round(compatibility, 1),
                    'is_verified': is_verified,
                    'priority_coefficient': priority_coefficient
                }
                
                # Распределяем по категориям совместимости
                if compatibility >= min_score:
                    high_compatible.append(result)
                    high_compat_count += 1
                else:
                    low_compatible.append(result)
                    low_compat_count += 1
            
            # Логируем статистику
            logger.info(f"Найдено пользователей: {high_compat_count} с высокой совместимостью, {low_compat_count} с низкой")
            
            # Сортируем по верификации, коэффициенту приоритета и совместимости
            high_compatible.sort(
                key=lambda x: (
                    x['is_verified'],  # Сначала верифицированные (True > False)
                    x['priority_coefficient'],  # Затем по коэффициенту приоритета
                    x['compatibility']  # Затем по совместимости
                ), 
                reverse=True
            )
            
            low_compatible.sort(
                key=lambda x: (
                    x['is_verified'],  # Сначала верифицированные (True > False)
                    x['priority_coefficient'],  # Затем по коэффициенту приоритета
                    x['compatibility']  # Затем по совместимости
                ), 
                reverse=True
            )
            
            # Применяем ограничение только если limit задан
            if limit is not None:
                return high_compatible[:limit], low_compatible[:limit]
            else:
                # Возвращаем все результаты без ограничений
                return high_compatible, low_compatible
            
        except Exception as e:
            logger.error(f"Ошибка при поиске совместимых пользователей: {e}")
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
