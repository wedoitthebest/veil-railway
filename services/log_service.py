
from datetime import datetime
from pathlib import Path
import json
import discord

LOG_FILE = Path("logs/veil_events.jsonl")

EVENT_COLORS = {
    "setup": 0x7C3CFF,
    "audit": 0xFFD166,
    "health": 0x4DA3FF,
    "ticket": 0x7C3CFF,
    "order": 0x44D69F,
    "stock": 0x44D69F,
    "vouch": 0xFFD166,
    "access": 0xE06C75,
    "error": 0xE06C75,
    "system": 0x99AAB5,
}

def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def compact(value, limit=900):
    value = str(value)
    return value if len(value) <= limit else value[:limit - 3] + "..."

def append_file(event_type, title, fields=None, guild=None, actor=None):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "time": now_iso(),
        "type": event_type,
        "title": title,
        "guild_id": str(getattr(guild, "id", "")) if guild else "",
        "guild_name": str(getattr(guild, "name", "")) if guild else "",
        "actor_id": str(getattr(actor, "id", "")) if actor else "",
        "actor": str(actor) if actor else "",
        "fields": fields or {},
    }
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")

def find_log_channel(guild):
    if not guild:
        return None
    preferred = ["logs", "staff-logs", "ticket-logs", "stock-logs", "mod-logs"]
    for name in preferred:
        channel = discord.utils.get(guild.text_channels, name=name)
        if channel:
            return channel
    for channel in guild.text_channels:
        if "log" in channel.name.lower():
            return channel
    return None

def make_embed(event_type, title, fields=None, actor=None):
    embed = discord.Embed(
        title=title,
        color=EVENT_COLORS.get(event_type, 0x7C3CFF),
        timestamp=discord.utils.utcnow(),
    )
    embed.set_footer(text=f"Veil Log • {event_type}")

    if actor:
        embed.add_field(name="Actor", value=f"{getattr(actor, 'mention', str(actor))}\n`{getattr(actor, 'id', '')}`", inline=True)

    for key, value in (fields or {}).items():
        inline = key.lower() in {"order id", "product id", "stock", "game", "status"}
        embed.add_field(name=str(key)[:256], value=compact(value, 1000) or "`empty`", inline=inline)

    return embed

async def log_event(guild, event_type, title, fields=None, actor=None, send=True):
    append_file(event_type, title, fields, guild, actor)

    if not send:
        return False

    channel = find_log_channel(guild)
    if not channel:
        return False

    try:
        await channel.send(embed=make_embed(event_type, title, fields, actor))
        return True
    except Exception:
        return False
