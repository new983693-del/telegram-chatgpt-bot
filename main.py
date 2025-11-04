from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
from gtts import gTTS
import os, asyncio
from keep_alive import keep_alive
keep_alive()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
client = OpenAI(api_key=OPENAI_API_KEY)
conversation_memory = {}

# ---------- commands ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Namaste! Main tumhara ChatGPT bot hoon.\n"
        "Mujhe kuch bhi pucho — reply ab ChatGPT-style animation me aayega 💬\n\n"
        "🧠 Commands:\n"
        "/reset – memory clear karo\n"
        "/help – info dekho"
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conversation_memory.pop(update.message.from_user.id, None)
    await update.message.reply_text("🧠 Memory clear kar di gayi!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✨ Main tumhara personal ChatGPT bot hoon!\n"
        "👉 Typing popup ab continuous chalega 💬\n"
        "👉 'voice me batao' likhne par voice reply milega 🔊"
    )

# ---------- chat ----------
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.lower()

    if any(w in text for w in ["photo","image","picture","pic","draw","bana do","photo bana do"]):
        await update.message.reply_text("🖼️ Image generation feature coming soon!")
        return

    if user_id not in conversation_memory:
        conversation_memory[user_id] = []
    conversation_memory[user_id].append({"role":"user","content":text})

    typing_active = True
    async def keep_typing():
        while typing_active:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            await asyncio.sleep(3)
    typing_task = asyncio.create_task(keep_typing())

    try:
        # ---- get GPT reply ----
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":"You are a friendly assistant who replies in Hinglish."},
                      *conversation_memory[user_id]]
        )
        reply = resp.choices[0].message.content.strip()

        # ---- DOT INTRO (blinking dots) ----
        sent = await update.message.reply_text("💬 Typing")
        for _ in range(6):  # 3 cycles of blinking dots
            for d in range(1,4):
                try:
                    await sent.edit_text("💬 Typing" + "."*d)
                except Exception:
                    pass
                await asyncio.sleep(0.18)

        # ---- ultra-fast type simulation ----
        chunk_size = 5      # characters per update
        delay = 0.003       # smaller = faster
        shown = ""

        for i in range(0, len(reply), chunk_size):
            new_text = reply[:i+chunk_size]
            if new_text != shown:
                shown = new_text
                try:
                    await sent.edit_text(shown)
                except Exception:
                    pass
            await asyncio.sleep(delay)

        # ensure final text
        try: await sent.edit_text(reply)
        except: pass

        typing_active = False
        typing_task.cancel()

        # ---- optional voice ----
        if any(w in text for w in ["voice","audio","bol kar","sunao","voice me"]):
            try:
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="record_voice")
                tts = gTTS(reply, lang="hi")
                tts.save("voice.mp3")
                await update.message.reply_voice(voice=open("voice.mp3","rb"))
                os.remove("voice.mp3")
            except Exception:
                await update.message.reply_text("⚠️ Voice generate karne me dikkat aayi.")

        # ---- memory ----
        conversation_memory[user_id].append({"role":"assistant","content":reply})
        if len(conversation_memory[user_id])>10:
            conversation_memory[user_id]=conversation_memory[user_id][-10:]

    except Exception as e:
        typing_active=False
        typing_task.cancel()
        await update.message.reply_text("⚠️ Chat error: "+str(e))

# ---------- setup ----------
app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("reset", reset))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

print("🤖 Bot chal raha hai... dot-intro + ultra-fast animation enabled ⚡💬")
app.run_polling()
