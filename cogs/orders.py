
import sqlite3
from pathlib import Path

import discord
from discord.ext import commands

from services.access_control import is_allowed
from services.ticket_panel import is_ticket_channel
from services.order_flow import complete_order_flow, init_orders_db

DB_PATH = Path("data/app.db")
VOUCHER_ROLE_NAME = "Voucher"
STAR_ROLE_NAME = "Star Shopper"

def connect():
    DB_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(DB_PATH)

def mark_vouched(guild_id, buyer_id):
    init_orders_db()
    with connect() as con:
        row = con.execute(
            "SELECT id FROM orders WHERE guild_id=? AND buyer_id=? AND vouch_status='pending' ORDER BY id DESC LIMIT 1",
            (str(guild_id), str(buyer_id))
        ).fetchone()
        if not row:
            return None
        con.execute("UPDATE orders SET vouch_status='received' WHERE id=?", (row[0],))
        con.commit()
        return row[0]

def get_order_stats(guild_id):
    init_orders_db()
    with connect() as con:
        total = con.execute("SELECT COUNT(*) FROM orders WHERE guild_id=?", (str(guild_id),)).fetchone()[0]
        pending = con.execute("SELECT COUNT(*) FROM orders WHERE guild_id=? AND vouch_status='pending'", (str(guild_id),)).fetchone()[0]
        vouched = con.execute("SELECT COUNT(*) FROM orders WHERE guild_id=? AND vouch_status='received'", (str(guild_id),)).fetchone()[0]
        return total, pending, vouched

def is_staff(member):
    if is_allowed(member.id):
        return True
    names = ["Owner", "Store Manager", "Support", "Store Owner", "Shelf Keeper", "Admin", "Moderator"]
    return member.guild_permissions.manage_channels or any(role.name in names for role in member.roles)

def valid_vouch_message(message):
    content = message.content.strip()
    lowered = content.lower()
    return lowered.startswith("vouch ") and " bought " in lowered and len(content) >= 20

async def get_or_create_role(guild, name, color):
    role = discord.utils.get(guild.roles, name=name)
    if role:
        return role
    return await guild.create_role(name=name, color=discord.Color(color), hoist=False, mentionable=False, reason="Veil role system")

class OrdersCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        init_orders_db()

    @commands.command(name="complete", aliases=["done", "ship", "finish", "fill", "sent", "ok"])
    async def complete_order(self, ctx, *, product="your order"):
        if not is_ticket_channel(ctx.channel):
            await ctx.reply("This command can only be used inside a ticket.", mention_author=False)
            return
        if not is_staff(ctx.author):
            await ctx.reply("Only staff can complete orders.", mention_author=False)
            return
        result = await complete_order_flow(ctx.guild, ctx.channel, ctx.author, product_query=product, close_delay=15)
        if not result.get("ok"):
            await ctx.reply(f"Could not complete order: `{result.get('error')}`", mention_author=False)

    @commands.command(name="orderstats", aliases=["os", "stats"])
    async def order_stats(self, ctx):
        if not is_allowed(ctx.author.id) and not ctx.author.guild_permissions.manage_channels:
            await ctx.reply("Only staff can view order stats.", mention_author=False)
            return
        total, pending, vouched = get_order_stats(ctx.guild.id)
        embed = discord.Embed(
            title="📊 Veil Order Stats",
            description=f"**Total completed:** `{total}`\n**Pending vouches:** `{pending}`\n**Received vouches:** `{vouched}`",
            color=0x7C3CFF
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        voucher_role = discord.utils.get(message.guild.roles, name=VOUCHER_ROLE_NAME)
        if not voucher_role or voucher_role not in getattr(message.author, "roles", []):
            return
        if "vouch" not in message.channel.name.lower() and "review" not in message.channel.name.lower() and "proof" not in message.channel.name.lower():
            return
        if not valid_vouch_message(message):
            try:
                await message.reply("Use: `vouch @seller bought PRODUCT - feedback`", mention_author=False, delete_after=10)
            except Exception:
                pass
            return
        try:
            star_role = await get_or_create_role(message.guild, STAR_ROLE_NAME, 0xFFD166)
            await message.author.remove_roles(voucher_role, reason="Voucher used")
            if star_role not in message.author.roles:
                await message.author.add_roles(star_role, reason="Valid vouch")
            order_id = mark_vouched(message.guild.id, message.author.id)
            await message.add_reaction("⭐")
            await message.add_reaction("✅")
            if order_id:
                await message.reply(f"Vouch received for order `{order_id}`. **{STAR_ROLE_NAME}** granted.", mention_author=False)
        except Exception:
            pass

async def setup(bot):
    await bot.add_cog(OrdersCog(bot))
