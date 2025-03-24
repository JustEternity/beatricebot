from .states import RegistrationStates
from .user import User  # Импортируем User
from .test_models import Question, Answer

# Если User определен в user.py как алиас для UserDB, добавьте:
from .user import UserDB as User

__all__ = [
    'RegistrationStates',
    'User',  # Теперь импортируется корректно
    'Question',
    'Answer'
]