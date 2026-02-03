import sqlite3
from datetime import datetime
import pytz

# Connect to database
conn = sqlite3.connect("event.db", check_same_thread=False)
cursor = conn.cursor()

# Create a more advanced table to track status and reasons
cursor.execute("""
CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    task_type TEXT,
    message_link TEXT,
    status TEXT,      -- 'valid', 'invalid', 'excess'
    reason TEXT,      -- Why it was rejected (e.g. 'No Screenshot')
    timestamp DATETIME
)
""")
conn.commit()

# Helper to get current IST time
def get_ist_now():
    return datetime.now(pytz.timezone('Asia/Kolkata'))

def get_today_str():
    return get_ist_now().strftime("%Y-%m-%d")

# Helper to get the start of the current week (Monday)
def get_week_start_str():
    now = get_ist_now()
    # adjust to monday
    start = now - datetime.timedelta(days=now.weekday())
    return start.strftime("%Y-%m-%d")
