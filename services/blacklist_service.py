
import json
from pathlib import Path
from datetime import datetime

BLACKLIST_FILE = Path("data/blacklist.json")

def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def load_blacklist():
    BLACKLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not BLACKLIST_FILE.exists():
        return {"users": {}}
    try:
        data = json.loads(BLACKLIST_FILE.read_text(encoding="utf-8"))
        if "users" not in data:
            data = {"users": data if isinstance(data, dict) else {}}
        return data
    except Exception:
        return {"users": {}}

def save_blacklist(data):
    BLACKLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    BLACKLIST_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

def blacklist_user(user_id, reason, actor_id=None, actor_name=None):
    data = load_blacklist()
    uid = str(int(user_id))
    data["users"][uid] = {
        "user_id": uid,
        "reason": str(reason or "No reason provided."),
        "created_at": now_iso(),
        "actor_id": str(actor_id or ""),
        "actor_name": str(actor_name or ""),
    }
    save_blacklist(data)
    return data["users"][uid]

def unblacklist_user(user_id):
    data = load_blacklist()
    uid = str(int(user_id))
    removed = data["users"].pop(uid, None)
    save_blacklist(data)
    return removed

def is_blacklisted(user_id):
    data = load_blacklist()
    return data["users"].get(str(int(user_id)))

def list_blacklisted():
    data = load_blacklist()
    return list(data["users"].values())
