import os, uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from db import init_db, cfg, save, logs, history, stats, DEFAULT, log
from eldorado_sync import sync_eldorado_products

load_dotenv()
init_db()
app=FastAPI(title="Veil Control Center")
app.mount("/static",StaticFiles(directory="static"),name="static")

class Payload(BaseModel):
    config: dict

@app.get("/")
def home(): return FileResponse("static/index.html")

@app.get("/api/config")
def get_config(): return cfg()

@app.post("/api/config")
def set_config(p:Payload):
    save(p.config); log("INFO","Saved from dashboard"); return {"ok":True}

@app.post("/api/reset")
def reset():
    save(DEFAULT); log("WARN","Reset config"); return {"ok":True}

@app.get("/api/logs")
def get_logs(): return logs()

@app.get("/api/history")
def get_history(): return history()

@app.get("/api/stats")
def get_stats(): return stats()

@app.post("/api/eldorado/sync")
def eldorado_sync_endpoint():
    try:
        return sync_eldorado_products()
    except Exception as exc:
        log("ERROR", f"Eldorado sync failed: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))

def main():
    uvicorn.run("app:app",host=os.getenv("HOST","127.0.0.1"),port=int(os.getenv("PORT","8787")))

if __name__=="__main__":
    main()
