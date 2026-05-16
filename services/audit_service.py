
import os
import json
from pathlib import Path
from urllib.parse import urlparse

import discord

REQUIRED_ROLES = ["Owner", "Store Manager", "Support", "Customer", "Voucher", "Star Shopper", "Muted"]

REQUIRED_CHANNELS = [
    "welcome", "announcements", "rules", "benefits",
    "aotr-stock", "gpo-stock", "sbtd-stock", "da-hood-stock", "other-stock",
    "order-here", "payments", "support",
    "vouches", "reviews", "proofs",
    "general", "questions",
    "staff-chat", "logs", "ticket-logs", "stock-logs",
]

STOCK_CHANNELS = ["aotr-stock", "gpo-stock", "sbtd-stock", "da-hood-stock", "other-stock"]

MESSAGE_CHANNELS = {
    "welcome": "🛒 Welcome to Veil's Grocery Store",
    "vouches": "⭐ Reviews & Referrals",
    "payments": "💳 Payment Options",
    "benefits": "🎁 Benefits",
    "rules": "🛡️ Store Rules & Safety",
    "order-here": "🎫 How to Order",
    "announcements": "📌 Store Information",
}

ENV_REQUIRED = ["DISCORD_TOKEN"]
ELDORADO_ENV = ["ELDORADO_EMAIL", "ELDORADO_PASSWORD"]
DATA_FILES = ["data/app.db", "data/admin_users.json", "data/banner_config.json"]

def ok(label, detail=""):
    return {"status": "ok", "label": label, "detail": detail}

def warn(label, detail=""):
    return {"status": "warn", "label": label, "detail": detail}

def fail(label, detail=""):
    return {"status": "fail", "label": label, "detail": detail}

def status_icon(status):
    return {"ok": "✅", "warn": "⚠️", "fail": "❌"}.get(status, "•")

def split_results(results):
    return {
        "ok": [r for r in results if r["status"] == "ok"],
        "warn": [r for r in results if r["status"] == "warn"],
        "fail": [r for r in results if r["status"] == "fail"],
    }

def duplicate_channels(guild):
    counts = {}
    for ch in guild.text_channels:
        counts[ch.name] = counts.get(ch.name, 0) + 1
    return {name: count for name, count in counts.items() if count > 1}

def role_position_issue(guild):
    bot_member = guild.me
    if not bot_member:
        return "Bot member unavailable."
    managed = [r for r in guild.roles if r.name in REQUIRED_ROLES]
    bad = []
    for role in managed:
        if role >= bot_member.top_role:
            bad.append(role.name)
    return ", ".join(bad)

def check_bot_perms(guild):
    me = guild.me
    if not me:
        return [fail("Bot member", "Bot member unavailable.")]

    perms = me.guild_permissions
    checks = []
    needed = {
        "Manage Channels": perms.manage_channels,
        "Manage Roles": perms.manage_roles,
        "Manage Messages": perms.manage_messages,
        "Read Message History": perms.read_message_history,
        "Send Messages": perms.send_messages,
        "Embed Links": perms.embed_links,
        "Attach Files": perms.attach_files,
    }

    for name, value in needed.items():
        checks.append(ok(f"Bot permission: {name}") if value else fail(f"Bot permission: {name}", "Missing permission."))

    position = role_position_issue(guild)
    if position:
        checks.append(warn("Bot role position", f"Bot role is not above: {position}"))
    else:
        checks.append(ok("Bot role position", "Bot role is above managed roles."))

    return checks

def check_roles(guild):
    role_names = {r.name for r in guild.roles}
    return [ok(f"Role: {r}") if r in role_names else fail(f"Role: {r}", "Missing role.") for r in REQUIRED_ROLES]

def check_channels(guild):
    channel_names = {c.name for c in guild.text_channels}
    results = []
    for c in REQUIRED_CHANNELS:
        results.append(ok(f"Channel: #{c}") if c in channel_names else fail(f"Channel: #{c}", "Missing channel."))

    dupes = duplicate_channels(guild)
    if dupes:
        results.append(warn("Duplicate channels", ", ".join(f"{k} x{v}" for k, v in dupes.items())[:900]))
    else:
        results.append(ok("Duplicate channels", "No duplicate text channel names found."))

    return results

def has_stock_board(channel):
    # Cannot inspect async here. This is handled in async audit.
    return False

async def check_stock_boards(guild):
    results = []
    for name in STOCK_CHANNELS:
        channel = discord.utils.get(guild.text_channels, name=name)
        if not channel:
            results.append(fail(f"Stock board: #{name}", "Channel missing."))
            continue

        found = False
        try:
            async for msg in channel.history(limit=30):
                if msg.author.bot and msg.embeds:
                    for embed in msg.embeds:
                        title = embed.title or ""
                        if title.startswith("🛒 ") and title.endswith(" Stock"):
                            found = True
                            break
                if found:
                    break
        except Exception as exc:
            results.append(warn(f"Stock board: #{name}", f"Could not inspect: {exc}"))
            continue

        results.append(ok(f"Stock board: #{name}") if found else warn(f"Stock board: #{name}", "No stock embed found in latest messages."))

    return results

async def check_message_embeds(guild):
    results = []
    for channel_name, title in MESSAGE_CHANNELS.items():
        channel = discord.utils.get(guild.text_channels, name=channel_name)
        if not channel:
            results.append(fail(f"Message embed: #{channel_name}", "Channel missing."))
            continue

        found = False
        try:
            async for msg in channel.history(limit=30):
                if msg.author.bot and msg.embeds:
                    if any((e.title or "") == title for e in msg.embeds):
                        found = True
                        break
        except Exception as exc:
            results.append(warn(f"Message embed: #{channel_name}", f"Could not inspect: {exc}"))
            continue

        results.append(ok(f"Message embed: #{channel_name}") if found else warn(f"Message embed: #{channel_name}", f"Missing `{title}` in latest messages."))

    return results

def check_env():
    results = []
    for key in ENV_REQUIRED:
        results.append(ok(f"Env: {key}") if os.getenv(key) else fail(f"Env: {key}", "Missing."))

    if os.getenv("ELDORADO_EMAIL") and os.getenv("ELDORADO_PASSWORD"):
        results.append(ok("Eldorado credentials", "Email/password present."))
    else:
        missing = [k for k in ELDORADO_ENV if not os.getenv(k)]
        results.append(warn("Eldorado credentials", f"Missing: {', '.join(missing)}"))

    return results

def check_files():
    results = []
    for path in DATA_FILES:
        p = Path(path)
        if p.exists():
            results.append(ok(f"File: {path}"))
        else:
            severity = warn if path.endswith("banner_config.json") else fail
            results.append(severity(f"File: {path}", "Missing."))

    Path("logs").mkdir(exist_ok=True)
    results.append(ok("Folder: logs"))
    Path("data").mkdir(exist_ok=True)
    results.append(ok("Folder: data"))

    return results

def valid_url(url):
    try:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False

def check_images():
    path = Path("data/banner_config.json")
    if not path.exists():
        return [warn("Image config", "No banner_config.json found.")]

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [fail("Image config", f"Invalid JSON: {exc}")]

    results = []
    if not data:
        return [warn("Image config", "No images configured.")]

    for key, url in data.items():
        if valid_url(url):
            results.append(ok(f"Image URL: {key}"))
        else:
            results.append(fail(f"Image URL: {key}", "Invalid URL."))

    return results

async def run_deep_audit(guild):
    results = []
    results += check_bot_perms(guild)
    results += check_roles(guild)
    results += check_channels(guild)
    results += check_env()
    results += check_files()
    results += check_images()
    results += await check_stock_boards(guild)
    results += await check_message_embeds(guild)
    return results

def format_results(results, limit=3600):
    parts = split_results(results)
    lines = []
    for status in ["fail", "warn", "ok"]:
        for item in parts[status]:
            line = f"{status_icon(status)} **{item['label']}**"
            if item.get("detail"):
                line += f" — {item['detail']}"
            lines.append(line)

    out = "\n".join(lines)
    if len(out) > limit:
        out = out[:limit - 120] + "\n... output shortened. Use focused checks if needed."
    return out

def summary_counts(results):
    parts = split_results(results)
    return len(parts["ok"]), len(parts["warn"]), len(parts["fail"])
