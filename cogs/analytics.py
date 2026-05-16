
import discord
from discord.ext import commands

from services.access_control import is_allowed
from services.analytics_service import (
    sales_summary,
    top_items,
    low_stock,
    stock_value,
    buyer_history,
    recent_orders,
    staff_stats,
    money,
)
from services.log_service import log_event

def allowed(ctx):
    return is_allowed(ctx.author.id) or ctx.author.guild_permissions.manage_channels

def line_product(order):
    oid = order.get("id", "?")
    product = order.get("product") or "unknown"
    buyer = order.get("buyer_name") or order.get("buyer_id") or "unknown buyer"
    staff = order.get("staff_name") or order.get("staff_id") or "unknown staff"
    date = order.get("completed_at") or order.get("created_at") or "unknown date"
    return f"`#{oid}` **{product}** — buyer `{buyer}` — staff `{staff}` — `{date}`"

def product_name(p):
    name = str(p.get("name") or "Unnamed")
    if len(name) > 80:
        name = name[:77] + "..."
    return name

class AnalyticsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="analytics", aliases=["biz", "business"])
    async def analytics_home(self, ctx):
        if not allowed(ctx):
            await ctx.reply("Only staff can view analytics.", mention_author=False)
            return

        embed = discord.Embed(
            title="📈 Veil Analytics",
            description=(
                "**Sales**\n"
                "`!sales today` / `!sales week` / `!sales month` / `!sales all`\n\n"
                "**Products**\n"
                "`!topitems` / `!lowstock` / `!stockvalue`\n\n"
                "**History**\n"
                "`!buyerhistory @user`\n"
                "`!orderhistory`\n"
                "`!staffstats week`"
            ),
            color=0x7C3CFF,
        )
        embed.set_footer(text="Revenue is estimated from current product prices when available.")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="sales")
    async def sales(self, ctx, period: str = "today"):
        if not allowed(ctx):
            await ctx.reply("Only staff can view sales.", mention_author=False)
            return

        data = sales_summary(ctx.guild.id, period)

        embed = discord.Embed(
            title=f"💰 Sales Summary — {data['period']}",
            description=(
                f"**Completed orders:** `{data['completed_count']}`\n"
                f"**Estimated revenue:** `{money(data['estimated_revenue'])}`\n"
                f"**Known prices:** `{data['known_prices']}`\n"
                f"**Unknown prices:** `{data['unknown_prices']}`\n"
                f"**Pending vouches:** `{data['pending_vouch']}`\n"
                f"**Vouched:** `{data['vouched']}`"
            ),
            color=0x44D69F,
        )

        items, _ = top_items(ctx.guild.id, period, limit=5)
        if items:
            embed.add_field(
                name="Top items",
                value="\n".join(f"• **{name}** — `{count}`" for name, count in items)[:1000],
                inline=False,
            )

        embed.set_footer(text="Estimated revenue uses current stored product prices, not historical prices.")
        await ctx.reply(embed=embed, mention_author=False)
        await log_event(ctx.guild, "system", "📈 Sales Summary Viewed", {"Period": data["period"]}, actor=ctx.author)

    @commands.command(name="topitems", aliases=["topsold"])
    async def top_items_cmd(self, ctx, period: str = "all"):
        if not allowed(ctx):
            await ctx.reply("Only staff can view top items.", mention_author=False)
            return

        rows, label = top_items(ctx.guild.id, period, limit=15)
        if not rows:
            await ctx.reply(f"No completed item sales found for `{label}`.", mention_author=False)
            return

        embed = discord.Embed(
            title=f"🏆 Top Sold Items — {label}",
            description="\n".join(f"`{idx}.` **{name}** — `{count}` sold" for idx, (name, count) in enumerate(rows, start=1))[:3900],
            color=0xFFD166,
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="lowstock", aliases=["ls"])
    async def low_stock_cmd(self, ctx, threshold: int = 5):
        if not allowed(ctx):
            await ctx.reply("Only staff can view low stock.", mention_author=False)
            return

        threshold = max(0, min(int(threshold), 1000000))
        rows = low_stock(threshold=threshold, limit=25)
        if not rows:
            await ctx.reply(f"No active products at or below `{threshold}` stock.", mention_author=False)
            return

        lines = []
        for p in rows:
            lines.append(
                f"`#{p.get('id')}` **{product_name(p)}** — `{p.get('game_slug') or 'other'}` — stock `{p.get('stock')}` — **{p.get('price') or 'Ask'}**"
            )

        embed = discord.Embed(
            title=f"⚠️ Low Stock — ≤ {threshold}",
            description="\n".join(lines)[:3900],
            color=0xE06C75,
        )
        embed.set_footer(text="Use !estock or restock product data before relying on this.")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="stockvalue", aliases=["inventoryvalue", "stockworth"])
    async def stock_value_cmd(self, ctx):
        if not allowed(ctx):
            await ctx.reply("Only staff can view stock value.", mention_author=False)
            return

        data = stock_value()
        embed = discord.Embed(
            title="📦 Stock Value Estimate",
            description=(
                f"**Active products:** `{data['products']}`\n"
                f"**Total units:** `{data['units']}`\n"
                f"**Estimated value:** `{money(data['estimated_value'])}`\n"
                f"**Known prices:** `{data['known_prices']}`\n"
                f"**Unknown prices:** `{data['unknown_prices']}`"
            ),
            color=0x7C3CFF,
        )

        lines = []
        for game, info in sorted(data["by_game"].items()):
            lines.append(f"• `{game}` — units `{info['units']}` — value `{money(info['value'])}`")
        if lines:
            embed.add_field(name="By game", value="\n".join(lines)[:1000], inline=False)

        embed.set_footer(text="Estimate uses current stored stock and current product prices.")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="buyerhistory", aliases=["bh"])
    async def buyer_history_cmd(self, ctx, member: discord.Member = None, *, fallback_name: str = None):
        if not allowed(ctx):
            await ctx.reply("Only staff can view buyer history.", mention_author=False)
            return

        if member is None and not fallback_name:
            await ctx.reply("Use `!buyerhistory @user` or `!buyerhistory name`.", mention_author=False)
            return

        rows = buyer_history(
            ctx.guild.id,
            buyer_id=member.id if member else None,
            buyer_name=fallback_name,
            limit=12,
        )

        target = member.mention if member else fallback_name
        if not rows:
            await ctx.reply(f"No completed order history found for `{target}`.", mention_author=False)
            return

        embed = discord.Embed(
            title=f"👤 Buyer History — {target}",
            description="\n".join(line_product(o) for o in rows)[:3900],
            color=0x7C3CFF,
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="orderhistory", aliases=["ordersrecent", "recentorders"])
    async def order_history_cmd(self, ctx, limit: int = 10):
        if not allowed(ctx):
            await ctx.reply("Only staff can view order history.", mention_author=False)
            return

        limit = max(1, min(int(limit), 20))
        rows = recent_orders(ctx.guild.id, limit=limit)
        if not rows:
            await ctx.reply("No completed orders found.", mention_author=False)
            return

        embed = discord.Embed(
            title=f"🧾 Recent Orders — last {limit}",
            description="\n".join(line_product(o) for o in rows)[:3900],
            color=0x7C3CFF,
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="staffstats", aliases=["staffsales"])
    async def staff_stats_cmd(self, ctx, period: str = "all"):
        if not allowed(ctx):
            await ctx.reply("Only staff can view staff stats.", mention_author=False)
            return

        rows, label = staff_stats(ctx.guild.id, period, limit=15)
        if not rows:
            await ctx.reply(f"No staff completion stats found for `{label}`.", mention_author=False)
            return

        embed = discord.Embed(
            title=f"🛠️ Staff Stats — {label}",
            description="\n".join(f"`{idx}.` **{name}** — `{count}` completed" for idx, (name, count) in enumerate(rows, start=1))[:3900],
            color=0x7C3CFF,
        )
        await ctx.reply(embed=embed, mention_author=False)

async def setup(bot):
    await bot.add_cog(AnalyticsCog(bot))
