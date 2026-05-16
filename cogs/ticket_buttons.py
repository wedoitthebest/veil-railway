
from discord.ext import commands
from services.ticket_actions import TicketActionView

class TicketButtonsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Persistent registration for existing ticket buttons after restart.
        try:
            bot.add_view(TicketActionView())
        except Exception:
            pass

async def setup(bot):
    await bot.add_cog(TicketButtonsCog(bot))
