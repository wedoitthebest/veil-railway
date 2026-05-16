
from discord.ext import commands
from services.ticket_buyer_service import BuyerActionView, clear_old_cooldowns

class TicketBuyerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        try:
            bot.add_view(BuyerActionView())
        except Exception:
            pass
        try:
            clear_old_cooldowns()
        except Exception:
            pass

async def setup(bot):
    await bot.add_cog(TicketBuyerCog(bot))
