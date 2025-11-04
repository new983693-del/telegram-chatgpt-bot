# main.py
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

# Replace with your actual Telegram ID (owner)
OWNER_ID = 123456789

# Conversation memory (in-memory short-term)
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

# Ensure files exist
ensure_file(USERS_FILE)
ensure_file(ADMINS_FILE)
ensure_file(BANNED_FILE)
ensure_file(BROADCAST_FILE)

# ========== USER / ADMIN / BAN HELPERS ==========
def load_users():
    return load_json(USERS_FILE)

def save_users(users):
    save_json(USERS_FILE, users)

def add_user(uid):
    users = load_users()
    if uid not in users:
        users.append(uid)
        save_users(users)

def load_admins():
    return load_json(ADMINS_FILE)

def save_admins(admins):
    save_json(ADMINS_FILE, admins)

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

def load_banned():
    return load_json(BANNED_FILE)

def save_banned(bans):
    save_json(BANNED_FILE, bans)

def ban_user(uid, reason=None, by=None):
    bans = load_banned()
    # store object for future potential use
    if not any(b.get("id") == uid for b in bans):
        bans.append({"id": uid, "reason": reason or "", "by": by or "", "time": asyncio.get_event_loop().time()})
        save_banned(bans)

def unban_user(uid):
    bans = load_banned()
    new = [b for b in bans if b.get("id") != uid]
    save_banned(new)

def is_banned(uid):
    bans = load_banned()
    return any(b.get("id") == uid for b in bans)

def load_broadcast_ids():
    return load_json(BROADCAST_FILE)

def save_broadcast_ids(data):
    save_json(BROADCAST_FILE, data)

# ========== UTILS ==========
def is_owner(uid):
    return uid == OWNER_ID

def is_admin(uid):
    return is_owner(uid) or (uid in load_admins())

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
    # avoid huge message: show count and up to first 200 IDs
    sample = users[:200]
    text = f"Total users: {len(users)}\nUser IDs (first {len(sample)}):\n" + "\n".join(map(str, sample))
    return text

async def send_priv_message(uid, text):
    try:
        app = context_app()  # will be bound later
        await app.bot.send_message(chat_id=uid, text=text)
    except Exception:
        pass

# We'll store application reference here to use in helpers if needed
_APP = None
def context_app():
    return _APP

# ========== COMMANDS ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    add_user(user.id)
    greet = f"Namaste {user.first_name if user.first_name else '📱'}! 😊"
    await update.message.reply_text(
        f"{greet} Main tumhara ChatGPT bot hoon. Tumhare har sawal ke jawab dene ke liye main ready hu 💬⚡"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✨ Available commands (based on role):\n"
        "/start - start\n"
        "/help - this message\n\n"
        "Owner only:\n"
        "/ma <user_id> - make admin\n"
        "/ra <user_id> - remove admin\n"
        "/mo <user_id> - make owner (transfer ownership)\n\n"
        "Admins & Owner:\n"
        "/stats - total users\n"
        "/broadcast <msg> - broadcast to all users\n"
        "/removebroadcast - delete last broadcast\n"
        "/showusers - show users (first 200)\n"
        "/ban <user_id> <reason?> - ban user (admins cannot ban the owner)\n"
        "/unban <user_id> - unban user\n\n"
        "If you're banned, use /appeal <reason> to appeal."
    )

# ===== Admin/Owner commands =====

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_admin(uid):
        await update.message.reply_text("🚫 *Yeh feature sirf Owner/Admins ke liye available hai.* 😎", parse_mode="Markdown")
        return
    users = load_users()
    await update.message.reply_text(f"📊 *Bot Users Stats*\nTotal Users: {len(users)} 👥", parse_mode="Markdown")

async def show_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_admin(uid):
        await update.message.reply_text("🚫 *Yeh feature sirf Owner/Admins ke liye available hai.* 😎", parse_mode="Markdown")
        return
    await update.message.reply_text(short_users_text())

async def make_admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if uid != OWNER_ID:
        await update.message.reply_text("🚫 *Yeh command sirf Bot Owner ke liye hai.* 👑", parse_mode="Markdown")
        return
    if len(context.args) < 1:
        await update.message.reply_text("⚙️ Usage: `/ma <user_id>`", parse_mode="Markdown")
        return
    try:
        new_admin = int(context.args[0])
    except:
        await update.message.reply_text("⚠️ Invalid user id.")
        return
    add_admin(new_admin)
    await update.message.reply_text(f"✅ User `{new_admin}` ab Admin bana diya gaya hai! 🔥", parse_mode="Markdown")

async def remove_admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if uid != OWNER_ID:
        await update.message.reply_text("🚫 *Yeh command sirf Bot Owner ke liye hai.* 👑", parse_mode="Markdown")
        return
    if len(context.args) < 1:
        await update.message.reply_text("⚙️ Usage: `/ra <user_id>`", parse_mode="Markdown")
        return
    try:
        rem = int(context.args[0])
    except:
        await update.message.reply_text("⚠️ Invalid user id.")
        return
    remove_admin(rem)
    await update.message.reply_text(f"✅ User `{rem}` ko Admin se hata diya gaya hai.")

async def make_owner_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if uid != OWNER_ID:
        await update.message.reply_text("🚫 *Yeh command sirf Bot Owner ke liye hai.* 👑", parse_mode="Markdown")
        return
    if len(context.args) < 1:
        await update.message.reply_text("⚙️ Usage: `/mo <user_id>`", parse_mode="Markdown")
        return
    try:
        new_owner = int(context.args[0])
    except:
        await update.message.reply_text("⚠️ Invalid user id.")
        return
    # transfer ownership
    global OWNER_ID
    previous_owner = OWNER_ID
    OWNER_ID = new_owner
    await update.message.reply_text(f"✅ Ownership transfer ho gaya. New Owner: `{new_owner}`", parse_mode="Markdown")
    # notify previous owner and new owner if possible
    try:
        await context.bot.send_message(chat_id=new_owner, text="👑 Aapko bot ka owner bana diya gaya hai.")
    except:
        pass
    try:
        await context.bot.send_message(chat_id=previous_owner, text=f"ℹ️ Aapne ownership transfer kar di: new owner = {new_owner}")
    except:
        pass

async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_admin(uid):
        await update.message.reply_text("🚫 *Yeh feature sirf Owner/Admins ke liye available hai.* 😎", parse_mode="Markdown")
        return
    msg = " ".join(context.args)
    if not msg:
        await update.message.reply_text("⚠️ Usage: `/broadcast <message>`", parse_mode="Markdown")
        return
    users = load_users()
    sent_records = []
    count = 0
    for u in users:
        try:
            m = await context.bot.send_message(chat_id=u, text=f"📢 *Broadcast:*\n{msg}", parse_mode="Markdown")
            sent_records.append({"chat_id": u, "msg_id": m.message_id})
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    save_broadcast_ids(sent_records)
    await update.message.reply_text(f"✅ Message bheja gaya {count} users ko.\n🗑 Agar galti se bheja, use /removebroadcast se hata sakte ho.", parse_mode="Markdown")

async def remove_broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_admin(uid):
        await update.message.reply_text("🚫 *Yeh feature sirf Owner/Admins ke liye available hai.* 😎", parse_mode="Markdown")
        return
    records = load_broadcast_ids()
    if not records:
        await update.message.reply_text("❌ Koi previous broadcast nahi mila.")
        return
    removed = 0
    for r in records:
        try:
            await context.bot.delete_message(chat_id=r["chat_id"], message_id=r["msg_id"])
            removed += 1
            await asyncio.sleep(0.02)
        except Exception:
            pass
    # clear stored broadcast
    if os.path.exists(BROADCAST_FILE):
        os.remove(BROADCAST_FILE)
    await update.message.reply_text(f"🗑 {removed} broadcast messages delete kar diye gaye.")

async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_admin(uid):
        await update.message.reply_text("🚫 *Yeh feature sirf Owner/Admins ke liye available hai.* 😎", parse_mode="Markdown")
        return
    if len(context.args) < 1:
        await update.message.reply_text("⚠️ Usage: `/ban <user_id> <optional reason>`", parse_mode="Markdown")
        return
    try:
        target = int(context.args[0])
    except:
        await update.message.reply_text("⚠️ Invalid user id.")
        return
    # Admin cannot ban owner
    if is_owner(target) and not is_owner(uid):
        await update.message.reply_text("🚫 Admins Owner ko ban nahi kar sakte.")
        return
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else ""
    ban_user(target, reason=reason, by=str(uid))
    # notify target if possible
    try:
        await context.bot.send_message(chat_id=target,
                                       text="❌ Aapko ban kar diya gaya hai.\n🔓 Agar ye galti se hua hai to /appeal <reason> likhiye.")
    except:
        pass
    await update.message.reply_text(f"✅ User `{target}` ko ban kar diya gaya.", parse_mode="Markdown")

async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_admin(uid):
        await update.message.reply_text("🚫 *Yeh feature sirf Owner/Admins ke liye available hai.* 😎", parse_mode="Markdown")
        return
    if len(context.args) < 1:
        await update.message.reply_text("⚠️ Usage: `/unban <user_id>`", parse_mode="Markdown")
        return
    try:
        target = int(context.args[0])
    except:
        await update.message.reply_text("⚠️ Invalid user id.")
        return
    # Admin can't unban owner? meaningless but keep rules: owner is owner (not banned normally)
    unban_user(target)
    # notify target
    try:
        await context.bot.send_message(chat_id=target, text="✅ Aapka ban hata diya gaya hai. Ab aap bot use kar sakte hain.")
    except:
        pass
    await update.message.reply_text(f"✅ User `{target}` ko unban kar diya gaya.", parse_mode="Markdown")

# Appeal: user calls /appeal <reason>
async def appeal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    uid = user.id
    if not is_banned(uid):
        await update.message.reply_text("ℹ️ Aap abhi banned nahi hain. Agar koi problem hai to contact admin.")
        return
    reason = " ".join(context.args).strip()
    if not reason:
        await update.message.reply_text("⚠️ Usage: /appeal <reason> — thoda detail me batao kyun aapko unban chahiye.")
        return

    # Prepare appeal message
    username = f"@{user.username}" if user.username else user.first_name or str(uid)
    appeal_text = (
        f"📩 *New Appeal Received*\n"
        f"From: {username} (`{uid}`)\n"
        f"Role: {'Admin' if uid in load_admins() else 'User'}\n"
        f"Reason: {reason}\n\n"
        f"Use /unban {uid} to unban if approved."
    )

    # If the banned person is an admin -> send appeal only to owner
    if uid in load_admins():
        # send only to owner
        try:
            await context.bot.send_message(chat_id=OWNER_ID, text=appeal_text, parse_mode="Markdown")
        except Exception:
            pass
        await update.message.reply_text("✅ Appeal bhej diya gaya Owner ko. Jaldi check karke wo action lenge.")
        return

    # else: normal user appeal -> send to all admins + owner individually
    receivers = set(load_admins())
    receivers.add(OWNER_ID)
    sent_count = 0
    for r in receivers:
        try:
            await context.bot.send_message(chat_id=r, text=appeal_text, parse_mode="Markdown")
            sent_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await update.message.reply_text(f"✅ Appeal bheja gaya {sent_count} admins/owner ko. Aapka wait kijiye.")

# ========== CHAT HANDLER ==========
# When a banned user sends any message, reply with ban notice & appeal hint (no normal chat)
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    user_name = update.message.from_user.first_name or "User"
    add_user(uid)

    # If banned -> special handling (no other actions allowed)
    if is_banned(uid):
        await update.message.reply_text(
            "❌ Aapko ban kar diya gaya hai.\n🔓 Agar ye galti se hua hai to appeal bhejne ke liye:\n"
            "Use: /appeal <reason>"
        )
        return

    text = update.message.text or ""
    text_lower = text.lower()

    # memory init + greeting once
    if uid not in conversation_memory:
        conversation_memory[uid] = []
        await update.message.reply_text(f"{generate_greeting(user_name)}! Main yaad rakhta hoon tumhe 🔥")

    conversation_memory[uid].append({"role": "user", "content": text_lower})

    # continuous typing indicator
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
        # Get GPT reply
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a friendly assistant replying in Hinglish casually."},
                *conversation_memory[uid]
            ]
        )
        reply = resp.choices[0].message.content.strip()

        # Animated fast reply
        sent = await update.message.reply_text("...")
        shown = ""
        chunk_size = 8
        delay = 0.0009  # ultra-fast as requested
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

        typing_active = False
        try:
            typing_task.cancel()
        except:
            pass

        # Voice on demand
        if any(w in text_lower for w in ["voice", "audio", "bol kar", "sunao", "voice me"]):
            try:
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="record_voice")
                tts = gTTS(reply, lang="hi")
                tts.save("voice.mp3")
                await update.message.reply_voice(voice=open("voice.mp3", "rb"))
                os.remove("voice.mp3")
            except Exception:
                await update.message.reply_text("⚠️ Voice generate karne me dikkat aayi.")

        # store assistant reply
        conversation_memory[uid].append({"role": "assistant", "content": reply})
        if len(conversation_memory[uid]) > 10:
            conversation_memory[uid] = conversation_memory[uid][-10:]

    except Exception as e:
        typing_active = False
        try:
            typing_task.cancel()
        except:
            pass
        tb = traceback.format_exc()
        print("Chat error:", tb)
        await update.message.reply_text(f"⚠️ Chat error: {e}")

# ========== SETUP / RUN ==========
def main():
    global _APP
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    _APP = app

    # command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", lambda u,c: reset(u,c)))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("showusers", show_users))
    app.add_handler(CommandHandler("ma", make_admin_cmd))
    app.add_handler(CommandHandler("ra", remove_admin_cmd))
    app.add_handler(CommandHandler("mo", make_owner_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("removebroadcast", remove_broadcast_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("appeal", appeal_cmd))

    # message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

    print("🤖 Bot chal raha hai... Full permissions & appeal system enabled.")
    app.run_polling()

if __name__ == "__main__":
    main()
