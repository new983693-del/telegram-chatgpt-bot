from flask import Flask
from threading import Thread
import time, logging

app = Flask('')

@app.route('/')
def home():
    return "✅ Bot Alive - Flask Running Smoothly!"

def run():
    try:
        app.run(host='0.0.0.0', port=8080)
    except Exception as e:
        logging.error(f"Flask server crashed: {e}")
        time.sleep(2)
        run()  # auto-restart if crash

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
