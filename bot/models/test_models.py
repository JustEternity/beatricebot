from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime

class QuestionBase(BaseModel):
    """Базовая модель вопроса"""
    text: str
    order: int  # Порядок отображения вопроса

class QuestionCreate(QuestionBase):
    """Модель для создания вопроса"""
    pass

class QuestionDB(QuestionBase):
    """Модель вопроса из базы данных"""
    id: int
    class Config:
        from_attributes = True

class AnswerBase(BaseModel):
    """Базовая модель ответа"""
    text: str
    question_id: int
    weight: float  # Вес ответа для алгоритма совместимости

class AnswerCreate(AnswerBase):
    """Модель для создания ответа"""
    pass

class AnswerDB(AnswerBase):
    """Модель ответа из базы данных"""
    id: int
    class Config:
        from_attributes = True

class TestSession(BaseModel):
    """Модель сессии тестирования пользователя"""
    user_id: int
    start_time: datetime
    current_question: int = 0
    answers: Dict[int, int] = {}  # {question_id: answer_id}

class TestResult(BaseModel):
    """Результаты тестирования для анализа совместимости"""
    user_id: int
    completion_date: datetime
    scores: Dict[int, float]  # {category_id: score}
    compatibility_coefficient: float

class Answer(AnswerBase):
    id: int

    class Config:
        from_attributes = True

class Question(QuestionBase):
    id: int

    class Config:
        from_attributes = True  # Заменяем orm_mode