from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
from gtts import gTTS
import os

from keep_alive import keep_alive
keep_alive()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
client = OpenAI(api_key=OPENAI_API_KEY)
conversation_memory = {}

# 🟢 /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Namaste! Main tumhara ChatGPT bot hoon.\n"
        "Main yaad rakhta hoon aur voice reply de sakta hoon!\n\n"
        "🧠 Commands:\n"
        "/reset - memory clear karo\n"
        "/help - info dekho"
    )

# 🧹 /reset command
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    conversation_memory[user_id] = []
    await update.message.reply_text("🧠 Memory clear kar di gayi!")

# 📖 /help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✨ Main tumhara personal ChatGPT bot hoon!\n"
        "👉 Image ke liye abhi reply aayega 'coming soon' 🖼️\n"
        "👉 Voice reply auto milta hai.\n"
        "👉 /reset se memory clear hoti hai."
    )

# 💬 Main chat function
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_text = update.message.text.lower()

    # 🖼️ Agar user 'photo/image' bole to bas ye message bhejna hai
    if any(word in user_text for word in ["photo", "image", "picture", "pic", "bana do", "draw", "photo bana do"]):
        await update.message.reply_text("🖼️ Image generation feature coming soon!")
        return  # ❌ No OpenAI image call at all

    # 🧠 Memory initialize karo
    if user_id not in conversation_memory:
        conversation_memory[user_id] = []

    conversation_memory[user_id].append({"role": "user", "content": user_text})

    try:
        # 💬 ChatGPT reply
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a friendly assistant who replies in Hinglish."},
                *conversation_memory[user_id]
            ]
        )

        reply = response.choices[0].message.content
        await update.message.reply_text(reply)

        # 🔊 Voice reply
        try:
            tts = gTTS(reply, lang='hi')
            tts.save("voice.mp3")
            await update.message.reply_voice(voice=open("voice.mp3", "rb"))
            os.remove("voice.mp3")
        except Exception:
            pass

        conversation_memory[user_id].append({"role": "assistant", "content": reply})

        if len(conversation_memory[user_id]) > 10:
            conversation_memory[user_id] = conversation_memory[user_id][-10:]

    except Exception as e:
        await update.message.reply_text("⚠️ Chat error: " + str(e))

# 🧩 Bot setup
app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("reset", reset))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

print("🤖 Bot chal raha hai... enjoy chatting!")
app.run_polling()
