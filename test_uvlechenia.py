import psycopg2

# Подключение к базе данных
def connect_to_db():
    try:
        conn = psycopg2.connect(
            dbname="",  
            user="",  
            password="",  
            host="",       
            port="5432"           
        )
        return conn
    except Exception as e:
        print(f"Ошибка подключения к базе данных: {e}")
        return None

# Проверка существования пользователя
def check_user_exists(conn, telegramid):
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT telegramid FROM "User" WHERE telegramid = %s;', (telegramid,))
            user = cur.fetchone()
            return user is not None
    except Exception as e:
        print(f"Ошибка при проверке пользователя: {e}")
        return False

# Получение вопросов и ответов из базы данных
def get_questions_and_answers(conn):
    questions_dict = {}
    answers_dict = {}

    try:
        with conn.cursor() as cur:
            # Получаем все вопросы
            cur.execute("SELECT questionid, questiontext FROM questions ORDER BY questionid;")
            questions = cur.fetchall()
            for question in questions:
                question_id, question_text = question
                questions_dict[question_id] = question_text

            # Получаем все ответы
            cur.execute("SELECT answerid, questionid, answertext FROM answers ORDER BY questionid, answerid;")
            answers = cur.fetchall()
            for answer in answers:
                answer_id, question_id, answer_text = answer
                if question_id not in answers_dict:
                    answers_dict[question_id] = {}
                answers_dict[question_id][answer_id] = answer_text

            return questions_dict, answers_dict
    except Exception as e:
        print(f"Ошибка при получении данных: {e}")
        return {}, {}

# Сохранение ответов пользователя
def save_user_answers(conn, telegramid, user_answers):
    try:
        with conn.cursor() as cur:
            for question_id, answer_id in user_answers.items():
                cur.execute('INSERT INTO useranswers (usertelegramid, questionid, answerid) VALUES (%s, %s, %s);',
                            (telegramid, question_id, answer_id))
            conn.commit()
    except Exception as e:
        print(f"Ошибка при сохранении ответов: {e}")

def main():
    conn = connect_to_db()
    if not conn:
        return

    # Запрашиваем telegramid пользователя  ТЕСТОВЫЙ АЙДИШНИК - 123
    telegramid = int(input("Введите ваш telegramid: "))

    # Проверяем, существует ли пользователь
    if not check_user_exists(conn, telegramid):
        print("Пользователь с таким telegramid не найден.")
        conn.close()
        return

    # Получаем вопросы и ответы
    questions_dict, answers_dict = get_questions_and_answers(conn)
    if not questions_dict or not answers_dict:
        print("Не удалось загрузить вопросы и ответы.")
        conn.close()
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
    save_user_answers(conn, telegramid, user_answers)

    # Закрываем соединение с базой данных
    conn.close()

    # Выводим собранные ответы
    print("\n ответы:")
    for question_id, answer_id in user_answers.items():
        print(f"Вопрос {question_id}: {answers_dict[question_id][answer_id]}")

if __name__ == "__main__":
    main()