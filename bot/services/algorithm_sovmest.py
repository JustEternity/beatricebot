from typing import List, Tuple, Dict
import logging

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
                limit: int = 5,
                min_score: float = 50.0
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
                limit: Максимальное количество результатов
                min_score: Минимальный процент совместимости
                
            Returns:
                Tuple[List[Dict], List[Dict]]: Два списка пользователей - 
                с высокой и низкой совместимостью
            """
            logger.debug(f"Finding compatible users for {user_id}, filters: city={city}, age={age_min}-{age_max}, gender={gender}")
            
            # Получаем ответы текущего пользователя
            user_answers = await self.get_user_answers(user_id)
            if not user_answers:
                logger.debug("User has no answers")
                return [], []
            
            # Получаем профиль текущего пользователя для определения пола и предпочтений
            current_user_profile = await self.db.get_user_profile(user_id)
            if not current_user_profile:
                logger.debug("Could not get current user profile")
                return [], []
            
            # Определяем пол текущего пользователя и его предпочтения
            current_user_gender = current_user_profile.get('gender')
            
            # Строим базовый запрос для получения пользователей
            query = """
                SELECT u.telegramid, u.name, u.age, u.gender, u.city as location, 
                    u.profiledescription as description
                FROM users u
                JOIN useranswers ua ON u.telegramid = ua.usertelegramid
                WHERE u.telegramid != $1
            """
            params = [user_id]
            param_index = 2
            
            # Добавляем фильтр по полу - показываем только противоположный пол
            # Если текущий пользователь мужчина (gender = '0'), показываем женщин (gender = '1')
            # Если текущий пользователь женщина (gender = '1'), показываем мужчин (gender = '0')
            if current_user_gender == '0':  # Мужчина ищет женщин
                query += f" AND u.gender = '1'"
            elif current_user_gender == '1':  # Женщина ищет мужчин
                query += f" AND u.gender = '0'"
            
            # Добавляем фильтры в запрос
            if city:
                query += f" AND u.city = ${param_index}"
                params.append(city)
                param_index += 1
            
            if age_min is not None and age_max is not None:
                query += f" AND u.age BETWEEN ${param_index} AND ${param_index + 1}"
                params.extend([age_min, age_max])
                param_index += 2
            
            # Если указан дополнительный фильтр по полу, применяем его
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
            
            # Добавляем группировку по пользователю
            query += " GROUP BY u.telegramid"
            
            # Выполняем запрос
            try:
                candidates = await self.db.pool.fetch(query, *params)
                logger.debug(f"Found {len(candidates)} candidates matching filters")
                
                if not candidates:
                    return [], []
                
                # Вычисляем совместимость для каждого кандидата
                high_compatible = []
                low_compatible = []
                
                for candidate in candidates:
                    # Получаем ответы кандидата
                    candidate_answers = await self.get_user_answers(candidate['telegramid'])
                    if not candidate_answers:
                        continue
                    
                    # Вычисляем совместимость
                    compatibility = self.calculate_compatibility(user_answers, candidate_answers)
                    
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
     
    async def get_compatibility_explanation(self, user1_id: int, user2_id: int) -> str:
        """
        Генерирует объяснение совместимости между пользователями
        
        Args:
            user1_id: ID первого пользователя
            user2_id: ID второго пользователя
            
        Returns:
            str: Текстовое объяснение совместимости
        """
        # Получаем ответы обоих пользователей
        user1_answers = await self.db.get_user_answers(user1_id)
        user2_answers = await self.db.get_user_answers(user2_id)
        
        if not user1_answers or not user2_answers:
            return "Недостаточно данных для анализа совместимости."
        
        # Получаем вопросы
        questions = await self.db.get_all_questions()
        
        # Находим совпадения и различия
        matches = []
        differences = []
        
        for q_id, question in questions.items():
            if q_id in user1_answers and q_id in user2_answers:
                if user1_answers[q_id] == user2_answers[q_id]:
                    matches.append(question['text'])
                else:
                    differences.append(question['text'])
        
        # Формируем объяснение
        explanation = "Анализ совместимости:\n\n"
        
        if matches:
            explanation += "🟢 Совпадения во взглядах:\n"
            for i, match in enumerate(matches[:3], 1):  # Показываем только первые 3 совпадения
                explanation += f"{i}. {match}\n"
            
            if len(matches) > 3:
                explanation += f"...и еще {len(matches) - 3} совпадений\n"
        
        if differences:
            explanation += "\n🔴 Различия во взглядах:\n"
            for i, diff in enumerate(differences[:3], 1):  # Показываем только первые 3 различия
                explanation += f"{i}. {diff}\n"
            
            if len(differences) > 3:
                explanation += f"...и еще {len(differences) - 3} различий\n"
        
        return explanation
