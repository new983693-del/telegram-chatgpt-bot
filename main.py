from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
from gtts import gTTS
import os, asyncio, random
from keep_alive import keep_alive
keep_alive()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
client = OpenAI(api_key=OPENAI_API_KEY)
conversation_memory = {}

# ---------------- GREETING HELPER ---------------- #
def generate_greeting(user_name: str):
    greetings = [
        f"Hey {user_name} 👋",
        f"Namaste {user_name}! 😊",
        f"Hello {user_name} 😎",
        f"Yo {user_name}! 🔥",
        f"Kya haal hai {user_name}? 🤖"
    ]
    return random.choice(greetings)

# ---------------- COMMANDS ---------------- #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user.first_name or "User"
    greet = generate_greeting(user)
    await update.message.reply_text(
        f"{greet}\nMain tumhara ChatGPT bot hoon.\n"
        "Fast animation aur smart replies ke sath ready hoon 💬⚡\n\n"
        "🧠 Commands:\n"
        "/reset – memory clear karo\n"
        "/help – info dekho"
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conversation_memory.pop(update.message.from_user.id, None)
    await update.message.reply_text("🧠 Memory clear kar di gayi!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user.first_name or "dost"
    await update.message.reply_text(
        f"{generate_greeting(user)}\n"
        "👉 Typing popup ab continuous chalega 💬\n"
        "👉 'voice me batao' likhne par voice reply milega 🔊"
    )

# ---------------- CHAT FUNCTION ---------------- #
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name or "User"
    text = update.message.text.lower()

    # 🖼 Image placeholder
    if any(w in text for w in ["photo", "image", "picture", "pic", "bana do", "draw"]):
        await update.message.reply_text("🖼️ Image generation feature coming soon!")
        return

    # 🧠 Memory init
    if user_id not in conversation_memory:
        conversation_memory[user_id] = []
        greeting = generate_greeting(user_name)
        await update.message.reply_text(f"{greeting}! Main yaad rakhta hoon tumhe 🔥")

    conversation_memory[user_id].append({"role": "user", "content": text})

    # 💭 Continuous typing indicator
    typing_active = True
    async def keep_typing():
        while typing_active:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            await asyncio.sleep(2)
    typing_task = asyncio.create_task(keep_typing())

    try:
        # 💬 GPT response
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a friendly AI assistant who replies in Hinglish, casual but clear."},
                *conversation_memory[user_id]
            ]
        )
        reply = resp.choices[0].message.content.strip()

        # ⚡ Ultra-fast animation
        sent = await update.message.reply_text("...")
        shown = ""
        chunk_size = 7     # characters per update
        delay = 0.0015     # ultra fast speed

        for i in range(0, len(reply), chunk_size):
            new_text = reply[:i+chunk_size]
            if new_text != shown:
                shown = new_text
                try:
                    await sent.edit_text(shown)
                except Exception:
                    pass
            await asyncio.sleep(delay)

        try:
            await sent.edit_text(reply)
        except:
            pass

        typing_active = False
        typing_task.cancel()

        # 🔊 Voice reply (on demand)
        if any(w in text for w in ["voice", "bol kar", "audio", "sunao", "voice me"]):
            try:
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="record_voice")
                tts = gTTS(reply, lang="hi")
                tts.save("voice.mp3")
                await update.message.reply_voice(voice=open("voice.mp3", "rb"))
                os.remove("voice.mp3")
            except Exception:
                await update.message.reply_text("⚠️ Voice generate karne me dikkat aayi.")

        # 🧠 Store memory
        conversation_memory[user_id].append({"role": "assistant", "content": reply})
        if len(conversation_memory[user_id]) > 10:
            conversation_memory[user_id] = conversation_memory[user_id][-10:]

    except Exception as e:
        typing_active = False
        typing_task.cancel()
        await update.message.reply_text(f"⚠️ Chat error: {e}")

# ---------------- BOT SETUP ---------------- #
app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("reset", reset))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

print("🤖 Bot chal raha hai... greetings + ultra-fast reply mode ON 💬⚡")
app.run_polling()
