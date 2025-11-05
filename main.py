# main.py (FINAL SAFE MERGED VERSION ✅)
# Render-safe, no conflicts, single instance, auto self-ping, typing sync

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
from gtts import gTTS
import os, asyncio, json, time, threading, requests, signal, sys, traceback

# ---------------- KEEP ALIVE ----------------
from keep_alive import keep_alive
keep_alive()

# ---------------- CONFIG ----------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
RENDER_URL = os.getenv("RENDER_URL") or "https://telegram-chatgpt-bot-p3gm.onrender.com/"
OWNER_ID = 7157701836  # 👑 MAIN OWNER ID (edit here if needed)

if not OPENAI_API_KEY or not TELEGRAM_BOT_TOKEN:
    print("❌ Missing API keys. Please set OPENAI_API_KEY and TELEGRAM_BOT_TOKEN.")
    sys.exit(1)

client = OpenAI(api_key=OPENAI_API_KEY)

# ---------------- SINGLE INSTANCE LOCK ----------------
LOCKFILE = "bot_instance.lock"

def is_process_running(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def create_lock_or_exit():
    if os.path.exists(LOCKFILE):
        try:
            pid = int(open(LOCKFILE).read())
            if is_process_running(pid):
                print(f"⚠️ Instance already running (PID={pid}). Exiting to avoid conflict.")
                sys.exit(0)
        except:
            print("Old lockfile ignored.")
    with open(LOCKFILE, "w") as f:
        f.write(str(os.getpid()))
    print(f"🔒 Lock acquired (PID={os.getpid()})")

def remove_lockfile():
    try:
        if os.path.exists(LOCKFILE):
            os.remove(LOCKFILE)
            print("🧹 Lockfile removed.")
    except:
        pass

create_lock_or_exit()
signal.signal(signal.SIGTERM, lambda s, f: (remove_lockfile(), sys.exit(0)))
signal.signal(signal.SIGINT, lambda s, f: (remove_lockfile(), sys.exit(0)))

# ---------------- FILES & MEMORY ----------------
conversation_memory = {}
FILES = ["users.json", "admins.json", "banned.json", "broadcast.json"]

for f in FILES:
    if not os.path.exists(f):
        with open(f, "w") as fh:
            json.dump([], fh)

def load_json(path):
    try:
        return json.load(open(path))
    except:
        return []

def save_json(path, data):
    json.dump(data, open(path, "w"), indent=2)

def load_users(): return load_json("users.json")
def save_users(x): save_json("users.json", x)
def add_user(uid):
    u = load_users()
    if uid not in u:
        u.append(uid)
        save_users(u)

def load_admins(): return load_json("admins.json")
def save_admins(x): save_json("admins.json", x)
def add_admin(uid):
    a = load_admins()
    if uid not in a:
        a.append(uid)
        save_admins(a)
def remove_admin(uid):
    a = load_admins()
    if uid in a:
        a.remove(uid)
        save_admins(a)

def load_banned(): return load_json("banned.json")
def save_banned(x): save_json("banned.json", x)
def ban_user(uid, reason=None, by=None):
    bans = load_banned()
    if not any(b.get("id") == uid for b in bans):
        bans.append({"id": uid, "reason": reason or "", "by": by or "", "time": int(time.time())})
        save_banned(bans)
def unban_user(uid):
    save_banned([b for b in load_banned() if b.get("id") != uid])
def is_banned(uid): return any(b.get("id") == uid for b in load_banned())

def load_broadcast(): return load_json("broadcast.json")
def save_broadcast(x): save_json("broadcast.json", x)

def is_owner(uid): return uid == OWNER_ID
def is_admin(uid): return is_owner(uid) or uid in load_admins()

def short_users_text():
    u = load_users()
    return f"👥 Total Users: {len(u)}\n" + "\n".join(map(str, u[:200]))

# ---------------- SELF PING ----------------
def start_self_ping(url, interval=300):
    def loop():
        while True:
            try:
                r = requests.get(url, timeout=10)
                print("🔁 Self-ping:", r.status_code)
            except Exception as e:
                print("⚠️ Self-ping failed:", e)
            time.sleep(interval)
    threading.Thread(target=loop, daemon=True).start()

start_self_ping(RENDER_URL, 300)

# ---------------- COMMANDS ----------------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_user(update.message.from_user.id)
    await update.message.reply_text(
        "Namaste 📴! 😊 Main tumhara ChatGPT bot hoon. "
        "Tumhare har sawal ke jawab dene ke liye ready hu 💬⚡\n\n"
        "✏️ Sare commands dekhne ke liye 👉 /help\n"
        "(📘 For viewing all commands - type /help)\n\n"
        "💭 Ya fir apna sawal pucho chat me 🔥"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📘 *Commands List*\n\n"
        "👑 *Owner:*\n"
        "/ma /ra /mo /ban /unban\n\n"
        "🛡 *Admin + Owner:*\n"
        "/stats /showusers /broadcast /removebroadcast\n\n"
        "👤 *User:*\n"
        "/start /help /whoami /appeal\n\n"
        "⚙️ *Notes:*\nAdmins can’t ban Owner.\nBanned users can only use /appeal.",
        parse_mode="Markdown"
    )

async def whoami_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    role = "👑 Owner" if is_owner(uid) else "🛡 Admin" if is_admin(uid) else "🚫 Banned" if is_banned(uid) else "👤 User"
    await update.message.reply_text(f"🪪 *Your Info:*\nRole: {role}\nID: `{uid}`", parse_mode="Markdown")

# ---------------- ADMIN / OWNER COMMANDS ----------------
async def ma_cmd(update, context):
    if not is_owner(update.message.from_user.id):
        return await update.message.reply_text("🚫 Sirf Owner ke liye.")
    if not context.args: return await update.message.reply_text("⚙️ Usage: /ma <user_id>")
    uid = int(context.args[0])
    add_admin(uid)
    await update.message.reply_text(f"✅ `{uid}` ab Admin hai!")
    try: await context.bot.send_message(uid, "🎉 Apko Owner ne Admin bana diya 🛡")
    except: pass

async def ra_cmd(update, context):
    if not is_owner(update.message.from_user.id):
        return await update.message.reply_text("🚫 Sirf Owner ke liye.")
    if not context.args: return await update.message.reply_text("⚙️ Usage: /ra <user_id>")
    uid = int(context.args[0])
    remove_admin(uid)
    await update.message.reply_text(f"⚠️ `{uid}` ko Admin se hata diya gaya.")
    try: await context.bot.send_message(uid, "⚠️ Apko Admin se hata diya gaya hai.")
    except: pass

async def ban_cmd(update, context):
    if not is_owner(update.message.from_user.id):
        return await update.message.reply_text("🚫 Sirf Owner ke liye.")
    if not context.args: return await update.message.reply_text("⚙️ Usage: /ban <user_id> <reason>")
    uid = int(context.args[0])
    reason = " ".join(context.args[1:]) or "No reason."
    ban_user(uid, reason)
    await update.message.reply_text(f"✅ `{uid}` banned.")
    try: await context.bot.send_message(uid, f"❌ Apko ban kar diya gaya hai.\nReason: {reason}")
    except: pass

async def unban_cmd(update, context):
    if not is_owner(update.message.from_user.id):
        return await update.message.reply_text("🚫 Sirf Owner ke liye.")
    if not context.args: return await update.message.reply_text("⚙️ Usage: /unban <user_id>")
    uid = int(context.args[0])
    unban_user(uid)
    await update.message.reply_text(f"✅ `{uid}` unbanned.")
    try: await context.bot.send_message(uid, "✅ Apka ban hata diya gaya hai!")
    except: pass

async def stats_cmd(update, context):
    if not is_admin(update.message.from_user.id):
        return await update.message.reply_text("🚫 Admins/Owner only.")
    await update.message.reply_text(f"📊 Total Users: {len(load_users())}")

async def showusers_cmd(update, context):
    if not is_admin(update.message.from_user.id):
        return await update.message.reply_text("🚫 Admins/Owner only.")
    await update.message.reply_text(short_users_text())

async def broadcast_cmd(update, context):
    if not is_admin(update.message.from_user.id):
        return await update.message.reply_text("🚫 Admins/Owner only.")
    msg = " ".join(context.args)
    if not msg: return await update.message.reply_text("⚙️ Usage: /broadcast <message>")
    users = load_users()
    sent = 0; rec = []
    for u in users:
        try:
            m = await context.bot.send_message(u, f"📢 *Broadcast:*\n{msg}", parse_mode="Markdown")
            rec.append({"chat_id": u, "msg_id": m.message_id})
            sent += 1
            await asyncio.sleep(0.05)
        except: pass
    save_broadcast(rec)
    await update.message.reply_text(f"✅ Sent to {sent} users.\n🗑 /removebroadcast to delete all.")

async def removebroadcast_cmd(update, context):
    if not is_admin(update.message.from_user.id):
        return await update.message.reply_text("🚫 Admins/Owner only.")
    data = load_broadcast()
    count = 0
    for r in data:
        try:
            await context.bot.delete_message(r["chat_id"], r["msg_id"])
            count += 1
        except: pass
    save_broadcast([])
    await update.message.reply_text(f"🗑 Deleted {count} broadcast messages.")

# ---------------- CHATGPT HANDLER (TYPING FIXED) ----------------
async def _typing_loop(bot, chat_id, stop_event):
    try:
        while not stop_event.is_set():
            await bot.send_chat_action(chat_id=chat_id, action="typing")
            await asyncio.sleep(1.5)
    except asyncio.CancelledError:
        pass

async def chat(update, context):
    uid = update.message.from_user.id
    if is_banned(uid):
        return await update.message.reply_text("❌ Aap banned hain. 🔓 Use /appeal <reason>.")
    add_user(uid)

    if uid not in conversation_memory:
        conversation_memory[uid] = []

    text = update.message.text
    conversation_memory[uid].append({"role": "user", "content": text})

    stop_event = asyncio.Event()
    typing_task = asyncio.create_task(_typing_loop(context.bot, update.effective_chat.id, stop_event))

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a friendly assistant who replies in Hinglish."}] + conversation_memory[uid]
        )
        reply = resp.choices[0].message.content.strip()

        stop_event.set()
        await asyncio.sleep(0.05)
        typing_task.cancel()

        msg = await update.message.reply_text("...")
        for i in range(0, len(reply), 8):
            try: await msg.edit_text(reply[:i+8])
            except: pass
            await asyncio.sleep(0.001)
        await msg.edit_text(reply)

        if any(w in text.lower() for w in ["voice", "audio", "bol kar", "sunao", "voice me"]):
            try:
                tts = gTTS(reply, lang="hi")
                tts.save("voice.mp3")
                await update.message.reply_voice(voice=open("voice.mp3", "rb"))
                os.remove("voice.mp3")
            except:
                await update.message.reply_text("⚠️ Voice generate karne me dikkat aayi.")

        conversation_memory[uid].append({"role": "assistant", "content": reply})
        if len(conversation_memory[uid]) > 10:
            conversation_memory[uid] = conversation_memory[uid][-10:]
    except Exception as e:
        stop_event.set(); typing_task.cancel()
        await update.message.reply_text(f"⚠️ Chat error: {e}")
        print("Error:", traceback.format_exc())

# ---------------- RUN BOT ----------------
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    cmds = [
        ("start", start_cmd), ("help", help_cmd), ("whoami", whoami_cmd),
        ("ma", ma_cmd), ("ra", ra_cmd), ("ban", ban_cmd), ("unban", unban_cmd),
        ("stats", stats_cmd), ("showusers", showusers_cmd),
        ("broadcast", broadcast_cmd), ("removebroadcast", removebroadcast_cmd)
    ]
    for name, func in cmds:
        app.add_handler(CommandHandler(name, func))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("🤖 Bot running stable — clean logs, synced typing, single instance OK.")
    app.run_polling()

if __name__ == "__main__":
    main()
