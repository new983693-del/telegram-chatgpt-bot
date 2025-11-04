from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from openai import OpenAI
from gtts import gTTS
import os, asyncio, json, random
from keep_alive import keep_alive
keep_alive()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
client = OpenAI(api_key=OPENAI_API_KEY)
conversation_memory = {}

USERS_FILE = "users.json"

# ---------- Load/Save User Data ----------
def load_users():
    if not os.path.exists(USERS_FILE):
        return []
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def add_user(user_id):
    users = load_users()
    if user_id not in users:
        users.append(user_id)
        save_users(users)

# ---------- Greetings ----------
def generate_greeting(user_name: str):
    greetings = [
        f"Hey {user_name} 👋",
        f"Namaste {user_name}! 😊",
        f"Hello {user_name} 😎",
        f"Yo {user_name}! 🔥",
        f"Kya haal hai {user_name}? 🤖"
    ]
    return random.choice(greetings)

# ---------- Inline Buttons ----------
def main_menu():
    buttons = [
        [
            InlineKeyboardButton("🔁 Reset", callback_data="reset"),
            InlineKeyboardButton("ℹ️ Help", callback_data="help"),
            InlineKeyboardButton("🎙 Voice", callback_data="voice")
        ]
    ]
    return InlineKeyboardMarkup(buttons)

# ---------- Commands ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    add_user(user.id)
    greet = generate_greeting(user.first_name or "User")
    await update.message.reply_text(
        f"{greet}\nMain tumhara ChatGPT bot hoon.\n"
        "Fast animation aur smart replies ke sath ready hoon 💬⚡",
        reply_markup=main_menu()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✨ Commands:\n"
        "/reset – memory clear karo\n"
        "/stats – total users dekho\n"
        "'voice me batao' likhne par voice reply milta hai 🔊",
        reply_markup=main_menu()
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conversation_memory.pop(update.message.from_user.id, None)
    await update.message.reply_text("🧠 Memory clear kar di gayi!", reply_markup=main_menu())

# ---------- Stats command ----------
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_users()
    await update.message.reply_text(
        f"📊 Bot Users Stats\nTotal Users: {len(users)} 👥",
        reply_markup=main_menu()
    )

# ---------- Callback for Inline Buttons ----------
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "reset":
        conversation_memory.pop(query.from_user.id, None)
        await query.edit_message_text("🧠 Memory clear kar di gayi!", reply_markup=main_menu())
    elif query.data == "help":
        await query.edit_message_text("ℹ️ Type kuch bhi aur main reply karunga 💬", reply_markup=main_menu())
    elif query.data == "voice":
        await query.edit_message_text("🎙 Voice mode ready! Ab bolo 'voice me batao' 😄", reply_markup=main_menu())

# ---------- Chat ----------
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name or "User"
    add_user(user_id)

    text = update.message.text.lower()
    if any(w in text for w in ["photo","image","picture","pic","draw","bana do"]):
        await update.message.reply_text("🖼️ Image generation feature coming soon!", reply_markup=main_menu())
        return

    if user_id not in conversation_memory:
        conversation_memory[user_id] = []
        await update.message.reply_text(f"{generate_greeting(user_name)}! Main Ready Hu🔥", reply_markup=main_menu())

    conversation_memory[user_id].append({"role": "user", "content": text})

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
                {"role": "system", "content": "You are a friendly AI assistant who replies in Hinglish."},
                *conversation_memory[user_id]
            ]
        )
        reply = resp.choices[0].message.content.strip()

        sent = await update.message.reply_text("...", reply_markup=main_menu())
        chunk_size, delay, shown = 8, 0.0012, ""
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
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="record_voice")
            tts = gTTS(reply, lang="hi")
            tts.save("voice.mp3")
            await update.message.reply_voice(voice=open("voice.mp3","rb"))
            os.remove("voice.mp3")

        conversation_memory[user_id].append({"role": "assistant","content": reply})
        if len(conversation_memory[user_id]) > 10:
            conversation_memory[user_id] = conversation_memory[user_id][-10:]

    except Exception as e:
        typing_active = False
        typing_task.cancel()
        await update.message.reply_text(f"⚠️ Chat error: {e}", reply_markup=main_menu())

# ---------- Setup ----------
app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("reset", reset))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CallbackQueryHandler(handle_buttons))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

print("🤖 Bot chal raha hai... inline buttons + user counter + ultra-fast mode 💬⚡")
app.run_polling()
