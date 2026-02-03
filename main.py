import os
import csv
from datetime import timedelta
from pyrogram import Client, filters
from config import API_ID, API_HASH, BOT_TOKEN, ADMIN_ID
from database import cursor, conn, get_ist_now, get_today_str

# Initialize Client
app = Client(
    "superex_event_bot_v3",  # Changed name to ensure fresh session
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- HELPER FUNCTIONS ---

def get_message_link(chat_id, msg_id):
    # Fix for private groups (-100 prefix)
    chat_str = str(chat_id)
    if chat_str.startswith("-100"):
        chat_str = chat_str[4:]
    return f"https://t.me/c/{chat_str}/{msg_id}"

def count_valid_tasks(user_id, task_type, period="daily"):
    query = "SELECT COUNT(*) FROM activity_log WHERE user_id = ? AND task_type = ? AND status = 'valid'"
    params = [user_id, task_type]
    
    if period == "daily":
        query += " AND date(timestamp) = ?"
        params.append(get_today_str())
    elif period == "weekly":
        # SQLite modifier for start of week
        query += " AND date(timestamp) >= date(?, 'weekday 0', '-6 days')" 
        params.append(get_today_str())
        
    cursor.execute(query, tuple(params))
    return cursor.fetchone()[0]

def log_activity(user, task, link, status, reason=""):
    cursor.execute(
        "INSERT INTO activity_log (user_id, username, task_type, message_link, status, reason, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user.id, user.username or "Unknown", task, link, status, reason, get_ist_now())
    )
    conn.commit()

# --- MAIN EVENT LISTENER ---

@app.on_message(filters.group)
async def task_tracker(client, message):
    text = (message.text or message.caption or "").lower()
    user = message.from_user
    if not user or not text:
        return

    # 1️⃣ TRADE TASK (#trade, #pnl)
    if "#trade" in text or "#pnl" in text:
        link = get_message_link(message.chat.id, message.id)
        if not (message.photo or message.document):
            log_activity(user, "trade", link, "invalid", "Missing Screenshot")
            # Optional: warn user silently or ignore
            return
        
        # Valid Trade
        log_activity(user, "trade", link, "valid")
        await message.reply_text(f"✅ **Trade Recorded!**")

    # 2️⃣ ANALYSIS (#analysis)
    elif "#analysis" in text:
        link = get_message_link(message.chat.id, message.id)
        daily_count = count_valid_tasks(user.id, "analysis", "daily")
        
        if daily_count >= 1:
            log_activity(user, "analysis", link, "excess", "Daily Limit Reached")
        else:
            log_activity(user, "analysis", link, "valid")
            await message.reply_text(f"✅ **Analysis Recorded!** (+2 pts)")

    # 3️⃣ SIGNAL (#signal)
    elif "#signal" in text:
        link = get_message_link(message.chat.id, message.id)
        required = ["entry", "sl", "target"]
        
        if not all(k in text for k in required):
            log_activity(user, "signal", link, "invalid", "Missing Entry/SL/Target")
            return

        daily_count = count_valid_tasks(user.id, "signal", "daily")
        if daily_count >= 2:
            log_activity(user, "signal", link, "excess", "Daily Limit Reached")
        else:
            log_activity(user, "signal", link, "valid")
            await message.reply_text(f"✅ **Signal Recorded!** (+1 pt)")

    # 4️⃣ TWITTER (x.com / twitter.com)
    elif "x.com" in text or "twitter.com" in text:
        link = get_message_link(message.chat.id, message.id)
        # Using a rough weekly check (last 7 days logic handled in DB query)
        weekly_count = count_valid_tasks(user.id, "twitter", "weekly")
        
        if weekly_count >= 3:
            log_activity(user, "twitter", link, "excess", "Weekly Limit Reached")
        else:
            log_activity(user, "twitter", link, "valid")
            await message.reply_text(f"✅ **X Post Recorded!** (+2 pts)")

# --- REPORT GENERATOR ---

def generate_report_text(target_date, specific_user_id=None):
    query = "SELECT username, task_type, message_link, status, reason FROM activity_log WHERE date(timestamp) = ?"
    params = [target_date]
    
    if specific_user_id:
        query += " AND user_id = ?"
        params.append(specific_user_id)
        
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    
    if not rows:
        return "📭 No activity found for this date."

    # Process Data
    users = {}
    flags = []
    
    for username, task, link, status, reason in rows:
        username = f"@{username}" if username else "Unknown"
        
        if status == 'valid':
            users.setdefault(username, {}).setdefault(task, []).append(link)
        else:
            flags.append(f"⚠️ {username} – {task.upper()}: {reason} [Link]({link})")

    # Build Text
    report = f"📊 **DAILY EVENT REPORT — {target_date}**\n"
    total_suggested = 0
    
    for user, tasks in users.items():
        report += f"\n👤 **{user}**\n"
        
        # Trade Slabs
        trades = tasks.get("trade", [])
        if trades:
            count = len(trades)
            if count == 1: pts = 3
            elif count <= 3: pts = 5
            elif count <= 6: pts = 7
            else: pts = 8
            total_suggested += pts
            report += f" #trade ×{count} → {pts} pts\n"
            for l in trades: report += f" 🔗 [Proof]({l})\n"

        # Analysis
        analysis = tasks.get("analysis", [])
        if analysis:
            pts = 2 * len(analysis) # Should be 1 max effectively
            total_suggested += pts
            report += f" #analysis ×{len(analysis)} → {pts} pts\n"
            for l in analysis: report += f" 🔗 [Proof]({l})\n"

        # Signal
        signals = tasks.get("signal", [])
        if signals:
            pts = 1 * len(signals)
            total_suggested += pts
            report += f" #signal ×{len(signals)} → {pts} pts\n"
            for l in signals: report += f" 🔗 [Proof]({l})\n"

        # Twitter
        tweets = tasks.get("twitter", [])
        if tweets:
            pts = 2 * len(tweets)
            total_suggested += pts
            report += f" 🐦 X Post ×{len(tweets)} → {pts} pts\n"
            for l in tweets: report += f" 🔗 [Proof]({l})\n"

    report += f"\n✅ **TOTAL SUGGESTED POINTS:** {total_suggested}\n"
    
    if flags:
        report += "\n**⚠️ FLAG SECTION**\n" + "\n".join(flags)

    return report

# --- ADMIN COMMANDS ---

@app.on_message(filters.command("today") & filters.private)
async def cmd_today(client, message):
    if message.from_user.id != ADMIN_ID: return
    report = generate_report_text(get_today_str())
    # Split if too long
    if len(report) > 4000:
        await message.reply(report[:4000])
        await message.reply(report[4000:])
    else:
        await message.reply(report)

@app.on_message(filters.command("user") & filters.private)
async def cmd_user(client, message):
    if message.from_user.id != ADMIN_ID: return
    if len(message.command) < 2:
        await message.reply("Usage: /user @username")
        return
    
    target_username = message.command[1].replace("@", "")
    # Find ID
    cursor.execute("SELECT user_id FROM activity_log WHERE username = ? LIMIT 1", (target_username,))
    res = cursor.fetchone()
    if not res:
        await message.reply("User not found in database.")
        return
        
    report = generate_report_text(get_today_str(), res[0])
    await message.reply(report)

@app.on_message(filters.command("export") & filters.private)
async def cmd_export(client, message):
    if message.from_user.id != ADMIN_ID: return
    
    cursor.execute("SELECT * FROM activity_log")
    with open("export.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "User ID", "Username", "Task", "Link", "Status", "Reason", "Timestamp"])
        writer.writerows(cursor.fetchall())
        
    await message.reply_document("export.csv")

if __name__ == "__main__":
    app.run()
