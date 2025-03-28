from typing import List, Tuple, Optional, Dict
import logging

logger = logging.getLogger(__name__)

class CompatibilityService:
    """Сервис для расчета совместимости между пользователями на основе их ответов на тест"""
    
    def __init__(self, db):
        self.db = db
        self.logger = logging.getLogger(__name__)
    
    def calculate_compatibility(self, user_answers: Dict[int, int], other_answers: Dict[int, int], weights: Dict[int, float] = None) -> float:
        """
        Рассчитывает совместимость между двумя пользователями на основе их ответов.
        
        Args:
            user_answers: Словарь {id_вопроса: ответ} для текущего пользователя
            other_answers: Словарь {id_вопроса: ответ} для другого пользователя
            weights: Словарь {id_вопроса: вес} для вопросов (опционально)
        
        Returns:
            Процент совместимости (0-100)
        """
        if not user_answers or not other_answers:
            return 0.0
        
        # Если веса не предоставлены, используем равные веса для всех вопросов
        if weights is None:
            weights = {}
        
        total_score = 0.0
        max_possible_score = 0.0
        
        # Находим общие вопросы, на которые ответили оба пользователя
        common_questions = set(user_answers.keys()) & set(other_answers.keys())
        
        if not common_questions:
            return 0.0
        
        for question_id in common_questions:
            # Получаем ответы обоих пользователей
            user_answer = user_answers[question_id]
            other_answer = other_answers[question_id]
            
            # Получаем вес вопроса (по умолчанию 1.0)
            weight = weights.get(question_id, 1.0)
            
            # Рассчитываем совпадение ответов (0-5)
            # Чем меньше разница, тем выше совпадение
            answer_diff = abs(user_answer - other_answer)
            match_score = 5 - min(answer_diff, 5)  # Максимальная разница 5
            
            # Добавляем взвешенный балл
            total_score += match_score * weight
            max_possible_score += 5 * weight  # Максимально возможный балл
        
        # Рассчитываем процент совместимости
        if max_possible_score > 0:
            compatibility = (total_score / max_possible_score) * 100
        else:
            compatibility = 0.0
        
        return compatibility
    
    async def _apply_preference_factors(self, user1_id: int, user2_id: int, base_compatibility: float) -> float:
        """
        Применяет дополнительные факторы к базовой совместимости
        
        Args:
            user1_id: ID первого пользователя
            user2_id: ID второго пользователя
            base_compatibility: Базовая совместимость
            
        Returns:
            float: Скорректированная совместимость
        """
        # Получаем данные пользователей
        user1_data = await self.db.get_user_data(user1_id)
        user2_data = await self.db.get_user_data(user2_id)
        
        if not user1_data or not user2_data:
            return base_compatibility
        
        # Проверяем соответствие предпочтений по возрасту, полу и т.д.
        # Это упрощенная логика, можно расширить
        
        # Проверка пола
        if user1_data.get('gender_preference') and user2_data.get('gender'):
            if user1_data['gender_preference'] != user2_data['gender']:
                return 0.0  # Несоответствие предпочтений по полу
        
        # Проверка возраста
        if user1_data.get('age_min') and user1_data.get('age_max') and user2_data.get('age'):
            if user2_data['age'] < user1_data['age_min'] or user2_data['age'] > user1_data['age_max']:
                return base_compatibility * 0.7  # Снижаем совместимость при несоответствии возраста
        
        # Можно добавить другие факторы
        
        return base_compatibility
    
    async def find_compatible_users(self, user_id: int, limit: int = 20, min_score: float = 50.0) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
        """Находит совместимых пользователей с учетом пола"""
        logger.debug(f"Finding compatible users for user {user_id}")
        try:
            # Получаем данные текущего пользователя
            current_user = await self.db.get_user(user_id)
            if not current_user:
                logger.warning(f"User {user_id} not found")
                return [], []
            
            # Получаем пол и предпочтения текущего пользователя
            user_gender = current_user.get('gender')
            looking_for = current_user.get('looking_for')
            
            logger.debug(f"User {user_id} gender: {user_gender}, looking for: {looking_for}")
            
            # Получаем ответы текущего пользователя
            user_answers = await self.db.get_user_answers(user_id)
            if not user_answers:
                logger.warning(f"User {user_id} has no answers")
                return [], []
            
            # Получаем пользователей, прошедших тест
            other_users = await self.db.get_users_with_answers(exclude_user_id=user_id)
            logger.debug(f"Found {len(other_users)} other users with answers")
            
            # Получаем веса ответов
            try:
                weights = await self.db.get_answer_weights()
            except Exception as e:
                logger.warning(f"Error getting answer weights: {e}. Using default weights.")
                weights = {}  # Используем пустой словарь, если не удалось получить веса
            
            # Рассчитываем совместимость с каждым пользователем
            high_compatible = []
            low_compatible = []
            
            for other_id in other_users:
                # Получаем данные другого пользователя
                other_user = await self.db.get_user(other_id)
                if not other_user:
                    continue
                
                # Получаем пол другого пользователя
                other_gender = other_user.get('gender')
                
                # Проверяем соответствие по полу
                # Если looking_for не установлен, используем противоположный пол по умолчанию
                if looking_for is None:
                    # Если пол пользователя 0 (мужской), то ищем 1 (женский) и наоборот
                    if user_gender == '0' or user_gender == 0:
                        effective_looking_for = '1'
                    else:
                        effective_looking_for = '0'
                    logger.debug(f"Looking_for not set, using default: {effective_looking_for}")
                else:
                    effective_looking_for = looking_for
                
                # Преобразуем к строкам для сравнения
                if isinstance(effective_looking_for, (int, float)):
                    effective_looking_for = str(effective_looking_for)
                if isinstance(other_gender, (int, float)):
                    other_gender = str(other_gender)
                
                # Проверяем соответствие
                if effective_looking_for == '0' and other_gender != '0':  # Ищет мужчин, но другой пользователь не мужчина
                    logger.debug(f"Skipping user {other_id} - gender mismatch (looking for men)")
                    continue
                if effective_looking_for == '1' and other_gender != '1':  # Ищет женщин, но другой пользователь не женщина
                    logger.debug(f"Skipping user {other_id} - gender mismatch (looking for women)")
                    continue
                
                # Получаем ответы другого пользователя
                other_answers = await self.db.get_user_answers(other_id)
                if not other_answers:
                    continue
                
                # Рассчитываем совместимость
                compatibility = self.calculate_compatibility(user_answers, other_answers, weights)
                
                # Добавляем пользователя в соответствующий список
                if compatibility >= min_score:
                    high_compatible.append((other_id, compatibility))
                elif compatibility > 30:  # Минимальный порог для низкой совместимости
                    low_compatible.append((other_id, compatibility))
            
            # Сортируем списки по совместимости (от высокой к низкой)
            high_compatible.sort(key=lambda x: x[1], reverse=True)
            low_compatible.sort(key=lambda x: x[1], reverse=True)
            
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
