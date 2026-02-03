from pyrogram import Client, filters
from datetime import datetime
from config import API_ID, API_HASH, BOT_TOKEN, ADMIN_ID
from database import cursor, conn

# I changed the name below to "superex_bot_v2" 
# This forces the bot to create a NEW login key and fixes the error!
app = Client(
    "superex_bot_v2",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

def today():
    return datetime.now().strftime("%Y-%m-%d")

def message_link(chat_id, msg_id):
    return f"https://t.me/c/{str(chat_id)[4:]}/{msg_id}"

# This makes the bot listen to Groups
@app.on_message(filters.group)
async def collect_tasks(client, message):
    text = (message.text or message.caption or "").lower()
    user = message.from_user
    if not user:
        return

    task = None

    # Check for keywords
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

    # If a task is found, save it and reply
    if task:
        link = message_link(message.chat.id, message.id)
        cursor.execute(
            "INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
            (user.id, user.username, today(), task, link)
        )
        conn.commit()
        # This sends the confirmation message to your group
        await message.reply_text(f"✅ **{task.capitalize()}** saved! Points added.")

# This is the Admin command to check points
@app.on_message(filters.command("today") & filters.private)
async def daily_report(client, message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("""
    SELECT username, task, message_link
    FROM tasks WHERE date = ?
    """, (today(),))

    rows = cursor.fetchall()
    if not rows:
        await message.reply("No data for today.")
        return

    report = "📊 **DAILY EVENT REPORT**\n\n"
    data = {}

    for username, task, link in rows:
        data.setdefault(username, {}).setdefault(task, []).append(link)

    for user, tasks in data.items():
        report += f"👤 @{user}\n"
        trade_count = len(tasks.get("trade", []))

        if trade_count:
            if trade_count == 1: pts = 3
            elif trade_count <= 3: pts = 5
            elif trade_count <= 6: pts = 7
            else: pts = 8
            report += f"• #trade ×{trade_count} → {pts} pts\n"

        if "analysis" in tasks:
            report += "• #analysis ×1 → 2 pts\n"

        if "signal" in tasks:
            count = len(tasks['signal'])
            report += f"• #signal ×{count} → {count} pts\n"

        if "twitter" in tasks:
            count = len(tasks['twitter'])
            report += f"• X Post ×{count} → {count * 2} pts\n"

        report += "\n"

    await client.send_message(ADMIN_ID, report)

if __name__ == "__main__":
    app.run()
