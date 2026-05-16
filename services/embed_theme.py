
import os
import json
from pathlib import Path
import discord

BRAND_COLOR = 0x7C3CFF
SUCCESS_COLOR = 0x44D69F
WARN_COLOR = 0xFFD166
ERROR_COLOR = 0xE06C75

FOOTER = "Veil's Grocery Store"
BANNER_FILE = Path("data/banner_config.json")

VALID_IMAGE_KEYS = [
    "welcome",
    "vouches",
    "payments",
    "benefits",
    "rules",
    "tickets",
    "announcements",
    "aotr",
    "gpo",
    "sbtd",
    "da-hood",
    "other",
]

IMAGE_PRESETS = {
    "dark": {
        "welcome": "https://images.unsplash.com/photo-1511512578047-dfb367046420?auto=format&fit=crop&w=1400&q=80",
        "tickets": "https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?auto=format&fit=crop&w=1400&q=80",
        "vouches": "https://images.unsplash.com/photo-1521737604893-d14cc237f11d?auto=format&fit=crop&w=1400&q=80",
        "payments": "https://images.unsplash.com/photo-1554224155-6726b3ff858f?auto=format&fit=crop&w=1400&q=80",
        "benefits": "https://images.unsplash.com/photo-1513151233558-d860c5398176?auto=format&fit=crop&w=1400&q=80",
        "rules": "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=1400&q=80",
        "announcements": "https://images.unsplash.com/photo-1495020689067-958852a7765e?auto=format&fit=crop&w=1400&q=80",
    },
    "neon": {
        "welcome": "https://images.unsplash.com/photo-1519608487953-e999c86e7455?auto=format&fit=crop&w=1400&q=80",
        "tickets": "https://images.unsplash.com/photo-1550745165-9bc0b252726f?auto=format&fit=crop&w=1400&q=80",
        "vouches": "https://images.unsplash.com/photo-1519389950473-47ba0277781c?auto=format&fit=crop&w=1400&q=80",
        "payments": "https://images.unsplash.com/photo-1563013544-824ae1b704d3?auto=format&fit=crop&w=1400&q=80",
        "benefits": "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?auto=format&fit=crop&w=1400&q=80",
        "rules": "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?auto=format&fit=crop&w=1400&q=80",
        "announcements": "https://images.unsplash.com/photo-1535223289827-42f1e9919769?auto=format&fit=crop&w=1400&q=80",
    },
    "clean": {
        "welcome": "https://images.unsplash.com/photo-1522202176988-66273c2fd55f?auto=format&fit=crop&w=1400&q=80",
        "tickets": "https://images.unsplash.com/photo-1521791136064-7986c2920216?auto=format&fit=crop&w=1400&q=80",
        "vouches": "https://images.unsplash.com/photo-1529156069898-49953e39b3ac?auto=format&fit=crop&w=1400&q=80",
        "payments": "https://images.unsplash.com/photo-1556742502-ec7c0e9f34b1?auto=format&fit=crop&w=1400&q=80",
        "benefits": "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?auto=format&fit=crop&w=1400&q=80",
        "rules": "https://images.unsplash.com/photo-1450101499163-c8848c66ca85?auto=format&fit=crop&w=1400&q=80",
        "announcements": "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1400&q=80",
    }
}

ENV_KEYS = {
    "welcome": "VEIL_IMAGE_WELCOME",
    "vouches": "VEIL_IMAGE_VOUCHES",
    "payments": "VEIL_IMAGE_PAYMENTS",
    "benefits": "VEIL_IMAGE_BENEFITS",
    "rules": "VEIL_IMAGE_RULES",
    "tickets": "VEIL_IMAGE_TICKETS",
    "announcements": "VEIL_IMAGE_ANNOUNCEMENTS",
    "aotr": "VEIL_IMAGE_AOTR",
    "gpo": "VEIL_IMAGE_GPO",
    "sbtd": "VEIL_IMAGE_SBTD",
    "da-hood": "VEIL_IMAGE_DAHOOD",
    "other": "VEIL_IMAGE_OTHER",
}

def load_banner_config():
    if not BANNER_FILE.exists():
        return {}
    try:
        return json.loads(BANNER_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_banner_config(data):
    BANNER_FILE.parent.mkdir(parents=True, exist_ok=True)
    BANNER_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

def normalize_key(key):
    key = str(key or "").lower().strip().replace("_", "-")
    if key in ["dahood", "da hood"]:
        return "da-hood"
    return key

def set_image(key, url):
    key = normalize_key(key)
    if key not in VALID_IMAGE_KEYS:
        return False, f"Invalid image key. Use: {', '.join(VALID_IMAGE_KEYS)}"

    url = str(url or "").strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return False, "Image URL must start with http:// or https://"

    data = load_banner_config()
    data[key] = url
    save_banner_config(data)
    return True, key

def apply_preset(name):
    name = str(name or "").lower().strip()
    if name not in IMAGE_PRESETS:
        return False, f"Invalid preset. Use: {', '.join(IMAGE_PRESETS.keys())}"

    data = load_banner_config()
    data.update(IMAGE_PRESETS[name])
    save_banner_config(data)
    return True, name

def clear_image(key):
    key = normalize_key(key)
    data = load_banner_config()
    if key in data:
        del data[key]
        save_banner_config(data)
        return True
    return False

def image_for(key):
    key = normalize_key(key)
    data = load_banner_config()
    if key in data and data[key]:
        return data[key]

    env_key = ENV_KEYS.get(key)
    if env_key:
        value = os.getenv(env_key, "").strip()
        if value:
            return value

    return None

def base_embed(title, description="", color=BRAND_COLOR, image_key=None, footer=FOOTER):
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text=footer)

    image_url = image_for(image_key) if image_key else None
    if image_url:
        embed.set_image(url=image_url)

    return embed

def add_fields(embed, fields):
    for name, value, inline in fields:
        embed.add_field(name=name, value=value, inline=inline)
    return embed

def success(title, description="", image_key=None):
    return base_embed(title, description, SUCCESS_COLOR, image_key=image_key)

def warning(title, description="", image_key=None):
    return base_embed(title, description, WARN_COLOR, image_key=image_key)

def error(title, description="", image_key=None):
    return base_embed(title, description, ERROR_COLOR, image_key=image_key)
