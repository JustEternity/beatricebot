from aiogram.fsm.state import State, StatesGroup

class RegistrationStates(StatesGroup):
    # Основные состояния регистрации
    POLICY = State()           # Согласие с политикой
    NAME = State()             # Ввод имени
    AGE = State()              # Ввод возраста
    GENDER = State()           # Выбор пола
    LOCATION = State()         # Ввод местоположения
    PHOTOS = State()           # Загрузка фотографий
    DESCRIPTION = State()      # Ввод описания
    MAIN_MENU = State()        # Главное меню после регистрации

    # Состояния редактирования профиля
    EDIT_NAME = State()        # Редактирование имени
    EDIT_AGE = State()         # Редактирование возраста
    EDIT_LOCATION = State()    # Редактирование локации
    EDIT_PHOTOS = State()      # Редактирование фотографий
    EDIT_DESCRIPTION = State() # Редактирование описания

    SET_FILTER_CITY = State()
    SET_FILTER_AGE = State()
    SET_FILTER_GENDER = State()
    SET_FILTER_OCCUPATION = State()
    SET_FILTER_GOALS = State()

    VIEW_PROFILE = State()     # Просмотр профиля

    # Состояния тестирования
    TEST_IN_PROGRESS = State() # Начало тестирования
    TEST_QUESTION = State()    # Обработка вопросов теста