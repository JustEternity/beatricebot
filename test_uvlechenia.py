import asyncio
import asyncpg

# Подключение к базе данных
async def connect_to_db():
    try:
        conn = await asyncpg.connect(
            database="beatrice",  # Имя базы данных
            user="nivalover",     # Имя пользователя
            password="iloveniva", # Пароль
            host="185.239.51.142",     # Хост
            port="5432"  # Порт
        )
        return conn
    except Exception as e:
        print(f"Ошибка подключения к базе данных: {e}")
        return None

# Проверка существования пользователя
async def check_user_exists(conn, telegramid):
    try:
        user = await conn.fetchrow('SELECT telegramid FROM "User" WHERE telegramid = $1;', telegramid)
        return user is not None
    except Exception as e:
        print(f"Ошибка при проверке пользователя: {e}")
        return False

# Получение вопросов и ответов из базы данных
async def get_questions_and_answers(conn):
    questions_dict = {}
    answers_dict = {}

    try:
        # Получаем все вопросы
        questions = await conn.fetch("SELECT questionid, questiontext FROM questions ORDER BY questionid;")
        for question in questions:
            question_id, question_text = question['questionid'], question['questiontext']
            questions_dict[question_id] = question_text

        # Получаем все ответы
        answers = await conn.fetch("SELECT answerid, questionid, answertext FROM answers ORDER BY questionid, answerid;")
        for answer in answers:
            answer_id, question_id, answer_text = answer['answerid'], answer['questionid'], answer['answertext']
            if question_id not in answers_dict:
                answers_dict[question_id] = {}
            answers_dict[question_id][answer_id] = answer_text

        return questions_dict, answers_dict
    except Exception as e:
        print(f"Ошибка при получении данных: {e}")
        return {}, {}

# Сохранение ответов пользователя
async def save_user_answers(conn, telegramid, user_answers):
    try:
        for question_id, answer_id in user_answers.items():
            await conn.execute('INSERT INTO useranswers (usertelegramid, questionid, answerid) VALUES ($1, $2, $3);',
                               telegramid, question_id, answer_id)
    except Exception as e:
        print(f"Ошибка при сохранении ответов: {e}")

async def main():
    conn = await connect_to_db()
    if not conn:
        return

    # Запрашиваем telegramid пользователя  ТЕСТОВЫЙ АЙДИШНИК - 123
    telegramid = int(input("Введите ваш telegramid: "))

    # Проверяем, существует ли пользователь
    if not await check_user_exists(conn, telegramid):
        print("Пользователь с таким telegramid не найден.")
        await conn.close()
        return

    # Получаем вопросы и ответы
    questions_dict, answers_dict = await get_questions_and_answers(conn)
    if not questions_dict or not answers_dict:
        print("Не удалось загрузить вопросы и ответы.")
        await conn.close()
        return

    # Словарь для хранения ответов пользователя
    user_answers = {}

    # Проходим по каждому вопросу
    for question_id, question_text in questions_dict.items():
        print(f"\nВопрос {question_id}: {question_text}")

        # Получаем доступные ответы
        if question_id not in answers_dict:
            print("Ответы не найдены.")
            continue

        answers = answers_dict[question_id]
        print("Варианты ответов:")
        for answer_id, answer_text in answers.items():
            print(f"{answer_id}. {answer_text}")

        # Запрашиваем ответ у пользователя
        while True:
            try:
                answer_id = int(input("Выберите номер ответа: "))
                if answer_id in answers:
                    user_answers[question_id] = answer_id
                    break
                else:
                    print("Неверный номер ответа. Попробуйте снова.")
            except ValueError:
                print("Пожалуйста, введите число.")

    # Сохраняем ответы пользователя
    await save_user_answers(conn, telegramid, user_answers)

    # Закрываем соединение с базой данных
    await conn.close()

    # Выводим собранные ответы
    print("\n ответы:")
    for question_id, answer_id in user_answers.items():
        print(f"Вопрос {question_id}: {answers_dict[question_id][answer_id]}")

if __name__ == "__main__":
    asyncio.run(main())