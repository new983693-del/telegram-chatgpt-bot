from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
from gtts import gTTS
import os, asyncio, json, random
from keep_alive import keep_alive
keep_alive()

# ========== CONFIG ==========
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
client = OpenAI(api_key=OPENAI_API_KEY)
conversation_memory = {}

USERS_FILE = "users.json"
ADMINS_FILE = "admins.json"
BROADCAST_FILE = "broadcast.json"   # store last broadcast

OWNER_ID = 7157701836  # 🔑 replace with your Telegram ID

# ========== JSON HELPERS ==========
def load_json(path):
    if not os.path.exists(path): return []
    with open(path, "r") as f: return json.load(f)

def save_json(path, data):
    with open(path, "w") as f: json.dump(data, f, indent=2)

def load_users(): return load_json(USERS_FILE)
def save_users(u): save_json(USERS_FILE, u)
def add_user(uid):
    users = load_users()
    if uid not in users:
        users.append(uid)
        save_users(users)

def load_admins(): return load_json(ADMINS_FILE)
def save_admins(a): save_json(ADMINS_FILE, a)
def add_admin(uid):
    admins = load_admins()
    if uid not in admins:
        admins.append(uid)
        save_admins(admins)

def is_admin(uid): return uid == OWNER_ID or uid in load_admins()

# ========== UTILITIES ==========
def generate_greeting(name):
    greetings = [
        f"Hey {name} 👋",
        f"Namaste {name}! 😊",
        f"Hello {name} 😎",
        f"Yo {name}! 🔥",
        f"Kya haal hai {name}? 🤖"
    ]
    return random.choice(greetings)

def save_broadcast_ids(msg_ids):
    save_json(BROADCAST_FILE, msg_ids)

def load_broadcast_ids():
    if not os.path.exists(BROADCAST_FILE):
        return []
    return load_json(BROADCAST_FILE)

# ========== COMMANDS ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    add_user(user.id)
    greet = f"Namaste {user.first_name if user.first_name else '📱'}! 😊"
    await update.message.reply_text(
        f"{greet} Main tumhara ChatGPT bot hoon. "
        "Tumhare har sawal ke jawab dene ke liye main ready hu 💬⚡"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✨ Commands:\n"
        "/stats – total users (admin only)\n"
        "/broadcast <msg> – sabko message bhejna (admin)\n"
        "/removebroadcast – last broadcast delete (admin)\n"
        "/ma <user_id> – kisi ko admin banana (owner only)"
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conversation_memory.pop(update.message.from_user.id, None)
    await update.message.reply_text("🧠 Memory clear kar di gayi!")

# ========== ADMIN COMMANDS ==========

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_admin(uid):
        await update.message.reply_text("🚫 *Yeh feature sirf Owner/Admins ke liye available hai.* 😎", parse_mode="Markdown")
        return
    users = load_users()
    await update.message.reply_text(f"📊 *Bot Users Stats*\nTotal Users: {len(users)} 👥", parse_mode="Markdown")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_admin(uid):
        await update.message.reply_text("🚫 *Yeh feature sirf Owner/Admins ke liye available hai.* 😎", parse_mode="Markdown")
        return

    msg = " ".join(context.args)
    if not msg:
        await update.message.reply_text("⚠️ Usage: `/broadcast <message>`", parse_mode="Markdown")
        return

    users = load_users()
    sent_ids = []
    count = 0

    for u in users:
        try:
            m = await context.bot.send_message(chat_id=u, text=f"📢 *Broadcast:*\n{msg}", parse_mode="Markdown")
            sent_ids.append({"chat_id": u, "msg_id": m.message_id})
            count += 1
            await asyncio.sleep(0.05)
        except:
            pass

    save_broadcast_ids(sent_ids)
    await update.message.reply_text(f"✅ Message bheja gaya {count} users ko.\n🗑 Agar galti se bheja, use /removebroadcast se hata sakte ho.")

async def remove_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_admin(uid):
        await update.message.reply_text("🚫 *Yeh feature sirf Owner/Admins ke liye available hai.* 😎", parse_mode="Markdown")
        return

    broadcast_msgs = load_broadcast_ids()
    if not broadcast_msgs:
        await update.message.reply_text("❌ Koi previous broadcast nahi mila.")
        return

    removed = 0
    for b in broadcast_msgs:
        try:
            await context.bot.delete_message(chat_id=b["chat_id"], message_id=b["msg_id"])
            removed += 1
            await asyncio.sleep(0.02)
        except:
            pass

    os.remove(BROADCAST_FILE)
    await update.message.reply_text(f"🗑 {removed} broadcast messages delete kar diye gaye.")

async def make_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if uid != OWNER_ID:
        await update.message.reply_text("🚫 *Yeh command sirf Bot Owner ke liye hai.* 👑", parse_mode="Markdown")
        return
    if len(context.args) < 1:
        await update.message.reply_text("⚙️ Usage: `/ma <user_id>`", parse_mode="Markdown")
        return
    new_admin = int(context.args[0])
    add_admin(new_admin)
    await update.message.reply_text(f"✅ User `{new_admin}` ab Admin bana diya gaya hai! 🔥", parse_mode="Markdown")

# ========== CHAT FUNCTION ==========
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    user = update.message.from_user.first_name or "User"
    add_user(uid)
    text = update.message.text.lower()

    if uid not in conversation_memory:
        conversation_memory[uid] = []
        await update.message.reply_text(f"{generate_greeting(user)}! Main yaad rakhta hoon tumhe 🔥")

    conversation_memory[uid].append({"role": "user", "content": text})

    typing_active = True
    async def keep_typing():
        while typing_active:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            await asyncio.sleep(2)
    typing_task = asyncio.create_task(keep_typing())

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a friendly assistant replying in Hinglish casually."},
                *conversation_memory[uid]
            ]
        )
        reply = resp.choices[0].message.content.strip()
        sent = await update.message.reply_text("...")
        shown, chunk_size, delay = "", 8, 0.001
        for i in range(0, len(reply), chunk_size):
            new_text = reply[:i+chunk_size]
            if new_text != shown:
                shown = new_text
                try: await sent.edit_text(shown)
                except: pass
            await asyncio.sleep(delay)
        try: await sent.edit_text(reply)
        except: pass

        typing_active = False
        typing_task.cancel()

        if any(w in text for w in ["voice","audio","bol kar","sunao","voice me"]):
            try:
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="record_voice")
                tts = gTTS(reply, lang="hi")
                tts.save("voice.mp3")
                await update.message.reply_voice(voice=open("voice.mp3","rb"))
                os.remove("voice.mp3")
            except Exception:
                await update.message.reply_text("⚠️ Voice generate karne me dikkat aayi.")

        conversation_memory[uid].append({"role": "assistant", "content": reply})
        if len(conversation_memory[uid]) > 10:
            conversation_memory[uid] = conversation_memory[uid][-10:]

    except Exception as e:
        typing_active = False
        typing_task.cancel()
        await update.message.reply_text(f"⚠️ Chat error: {e}")

# ========== SETUP ==========
app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("reset", reset))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("broadcast", broadcast))
app.add_handler(CommandHandler("removebroadcast", remove_broadcast))
app.add_handler(CommandHandler("ma", make_admin))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

print("🤖 Bot chal raha hai... Clean + Admin System + Broadcast Delete feature enabled 💬⚡")
app.run_polling()
