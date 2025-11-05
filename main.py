# main.py (FINAL SAFE MERGED VERSION)
# - Single-instance lockfile (prevents getUpdates Conflict)
# - Self-ping (keeps Render awake)
# - Gist backup/restore (optional, needs GITHUB_TOKEN)
# - Typing indicator sync fixed
# - All commands + broadcast + persistence

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
from gtts import gTTS
import os, asyncio, json, random, traceback, time, threading, requests, sys, signal

# keep_alive must exist in project (Flask server). It runs the HTTP endpoint.
from keep_alive import keep_alive
keep_alive()

# ========== CONFIG ==========
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # optional (gist backup)
RENDER_URL = os.getenv("RENDER_URL") or "https://telegram-chatgpt-bot-p3gm.onrender.com/"

if not OPENAI_API_KEY or not TELEGRAM_BOT_TOKEN:
    print("ERROR: Set OPENAI_API_KEY and TELEGRAM_BOT_TOKEN environment variables.")
    sys.exit(1)

client = OpenAI(api_key=OPENAI_API_KEY)
OWNER_ID = 7157701836  # your owner id

# ===== lockfile (prevent multiple getUpdates) =====
LOCKFILE = "bot_instance.lock"

def is_process_running(pid):
    try:
        # signal 0 does not kill but checks existence
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True

def create_lock_or_exit():
    # If lock exists, read pid and check if alive
    if os.path.exists(LOCKFILE):
        try:
            pid = int(open(LOCKFILE).read().strip())
            if is_process_running(pid):
                print(f"Another instance (pid={pid}) seems to be running. Exiting to avoid getUpdates Conflict.")
                # try notify owner that an instance attempted to start (best-effort)
                try:
                    from telegram import Bot
                    Bot(token=TELEGRAM_BOT_TOKEN).send_message(chat_id=OWNER_ID,
                        text=f"⚠️ Another instance attempted to start (pid={os.getpid()}). I exited to avoid conflict.")
                except Exception:
                    pass
                sys.exit(0)
            else:
                print("Stale lockfile found, removing and acquiring new lock.")
        except Exception:
            print("Bad lockfile contents, overwriting.")
    # write current pid
    try:
        with open(LOCKFILE, "w") as fh:
            fh.write(str(os.getpid()))
        print("Lock acquired, pid:", os.getpid())
    except Exception as e:
        print("Could not write lockfile:", e)
        sys.exit(1)

def remove_lockfile():
    try:
        if os.path.exists(LOCKFILE):
            os.remove(LOCKFILE)
            print("Lockfile removed.")
    except Exception as e:
        print("Failed to remove lockfile:", e)

# ensure lock created at start
create_lock_or_exit()
# remove lock gracefully on exit
def _graceful_exit(signum=None, frame=None):
    remove_lockfile()
    sys.exit(0)
signal.signal(signal.SIGTERM, _graceful_exit)
signal.signal(signal.SIGINT, _graceful_exit)

# ===== Files & Memory =====
conversation_memory = {}
USERS_FILE = "users.json"
ADMINS_FILE = "admins.json"
BANNED_FILE = "banned.json"
BROADCAST_FILE = "broadcast.json"
GIST_ID_FILE = "gist_id.txt"
FILES = [USERS_FILE, ADMINS_FILE, BANNED_FILE, BROADCAST_FILE]

for f in FILES:
    if not os.path.exists(f):
        try:
            with open(f, "w") as fh:
                json.dump([], fh)
        except Exception as e:
            print("Error creating file", f, e)

# ===== JSON helpers =====
def safe_load(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return []

def safe_save(path, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print("Error saving", path, e)

# ===== Data functions =====
def load_users(): return safe_load(USERS_FILE)
def save_users(data): safe_save(USERS_FILE, data)
def add_user(uid):
    u = load_users()
    if uid not in u:
        u.append(uid)
        save_users(u)

def load_admins(): return safe_load(ADMINS_FILE)
def save_admins(data): safe_save(ADMINS_FILE, data)
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

def load_banned(): return safe_load(BANNED_FILE)
def save_banned(data): safe_save(BANNED_FILE, data)
def ban_user(uid, reason=None, by=None):
    bans = load_banned()
    if not any(x.get("id") == uid for x in bans):
        bans.append({"id": uid, "reason": reason or "", "by": by or "", "time": int(time.time())})
        save_banned(bans)
def unban_user(uid):
    save_banned([b for b in load_banned() if b.get("id") != uid])
def is_banned(uid): return any(x.get("id") == uid for x in load_banned())

def load_broadcast(): return safe_load(BROADCAST_FILE)
def save_broadcast(data): safe_save(BROADCAST_FILE, data)

def short_users_text():
    u = load_users()
    if not u:
        return "No users yet."
    sample = u[:200]
    return f"👥 Total Users: {len(u)}\n" + "\n".join(map(str, sample))

def is_owner(uid): return uid == OWNER_ID
def is_admin(uid): return is_owner(uid) or (uid in load_admins())

# ===== GitHub Gist helpers (optional) =====
GIST_API = "https://api.github.com/gists"
GIST_FILENAMES = FILES

def read_local_gist_id():
    if os.path.exists(GIST_ID_FILE):
        try:
            return open(GIST_ID_FILE).read().strip()
        except:
            pass
    return None

def write_local_gist_id(gid):
    try:
        with open(GIST_ID_FILE, "w") as f:
            f.write(gid)
    except:
        pass

def create_gist_from_files():
    if not GITHUB_TOKEN:
        print("No GITHUB_TOKEN set; skipping gist create.")
        return None
    files_payload = {}
    for fn in GIST_FILENAMES:
        content = "[]"
        try:
            with open(fn, "r") as f:
                content = f.read()
        except:
            pass
        files_payload[fn] = {"content": content}
    body = {"description": "Bot JSON backup", "public": False, "files": files_payload}
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    try:
        resp = requests.post(GIST_API, json=body, headers=headers, timeout=15)
        if resp.status_code in (200,201):
            gid = resp.json().get("id")
            write_local_gist_id(gid)
            print("Created gist id:", gid)
            return gid
        else:
            print("Gist create failed:", resp.status_code, resp.text)
    except Exception as e:
        print("Gist create exception:", e)
    return None

def update_gist(gist_id):
    if not GITHUB_TOKEN or not gist_id:
        return False
    files_payload = {}
    for fn in GIST_FILENAMES:
        try:
            with open(fn, "r") as f:
                files_payload[fn] = {"content": f.read()}
        except:
            files_payload[fn] = {"content": "[]"}
    body = {"files": files_payload}
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    try:
        resp = requests.patch(f"{GIST_API}/{gist_id}", json=body, headers=headers, timeout=15)
        if resp.status_code == 200:
            print("Gist updated.")
            return True
        else:
            print("Gist update failed:", resp.status_code, resp.text)
    except Exception as e:
        print("Gist update exception:", e)
    return False

def restore_from_gist(gist_id):
    if not GITHUB_TOKEN or not gist_id:
        return False
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    try:
        resp = requests.get(f"{GIST_API}/{gist_id}", headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            files = data.get("files", {})
            for fname in GIST_FILENAMES:
                fobj = files.get(fname)
                if fobj:
                    content = fobj.get("content", "[]")
                    try:
                        with open(fname, "w") as fh:
                            fh.write(content)
                        print("Restored", fname, "from gist.")
                    except Exception as e:
                        print("Write restore error", fname, e)
            return True
        else:
            print("Gist fetch failed:", resp.status_code, resp.text)
    except Exception as e:
        print("Gist fetch exception:", e)
    return False

def startup_restore():
    need_restore = False
    for fn in GIST_FILENAMES:
        try:
            if not os.path.exists(fn) or os.path.getsize(fn) < 3:
                need_restore = True
        except:
            need_restore = True
    if not need_restore:
        return
    gist_id = read_local_gist_id()
    if gist_id:
        print("Attempting restore from local gist id:", gist_id)
        ok = restore_from_gist(gist_id)
        if ok:
            print("Restore from gist successful.")
            return
    if GITHUB_TOKEN:
        print("No valid gist restore found. Creating initial gist backup.")
        gid = create_gist_from_files()
        if gid:
            print("Initial gist created:", gid)

def start_periodic_backup(interval_seconds=600):
    def run():
        while True:
            try:
                gid = read_local_gist_id()
                if not gid and GITHUB_TOKEN:
                    gid = create_gist_from_files()
                if gid:
                    update_gist(gid)
            except Exception as e:
                print("Periodic backup error:", e)
            time.sleep(interval_seconds)
    t = threading.Thread(target=run, daemon=True)
    t.start()

# startup restore & periodic backup
startup_restore()
if GITHUB_TOKEN:
    start_periodic_backup(600)

# ===== Self-ping (keeps Render awake) =====
def start_self_ping(url, interval=240):
    def ping_loop():
        while True:
            try:
                r = requests.get(url, timeout=10)
                print("🔁 Self-ping status:", r.status_code)
            except Exception as e:
                print("⚠️ Self-ping failed:", e)
            time.sleep(interval)
    t = threading.Thread(target=ping_loop, daemon=True)
    t.start()

start_self_ping(RENDER_URL, interval=240)

# ===== Commands =====
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    add_user(user.id)
    await update.message.reply_text(
        "Namaste 📴! 😊 Main tumhara ChatGPT bot hoon. Tumhare har sawal ke jawab dene ke liye ready hu 💬⚡\n\n"
        "✏️ Sare commands dekhne ke liye 👉 /help\n"
        "(📘 For viewing all commands - type /help)\n\n"
        "💭 Ya fir apna sawal pucho chat me 🔥"
    )

async def whoami_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    role = "👑 Owner" if is_owner(uid) else "🛡 Admin" if is_admin(uid) else "🚫 Banned" if is_banned(uid) else "👤 User"
    await update.message.reply_text(f"🪪 *Your Info:*\nRole: {role}\nID: `{uid}`", parse_mode="Markdown")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📘 *Commands List*\n\n"
        "👑 *Owner:*\n"
        "/ma - Make Admin\n"
        "/ra - Remove Admin\n"
        "/mo - Transfer Ownership\n        /ban - Ban User/Admin\n"
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

# ===== Owner-only commands =====
async def ma_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_owner(uid):
        return await update.message.reply_text("🚫 *Sirf Owner ke liye hai.*", parse_mode="Markdown")
    if not context.args: return await update.message.reply_text("⚙️ Usage: /ma <user_id>")
    target = int(context.args[0]); add_admin(target)
    await update.message.reply_text(f"✅ User `{target}` ab Admin bana diya gaya hai!", parse_mode="Markdown")
    try:
        await context.bot.send_message(target, "🎉 *Congratulations!* Apka promotion ho gaya hai 🙌\nOwner ne apko Admin bana diya hai 🛡", parse_mode="Markdown")
    except: pass

async def ra_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_owner(uid):
        return await update.message.reply_text("🚫 *Sirf Owner hi kar sakte hain.*", parse_mode="Markdown")
    if not context.args: return await update.message.reply_text("⚙️ Usage: /ra <user_id>")
    target = int(context.args[0]); remove_admin(target)
    await update.message.reply_text(f"⚠️ User `{target}` ko Admin se hata diya gaya hai.", parse_mode="Markdown")
    try:
        await context.bot.send_message(target, "⚠️ Maaf kijiye 🙏 Apko Admin post se nikal diya gaya hai Owner ke dwara 😔", parse_mode="Markdown")
    except: pass

async def mo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global OWNER_ID
    uid = update.message.from_user.id
    if not is_owner(uid):
        return await update.message.reply_text("🚫 *Sirf Owner hi kar sakte hain.*", parse_mode="Markdown")
    if not context.args: return await update.message.reply_text("⚙️ Usage: /mo <user_id>")
    new_owner = int(context.args[0]); prev = OWNER_ID; OWNER_ID = new_owner
    await update.message.reply_text(f"👑 Ownership transfer ho gaya to `{new_owner}`", parse_mode="Markdown")
    try:
        await context.bot.send_message(new_owner, "👑 *Congratulations!* Ab aap bot ke naye Owner ban gaye hain 💼", parse_mode="Markdown")
    except: pass
    try:
        await context.bot.send_message(prev, f"ℹ️ Aapne ownership transfer kar di: new owner = {new_owner}")
    except: pass

async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_owner(uid):
        return await update.message.reply_text("🚫 *Sirf Owner hi kar sakte hain.*", parse_mode="Markdown")
    if not context.args: return await update.message.reply_text("⚙️ Usage: /ban <user_id> <reason>")
    target = int(context.args[0])
    if is_owner(target): return await update.message.reply_text("🚫 Owner ko ban nahi kar sakte.")
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "No reason given."
    ban_user(target, reason=reason, by=str(uid))
    try:
        await context.bot.send_message(target, f"❌ *Aapko ban kar diya gaya hai Owner ke dwara.*\nReason: {reason}\n🔓 Appeal: /appeal <reason>", parse_mode="Markdown")
    except: pass
    await update.message.reply_text(f"✅ User `{target}` ban kar diya gaya.", parse_mode="Markdown")

async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_owner(uid):
        return await update.message.reply_text("🚫 *Sirf Owner hi kar sakte hain.*", parse_mode="Markdown")
    if not context.args: return await update.message.reply_text("⚙️ Usage: /unban <user_id>")
    target = int(context.args[0]); unban_user(target)
    await update.message.reply_text(f"✅ User `{target}` unban ho gaya.", parse_mode="Markdown")
    try:
        await context.bot.send_message(target, "✅ *Aapka ban hata diya gaya hai.* Ab aap fir se bot use kar sakte hain 😄", parse_mode="Markdown")
    except: pass

# ===== Appeal =====
async def appeal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user; uid = user.id
    if not is_banned(uid): return await update.message.reply_text("ℹ️ Aap banned nahi hain.")
    if not context.args: return await update.message.reply_text("⚙️ Usage: /appeal <reason>")
    reason = " ".join(context.args)
    msg = f"📩 *Appeal Received*\nFrom: @{user.username or user.first_name} (`{uid}`)\nReason: {reason}\nUse /unban {uid} to approve."
    try: await context.bot.send_message(OWNER_ID, msg, parse_mode="Markdown")
    except: pass
    await update.message.reply_text("✅ Appeal bhej diya gaya Owner ko 🙏")

# ===== Admin + Owner utilities =====
async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_admin(uid):
        return await update.message.reply_text("🚫 *Admins/Owner only.*", parse_mode="Markdown")
    await update.message.reply_text(f"📊 Total Users: {len(load_users())} 👥", parse_mode="Markdown")

async def showusers_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_admin(uid):
        return await update.message.reply_text("🚫 *Admins/Owner only.*", parse_mode="Markdown")
    await update.message.reply_text(short_users_text())

async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_admin(uid):
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
    try:
        await context.bot.send_message(update.message.from_user.id, f"📢 *Broadcast Preview:*\n{msg}", parse_mode="Markdown")
    except: pass
    await update.message.reply_text(f"✅ Message bheja gaya {count} users ko.\n🗑 /removebroadcast se delete kar sakte ho.", parse_mode="Markdown")

async def removebroadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if not is_admin(uid):
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

# ===== Typing helper (reliable start/stop) =====
async def _start_typing_task(bot, chat_id, stop_event: asyncio.Event):
    try:
        while not stop_event.is_set():
            try:
                await bot.send_chat_action(chat_id=chat_id, action="typing")
            except:
                pass
            # send every 1.5 seconds while reply is generating
            await asyncio.sleep(1.5)
    except asyncio.CancelledError:
        pass

# ===== ChatGPT Handler (improved typing sync) =====
async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if is_banned(uid):
        return await update.message.reply_text("❌ Aap banned hain. 🔓 Use /appeal <reason>.")
    add_user(uid)

    if uid not in conversation_memory:
        conversation_memory[uid] = []

    text = update.message.text or ""
    conversation_memory[uid].append({"role": "user", "content": text})

    # start typing task before generation
    stop_event = asyncio.Event()
    typing_task = asyncio.create_task(_start_typing_task(context.bot, update.effective_chat.id, stop_event))

    try:
        # generate reply
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a friendly assistant who replies in Hinglish."}] + conversation_memory[uid]
        )
        reply = resp.choices[0].message.content.strip()

        # stop typing BEFORE sending final message so platform removes indicator immediately
        stop_event.set()
        # give tiny moment for task to stop
        await asyncio.sleep(0.05)
        try:
            typing_task.cancel()
        except:
            pass

        # send animated edit reply
        sent = await update.message.reply_text("...")
        shown = ""
        for i in range(0, len(reply), 8):
            new = reply[:i+8]
            if new != shown:
                shown = new
                try:
                    await sent.edit_text(shown)
                except:
                    pass
            await asyncio.sleep(0.001)
        try:
            await sent.edit_text(reply)
        except:
            pass

        # voice-on-demand
        if any(w in text.lower() for w in ["voice", "audio", "bol kar", "sunao", "voice me"]):
            try:
                tts = gTTS(reply, lang="hi")
                tts.save("voice.mp3")
                await update.message.reply_voice(voice=open("voice.mp3", "rb"))
                os.remove("voice.mp3")
            except Exception:
                await update.message.reply_text("⚠️ Voice generate karne me dikkat aayi.")

        # save conversation
        conversation_memory[uid].append({"role": "assistant", "content": reply})
        if len(conversation_memory[uid]) > 10:
            conversation_memory[uid] = conversation_memory[uid][-10:]

    except Exception as e:
        print("Chat error:", traceback.format_exc())
        await update.message.reply_text(f"⚠️ Chat error: {e}")
    finally:
        # ensure typing stopped
        try:
            stop_event.set()
            await asyncio.sleep(0.02)
            typing_task.cancel()
        except:
            pass

# ===== Setup & Run =====
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # commands
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("whoami", whoami_cmd))
    app.add_handler(CommandHandler("ma", ma_cmd))
    app.add_handler(CommandHandler("ra", ra_cmd))
    app.add_handler(CommandHandler("mo", mo_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("appeal", appeal_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("showusers", showusers_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("removebroadcast", removebroadcast_cmd))

    # chat handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))

    print("🤖 Bot running stable (self-ping + gist backup + lockfile + typing sync).")
    try:
        app.run_polling()
    finally:
        # cleanup lockfile on exit
        remove_lockfile()

if __name__ == "__main__":
    main()
