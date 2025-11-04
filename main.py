from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
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

# Files for saving user/admin data
USERS_FILE = "users.json"
ADMINS_FILE = "admins.json"

OWNER_ID = 7157701836  # 🔑 Replace with your own Telegram ID

# ========== STORAGE HELPERS ==========
def load_json(path):
    if not os.path.exists(path): return []
    with open(path, "r") as f: return json.load(f)

def save_json(path, data):
    with open(path, "w") as f: json.dump(data, f, indent=2)

def load_users(): return load_json(USERS_FILE)
def save_users(users): save_json(USERS_FILE, users)
def add_user(user_id):
    users = load_users()
    if user_id not in users:
        users.append(user_id)
        save_users(users)

def load_admins(): return load_json(ADMINS_FILE)
def save_admins(admins): save_json(ADMINS_FILE, admins)
def add_admin(user_id):
    admins = load_admins()
    if user_id not in admins:
        admins.append(user_id)
        save_admins(admins)

def is_admin(user_id):
    return user_id == OWNER_ID or user_id in load_admins()

# ========== UI HELPERS ==========
def main_menu():
    buttons = [
        [
            InlineKeyboardButton("🔁 Reset", callback_data="reset"),
            InlineKeyboardButton("ℹ️ Help", callback_data="help"),
            InlineKeyboardButton("🎙 Voice", callback_data="voice")
        ]
    ]
    return InlineKeyboardMarkup(buttons)

def generate_greeting(name):
    greetings = [
        f"Hey {name} 👋",
        f"Namaste {name}! 😊",
        f"Hello {name} 😎",
        f"Yo {name}! 🔥",
        f"Kya haal hai {name}? 🤖"
    ]
    return random.choice(greetings)

# ========== COMMANDS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    add_user(user.id)
    greet = f"Namaste {user.first_name if user.first_name else '📱'}! 😊"
    await update.message.reply_text(
        f"{greet} Main tumhara ChatGPT bot hoon. Tumhare har sawal ke jawab dene ke liye main ready hu 💬⚡",
        reply_markup=main_menu()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✨ Commands:\n"
        "/stats – total users (admin only)\n"
        "/broadcast <msg> – sabko message bhejna (admin)\n"
        "/ma <user_id> – kisi ko admin banana (owner only)",
        reply_markup=main_menu()
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conversation_memory.pop(update.message.from_user.id, None)
    await update.message.reply_text("🧠 Memory clear kar di gayi!", reply_markup=main_menu())

# ========== ADMIN COMMANDS ==========
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_admin(uid):
        await update.message.reply_text("🚫 *Yeh feature sirf Owner/Admins ke liye available hai.* 😎", parse_mode="Markdown")
        return
    users = load_users()
    await update.message.reply_text(f"📊 *Bot Users Stats*\nTotal Users: {len(users)} 👥", parse_mode="Markdown", reply_markup=main_menu())

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
    count = 0
    for u in users:
        try:
            await context.bot.send_message(chat_id=u, text=f"📢 *Broadcast:*\n{msg}", parse_mode="Markdown")
            count += 1
            await asyncio.sleep(0.03)
        except: pass
    await update.message.reply_text(f"✅ Message bheja gaya {count} users ko.", reply_markup=main_menu())

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

async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_admin(uid):
        await update.message.reply_text("🚫 *Yeh feature sirf Owner/Admins ke liye available hai.* 😎", parse_mode="Markdown")
        return
    admins = load_admins()
    msg = "👑 *Owner/Admin List:*\n"
    msg += f"• Owner: `{OWNER_ID}`\n"
    for a in admins:
        msg += f"• Admin: `{a}`\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

# ========== INLINE BUTTON HANDLER ==========
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "reset":
        conversation_memory.pop(q.from_user.id, None)
        await q.edit_message_text("🧠 Memory clear kar di gayi!", reply_markup=main_menu())
    elif q.data == "help":
        await q.edit_message_text("ℹ️ Type kuch bhi aur main reply karunga 💬", reply_markup=main_menu())
    elif q.data == "voice":
        await q.edit_message_text("🎙 Voice mode ready! Ab bolo 'voice me batao' 😄", reply_markup=main_menu())

# ========== CHAT FUNCTION ==========
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    user = update.message.from_user.first_name or "User"
    add_user(uid)
    text = update.message.text.lower()

    if uid not in conversation_memory:
        conversation_memory[uid] = []
        await update.message.reply_text(f"{generate_greeting(user)}! Main yaad rakhta hoon tumhe 🔥", reply_markup=main_menu())

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

        sent = await update.message.reply_text("...", reply_markup=main_menu())
        shown, chunk_size, delay = "", 8, 0.001
        for i in range(0, len(reply), chunk_size):
            new_text = reply[:i+chunk_size]
            if new_text != shown:
                shown = new_text
                try: await sent.edit_text(shown, reply_markup=main_menu())
                except: pass
            await asyncio.sleep(delay)
        try: await sent.edit_text(reply, reply_markup=main_menu())
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
                await update.message.reply_text("⚠️ Voice generate karne me dikkat aayi.", reply_markup=main_menu())

        conversation_memory[uid].append({"role": "assistant", "content": reply})
        if len(conversation_memory[uid]) > 10:
            conversation_memory[uid] = conversation_memory[uid][-10:]

    except Exception as e:
        typing_active = False
        typing_task.cancel()
        await update.message.reply_text(f"⚠️ Chat error: {e}", reply_markup=main_menu())

# ========== SETUP ==========
app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("reset", reset))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("broadcast", broadcast))
app.add_handler(CommandHandler("ma", make_admin))
app.add_handler(CommandHandler("admins", list_admins))
app.add_handler(CallbackQueryHandler(handle_buttons))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

print("🤖 Bot chal raha hai... Professional mode ON 💬⚡")
app.run_polling()
