
import sqlite3
from pathlib import Path
from datetime import datetime

import discord

from services import product_service
from services import delivery_service
from services.ticket_panel import ticket_owner_id, ticket_product_id, ticket_game_slug, update_ticket_panel
from services.stock_board_service import rebuild_game_board, short_name
from services.log_service import log_event

DB_PATH = Path("data/app.db")
VOUCHER_ROLE_NAME = "Voucher"
STAR_ROLE_NAME = "Star Shopper"

def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def connect():
    DB_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_orders_db():
    with connect() as con:
        con.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                guild_id TEXT,
                ticket_channel_id TEXT,
                ticket_channel_name TEXT,
                buyer_id TEXT,
                buyer_name TEXT,
                staff_id TEXT,
                staff_name TEXT,
                product TEXT,
                status TEXT NOT NULL,
                vouch_status TEXT NOT NULL DEFAULT 'pending'
            )
        ''')
        con.commit()

def create_order_record(guild, channel, buyer, staff, product):
    init_orders_db()
    with connect() as con:
        cur = con.execute(
            '''
            INSERT INTO orders(
                created_at, completed_at, guild_id, ticket_channel_id, ticket_channel_name,
                buyer_id, buyer_name, staff_id, staff_name, product, status, vouch_status
            )
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            ''',
            (
                now_iso(), now_iso(), str(guild.id), str(channel.id), channel.name,
                str(buyer.id), str(buyer), str(staff.id), str(staff), product,
                "completed", "pending"
            )
        )
        con.commit()
        return cur.lastrowid

async def get_or_create_role(guild, name, color):
    role = discord.utils.get(guild.roles, name=name)
    if role:
        return role
    return await guild.create_role(name=name, color=discord.Color(color), hoist=False, mentionable=False, reason="Veil role system")

def find_vouch_channel(guild):
    for name in ["vouches", "reviews", "proofs"]:
        channel = discord.utils.get(guild.text_channels, name=name)
        if channel:
            return channel
    for channel in guild.text_channels:
        lowered = channel.name.lower()
        if "vouch" in lowered or "review" in lowered or "proof" in lowered:
            return channel
    return None

def vouch_dm_embed(guild, product):
    channel = find_vouch_channel(guild)
    channel_text = channel.mention if channel else "#vouches"
    embed = discord.Embed(
        title="⭐ Leave Your Review",
        description=(
            "Your order has been completed.\n\n"
            f"You temporarily received the **{VOUCHER_ROLE_NAME}** role so you can leave one review.\n\n"
            f"Post in {channel_text}:\n"
            f"`vouch @seller bought {product or 'item'} - feedback`\n\n"
            f"After your vouch is accepted, **{VOUCHER_ROLE_NAME}** becomes **{STAR_ROLE_NAME}**."
        ),
        color=0x7C3CFF
    )
    embed.set_footer(text="Veil's Grocery Store • Review Reminder")
    return embed

def resolve_product(channel, product_query):
    query = str(product_query or "").strip()
    if query and query.lower() not in ["your order", "order"]:
        found = product_service.find_product(query)
        if found:
            return found
    pid = ticket_product_id(channel)
    if pid:
        return product_service.get_product(pid)
    return None

async def complete_order_flow(guild, channel, staff, product_query="your order", close_delay=15):
    owner_id = ticket_owner_id(channel)
    if not owner_id:
        await update_ticket_panel(channel, status="cancelled", staff=staff, note="No ticket owner detected.")
        return {"ok": False, "error": "No ticket owner detected."}

    member = guild.get_member(owner_id)
    if not member:
        await update_ticket_panel(channel, status="cancelled", staff=staff, note="Ticket owner not in server.")
        return {"ok": False, "error": "Ticket owner not in server."}

    linked_product = resolve_product(channel, product_query)
    if not linked_product:
        await update_ticket_panel(channel, status="cancelled", staff=staff, note="No linked product found. Use !ship item name.")
        return {"ok": False, "error": "No linked product found. Use !ship item name."}

    product_label = short_name(linked_product)
    game_slug = linked_product.get("game_slug") or ticket_game_slug(channel)

    await update_ticket_panel(channel, status="delivering", staff=staff, product=product_label, note="Completing order and updating stock.")

    delivery_result = {"delivered": False, "mode": "manual"}
    try:
        delivery_result = await delivery_service.deliver_if_available(member, linked_product)
    except Exception as exc:
        delivery_result = {"delivered": False, "mode": "manual", "error": str(exc)}

    ok, msg = product_service.decrement(linked_product["id"], 1)
    if not ok:
        await update_ticket_panel(channel, status="cancelled", staff=staff, product=product_label, note=f"Stock update failed: {msg}")
        await log_event(guild, "error", "❌ Ship Failed", {"Ticket": channel.mention, "Product": product_label, "Error": msg}, actor=staff)
        return {"ok": False, "error": msg}

    updated = product_service.get_product(linked_product["id"])

    voucher_role = await get_or_create_role(guild, VOUCHER_ROLE_NAME, 0x7C3CFF)
    await get_or_create_role(guild, STAR_ROLE_NAME, 0xFFD166)

    voucher_ok = True
    try:
        await member.add_roles(voucher_role, reason=f"Order completed by {staff}")
    except Exception as exc:
        voucher_ok = False
        await log_event(guild, "error", "Voucher Role Failed", {"Buyer": member.mention, "Error": exc}, actor=staff)

    order_id = create_order_record(guild, channel, member, staff, product_label)

    delivery_text = "Auto DM" if delivery_result and delivery_result.get("delivered") else "Manual"

    await update_ticket_panel(
        channel,
        status="completed",
        staff=staff,
        product=product_label,
        stock=updated.get("stock"),
        delivery=delivery_text,
        note=f"Order #{order_id} completed. Voucher role {'granted' if voucher_ok else 'failed'}."
    )

    board_refreshed = False
    if game_slug:
        try:
            await rebuild_game_board(guild, game_slug)
            board_refreshed = True
        except Exception as exc:
            await log_event(guild, "error", "Stock Board Refresh Failed", {"Game": game_slug, "Error": exc}, actor=staff)

    dm_ok = True
    try:
        await member.send(embed=vouch_dm_embed(guild, product_label))
    except Exception:
        dm_ok = False

    await log_event(
        guild,
        "order",
        "✅ Order Shipped",
        {
            "Order ID": order_id,
            "Ticket": channel.mention,
            "Buyer": member.mention,
            "Product": product_label,
            "Product ID": linked_product["id"],
            "Game": game_slug or "unknown",
            "Stock": updated.get("stock"),
            "Delivery": delivery_text,
            "Voucher role": "granted" if voucher_ok else "failed",
            "DM reminder": "sent" if dm_ok else "failed",
            "Stock board": "refreshed" if board_refreshed else "not refreshed",
        },
        actor=staff,
    )

    embed = discord.Embed(
        title="✅ Order Completed",
        description=(
            f"**Order ID:** `{order_id}`\n"
            f"**Buyer:** {member.mention}\n"
            f"**Product:** `{product_label}`\n"
            f"**Stock left:** `{updated.get('stock')}`\n"
            f"**Completed by:** {staff.mention}\n\n"
            f"Ticket closes automatically in **{close_delay} seconds**."
        ),
        color=0x44D69F
    )
    embed.set_footer(text="Veil's Grocery Store • Completed Order")
    await channel.send(embed=embed)

    import asyncio
    await asyncio.sleep(close_delay)
    try:
        await channel.delete(reason=f"Order completed by {staff}: {product_label}")
    except Exception:
        pass

    return {"ok": True, "order_id": order_id, "product": product_label, "stock": updated.get("stock")}
