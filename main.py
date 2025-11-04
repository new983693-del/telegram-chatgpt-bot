# main.py (FINAL PRO OWNER CONTROL VERSION)
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
from gtts import gTTS
import os, asyncio, json, random, traceback
from keep_alive import keep_alive

keep_alive()

# ========== CONFIG ==========
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
client = OpenAI(api_key=OPENAI_API_KEY)

OWNER_ID = 7157701836  # <- Your Owner ID

FILES = ["users.json", "admins.json", "banned.json", "broadcast.json"]
for f in FILES:
    if not os.path.exists(f): open(f, "w").write("[]")

# ========== UTILS ==========
def load_json(f): return json.load(open(f)) if os.path.exists(f) else []
def save_json(f, data): json.dump(data, open(f, "w"), indent=2)

def load_users(): return load_json("users.json")
def save_users(d): save_json("users.json", d)
def add_user(uid):
    users = load_users()
    if uid not in users:
        users.append(uid)
        save_users(users)

def load_admins(): return load_json("admins.json")
def save_admins(d): save_json("admins.json", d)
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

def load_banned(): return load_json("banned.json")
def save_banned(d): save_json("banned.json", d)
def ban_user(uid, reason=None, by=None):
    bans = load_banned()
    if not any(b["id"] == uid for b in bans):
        bans.append({"id": uid, "reason": reason or "", "by": by or ""})
        save_banned(bans)

def unban_user(uid):
    bans = [b for b in load_banned() if b["id"] != uid]
    save_banned(bans)

def is_owner(uid): return uid == OWNER_ID
def is_admin(uid): return uid in load_admins()
def is_banned(uid): return any(b["id"] == uid for b in load_banned())

conversation_memory = {}

# ========== COMMANDS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_user(update.message.from_user.id)
    user = update.message.from_user
    await update.message.reply_text(
        f"Namaste {user.first_name if user.first_name else '📱'}! 😊 "
        f"Main tumhara ChatGPT bot hoon. Tumhare har sawal ke jawab dene ke liye main ready hu 💬⚡"
    )

# /whoami
async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if is_owner(uid): role = "👑 Owner"
    elif is_admin(uid): role = "🛡 Admin"
    elif is_banned(uid): role = "🚫 Banned"
    else: role = "👤 User"
    await update.message.reply_text(f"🪪 *Your Info:*\nRole: {role}\nID: `{uid}`", parse_mode="Markdown")

# /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📘 *Commands List*\n\n"
        "👑 *Owner Only:*\n"
        "/ma - Make Admin\n"
        "/ra - Remove Admin\n"
        "/mo - Transfer Ownership\n"
        "/ban - Ban User/Admin\n"
        "/unban - Unban User/Admin\n"
        "/broadcast - Send message to all\n"
        "/removebroadcast - Delete broadcast\n"
        "/showusers - Show all users\n"
        "/stats - Total user count\n\n"
        "👤 *User Commands:*\n"
        "/start - Start bot\n"
        "/help - Show this list\n"
        "/whoami - Your Role Info\n"
        "/appeal - Request unban\n\n"
        "⚙️ *Notes:*\nAdmins can’t ban/unban Owner.\nBanned users can only use /appeal."
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# /ma - make admin
async def make_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_owner(uid):
        return await update.message.reply_text("🚫 *Yeh command sirf Owner ke liye hai.*", parse_mode="Markdown")
    if not context.args: return await update.message.reply_text("⚙️ Usage: /ma <user_id>")
    new_admin = int(context.args[0])
    add_admin(new_admin)
    await update.message.reply_text(f"✅ User `{new_admin}` ab Admin bana diya gaya hai!", parse_mode="Markdown")
    try:
        await context.bot.send_message(
            chat_id=new_admin,
            text="🎉 *Congratulations!* Apka promotion ho gaya hai 🙌\nOwner ne apko Admin bana diya hai 🛡",
            parse_mode="Markdown"
        )
    except: pass

# /ra - remove admin
async def remove_admin_cmd(update, context):
    uid = update.message.from_user.id
    if not is_owner(uid):
        return await update.message.reply_text("🚫 *Sirf Owner hi remove kar sakte hain.*", parse_mode="Markdown")
    if not context.args: return await update.message.reply_text("⚙️ Usage: /ra <user_id>")
    target = int(context.args[0])
    remove_admin(target)
    await update.message.reply_text(f"⚠️ User `{target}` ko Admin se hata diya gaya hai.", parse_mode="Markdown")
    try:
        await context.bot.send_message(
            chat_id=target,
            text="⚠️ Maaf kijiye 🙏\nApko Admin post se nikal diya gaya hai Owner ke dwara 😔",
            parse_mode="Markdown"
        )
    except: pass

# /mo - make owner
async def make_owner(update, context):
    global OWNER_ID
    uid = update.message.from_user.id
    if not is_owner(uid):
        return await update.message.reply_text("🚫 *Sirf Owner hi kar sakte hain.*")
    if not context.args: return await update.message.reply_text("⚙️ Usage: /mo <user_id>")
    new_owner = int(context.args[0])
    prev_owner = OWNER_ID
    OWNER_ID = new_owner
    await update.message.reply_text(f"👑 Ownership transfer ho gaya to `{new_owner}`", parse_mode="Markdown")
    try:
        await context.bot.send_message(
            chat_id=new_owner,
            text="👑 *Congratulations!* Ab aap bot ke naye Owner ban gaye hain 💼",
            parse_mode="Markdown"
        )
    except: pass

# /ban
async def ban_cmd(update, context):
    uid = update.message.from_user.id
    if not is_owner(uid):  # Only owner now
        return await update.message.reply_text("🚫 *Yeh command sirf Owner ke liye hai.*", parse_mode="Markdown")
    if not context.args: return await update.message.reply_text("⚙️ Usage: /ban <user_id> <reason>")
    target = int(context.args[0])
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Koi reason nahi diya gaya."
    if is_owner(target): return await update.message.reply_text("🚫 Owner ko ban nahi kar sakte.")
    ban_user(target, reason, by=str(uid))
    try:
        await context.bot.send_message(
            chat_id=target,
            text=f"❌ *Aapko ban kar diya gaya hai Owner ke dwara.*\nReason: {reason}\n🔓 Appeal: /appeal <reason>",
            parse_mode="Markdown"
        )
    except: pass
    await update.message.reply_text(f"✅ User `{target}` ban kar diya gaya.", parse_mode="Markdown")

# /unban
async def unban_cmd(update, context):
    uid = update.message.from_user.id
    if not is_owner(uid): return await update.message.reply_text("🚫 *Sirf Owner hi kar sakte hain.*")
    if not context.args: return await update.message.reply_text("⚙️ Usage: /unban <user_id>")
    target = int(context.args[0])
    unban_user(target)
    await update.message.reply_text(f"✅ User `{target}` unban ho gaya.", parse_mode="Markdown")
    try:
        await context.bot.send_message(
            chat_id=target,
            text="✅ *Aapka ban hata diya gaya hai.* Ab aap fir se bot use kar sakte hain 😄",
            parse_mode="Markdown"
        )
    except: pass

# /appeal
async def appeal(update, context):
    user = update.message.from_user
    uid = user.id
    if not is_banned(uid):
        return await update.message.reply_text("ℹ️ Aap banned nahi hain.")
    if not context.args:
        return await update.message.reply_text("⚙️ Usage: /appeal <reason>")
    reason = " ".join(context.args)
    name = f"@{user.username}" if user.username else user.first_name
    msg = f"📩 *Appeal Received*\nFrom: {name} (`{uid}`)\nReason: {reason}\nUse /unban {uid} to approve."
    try: await context.bot.send_message(chat_id=OWNER_ID, text=msg, parse_mode="Markdown")
    except: pass
    await update.message.reply_text("✅ Appeal bhej diya gaya Owner ko. Jaldi check hoga 🙏")

# /broadcast (Owner only)
async def broadcast(update, context):
    uid = update.message.from_user.id
    if not is_owner(uid):
        return await update.message.reply_text("🚫 *Sirf Owner kar sakte hain.*", parse_mode="Markdown")
    msg = " ".join(context.args)
    if not msg: return await update.message.reply_text("⚙️ Usage: /broadcast <message>")
    users = load_users()
    sent = 0
    for u in users:
        try:
            await context.bot.send_message(chat_id=u, text=f"📢 *Broadcast:*\n{msg}", parse_mode="Markdown")
            sent += 1
            await asyncio.sleep(0.03)
        except: pass
    await update.message.reply_text(f"✅ Message bheja gaya {sent} users ko.", parse_mode="Markdown")

# /removebroadcast dummy (Owner)
async def remove_broadcast(update, context):
    if not is_owner(update.message.from_user.id):
        return await update.message.reply_text("🚫 *Sirf Owner kar sakte hain.*")
    await update.message.reply_text("🗑 Broadcast messages removed (placeholder).")

# /showusers
async def showusers(update, context):
    if not is_owner(update.message.from_user.id):
        return await update.message.reply_text("🚫 *Sirf Owner kar sakte hain.*")
    users = load_users()
    await update.message.reply_text(f"👥 Total Users: {len(users)}\n" + "\n".join(map(str, users[:200])))

# /stats
async def stats(update, context):
    if not is_owner(update.message.from_user.id):
        return await update.message.reply_text("🚫 *Sirf Owner kar sakte hain.*")
    await update.message.reply_text(f"📊 Total Users: {len(load_users())}")

# Chat Handler (fixed)
async def chat(update, context):
    uid = update.message.from_user.id
    if is_banned(uid):
        return await update.message.reply_text("❌ Aap banned hain. 🔓 Use /appeal <reason>.")
    add_user(uid)
    text = update.message.text.lower()
    conversation_memory.setdefault(uid, []).append({"role": "user", "content": text})

    typing = True
    async def typing_loop():
        while typing:
            try: await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            except: pass
            await asyncio.sleep(2)
    task = asyncio.create_task(typing_loop())

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "Reply in Hinglish friendly tone."}] + conversation_memory[uid]
        )
        reply = resp.choices[0].message.content.strip()
        msg = await update.message.reply_text("...")
        chunk = ""
        for i in range(0, len(reply), 8):
            new = reply[:i+8]
            if new != chunk:
                chunk = new
                try: await msg.edit_text(chunk)
                except: pass
            await asyncio.sleep(0.001)
        try: await msg.edit_text(reply)
        except: pass
    except Exception as e:
        await update.message.reply_text(f"⚠️ Chat error: {e}")
    finally:
        typing = False
        task.cancel()

# ========== SETUP ==========
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("whoami", whoami))
    app.add_handler(CommandHandler("ma", make_admin))
    app.add_handler(CommandHandler("ra", remove_admin_cmd))
    app.add_handler(CommandHandler("mo", make_owner))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("appeal", appeal))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("removebroadcast", remove_broadcast))
    app.add_handler(CommandHandler("showusers", showusers))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("🤖 Bot running: Owner system, fixed animation & professional messages.")
    app.run_polling()

if __name__ == "__main__":
    main()
