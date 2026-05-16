
import discord
from datetime import datetime

PANEL_TITLES = {"🧾 Order Ticket", "🎫 Order Ticket"}

STATUS_COLORS = {
    "waiting": 0x7C3CFF,
    "claimed": 0xFFD166,
    "paid": 0x44D69F,
    "delivering": 0x4DA3FF,
    "completed": 0x44D69F,
    "closed": 0x99AAB5,
    "cancelled": 0xE06C75,
}

STATUS_LABELS = {
    "waiting": "Waiting for staff confirmation",
    "claimed": "Claimed by staff",
    "paid": "Payment marked as received",
    "delivering": "Delivery in progress",
    "completed": "Completed",
    "closed": "Closed",
    "cancelled": "Cancelled",
}

def utc_stamp():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

def is_ticket_channel(channel):
    return getattr(channel, "name", "").startswith("ticket-")

def parse_topic(channel):
    topic = channel.topic or ""
    data = {}
    for part in topic.split():
        if ":" in part:
            key, value = part.split(":", 1)
            data[key.strip()] = value.strip()
    return data

def ticket_owner_id(channel):
    data = parse_topic(channel)
    value = data.get("veil-ticket-owner")
    if not value:
        return None
    try:
        return int(value)
    except Exception:
        return None

def ticket_product_id(channel):
    data = parse_topic(channel)
    value = data.get("product-id")
    if not value:
        return None
    try:
        return int(value)
    except Exception:
        return None

def ticket_game_slug(channel):
    return parse_topic(channel).get("game-slug")

async def find_ticket_panel_message(channel):
    async for msg in channel.history(limit=80, oldest_first=True):
        if not msg.author.bot or not msg.embeds:
            continue
        for embed in msg.embeds:
            if (embed.title or "") in PANEL_TITLES:
                return msg, embed
    return None, None

def make_field(name, value, inline=False):
    return {"name": name, "value": value, "inline": inline}

def normalize_status(status):
    status = str(status or "waiting").lower().strip()
    return status if status in STATUS_LABELS else "waiting"

async def update_ticket_panel(channel, *, status=None, staff=None, note=None, product=None, stock=None, delivery=None):
    msg, old = await find_ticket_panel_message(channel)
    if not msg or not old:
        return False

    status = normalize_status(status)
    color = STATUS_COLORS.get(status, 0x7C3CFF)

    # Preserve base description when possible.
    description = old.description or "Order ticket."
    embed = discord.Embed(title=old.title or "🧾 Order Ticket", description=description, color=color)

    for field in old.fields:
        if field.name.lower() not in {"status", "staff", "last update", "note", "delivery", "stock left"}:
            embed.add_field(name=field.name, value=field.value, inline=field.inline)

    embed.add_field(name="Status", value=f"`{STATUS_LABELS[status]}`", inline=False)

    if product:
        embed.add_field(name="Product", value=f"`{product}`", inline=True)
    if stock is not None:
        embed.add_field(name="Stock left", value=f"`{stock}`", inline=True)
    if delivery:
        embed.add_field(name="Delivery", value=f"`{delivery}`", inline=True)
    if staff:
        embed.add_field(name="Staff", value=staff.mention if hasattr(staff, "mention") else str(staff), inline=True)
    if note:
        embed.add_field(name="Note", value=str(note)[:1000], inline=False)

    embed.add_field(name="Last update", value=f"`{utc_stamp()}`", inline=False)
    embed.set_footer(text="Veil's Grocery Store • Order Panel")

    # Preserve image.
    try:
        if old.image and old.image.url:
            embed.set_image(url=old.image.url)
    except Exception:
        pass

    await msg.edit(embed=embed)
    return True

async def ensure_ticket_panel(channel, user=None, product=None, game_label=None, image_url=None):
    existing, _ = await find_ticket_panel_message(channel)
    if existing:
        return existing

    desc = "Order ticket created."
    if user:
        desc = f"Welcome {user.mention}.\n\nConfirm quantity, payment method, and any notes below."

    embed = discord.Embed(title="🧾 Order Ticket", description=desc, color=0x7C3CFF)
    if game_label:
        embed.add_field(name="Game", value=f"`{game_label}`", inline=True)
    if product:
        embed.add_field(name="Item", value=f"`{product}`", inline=True)
    embed.add_field(name="Status", value="`Waiting for staff confirmation`", inline=False)
    embed.add_field(name="Staff flow", value="`!cl` → `!p` → `!d` → `!ship`", inline=False)
    embed.set_footer(text="Veil's Grocery Store • Order Panel")
    if image_url:
        embed.set_image(url=image_url)
    return await channel.send(embed=embed)
