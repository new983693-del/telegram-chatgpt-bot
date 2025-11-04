# main.py (Merged: Admin limited access + fixed broadcast/remove + pro messages)
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

OWNER_ID = 7157701836  # <- Your Owner ID

USERS_FILE = "users.json"
ADMINS_FILE = "admins.json"
BANNED_FILE = "banned.json"
BROADCAST_FILE = "broadcast.json"

# ensure files exist
for f in [USERS_FILE, ADMINS_FILE, BANNED_FILE, BROADCAST_FILE]:
    if not os.path.exists(f):
        with open(f, "w") as fh:
            json.dump([], fh)

# ========== HELPERS ==========
def load_json(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return []

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

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
    if not any(b.get("id") == uid for b in bans):
        bans.append({"id": uid, "reason": reason or "", "by": by or ""})
        save_banned(bans)

def unban_user(uid):
    bans = [b for b in load_banned() if b.get("id") != uid]
    save_banned(bans)

def is_banned(uid):
    return any(b.get("id") == uid for b in load_banned())

def load_broadcast_ids(): return load_json(BROADCAST_FILE)
def save_broadcast_ids(data): save_json(BROADCAST_FILE, data)

def is_owner(uid): return uid == OWNER_ID
def is_admin(uid): return is_owner(uid) or (uid in load_admins())

def generate_greeting(name):
    greetings = [
        f"Hey {name} 👋",
        f"Namaste {name}! 😊",
        f"Hello {name} 😎",
        f"Yo {name}! 🔥",
        f"Kya haal hai {name}? 🤖"
    ]
    return random.choice(greetings)

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

# /whoami
async def whoami_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if is_owner(uid): role = "👑 Owner"
    elif is_admin(uid): role = "🛡 Admin"
    elif is_banned(uid): role = "🚫 Banned"
    else: role = "👤 User"
    await update.message.reply_text(f"🪪 *Your Info:*\nRole: {role}\nID: `{uid}`", parse_mode="Markdown")

# /help (short commands + notes)
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📘 *Commands List*\n\n"
        "👑 *Owner Only:*\n"
        "/ma - Make Admin\n"
        "/ra - Remove Admin\n"
        "/mo - Transfer Ownership\n"
        "/ban - Ban User/Admin\n"
        "/unban - Unban User/Admin\n\n"
        "🛡 *Admin + Owner:*\n"
        "/stats - Total users\n"
        "/showusers - Show users list\n"
        "/broadcast - Send message to all users\n"
        "/removebroadcast - Delete last broadcast\n\n"
        "👤 *User Commands:*\n"
        "/start - Start bot\n"
        "/help - Show this list\n"
        "/whoami - Your Role Info\n"
        "/appeal - Request unban\n\n"
        "⚙️ *Notes:*\nAdmins can’t ban/unban Owner.\nBanned users can only use /appeal."
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ========== OWNER-ONLY (make admin / remove admin / make owner) ==========
async def ma_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_owner(uid):
        return await update.message.reply_text("🚫 *Yeh command sirf Owner ke liye hai.*", parse_mode="Markdown")
    if not context.args:
        return await update.message.reply_text("⚙️ Usage: /ma <user_id>")
    try:
        new_admin = int(context.args[0])
    except:
        return await update.message.reply_text("⚠️ Invalid user id.")
    add_admin(new_admin)
    await update.message.reply_text(f"✅ User `{new_admin}` ab Admin bana diya gaya hai!", parse_mode="Markdown")
    # notify promoted user
    try:
        await context.bot.send_message(
            chat_id=new_admin,
            text="🎉 *Congratulations!* Apka promotion ho gaya hai 🙌\nOwner ne apko Admin bana diya hai 🛡",
            parse_mode="Markdown"
        )
    except:
        pass

async def ra_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_owner(uid):
        return await update.message.reply_text("🚫 *Sirf Owner hi remove kar sakte hain.*", parse_mode="Markdown")
    if not context.args:
        return await update.message.reply_text("⚙️ Usage: /ra <user_id>")
    try:
        target = int(context.args[0])
    except:
        return await update.message.reply_text("⚠️ Invalid user id.")
    remove_admin(target)
    await update.message.reply_text(f"⚠️ User `{target}` ko Admin se hata diya gaya hai.", parse_mode="Markdown")
    try:
        await context.bot.send_message(
            chat_id=target,
            text="⚠️ Maaf kijiye 🙏\nApko Admin post se nikal diya gaya hai Owner ke dwara 😔",
            parse_mode="Markdown"
        )
    except:
        pass

async def mo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global OWNER_ID
    uid = update.message.from_user.id
    if not is_owner(uid):
        return await update.message.reply_text("🚫 *Sirf Owner hi kar sakte hain.*", parse_mode="Markdown")
    if not context.args:
        return await update.message.reply_text("⚙️ Usage: /mo <user_id>")
    try:
        new_owner = int(context.args[0])
    except:
        return await update.message.reply_text("⚠️ Invalid user id.")
    prev = OWNER_ID
    OWNER_ID = new_owner
    await update.message.reply_text(f"👑 Ownership transfer ho gaya to `{new_owner}`", parse_mode="Markdown")
    # notify new owner
    try:
        await context.bot.send_message(
            chat_id=new_owner,
            text="👑 *Congratulations!* Ab aap bot ke naye Owner ban gaye hain 💼",
            parse_mode="Markdown"
        )
    except:
        pass
    # notify previous owner
    try:
        await context.bot.send_message(chat_id=prev, text=f"ℹ️ Aapne ownership transfer kar di: new owner = {new_owner}")
    except:
        pass

# ========== OWNER-ONLY: ban/unban ==========
async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_owner(uid):
        return await update.message.reply_text("🚫 *Yeh command sirf Owner ke liye hai.*", parse_mode="Markdown")
    if not context.args:
        return await update.message.reply_text("⚙️ Usage: /ban <user_id> <reason>")
    try:
        target = int(context.args[0])
    except:
        return await update.message.reply_text("⚠️ Invalid user id.")
    if is_owner(target):
        return await update.message.reply_text("🚫 Owner ko ban nahi kar sakte.")
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Koi reason nahi diya gaya."
    ban_user(target, reason=reason, by=str(uid))
    # notify target
    try:
        await context.bot.send_message(
            chat_id=target,
            text=f"❌ *Aapko ban kar diya gaya hai Owner ke dwara.*\nReason: {reason}\n🔓 Appeal: /appeal <reason>",
            parse_mode="Markdown"
        )
    except:
        pass
    await update.message.reply_text(f"✅ User `{target}` ko ban kar diya gaya.", parse_mode="Markdown")

async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_owner(uid):
        return await update.message.reply_text("🚫 *Sirf Owner hi kar sakte hain.*", parse_mode="Markdown")
    if not context.args:
        return await update.message.reply_text("⚙️ Usage: /unban <user_id>")
    try:
        target = int(context.args[0])
    except:
        return await update.message.reply_text("⚠️ Invalid user id.")
    unban_user(target)
    # notify target
    try:
        await context.bot.send_message(chat_id=target, text="✅ *Aapka ban hata diya gaya hai.* Ab aap fir se bot use kar sakte hain 😄", parse_mode="Markdown")
    except:
        pass
    await update.message.reply_text(f"✅ User `{target}` ko unban kar diya gaya.", parse_mode="Markdown")

# ========== APPEAL ==========
async def appeal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    uid = user.id
    if not is_banned(uid):
        return await update.message.reply_text("ℹ️ Aap banned nahi hain.")
    if not context.args:
        return await update.message.reply_text("⚙️ Usage: /appeal <reason>")
    reason = " ".join(context.args)
    username = f"@{user.username}" if user.username else user.first_name or str(uid)
    role = "Admin" if uid in load_admins() else "User"
    appeal_text = (
        f"📩 *New Appeal Received*\n"
        f"From: {username} (`{uid}`)\n"
        f"Role: {role}\n"
        f"Reason: {reason}\n\n"
        f"Use /unban {uid} to unban if approved."
    )
    # If banned admin => send only to owner
    if uid in load_admins():
        try:
            await context.bot.send_message(chat_id=OWNER_ID, text=appeal_text, parse_mode="Markdown")
        except:
            pass
        await update.message.reply_text("✅ Appeal bhej diya gaya Owner ko. Jaldi check karke wo action lenge.")
        return
    # else normal user -> notify all admins + owner
    receivers = set(load_admins())
    receivers.add(OWNER_ID)
    sent = 0
    for r in receivers:
        try:
            await context.bot.send_message(chat_id=r, text=appeal_text, parse_mode="Markdown")
            sent += 1
            await asyncio.sleep(0.03)
        except:
            pass
    await update.message.reply_text(f"✅ Appeal bheja gaya {sent} admins/owner ko. Aapka wait kijiye.")

# ========== ADMIN+OWNER: stats / showusers / broadcast / removebroadcast ==========
async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_admin(uid):
        return await update.message.reply_text("🚫 *Yeh feature sirf Admins/Owner ke liye hai.*", parse_mode="Markdown")
    users = load_users()
    await update.message.reply_text(f"📊 Total Users: {len(users)} 👥", parse_mode="Markdown")

async def showusers_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_admin(uid):
        return await update.message.reply_text("🚫 *Yeh feature sirf Admins/Owner ke liye hai.*", parse_mode="Markdown")
    await update.message.reply_text(short_users_text())

# broadcast: admins+owner allowed
async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_admin(uid):
        return await update.message.reply_text("🚫 *Sirf Admins/Owner kar sakte hain.*", parse_mode="Markdown")
    msg = " ".join(context.args)
    if not msg:
        return await update.message.reply_text("⚠️ Usage: /broadcast <message>")
    users = load_users()
    sent_records = []
    count = 0
    for u in users:
        try:
            m = await context.bot.send_message(chat_id=u, text=f"📢 *Broadcast:*\n{msg}", parse_mode="Markdown")
            sent_records.append({"chat_id": u, "msg_id": m.message_id})
            count += 1
            await asyncio.sleep(0.05)
        except:
            pass
    # Save sent records for possible removal
    save_broadcast_ids(sent_records)
    # send preview to sender so they see exact message
    try:
        await context.bot.send_message(chat_id=uid, text=f"📢 *Broadcast Preview:*\n{msg}", parse_mode="Markdown")
    except:
        pass
    await update.message.reply_text(f"✅ Message bheja gaya {count} users ko.\n🗑 Agar galti se bheja, use /removebroadcast se hata sakte ho.", parse_mode="Markdown")

async def removebroadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_admin(uid):
        return await update.message.reply_text("🚫 *Sirf Admins/Owner kar sakte hain.*", parse_mode="Markdown")
    records = load_broadcast_ids()
    if not records:
        return await update.message.reply_text("❌ Koi previous broadcast record nahi mila.")
    removed = 0
    for r in records:
        try:
            await context.bot.delete_message(chat_id=r.get("chat_id"), message_id=r.get("msg_id"))
            removed += 1
            await asyncio.sleep(0.02)
        except:
            pass
    # clear stored broadcast file
    save_broadcast_ids([])
    await update.message.reply_text(f"🗑 {removed} broadcast messages try kar ke delete kar diye gaye.", parse_mode="Markdown")

# ========== CHAT (GPT) ==========
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if is_banned(uid):
        return await update.message.reply_text("❌ Aap banned hain. 🔓 Use /appeal <reason>.")
    add_user(uid)
    text = update.message.text or ""
    text_lower = text.lower()

    if uid not in conversation_memory:
        conversation_memory[uid] = []
        # optional greeting on first message
        await update.message.reply_text(f"{generate_greeting(update.message.from_user.first_name or 'User')}! Main yaad rakhta hoon tumhe 🔥")

    conversation_memory[uid].append({"role": "user", "content": text_lower})

    # typing indicator
    typing_active = True
    async def keep_typing():
        while typing_active:
            try:
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            except:
                pass
            await asyncio.sleep(2)
    typing_task = asyncio.create_task(keep_typing())

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a friendly assistant who replies in Hinglish."}] + conversation_memory[uid]
        )
        reply = resp.choices[0].message.content.strip()

        sent = await update.message.reply_text("...")
        shown = ""
        chunk_size = 8
        delay = 0.001  # fast but safe
        for i in range(0, len(reply), chunk_size):
            new_text = reply[:i+chunk_size]
            if new_text != shown:
                shown = new_text
                try:
                    await sent.edit_text(shown)
                except:
                    pass
            await asyncio.sleep(delay)
        try:
            await sent.edit_text(reply)
        except:
            pass

        # voice-on-demand
        if any(w in text_lower for w in ["voice", "audio", "bol kar", "sunao", "voice me"]):
            try:
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="record_voice")
                tts = gTTS(reply, lang="hi")
                tts.save("voice.mp3")
                await update.message.reply_voice(voice=open("voice.mp3", "rb"))
                os.remove("voice.mp3")
            except:
                await update.message.reply_text("⚠️ Voice generate karne me dikkat aayi.")

        conversation_memory[uid].append({"role": "assistant", "content": reply})
        if len(conversation_memory[uid]) > 10:
            conversation_memory[uid] = conversation_memory[uid][-10:]

    except Exception as e:
        tb = traceback.format_exc()
        print("Chat error:", tb)
        await update.message.reply_text(f"⚠️ Chat error: {e}")
    finally:
        typing_active = False
        try:
            typing_task.cancel()
        except:
            pass

# ========== SETUP / RUN ==========
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # public
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("whoami", whoami_cmd))
    app.add_handler(CommandHandler("appeal", appeal_cmd))

    # owner-only
    app.add_handler(CommandHandler("ma", ma_cmd))
    app.add_handler(CommandHandler("ra", ra_cmd))
    app.add_handler(CommandHandler("mo", mo_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))

    # admin+owner (limited)
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("showusers", showusers_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("removebroadcast", removebroadcast_cmd))

    # chat messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

    print("🤖 Bot running — Owner+Admin rules applied, broadcasts fixed.")
    app.run_polling()

if __name__ == "__main__":
    main()
