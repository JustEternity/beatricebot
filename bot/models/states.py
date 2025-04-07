from aiogram.fsm.state import State, StatesGroup

class RegistrationStates(StatesGroup):
    # Основные состояния регистрации
    POLICY = State()           # Согласие с политикой
    POLICY_SECOND_TIME = State() # Согласие с политикой при её обновлении
    NAME = State()             # Ввод имени
    AGE = State()              # Ввод возраста
    GENDER = State()           # Выбор пола
    LOCATION = State()         # Ввод местоположения
    PHOTOS = State()           # Загрузка фотографий
    DESCRIPTION = State()      # Ввод описания
    VERIFICATION = State()     # Отправка видео для верификации
    MAIN_MENU = State()        # Главное меню после регистрации

    ADMIN_AUTH = State()  # Состояние для ввода пароля админа
    ADMIN_MENU = State()       # Меню админа
    WATCH_REPORTS = State()    # Просмотр доступных отчетов админу
    AWAIT_YEAR = State()       # Ожидание года для отчета
    AWAIT_YEAR_FOR_SERV = State() # Ожидание года для отчета по купленным услугам
    WATCH_FEEDBACK = State()   # просмотр обратной связи в режиме админа
    WATCH_COMPLAINTS = State() # Просмотр жалоб в режиме админа
    WATCH_VERIFY = State()     # Просмотр верификаций в режиме админа
    WATCH_MODER = State()      # Модерация анкет в режиме админа
    AWAIT_REJECT_REASON = State() # Ожидание ввода причны негативной верификации
    AWAIT_BLOCK_REASON = State() # Ожидание ввода причины блока анкеты

    # Состояния редактирования профиля
    EDIT_NAME = State()        # Редактирование имени
    EDIT_AGE = State()         # Редактирование возраста
    EDIT_LOCATION = State()    # Редактирование локации
    EDIT_PHOTOS = State()      # Редактирование фотографий
    EDIT_DESCRIPTION = State() # Редактирование описания

    FILTERS = State()
    SET_FILTER_CITY = State()
    SET_FILTER_AGE = State()
    SET_FILTER_GENDER = State()
    SET_FILTER_OCCUPATION = State()
    SET_FILTER_GOALS = State()

    VIEW_PROFILE = State()     # Просмотр профиля
    SEND_FEEDBACK = State()    # Отправка обратной связи

    # Состояния тестирования
    TEST_IN_PROGRESS = State() # Начало тестирования
    TEST_QUESTION = State()    # Обработка вопросов теста

    # Состояния просмотра лайков
    VIEWING_LIKES = State()    # Просмотр лайков


class ViewLikesState(StatesGroup):
    """Состояния для просмотра лайков"""
    viewing = State()
