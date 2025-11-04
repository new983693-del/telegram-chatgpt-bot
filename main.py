# main.py (Final Polished Version with /whoami + improved /help)
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes
)
from openai import OpenAI
from gtts import gTTS
import os, asyncio, json, random, traceback
from keep_alive import keep_alive

keep_alive()

# ========== CONFIG ==========
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
client = OpenAI(api_key=OPENAI_API_KEY)

# File names
USERS_FILE = "users.json"
ADMINS_FILE = "admins.json"
BANNED_FILE = "banned.json"
BROADCAST_FILE = "broadcast.json"

# Owner ID (as requested)
OWNER_ID = 7157701836

conversation_memory = {}

# ========== JSON HELPERS ==========
def load_json(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return []

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def ensure_file(path):
    if not os.path.exists(path):
        save_json(path, [])

for f in [USERS_FILE, ADMINS_FILE, BANNED_FILE, BROADCAST_FILE]:
    ensure_file(f)

# ========== HELPERS ==========
def load_users(): return load_json(USERS_FILE)
def save_users(data): save_json(USERS_FILE, data)
def add_user(uid):
    users = load_users()
    if uid not in users:
        users.append(uid)
        save_users(users)

def load_admins(): return load_json(ADMINS_FILE)
def save_admins(data): save_json(ADMINS_FILE, data)
def add_admin(uid):
    admins = load_admins()
    if uid not in admins:
        admins.append(uid)
        save_admins(admins)

def remove_admin(uid):
    admins = load_admins()
    if uid in admins:
        admins.remove(uid)
        save_admins(admins)

def load_banned(): return load_json(BANNED_FILE)
def save_banned(data): save_json(BANNED_FILE, data)
def ban_user(uid, reason=None, by=None):
    bans = load_banned()
    if not any(b["id"] == uid for b in bans):
        bans.append({"id": uid, "reason": reason or "", "by": by or ""})
        save_banned(bans)

def unban_user(uid):
    bans = load_banned()
    bans = [b for b in bans if b["id"] != uid]
    save_banned(bans)

def is_banned(uid):
    return any(b["id"] == uid for b in load_banned())

def is_owner(uid): return uid == OWNER_ID
def is_admin(uid): return uid == OWNER_ID or uid in load_admins()

def short_users_text():
    users = load_users()
    if not users:
        return "No users yet."
    sample = users[:200]
    return f"Total users: {len(users)}\nUser IDs (first {len(sample)}):\n" + "\n".join(map(str, sample))

# ========== COMMANDS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    add_user(user.id)
    greet = f"Namaste {user.first_name if user.first_name else '📱'}! 😊"
    await update.message.reply_text(
        f"{greet} Main tumhara ChatGPT bot hoon. Tumhare har sawal ke jawab dene ke liye main ready hu 💬⚡"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📘 *Bot Commands List*\n\n"
        "👑 *Owner Commands:*\n"
        "/ma - Make Admin\n"
        "/ra - Remove Admin\n"
        "/mo - Transfer Ownership\n"
        "/ban - Ban User/Admin\n"
        "/unban - Unban User/Admin\n"
        "/stats - Show total users\n"
        "/broadcast - Send message to all users\n"
        "/removebroadcast - Delete last broadcast\n"
        "/showusers - Show list of users\n\n"
        "🛡 *Admin Commands:*\n"
        "/stats - Show total users\n"
        "/broadcast - Send message to all users\n"
        "/removebroadcast - Delete last broadcast\n"
        "/showusers - Show list of users\n"
        "/ban - Ban a user\n"
        "/unban - Unban a user\n\n"
        "👤 *User Commands:*\n"
        "/start - Start the bot\n"
        "/help - Show this message\n"
        "/appeal - Send unban request\n"
        "/whoami - Show your role info\n\n"
        "⚙️ *Notes:*\n"
        "Admins can’t ban/unban the Owner.\n"
        "Banned users can only use /appeal.\n"
        "Appeals go directly to admins/owner privately."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

# 🧑‍💼 WHOAMI Command
async def whoami_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    role = "👑 Owner" if is_owner(uid) else "🛡 Admin" if is_admin(uid) else "🚫 Banned" if is_banned(uid) else "👤 User"
    await update.message.reply_text(f"🪪 *Your Info:*\nRole: {role}\nID: `{uid}`", parse_mode="Markdown")

# ====== Admin/Owner Core ======
async def stats_cmd(update, context):
    uid = update.message.from_user.id
    if not is_admin(uid):
        return await update.message.reply_text("🚫 *Yeh feature sirf Owner/Admins ke liye hai.*", parse_mode="Markdown")
    users = load_users()
    await update.message.reply_text(f"📊 Total Users: {len(users)} 👥", parse_mode="Markdown")

async def showusers_cmd(update, context):
    uid = update.message.from_user.id
    if not is_admin(uid):
        return await update.message.reply_text("🚫 *Yeh feature sirf Owner/Admins ke liye hai.*", parse_mode="Markdown")
    await update.message.reply_text(short_users_text())

async def make_admin_cmd(update, context):
    uid = update.message.from_user.id
    if not is_owner(uid):
        return await update.message.reply_text("🚫 *Sirf Owner kar sakte hain.* 👑", parse_mode="Markdown")
    if not context.args:
        return await update.message.reply_text("⚙️ Usage: /ma <user_id>")
    add_admin(int(context.args[0]))
    await update.message.reply_text(f"✅ User `{context.args[0]}` ab Admin bana diya gaya hai!", parse_mode="Markdown")

async def remove_admin_cmd(update, context):
    uid = update.message.from_user.id
    if not is_owner(uid):
        return await update.message.reply_text("🚫 *Sirf Owner kar sakte hain.* 👑", parse_mode="Markdown")
    if not context.args:
        return await update.message.reply_text("⚙️ Usage: /ra <user_id>")
    remove_admin(int(context.args[0]))
    await update.message.reply_text(f"✅ User `{context.args[0]}` Admin se hata diya gaya.", parse_mode="Markdown")

async def make_owner_cmd(update, context):
    global OWNER_ID
    uid = update.message.from_user.id
    if not is_owner(uid):
        return await update.message.reply_text("🚫 *Sirf Owner kar sakte hain.* 👑", parse_mode="Markdown")
    if not context.args:
        return await update.message.reply_text("⚙️ Usage: /mo <user_id>")
    new_owner = int(context.args[0])
    previous_owner = OWNER_ID
    OWNER_ID = new_owner
    await update.message.reply_text(f"✅ Ownership transfer ho gaya. New Owner: `{new_owner}`", parse_mode="Markdown")
    try:
        await context.bot.send_message(chat_id=new_owner, text="👑 Aapko bot ka owner bana diya gaya hai.")
    except: pass

# ====== Ban System ======
async def ban_cmd(update, context):
    uid = update.message.from_user.id
    if not is_admin(uid):
        return await update.message.reply_text("🚫 *Yeh feature sirf Owner/Admins ke liye hai.* 😎", parse_mode="Markdown")
    if not context.args:
        return await update.message.reply_text("⚙️ Usage: /ban <user_id> <reason>")
    target = int(context.args[0])
    if is_owner(target) and not is_owner(uid):
        return await update.message.reply_text("🚫 Admins Owner ko ban nahi kar sakte.")
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else ""
    ban_user(target, reason, by=str(uid))
    try:
        await context.bot.send_message(chat_id=target, text="❌ Aapko ban kar diya gaya hai.\n🔓 Use /appeal <reason> for unban.")
    except: pass
    await update.message.reply_text(f"✅ User `{target}` ban ho gaya.", parse_mode="Markdown")

async def unban_cmd(update, context):
    uid = update.message.from_user.id
    if not is_admin(uid):
        return await update.message.reply_text("🚫 *Yeh feature sirf Owner/Admins ke liye hai.* 😎", parse_mode="Markdown")
    if not context.args:
        return await update.message.reply_text("⚙️ Usage: /unban <user_id>")
    target = int(context.args[0])
    unban_user(target)
    try:
        await context.bot.send_message(chat_id=target, text="✅ Aapka ban hata diya gaya hai.")
    except: pass
    await update.message.reply_text(f"✅ User `{target}` unban ho gaya.", parse_mode="Markdown")

# ====== Broadcast ======
async def broadcast_cmd(update, context):
    uid = update.message.from_user.id
    if not is_admin(uid):
        return await update.message.reply_text("🚫 *Sirf Owner/Admins ke liye hai.*", parse_mode="Markdown")
    msg = " ".join(context.args)
    if not msg:
        return await update.message.reply_text("⚠️ Usage: /broadcast <message>", parse_mode="Markdown")
    users = load_users()
    records, count = [], 0
    for u in users:
        try:
            m = await context.bot.send_message(chat_id=u, text=f"📢 *Broadcast:*\n{msg}", parse_mode="Markdown")
            records.append({"chat_id": u, "msg_id": m.message_id})
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    save_json(BROADCAST_FILE, records)
    await context.bot.send_message(chat_id=uid, text=f"📢 *Broadcast Preview:*\n{msg}", parse_mode="Markdown")
    await update.message.reply_text(f"✅ Message bheja gaya {count} users ko.\n🗑 Use /removebroadcast to undo.", parse_mode="Markdown")

async def removebroadcast_cmd(update, context):
    uid = update.message.from_user.id
    if not is_admin(uid):
        return await update.message.reply_text("🚫 *Sirf Owner/Admins ke liye hai.*", parse_mode="Markdown")
    data = load_json(BROADCAST_FILE)
    removed = 0
    for r in data:
        try:
            await context.bot.delete_message(chat_id=r["chat_id"], message_id=r["msg_id"])
            removed += 1
            await asyncio.sleep(0.02)
        except: pass
    save_json(BROADCAST_FILE, [])
    await update.message.reply_text(f"🗑 {removed} broadcast messages delete kar diye gaye.")

# ====== Appeal ======
async def appeal_cmd(update, context):
    user = update.message.from_user
    uid = user.id
    if not is_banned(uid):
        return await update.message.reply_text("ℹ️ Aap banned nahi hain.")
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /appeal <reason>")
    reason = " ".join(context.args)
    username = f"@{user.username}" if user.username else user.first_name or str(uid)
    text = f"📩 *New Appeal*\nFrom: {username} (`{uid}`)\nReason: {reason}\nUse /unban {uid} to approve."
    receivers = [OWNER_ID] if uid in load_admins() else list(set(load_admins() + [OWNER_ID]))
    for r in receivers:
        try: await context.bot.send_message(chat_id=r, text=text, parse_mode="Markdown")
        except: pass
    await update.message.reply_text("✅ Appeal bhej diya gaya. Please wait for review.")

# ====== Chat GPT ======
async def chat(update, context):
    uid = update.message.from_user.id
    if is_banned(uid):
        return await update.message.reply_text("❌ Aapko ban kar diya gaya hai.\n🔓 Use /appeal <reason> to unban.")
    add_user(uid)
    text = update.message.text or ""
    text_lower = text.lower()

    if uid not in conversation_memory:
        conversation_memory[uid] = []
    conversation_memory[uid].append({"role": "user", "content": text_lower})

    typing_active = True
    async def keep_typing():
        while typing_active:
            try:
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            except: pass
            await asyncio.sleep(2)
    typing_task = asyncio.create_task(keep_typing())

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You reply in Hinglish."}] + conversation_memory[uid]
        )
        reply = resp.choices[0].message.content.strip()
        sent = await update.message.reply_text("...")
        chunk_size = 8
        for i in range(0, len(reply), chunk_size):
            try: await sent.edit_text(reply[:i+chunk_size])
            except: pass
            await asyncio.sleep(0.001)
        await sent.edit_text(reply)
        typing_active = False; typing_task.cancel()
        if any(w in text_lower for w in ["voice", "audio", "bol kar", "sunao", "voice me"]):
            tts = gTTS(reply, lang="hi"); tts.save("v.mp3")
            await update.message.reply_voice(voice=open("v.mp3", "rb"))
            os.remove("v.mp3")
    except Exception as e:
        typing_active = False; typing_task.cancel()
        await update.message.reply_text(f"⚠️ Chat error: {e}")

# ========== SETUP ==========
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("whoami", whoami_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("showusers", showusers_cmd))
    app.add_handler(CommandHandler("ma", make_admin_cmd))
    app.add_handler(CommandHandler("ra", remove_admin_cmd))
    app.add_handler(CommandHandler("mo", make_owner_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("removebroadcast", removebroadcast_cmd))
    app.add_handler(CommandHandler("appeal", appeal_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("🤖 Bot running with /whoami + short /help ready.")
    app.run_polling()

if __name__ == "__main__":
    main()
