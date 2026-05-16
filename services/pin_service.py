import json
from pathlib import Path
PIN_FILE=Path("data/pinned_messages.json")
def load_pins():
    PIN_FILE.parent.mkdir(parents=True,exist_ok=True)
    if not PIN_FILE.exists(): return {}
    try:
        data=json.loads(PIN_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data,dict) else {}
    except Exception:
        return {}
def save_pins(data):
    PIN_FILE.parent.mkdir(parents=True,exist_ok=True)
    PIN_FILE.write_text(json.dumps(data,indent=2),encoding="utf-8")
def pin_key(guild_id,channel_id,name): return f"{guild_id}:{channel_id}:{name}"
def remember_pin(guild_id,channel_id,name,message_id):
    data=load_pins()
    data[pin_key(guild_id,channel_id,name)]={"guild_id":str(guild_id),"channel_id":str(channel_id),"name":str(name),"message_id":str(message_id)}
    save_pins(data)
def forget_pin(guild_id,channel_id,name):
    data=load_pins(); key=pin_key(guild_id,channel_id,name); existed=key in data; data.pop(key,None); save_pins(data); return existed
def get_pin(guild_id,channel_id,name): return load_pins().get(pin_key(guild_id,channel_id,name))
def list_channel_pins(guild_id,channel_id):
    prefix=f"{guild_id}:{channel_id}:"
    return [v for k,v in load_pins().items() if k.startswith(prefix)]
