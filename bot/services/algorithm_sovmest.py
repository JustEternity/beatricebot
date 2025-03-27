from typing import List, Tuple, Optional
import logging

class CompatibilityService:
    """Сервис для расчета совместимости между пользователями на основе их ответов на тест"""
    
    def __init__(self, db):
        self.db = db
        self.logger = logging.getLogger(__name__)
    
    async def calculate_compatibility(self, user1_id: int, user2_id: int) -> float:
        """
        Рассчитывает процент совместимости между двумя пользователями
        
        Args:
            user1_id: ID первого пользователя
            user2_id: ID второго пользователя
            
        Returns:
            float: Процент совместимости (0-100)
        """
        # Получаем ответы обоих пользователей
        user1_answers = await self.db.get_user_answers(user1_id)
        user2_answers = await self.db.get_user_answers(user2_id)
        
        if not user1_answers or not user2_answers:
            self.logger.warning(f"Не найдены ответы для пользователей {user1_id} и/или {user2_id}")
            return 0.0
        
        # Общее количество вопросов
        total_questions = len(user1_answers)
        if total_questions == 0:
            return 0.0
        
        # Подсчитываем совпадения
        matches = 0
        for question_id in user1_answers:
            if question_id in user2_answers and user1_answers[question_id] == user2_answers[question_id]:
                matches += 1
        
        # Рассчитываем процент совместимости
        compatibility = (matches / total_questions) * 100
        
        # Применяем дополнительные факторы (например, учитываем предпочтения)
        compatibility = await self._apply_preference_factors(user1_id, user2_id, compatibility)
        
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
    
    async def find_compatible_users(self, user_id: int, limit: int = 10, min_score: float = 50.0) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
        """
        Находит пользователей, совместимых с указанным пользователем
        
        Args:
            user_id: ID пользователя
            limit: Максимальное количество результатов
            min_score: Минимальный порог совместимости
            
        Returns:
            Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]: 
                Кортеж из двух списков:
                1. Список кортежей (ID пользователя, процент совместимости) с высокой совместимостью (≥min_score)
                2. Список кортежей (ID пользователя, процент совместимости) с низкой совместимостью (<min_score)
        """
        # Получаем всех пользователей, прошедших тест
        all_users = await self.db.get_users_with_answers()
        
        # Исключаем текущего пользователя
        other_users = [u for u in all_users if u != user_id]
        
        # Рассчитываем совместимость с каждым пользователем
        high_compatibility_scores = []  # Пользователи с высокой совместимостью (≥min_score)
        low_compatibility_scores = []   # Пользователи с низкой совместимостью (<min_score)
        
        for other_id in other_users:
            score = await self.calculate_compatibility(user_id, other_id)
            
            if score >= min_score:
                high_compatibility_scores.append((other_id, score))
            else:
                # Добавляем пользователей с низкой совместимостью, но не ниже 20%
                if score >= 20.0:
                    low_compatibility_scores.append((other_id, score))
        
        # Сортируем оба списка по убыванию совместимости
        high_compatibility_scores.sort(key=lambda x: x[1], reverse=True)
        low_compatibility_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Возвращаем ограниченное количество результатов для обоих списков
        return high_compatibility_scores[:limit], low_compatibility_scores[:limit]

    
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
