import os
import csv
from datetime import datetime
from pyrogram import Client, filters
from config import API_ID, API_HASH, BOT_TOKEN, ADMIN_ID
from database import cursor, conn, get_ist_now, get_today_str

# Initialize Client
app = Client(
    "superex_event_bot_v4", 
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- HELPER FUNCTIONS ---

def get_message_link(chat_id, msg_id):
    chat_str = str(chat_id)
    if chat_str.startswith("-100"):
        chat_str = chat_str[4:]
    return f"https://t.me/c/{chat_str}/{msg_id}"

def get_formatted_date():
    return get_ist_now().strftime("%b %d") # Returns "Feb 04"

def count_valid_tasks(user_id, task_type, period="daily"):
    query = "SELECT COUNT(*) FROM activity_log WHERE user_id = ? AND task_type = ? AND status = 'valid'"
    params = [user_id, task_type]
    
    if period == "daily":
        query += " AND date(timestamp) = ?"
        params.append(get_today_str())
    elif period == "weekly":
        query += " AND date(timestamp) >= date(?, 'weekday 0', '-6 days')" 
        params.append(get_today_str())
        
    cursor.execute(query, tuple(params))
    return cursor.fetchone()[0]

def log_activity(user, task, link, status, reason=""):
    timestamp_str = get_ist_now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO activity_log (user_id, username, task_type, message_link, status, reason, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user.id, user.username or "Unknown", task, link, status, reason, timestamp_str)
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
            return
        
        # Valid Trade
        log_activity(user, "trade", link, "valid")
        # Silent success to reduce spam, or uncomment below:
        # await message.reply_text(f"✅ Trade Recorded!")

    # 2️⃣ ANALYSIS (#analysis)
    elif "#analysis" in text:
        link = get_message_link(message.chat.id, message.id)
        daily_count = count_valid_tasks(user.id, "analysis", "daily")
        
        if daily_count >= 1:
            log_activity(user, "analysis", link, "excess", "Daily Limit Reached")
        else:
            log_activity(user, "analysis", link, "valid")
            await message.reply_text(f"✅ Analysis Recorded! (+2 pts)")

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
            await message.reply_text(f"✅ Signal Recorded! (+1 pt)")

    # 4️⃣ TWITTER (x.com / twitter.com)
    elif "x.com" in text or "twitter.com" in text:
        link = get_message_link(message.chat.id, message.id)
        weekly_count = count_valid_tasks(user.id, "twitter", "weekly")
        
        if weekly_count >= 3:
            log_activity(user, "twitter", link, "excess", "Weekly Limit Reached")
        else:
            log_activity(user, "twitter", link, "valid")
            await message.reply_text(f"✅ X Post Recorded! (+2 pts)")

# --- REPORT GENERATOR ---

def generate_report_text(target_date):
    query = "SELECT username, task_type, message_link, status, reason FROM activity_log WHERE date(timestamp) = ?"
    cursor.execute(query, (target_date,))
    rows = cursor.fetchall()
    
    if not rows:
        return "📭 No activity found for this date."

    # Group Data
    users = {}
    
    for username, task, link, status, reason in rows:
        username = f"@{username}" if username else "Unknown"
        if status == 'valid':
            users.setdefault(username, {}).setdefault(task, []).append(link)

    # Build Report
    report_lines = []
    
    for user, tasks in users.items():
        report_lines.append(f"👤 {user}")
        daily_total = 0
        date_str = f"Date: {get_formatted_date()}"

        # 1. ANALYSIS
        analysis_links = tasks.get("analysis", [])
        if analysis_links:
            count = len(analysis_links)
            pts = count * 2 # Max 1 usually
            daily_total += pts
            report_lines.append(f"#analysis ×{count} → {pts} pts")
            for link in analysis_links:
                report_lines.append(f"Post Link - {link}")
            report_lines.append(date_str + "\n")

        # 2. SIGNAL
        signal_links = tasks.get("signal", [])
        if signal_links:
            count = len(signal_links)
            pts = count * 1
            daily_total += pts
            report_lines.append(f"#signal × {count} → {pts} pts")
            for i, link in enumerate(signal_links, 1):
                report_lines.append(f"Post link {i} - {link}")
            report_lines.append(date_str + "\n")

        # 3. TRADE (Complex Breakdown)
        trade_links = tasks.get("trade", [])
        if trade_links:
            count = len(trade_links)
            
            # Slab Logic: 1->3, 2-3->5, 4-6->7, 7+->8
            if count == 1: total_trade_pts = 3
            elif count <= 3: total_trade_pts = 5
            elif count <= 6: total_trade_pts = 7
            else: total_trade_pts = 8
            
            daily_total += total_trade_pts
            
            # Visual Breakdown
            report_lines.append(f"#trade Total: {count} Trades")
            
            # Fake incremental breakdown for display
            current_pts = 0
            for i in range(1, count + 1):
                if i == 1: pts_add = 3
                elif i == 2: pts_add = 2 # 3+2=5
                elif i == 4: pts_add = 2 # 5+2=7
                elif i == 7: pts_add = 1 # 7+1=8
                else: pts_add = 0 # No extra points for 3rd, 5th, 6th
                
                if pts_add > 0:
                    report_lines.append(f"#trade {i} → +{pts_add} points")
                else:
                    report_lines.append(f"#trade {i} → 0 points (Slab Limit)")

            report_lines.append(f"Total Points for trade - {total_trade_pts}")
            for i, link in enumerate(trade_links, 1):
                report_lines.append(f"Post link {i} - {link}")
            report_lines.append("")

        # 4. TWITTER
        twitter_links = tasks.get("twitter", [])
        if twitter_links:
            count = len(twitter_links)
            pts = count * 2
            daily_total += pts
            report_lines.append(f"X Post ×{count} → {pts} pts")
            for link in twitter_links:
                report_lines.append(f"Post Link - {link}")
            report_lines.append(date_str + "\n")

        # TOTAL FOOTER
        report_lines.append(f"Today Total points of {user} - {daily_total} points")
        report_lines.append("-----------------------------")

    return "\n".join(report_lines)

# --- COMMANDS ---

@app.on_message(filters.command("today") & filters.private)
async def cmd_today(client, message):
    if message.from_user.id != ADMIN_ID: return
    
    report = generate_report_text(get_today_str())
    
    # Send in chunks if too long
    if len(report) > 4000:
        await message.reply(report[:4000])
        await message.reply(report[4000:])
    else:
        await message.reply(report)

if __name__ == "__main__":
    app.run()
