
import os
import time
import asyncio
from discord.ext import commands

from services.ticket_panel import ticket_owner_id, is_ticket_channel, update_ticket_panel
from services.log_service import log_event

WARN_AFTER_SECONDS = int(os.getenv("VEIL_TICKET_WARN_AFTER_SECONDS", "7200"))
CLOSE_AFTER_SECONDS = int(os.getenv("VEIL_TICKET_CLOSE_AFTER_SECONDS", "14400"))
CHECK_EVERY_SECONDS = int(os.getenv("VEIL_TICKET_INACTIVITY_CHECK_SECONDS", "900"))

def topic_opened_at(channel):
    topic = channel.topic or ""
    marker = "opened-at:"
    if marker not in topic:
        return None
    try:
        return int(topic.split(marker, 1)[1].split()[0])
    except Exception:
        return None

def has_warned(channel):
    return "inactivity-warned:1" in (channel.topic or "")

async def set_warned(channel):
    topic = channel.topic or ""
    if "inactivity-warned:1" not in topic:
        try:
            await channel.edit(topic=(topic + " inactivity-warned:1")[:1024])
        except Exception:
            pass

async def last_user_activity(channel):
    latest = None
    try:
        async for msg in channel.history(limit=50):
            if not msg.author.bot:
                latest = int(msg.created_at.timestamp())
                break
    except Exception:
        pass
    return latest

class TicketInactivityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.task = bot.loop.create_task(self.inactivity_loop())

    def cog_unload(self):
        try:
            self.task.cancel()
        except Exception:
            pass

    async def inactivity_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                for guild in self.bot.guilds:
                    await self.check_guild(guild)
            except Exception as exc:
                print(f"[INACTIVITY ERROR] {exc}")
            await asyncio.sleep(CHECK_EVERY_SECONDS)

    async def check_guild(self, guild):
        now = int(time.time())
        for channel in guild.text_channels:
            if not is_ticket_channel(channel):
                continue

            opened = topic_opened_at(channel)
            activity = await last_user_activity(channel)
            baseline = activity or opened
            if not baseline:
                continue

            age = now - baseline
            owner_id = ticket_owner_id(channel)
            owner = guild.get_member(owner_id) if owner_id else None

            if age >= CLOSE_AFTER_SECONDS:
                await update_ticket_panel(channel, status="closed", note="Ticket auto-closed for inactivity.")
                await log_event(guild, "ticket", "⏱️ Ticket Auto-Closed", {"Ticket": channel.name, "Age seconds": age}, actor=None)
                try:
                    await channel.send("Ticket auto-closing for inactivity.")
                    await asyncio.sleep(5)
                    await channel.delete(reason="Veil inactivity auto-close")
                except Exception:
                    pass
                continue

            if age >= WARN_AFTER_SECONDS and not has_warned(channel):
                await set_warned(channel)
                await update_ticket_panel(channel, status="waiting", note="Inactivity warning sent.")
                mention = owner.mention if owner else "Buyer"
                await channel.send(f"{mention}, this ticket has been inactive. Reply soon or it may be closed automatically.")
                await log_event(guild, "ticket", "⏱️ Ticket Inactivity Warning", {"Ticket": channel.mention, "Age seconds": age}, actor=None)

async def setup(bot):
    await bot.add_cog(TicketInactivityCog(bot))
