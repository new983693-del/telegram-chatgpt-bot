# main.py (FINAL STABLE MERGED VERSION ✅)
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

OWNER_ID = 7157701836  # <-- your Owner ID

# memory & file setup
conversation_memory = {}
FILES = ["users.json", "admins.json", "banned.json", "broadcast.json"]
for f in FILES:
    if not os.path.exists(f): open(f, "w").write("[]")

# ===== JSON Helpers =====
def load_json(path):
    try: return json.load(open(path))
    except: return []
def save_json(path, data):
    json.dump(data, open(path, "w"), indent=2)

# ===== Data Functions =====
def load_users(): return load_json("users.json")
def save_users(data): save_json("users.json", data)
def add_user(uid):
    u = load_users()
    if uid not in u:
        u.append(uid)
        save_users(u)

def load_admins(): return load_json("admins.json")
def save_admins(data): save_json("admins.json", data)
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
def save_banned(data): save_json("banned.json", data)
def ban_user(uid, reason=None, by=None):
    bans = load_banned()
    if not any(x["id"] == uid for x in bans):
        bans.append({"id": uid, "reason": reason or "", "by": by or ""})
        save_banned(bans)
def unban_user(uid):
    save_banned([b for b in load_banned() if b["id"] != uid])
def is_banned(uid): return any(x["id"] == uid for x in load_banned())

def is_owner(uid): return uid == OWNER_ID
def is_admin(uid): return is_owner(uid) or uid in load_admins()

def load_broadcast(): return load_json("broadcast.json")
def save_broadcast(data): save_json("broadcast.json", data)

def short_users():
    u = load_users()
    return f"👥 Total Users: {len(u)}\n" + "\n".join(map(str, u[:200]))

# ===== Commands =====
async def start(update, context):
    user = update.message.from_user
    add_user(user.id)
    await update.message.reply_text(
        f"Namaste {user.first_name or '📱'}! 😊 Main tumhara ChatGPT bot hoon. "
        "Tumhare har sawal ke jawab dene ke liye ready hu 💬⚡"
    )

async def whoami(update, context):
    uid = update.message.from_user.id
    role = "👑 Owner" if is_owner(uid) else "🛡 Admin" if is_admin(uid) else "🚫 Banned" if is_banned(uid) else "👤 User"
    await update.message.reply_text(f"🪪 *Your Info:*\nRole: {role}\nID: `{uid}`", parse_mode="Markdown")

async def help_cmd(update, context):
    await update.message.reply_text(
        "📘 *Commands List*\n\n"
        "👑 *Owner:*\n"
        "/ma - Make Admin\n"
        "/ra - Remove Admin\n"
        "/mo - Transfer Ownership\n"
        "/ban - Ban User/Admin\n"
        "/unban - Unban User/Admin\n\n"
        "🛡 *Admin + Owner:*\n"
        "/stats - Total Users\n"
        "/showusers - Show Users\n"
        "/broadcast - Send Message to All\n"
        "/removebroadcast - Delete Broadcast\n\n"
        "👤 *User:*\n"
        "/start - Start Bot\n"
        "/help - Show Commands\n"
        "/whoami - Your Info\n"
        "/appeal - Request Unban\n\n"
        "⚙️ *Notes:*\nAdmins can’t ban/unban Owner.\nBanned users can only use /appeal.",
        parse_mode="Markdown"
    )

# ===== Owner Only =====
async def ma(update, context):
    if not is_owner(update.message.from_user.id):
        return await update.message.reply_text("🚫 *Sirf Owner ke liye hai.*", parse_mode="Markdown")
    if not context.args: return await update.message.reply_text("⚙️ Usage: /ma <user_id>")
    uid = int(context.args[0]); add_admin(uid)
    await update.message.reply_text(f"✅ User `{uid}` ab Admin bana diya gaya hai!", parse_mode="Markdown")
    try:
        await context.bot.send_message(uid, "🎉 *Congratulations!* Apka promotion ho gaya hai 🙌\nOwner ne apko Admin bana diya hai 🛡", parse_mode="Markdown")
    except: pass

async def ra(update, context):
    if not is_owner(update.message.from_user.id):
        return await update.message.reply_text("🚫 *Sirf Owner hi kar sakte hain.*", parse_mode="Markdown")
    if not context.args: return await update.message.reply_text("⚙️ Usage: /ra <user_id>")
    uid = int(context.args[0]); remove_admin(uid)
    await update.message.reply_text(f"⚠️ User `{uid}` ko Admin se hata diya gaya hai.", parse_mode="Markdown")
    try:
        await context.bot.send_message(uid, "⚠️ Maaf kijiye 🙏 Apko Admin post se nikal diya gaya hai Owner ke dwara 😔", parse_mode="Markdown")
    except: pass

async def mo(update, context):
    global OWNER_ID
    if not is_owner(update.message.from_user.id):
        return await update.message.reply_text("🚫 *Sirf Owner hi kar sakte hain.*", parse_mode="Markdown")
    if not context.args: return await update.message.reply_text("⚙️ Usage: /mo <user_id>")
    new_owner = int(context.args[0])
    prev = OWNER_ID; OWNER_ID = new_owner
    await update.message.reply_text(f"👑 Ownership transfer ho gaya to `{new_owner}`", parse_mode="Markdown")
    try: await context.bot.send_message(new_owner, "👑 *Congratulations!* Ab aap bot ke naye Owner ban gaye hain 💼", parse_mode="Markdown")
    except: pass

async def ban(update, context):
    if not is_owner(update.message.from_user.id):
        return await update.message.reply_text("🚫 *Sirf Owner hi kar sakte hain.*", parse_mode="Markdown")
    if not context.args: return await update.message.reply_text("⚙️ Usage: /ban <user_id> <reason>")
    uid = int(context.args[0])
    if is_owner(uid): return await update.message.reply_text("🚫 Owner ko ban nahi kar sakte.")
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "No reason given."
    ban_user(uid, reason)
    try: await context.bot.send_message(uid, f"❌ *Aapko ban kar diya gaya hai Owner ke dwara.*\nReason: {reason}\n🔓 Appeal: /appeal <reason>", parse_mode="Markdown")
    except: pass
    await update.message.reply_text(f"✅ User `{uid}` ban kar diya gaya.", parse_mode="Markdown")

async def unban(update, context):
    if not is_owner(update.message.from_user.id):
        return await update.message.reply_text("🚫 *Sirf Owner hi kar sakte hain.*", parse_mode="Markdown")
    if not context.args: return await update.message.reply_text("⚙️ Usage: /unban <user_id>")
    uid = int(context.args[0]); unban_user(uid)
    await update.message.reply_text(f"✅ User `{uid}` unban ho gaya.", parse_mode="Markdown")
    try: await context.bot.send_message(uid, "✅ *Aapka ban hata diya gaya hai.* Ab aap fir se bot use kar sakte hain 😄", parse_mode="Markdown")
    except: pass

# ===== Appeal =====
async def appeal(update, context):
    user = update.message.from_user
    uid = user.id
    if not is_banned(uid): return await update.message.reply_text("ℹ️ Aap banned nahi hain.")
    if not context.args: return await update.message.reply_text("⚙️ Usage: /appeal <reason>")
    reason = " ".join(context.args)
    msg = f"📩 *Appeal Received*\nFrom: @{user.username or user.first_name} (`{uid}`)\nReason: {reason}\nUse /unban {uid} to approve."
    try: await context.bot.send_message(OWNER_ID, msg, parse_mode="Markdown")
    except: pass
    await update.message.reply_text("✅ Appeal bhej diya gaya Owner ko 🙏")

# ===== Admin + Owner =====
async def stats(update, context):
    if not is_admin(update.message.from_user.id):
        return await update.message.reply_text("🚫 *Admins/Owner only.*", parse_mode="Markdown")
    await update.message.reply_text(f"📊 Total Users: {len(load_users())} 👥", parse_mode="Markdown")

async def showusers(update, context):
    if not is_admin(update.message.from_user.id):
        return await update.message.reply_text("🚫 *Admins/Owner only.*", parse_mode="Markdown")
    await update.message.reply_text(short_users())

async def broadcast(update, context):
    if not is_admin(update.message.from_user.id):
        return await update.message.reply_text("🚫 *Admins/Owner only.*", parse_mode="Markdown")
    msg = " ".join(context.args)
    if not msg: return await update.message.reply_text("⚙️ Usage: /broadcast <message>")
    users = load_users()
    rec, count = [], 0
    for u in users:
        try:
            m = await context.bot.send_message(u, f"📢 *Broadcast:*\n{msg}", parse_mode="Markdown")
            rec.append({"chat_id": u, "msg_id": m.message_id}); count += 1
            await asyncio.sleep(0.05)
        except: pass
    save_broadcast(rec)
    await context.bot.send_message(update.message.from_user.id, f"📢 *Broadcast Preview:*\n{msg}", parse_mode="Markdown")
    await update.message.reply_text(f"✅ Message bheja gaya {count} users ko.\n🗑 /removebroadcast se delete kar sakte ho.", parse_mode="Markdown")

async def removebroadcast(update, context):
    if not is_admin(update.message.from_user.id):
        return await update.message.reply_text("🚫 *Admins/Owner only.*", parse_mode="Markdown")
    data = load_broadcast()
    removed = 0
    for r in data:
        try:
            await context.bot.delete_message(r["chat_id"], r["msg_id"])
            removed += 1
        except: pass
    save_broadcast([])
    await update.message.reply_text(f"🗑 {removed} broadcast messages deleted.", parse_mode="Markdown")

# ===== ChatGPT Handler =====
async def chat(update, context):
    uid = update.message.from_user.id
    if is_banned(uid):
        return await update.message.reply_text("❌ Aap banned hain. 🔓 Use /appeal <reason>.")
    add_user(uid)
    global conversation_memory
    if uid not in conversation_memory: conversation_memory[uid] = []
    text = update.message.text.lower()
    conversation_memory[uid].append({"role": "user", "content": text})
    typing = True
    async def loop():
        while typing:
            try: await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            except: pass
            await asyncio.sleep(2)
    task = asyncio.create_task(loop())
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a friendly assistant who replies in Hinglish."}] + conversation_memory[uid]
        )
        reply = resp.choices[0].message.content.strip()
        msg = await update.message.reply_text("...")
        shown = ""
        for i in range(0, len(reply), 8):
            new = reply[:i+8]
            if new != shown:
                shown = new
                try: await msg.edit_text(shown)
                except: pass
            await asyncio.sleep(0.001)
        try: await msg.edit_text(reply)
        except: pass
    except Exception as e:
        await update.message.reply_text(f"⚠️ Chat error: {e}")
    finally:
        typing = False; task.cancel()

# ===== RUN =====
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("whoami", whoami))
    app.add_handler(CommandHandler("ma", ma))
    app.add_handler(CommandHandler("ra", ra))
    app.add_handler(CommandHandler("mo", mo))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("appeal", appeal))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("showusers", showusers))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("removebroadcast", removebroadcast))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("🤖 Bot running stable on Render (single instance, all permissions OK).")
    app.run_polling()

if __name__ == "__main__":
    main()
