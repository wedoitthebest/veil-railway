import threading, time, webbrowser, os, uvicorn
from dotenv import load_dotenv
from db import init_db, log
from bot import main as bot_main

load_dotenv()

def web():
    uvicorn.run("app:app",host=os.getenv("HOST","127.0.0.1"),port=int(os.getenv("PORT","8787")))

if __name__=="__main__":
    init_db()
    log("INFO","Starting control center")
    threading.Thread(target=web,daemon=True).start()
    time.sleep(1)
    webbrowser.open("http://127.0.0.1:8787")
    bot_main()
