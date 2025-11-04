from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
from gtts import gTTS
import os
import asyncio

from keep_alive import keep_alive
keep_alive()

# 🔑 Environment keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

client = OpenAI(api_key=OPENAI_API_KEY)
conversation_memory = {}

# 🟢 /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Namaste! Main tumhara ChatGPT bot hoon.\n"
        "Main yaad rakhta hoon aur voice me bhi reply kar sakta hoon jab tum bolo.\n\n"
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
        "👉 'voice me batao' ya 'bol kar bata' likhne par voice reply milega 🔊\n"
        "👉 /reset se memory clear hoti hai.\n"
        "👉 Ab reply ChatGPT jaisa animate hota hai 💬"
    )

# 💬 Main chat function
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_text = update.message.text.lower()

    # 🖼️ Image placeholder
    if any(word in user_text for word in ["photo", "image", "picture", "pic", "bana do", "draw", "photo bana do"]):
        await update.message.reply_text("🖼️ Image generation feature coming soon!")
        return

    # 🧠 Memory init
    if user_id not in conversation_memory:
        conversation_memory[user_id] = []

    conversation_memory[user_id].append({"role": "user", "content": user_text})

    try:
        # 💭 Typing indicator
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        # 💬 GPT reply
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a friendly assistant who replies in Hinglish."},
                *conversation_memory[user_id]
            ]
        )

        full_reply = response.choices[0].message.content

        # 🧩 ChatGPT-style animation
        display_text = ""
        sent_message = await update.message.reply_text("...")

        for char in full_reply:
            display_text += char
            # edit message continuously
            await sent_message.edit_text(display_text)
            await asyncio.sleep(0.02)  # typing speed
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        # 🎙️ Voice only if requested
        if any(word in user_text for word in ["voice", "bol kar", "audio", "sunao", "voice me"]):
            try:
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="record_voice")
                tts = gTTS(full_reply, lang='hi')
                tts.save("voice.mp3")
                await update.message.reply_voice(voice=open("voice.mp3", "rb"))
                os.remove("voice.mp3")
            except Exception:
                await update.message.reply_text("⚠️ Voice generate karne me dikkat aayi.")

        # 🧠 Memory update
        conversation_memory[user_id].append({"role": "assistant", "content": full_reply})
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

print("🤖 Bot chal raha hai... enjoy chatting with animation!")
app.run_polling()
