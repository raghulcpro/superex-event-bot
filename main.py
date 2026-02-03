from pyrogram.client import Client
from pyrogram import filters
from datetime import datetime
from config import API_ID, API_HASH, BOT_TOKEN, ADMIN_ID
from database import cursor, conn

app = Client(
    "event_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

def today():
    return datetime.now().strftime("%Y-%m-%d")

def message_link(chat_id, msg_id):
    return f"https://t.me/c/{str(chat_id)[4:]}/{msg_id}"

@app.on_message(filters.group)
def collect_tasks(client, message):
    text = (message.text or message.caption or "").lower()
    user = message.from_user
    if not user:
        return

    task = None

    if "#trade" in text or "#pnl" in text:
        if message.photo or message.document:
            task = "trade"
        else:
            return

    elif "#analysis" in text:
        task = "analysis"

    elif "#signal" in text:
        if all(x in text for x in ["entry", "sl", "target"]):
            task = "signal"
        else:
            return

    elif "x.com" in text or "twitter.com" in text:
        task = "twitter"

    if task:
        link = message_link(message.chat.id, message.id)
        cursor.execute(
            "INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
            (user.id, user.username, today(), task, link)
        )
        conn.commit()

@app.on_message(filters.command("today") & filters.private)
def daily_report(client, message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("""
    SELECT username, task, message_link
    FROM tasks WHERE date = ?
    """, (today(),))

    rows = cursor.fetchall()
    if not rows:
        message.reply("No data for today.")
        return

    report = "📊 DAILY EVENT REPORT\n\n"
    data = {}

    for username, task, link in rows:
        data.setdefault(username, {}).setdefault(task, []).append(link)

    for user, tasks in data.items():
        report += f"👤 @{user}\n"
        trade_count = len(tasks.get("trade", []))

        if trade_count:
            if trade_count == 1:
                pts = 3
            elif trade_count <= 3:
                pts = 5
            elif trade_count <= 6:
                pts = 7
            else:
                pts = 8
            report += f"#trade ×{trade_count} → {pts} pts\n"

        if "analysis" in tasks:
            report += "#analysis ×1 → 2 pts\n"

        if "signal" in tasks:
            report += f"#signal ×{len(tasks['signal'])} → {len(tasks['signal'])} pts\n"

        if "twitter" in tasks:
            report += f"X Post ×{len(tasks['twitter'])} → {len(tasks['twitter']) * 2} pts\n"

        report += "\n"

    client.send_message(ADMIN_ID, report)

app.run()
