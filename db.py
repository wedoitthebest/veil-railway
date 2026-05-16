import sqlite3, json
from pathlib import Path
from datetime import datetime
from copy import deepcopy

DB = Path("data/app.db")

DEFAULT = {
    "server_name": "Veil's Grocery Store v1",
    "bot_status": "Veil's Grocery Store v1",
    "roles": [
        {"name":"Owner","color":"#7c3cff","hoist":True},
        {"name":"Admin","color":"#c43cff","hoist":True},
        {"name":"Moderator","color":"#3c8cff","hoist":True},
        {"name":"Trusted","color":"#46d39a","hoist":False},
        {"name":"Customer","color":"#ffd166","hoist":False},
        {"name":"Member","color":"#b8a8d9","hoist":False},
        {"name":"New User","color":"#888888","hoist":False},
        {"name":"Muted","color":"#333333","hoist":False}
    ],
    "structure": [
        {"name":"START HERE","channels":[{"name":"welcome","private":False},{"name":"rules","private":False},{"name":"announcements","private":False},{"name":"how-to-order","private":False}]},
        {"name":"SHOP","channels":[{"name":"products","private":False},{"name":"prices","private":False},{"name":"stock-updates","private":False},{"name":"vouches","private":False}]},
        {"name":"COMMUNITY","channels":[{"name":"general","private":False},{"name":"media","private":False},{"name":"memes","private":False}]},
        {"name":"SUPPORT","channels":[{"name":"create-ticket","private":False},{"name":"faq","private":False}]},
        {"name":"STAFF","channels":[{"name":"staff-chat","private":True},{"name":"logs","private":True}]}
    ],
    "starter_messages": {
        "welcome": "Welcome to **Veil's Grocery Store v1**.\n\nRead #rules and #how-to-order before opening a ticket.",
        "rules": "**Server Rules**\n\n1. Be respectful.\n2. No spam.\n3. No fake vouches.\n4. Open tickets only for real questions/orders.\n5. Do not DM staff unless told.",
        "how-to-order": "**How to Order**\n\n1. Check #products and #prices.\n2. Open a ticket in #create-ticket.\n3. Wait for staff confirmation.\n4. Follow the delivery instructions.",
        "faq": "**FAQ**\n\n**How do I order?** Open a ticket.\n**Where are products?** Check #products.\n**Where is proof?** Check #vouches."
    },
    "embeds": {
        "shop_panel": {"title":"Veil's Grocery Store v1","description":"Premium game items, clean service, fast support.\n\nOpen a ticket when you are ready to order.","color":8133887,"footer":"Veil Network"},
        "ticket_panel": {"title":"Create a Ticket","description":"Need help or want to order? Open a ticket and staff will respond.","color":8133887,"footer":"Support Team"},
        "vouch_panel": {"title":"Leave a Vouch","description":"Finished an order? Leave a clean vouch with what you bought and how it went.","color":8133887,"footer":"Thank you"}
    },
    "products": [
        {"name":"Game Item Bundle","category":"Game Items","price":"4.99","stock":10,"delivery":"Manual delivery","description":"Edit this product in the dashboard.","active":True}
    ],
    "ticket_settings": {"category_name":"TICKETS","staff_roles":["Owner","Admin","Moderator"],"panel_embed":"ticket_panel"},
    "vouch_settings": {"channel_name":"vouches","panel_embed":"vouch_panel"},
    "setup_runs": 0
}

def now():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def con():
    return sqlite3.connect(DB)

def init_db():
    Path("data").mkdir(exist_ok=True)
    with con() as c:
        c.execute("CREATE TABLE IF NOT EXISTS config(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY,created_at TEXT,level TEXT,message TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY,created_at TEXT,guild TEXT,result TEXT)")
    if not raw():
        save(DEFAULT)
        log("INFO","Created default memory")

def raw():
    with con() as c:
        r=c.execute("SELECT value FROM config WHERE key='main'").fetchone()
        return r[0] if r else None

def merge(default, current):
    if isinstance(default, dict) and isinstance(current, dict):
        result = deepcopy(default)
        for k, v in current.items():
            result[k] = merge(default.get(k), v) if k in default else v
        return result
    if current is None:
        return deepcopy(default)
    return current

def normalize_config(x):
    x = merge(DEFAULT, x if isinstance(x, dict) else {})
    if not x.get("roles"):
        x["roles"] = deepcopy(DEFAULT["roles"])
    if not x.get("structure"):
        x["structure"] = deepcopy(DEFAULT["structure"])
    if not x.get("products"):
        x["products"] = deepcopy(DEFAULT["products"])
    if not x.get("embeds"):
        x["embeds"] = deepcopy(DEFAULT["embeds"])
    return x

def cfg():
    r=raw()
    if not r:
        return deepcopy(DEFAULT)
    try:
        return normalize_config(json.loads(r))
    except Exception:
        return deepcopy(DEFAULT)

def save(x):
    x = normalize_config(x)
    with con() as c:
        c.execute("INSERT OR REPLACE INTO config VALUES('main',?)",(json.dumps(x,indent=2,ensure_ascii=False),))

def log(level,msg):
    with con() as c:
        c.execute("INSERT INTO logs(created_at,level,message) VALUES(?,?,?)",(now(),level,str(msg)))

def logs(limit=150):
    with con() as c:
        rows=c.execute("SELECT created_at,level,message FROM logs ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
    return [{"created_at":a,"level":b,"message":m} for a,b,m in rows]

def hist(guild,result):
    with con() as c:
        c.execute("INSERT INTO history(created_at,guild,result) VALUES(?,?,?)",(now(),guild,result))

def history(limit=80):
    with con() as c:
        rows=c.execute("SELECT created_at,guild,result FROM history ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
    return [{"created_at":a,"guild":g,"result":r} for a,g,r in rows]

def stats():
    x=cfg()
    return {
        "roles": len(x.get("roles",[])),
        "categories": len(x.get("structure",[])),
        "channels": sum(len(c.get("channels",[])) for c in x.get("structure",[])),
        "products": len(x.get("products",[])),
        "embeds": len(x.get("embeds",{})),
        "setup_runs": x.get("setup_runs",0)
    }
