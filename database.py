import sqlite3

conn = sqlite3.connect("event.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    user_id INTEGER,
    username TEXT,
    date TEXT,
    task TEXT,
    message_link TEXT
)
""")

conn.commit()
