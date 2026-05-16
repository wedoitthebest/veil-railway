
import discord
from discord.ext import commands
from pathlib import Path
from datetime import datetime

from services.access_control import is_allowed
from services.ticket_panel import update_ticket_panel, is_ticket_channel
from services.log_service import log_event

def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def is_staff(member):
    if is_allowed(member.id):
        return True
    names = ["Owner", "Store Manager", "Support", "Store Owner", "Shelf Keeper", "Admin", "Moderator"]
    return member.guild_permissions.manage_channels or any(role.name in names for role in member.roles)

async def make_transcript(channel):
    import html
    transcript_dir = Path("data/transcripts")
    transcript_dir.mkdir(parents=True, exist_ok=True)
    messages = []
    async for message in channel.history(limit=500, oldest_first=True):
        content = html.escape(message.content or "")
        author = html.escape(str(message.author))
        created = message.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        embed_text = ""
        for em in message.embeds:
            if em.title:
                embed_text += f"<div class='embed-title'>{html.escape(em.title)}</div>"
            if em.description:
                embed_text += f"<div class='embed-desc'>{html.escape(em.description)}</div>"
        messages.append(
            "<div class='msg'>"
            f"<div class='meta'><b>{author}</b> <span>{created}</span></div>"
            f"<div class='content'>{content}</div>{embed_text}</div>"
        )
    path = transcript_dir / f"{channel.name}-{channel.id}.html"
    page = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>Transcript - {html.escape(channel.name)}</title>"
        "<style>"
        "body{background:#08050d;color:#f6f0ff;font-family:Arial,sans-serif;padding:30px;}"
        "h1{color:#c5b6ff}.msg{background:#100a1b;border:1px solid #33204d;border-radius:12px;padding:14px;margin:12px 0;}"
        ".meta{color:#c5b6ff;margin-bottom:8px}.meta span{color:#8d82aa;font-size:12px}.content{white-space:pre-wrap}"
        ".embed-title{margin-top:10px;color:#ffd166;font-weight:bold}.embed-desc{color:#ddd1ff;white-space:pre-wrap}"
        "</style></head><body>"
        f"<h1>Transcript: #{html.escape(channel.name)}</h1><p>Generated: {now_iso()}</p>"
        + "".join(messages) + "</body></html>"
    )
    path.write_text(page, encoding="utf-8")
    return path

class TicketOpsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="flow")
    async def order_flow(self, ctx):
        if not is_allowed(ctx.author.id):
            await ctx.reply("You are not allowed to view staff flow.", mention_author=False)
            return
        embed = discord.Embed(
            title="🧾 Staff Order Flow",
            description=(
                "**Button flow inside ticket:**\n"
                "`Claim` → `Paid` → `Delivering` → `Ship`\n\n"
                "**Command flow:**\n"
                "`!cl` → `!p` → `!d` → `!ship`\n\n"
                "**Manual item completion:**\n"
                "`!ship item name`\n\n"
                "**Close only:**\n"
                "`!ct reason`"
            ),
            color=0x7C3CFF,
        )
        embed.set_footer(text="Veil's Grocery Store • Staff Flow")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="claim", aliases=["cl"])
    async def claim_ticket(self, ctx):
        if not is_ticket_channel(ctx.channel):
            await ctx.reply("Use this inside a ticket.", mention_author=False)
            return
        if not is_staff(ctx.author):
            await ctx.reply("Only staff can claim tickets.", mention_author=False)
            return
        await update_ticket_panel(ctx.channel, status="claimed", staff=ctx.author, note="Ticket claimed.")
        await log_event(ctx.guild, "ticket", "🎫 Ticket Claimed", {"Ticket": ctx.channel.mention}, actor=ctx.author)
        await ctx.reply(f"Ticket claimed by {ctx.author.mention}.", mention_author=False)

    @commands.command(name="paid", aliases=["p"])
    async def paid_ticket(self, ctx, *, note="Payment confirmed."):
        if not is_ticket_channel(ctx.channel):
            await ctx.reply("Use this inside a ticket.", mention_author=False)
            return
        if not is_staff(ctx.author):
            await ctx.reply("Only staff can mark payment.", mention_author=False)
            return
        await update_ticket_panel(ctx.channel, status="paid", staff=ctx.author, note=note)
        await log_event(ctx.guild, "ticket", "💳 Payment Marked", {"Ticket": ctx.channel.mention, "Note": note}, actor=ctx.author)
        await ctx.reply("Payment marked.", mention_author=False)

    @commands.command(name="delivering", aliases=["d"])
    async def delivering_ticket(self, ctx, *, note="Delivery in progress."):
        if not is_ticket_channel(ctx.channel):
            await ctx.reply("Use this inside a ticket.", mention_author=False)
            return
        if not is_staff(ctx.author):
            await ctx.reply("Only staff can mark delivery.", mention_author=False)
            return
        await update_ticket_panel(ctx.channel, status="delivering", staff=ctx.author, note=note)
        await log_event(ctx.guild, "ticket", "📦 Delivery Started", {"Ticket": ctx.channel.mention, "Note": note}, actor=ctx.author)
        await ctx.reply("Delivery marked.", mention_author=False)

    @commands.command(name="transcript", aliases=["tr"])
    async def transcript(self, ctx):
        if not is_ticket_channel(ctx.channel):
            await ctx.reply("Use this inside a ticket.", mention_author=False)
            return
        if not is_staff(ctx.author):
            await ctx.reply("Only staff can make transcripts.", mention_author=False)
            return
        path = await make_transcript(ctx.channel)
        await ctx.reply(file=discord.File(path), mention_author=False)

    @commands.command(name="closeticket", aliases=["ct", "close"])
    async def close_ticket(self, ctx, *, reason="Closed by staff."):
        if not is_ticket_channel(ctx.channel):
            await ctx.reply("Use this inside a ticket.", mention_author=False)
            return
        if not is_staff(ctx.author):
            await ctx.reply("Only staff can close tickets.", mention_author=False)
            return
        await update_ticket_panel(ctx.channel, status="closed", staff=ctx.author, note=reason)
        path = None
        try:
            path = await make_transcript(ctx.channel)
        except Exception:
            pass
        await log_event(ctx.guild, "ticket", "🔒 Ticket Closed", {"Ticket": ctx.channel.name, "Reason": reason}, actor=ctx.author)
        log = discord.utils.get(ctx.guild.text_channels, name="logs") or discord.utils.get(ctx.guild.text_channels, name="ticket-logs")
        if log and path:
            await log.send(file=discord.File(path))
        await ctx.reply("Ticket closing in 5 seconds.", mention_author=False)
        import asyncio
        await asyncio.sleep(5)
        try:
            await ctx.channel.delete(reason=reason)
        except Exception:
            pass

    @commands.command(name="cancelorder", aliases=["co"])
    async def cancel_order(self, ctx, *, reason="Cancelled."):
        if not is_ticket_channel(ctx.channel):
            await ctx.reply("Use this inside a ticket.", mention_author=False)
            return
        if not is_staff(ctx.author):
            await ctx.reply("Only staff can cancel orders.", mention_author=False)
            return
        await update_ticket_panel(ctx.channel, status="cancelled", staff=ctx.author, note=reason)
        await log_event(ctx.guild, "ticket", "❌ Order Cancelled", {"Ticket": ctx.channel.mention, "Reason": reason}, actor=ctx.author)
        await ctx.reply(f"Order cancelled: `{reason}`", mention_author=False)

async def setup(bot):
    await bot.add_cog(TicketOpsCog(bot))
