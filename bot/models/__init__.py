from .states import RegistrationStates
from .user import User  # Импортируем User
from .test_models import Question, Answer
from .user import UserDB as User

__all__ = [
    'RegistrationStates',
    'User',
    'Question',
    'Answer'
]