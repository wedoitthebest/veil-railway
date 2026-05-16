
import json
from pathlib import Path

ROOT_OWNER_ID = 755454388310638603
ADMIN_FILE = Path("data/admin_users.json")

DEFAULT_DATA = {
    "root_owner_id": ROOT_OWNER_ID,
    "owner_ids": [ROOT_OWNER_ID],
    "allowed_ids": [ROOT_OWNER_ID],
}

PROTECTED_COMMANDS = {
    "cmds", "commands", "helpme",
    "launch", "admin", "audit",
    "allowid", "denyid", "allowedids",
    "addowner", "removeowner", "owners",
    "setupall", "vsetup", "fullsetup", "setupserver",
    "vroles", "fixroles", "vchannels", "fixchannels", "vperms", "fixperms", "vclean", "serverplan",
    "cleanmsgs", "msgs", "postmsgs", "refreshmsgs", "msg", "postmsg",
    "setimage", "setbanner", "clearimage", "clearbanner", "imagekeys", "imgs", "banners", "imagepreset", "presetimages", "previewimage", "previewbanner",
    "estock", "eldostock", "syncstock", "stockboard", "sb", "eroute", "egame", "eall", "stocksetup", "ssu",
    "ap", "ep", "dp", "rp", "panel", "si", "sis", "stockitems",
    "ship", "done", "finish", "fill", "sent", "ok", "complete",
    "ct", "close", "cl", "p", "d", "co", "tr", "os", "orderstats", "stats",
}

def _int_set(values):
    out = set()
    for value in values or []:
        try:
            out.add(int(value))
        except Exception:
            pass
    return out

def _ensure_file():
    ADMIN_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not ADMIN_FILE.exists():
        ADMIN_FILE.write_text(json.dumps(DEFAULT_DATA, indent=2), encoding="utf-8")

def load_data():
    _ensure_file()
    try:
        raw = json.loads(ADMIN_FILE.read_text(encoding="utf-8"))
    except Exception:
        raw = DEFAULT_DATA.copy()

    # Backward compatibility with v34 file shape.
    old_owner = raw.get("owner_id")
    owner_ids = _int_set(raw.get("owner_ids", []))
    allowed_ids = _int_set(raw.get("allowed_ids", []))

    if old_owner:
        try:
            owner_ids.add(int(old_owner))
            allowed_ids.add(int(old_owner))
        except Exception:
            pass

    owner_ids.add(ROOT_OWNER_ID)
    allowed_ids.update(owner_ids)

    data = {
        "root_owner_id": ROOT_OWNER_ID,
        "owner_ids": sorted(owner_ids),
        "allowed_ids": sorted(allowed_ids),
    }

    save_data(data)
    return data

def save_data(data):
    owner_ids = _int_set(data.get("owner_ids", []))
    allowed_ids = _int_set(data.get("allowed_ids", []))

    owner_ids.add(ROOT_OWNER_ID)
    allowed_ids.update(owner_ids)

    ADMIN_FILE.parent.mkdir(parents=True, exist_ok=True)
    ADMIN_FILE.write_text(
        json.dumps(
            {
                "root_owner_id": ROOT_OWNER_ID,
                "owner_ids": sorted(owner_ids),
                "allowed_ids": sorted(allowed_ids),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

def is_root_owner(user_id):
    try:
        return int(user_id) == ROOT_OWNER_ID
    except Exception:
        return False

def is_owner(user_id):
    try:
        user_id = int(user_id)
    except Exception:
        return False
    data = load_data()
    return user_id in set(data["owner_ids"])

def is_allowed(user_id):
    try:
        user_id = int(user_id)
    except Exception:
        return False
    data = load_data()
    return user_id in set(data["allowed_ids"]) or user_id in set(data["owner_ids"])

def add_owner(user_id):
    data = load_data()
    user_id = int(user_id)
    owner_ids = set(data["owner_ids"])
    allowed_ids = set(data["allowed_ids"])
    owner_ids.add(user_id)
    allowed_ids.add(user_id)
    data["owner_ids"] = sorted(owner_ids)
    data["allowed_ids"] = sorted(allowed_ids)
    save_data(data)
    return load_data()

def remove_owner(user_id):
    user_id = int(user_id)
    if user_id == ROOT_OWNER_ID:
        return load_data(), False, "Root owner cannot be removed."

    data = load_data()
    owner_ids = set(data["owner_ids"])
    removed = user_id in owner_ids
    owner_ids.discard(user_id)
    data["owner_ids"] = sorted(owner_ids)

    # Do not automatically remove from allowed_ids. They may still be staff.
    save_data(data)
    return load_data(), removed, None

def add_allowed(user_id):
    data = load_data()
    ids = set(data["allowed_ids"])
    ids.add(int(user_id))
    data["allowed_ids"] = sorted(ids)
    save_data(data)
    return load_data()

def remove_allowed(user_id):
    user_id = int(user_id)
    data = load_data()

    if user_id == ROOT_OWNER_ID:
        return data, False, "Root owner cannot be removed."
    if user_id in set(data["owner_ids"]):
        return data, False, "Owner IDs cannot be removed from allowed users. Remove owner first."

    ids = set(data["allowed_ids"])
    removed = user_id in ids
    ids.discard(user_id)
    data["allowed_ids"] = sorted(ids)
    save_data(data)
    return load_data(), removed, None

async def global_admin_check(ctx):
    command_name = ""
    try:
        command_name = (ctx.command.name or "").lower()
    except Exception:
        return True

    aliases = set()
    try:
        aliases = {a.lower() for a in ctx.command.aliases}
    except Exception:
        pass

    protected = command_name in PROTECTED_COMMANDS or bool(aliases & PROTECTED_COMMANDS)
    if not protected:
        return True

    return is_allowed(ctx.author.id)

def require_allowed():
    def predicate(ctx):
        return is_allowed(ctx.author.id)
    return predicate

def require_owner():
    def predicate(ctx):
        return is_owner(ctx.author.id)
    return predicate

def require_root_owner():
    def predicate(ctx):
        return is_root_owner(ctx.author.id)
    return predicate
