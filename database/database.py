import psycopg2
import os

# Database connection parameters
DB_NAME = os.getenv('DB_NAME', 'mafia_bot')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'your_password')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')

# Create connection
conn = psycopg2.connect(
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT
)

# Create cursor
cursor = conn.cursor()

# Create tables if they don't exist
def create_tables():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id BIGINT, 
            tg_name VARCHAR, 
            link VARCHAR,
            role TEXT,
            killed INT DEFAULT 0,
            cured INT DEFAULT 0,
            money INT DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_panel(
            creator_id BIGINT,
            group_id BIGINT,
            doctor VARCHAR DEFAULT 'Лікар',
            doctor_text VARCHAR DEFAULT 'Цієї гри ти - Лікар!\nРоби все, щоб врятувати якомога більше мирних людей.', 
            all_capone VARCHAR DEFAULT 'Аль Капоне',
            all_capone_text VARCHAR DEFAULT 'Цієї гри ти - Аль Капоне!\nРоби все, щоб твоя сім`я отримала перемогу, над цими нікчемними мирними жителями.', 
            civilian VARCHAR DEFAULT 'Мирний Житель',
            civilian_text VARCHAR DEFAULT 'Цієї гри ти - Мирний житель!\nРоби все, щоб знищити підступне угрупування Аль Капоне.'
        )
    """)
    conn.commit()

create_tables()

# list = [("Чи любиш ти пити каву зранку?", "Так", "Ні"), 
#         ("Чи вмієш ти готувати яєчню?", "Так", "Ні"), 
#         ("Ти віддаєш перевагу перегляду фільмів вдома, чи кінотеатрі?", "Вдома", "В кінотеатрі"),
#         ("Ти полюбляєш вечірні прогулянки?", "Так", "Ні"), 
#         ("Ти за паперові чи електронні книги?", "Паперові", "Електронні"), 
#         ("Ти слухаєш подкасти?", "Так", "Ні"), 
#         ("Ти маєш улюблену музичну групу, чи виконавців?", "Так", "Ні"),
#         ("Чи часто ти відвідуєш музеї/виставки?", "Так", "Ні"), 
#         ("У тебе є домашні улюбленці?", "Так", "Ні"), 
#         ("Любиш подорожі на велосипеді?", "Так", "Ні")]

# i = 0
# for text, answer1, answer2 in list:
#     new_column_name = 'question_for_civilian_answer'
#     new_column_data_type = 'VARCHAR'
#     i += 1

#cursor.execute(f"ALTER TABLE users ADD COLUMN voites INTEGER DEFAULT 0")