
import discord
from discord.ext import commands
from services.access_control import is_allowed

def embed_page(title, description):
    embed = discord.Embed(title=title, description=description, color=0x7C3CFF)
    embed.set_footer(text="Veil's Grocery Store • Commands")
    return embed

class CommandCenterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="cmds", aliases=["commands", "helpme"])
    async def cmds(self, ctx, page: str = "all"):
        if not is_allowed(ctx.author.id):
            await ctx.reply("You are not allowed to view Veil commands.", mention_author=False)
            return

        page = str(page or "all").lower().strip()

        pages = {
            "analytics": (
                "**Sales Analytics + Stock Intelligence**\n"
                "`!analytics` — analytics menu\n"
                "`!sales today` — daily sales summary\n"
                "`!sales week` — weekly sales summary\n"
                "`!sales month` — monthly sales summary\n"
                "`!sales all` — all-time sales summary\n"
                "`!topitems` — top sold items\n"
                "`!lowstock` — products at or below 5 stock\n"
                "`!lowstock 2` — products at or below 2 stock\n"
                "`!stockvalue` — estimated inventory value\n"
                "`!buyerhistory @user` — buyer order history\n"
                "`!orderhistory` — recent completed orders\n"
                "`!staffstats week` — staff completed order stats"
            ),
            "moderation": (
                "**Ticket Moderation / Production Tools**\n"
                "`!lockticket reason`\n"
                "`!unlockticket reason`\n"
                "`!rename new-name`\n"
                "`!addbuyer @user`\n"
                "`!removebuyer @user`\n"
                "`!note text`\n"
                "`!blacklist @user reason`\n"
                "`!unblacklist @user`\n"
                "`!blacklistcheck @user`\n"
                "`!blacklistlist`"
            ),
            "short": (
                "**Best Commands**\n"
                "`!launch dark`\n"
                "`!conflicts`\n"
                "`!deepaudit`\n"
                "`!estock`\n"
                "`!sales today`\n"
                "`!topitems`\n"
                "`!lowstock`\n"
                "`!flow`\n"
                "`!ship`\n"
                "`!ct`"
            ),
            "buyer": (
                "**Buyer Controls**\n"
                "Buyers get checklist + I Paid / Ask Staff / Cancel buttons.\n"
                "Blacklisted buyers cannot open tickets."
            ),
            "flow": (
                "**Ticket Flow**\n"
                "**Buyer:** select item → fill checklist → I Paid\n"
                "**Staff:** Claim → Paid verify → Delivering → Ship\n\n"
                "Moderation tools: `!lockticket`, `!note`, `!blacklist`"
            ),
        }

        if page in pages:
            await ctx.reply(embed=embed_page(f"Commands: {page}", pages[page]), mention_author=False)
            return

        desc = (
            "**Pages**\n"
            "`!cmds short`\n"
            "`!cmds analytics`\n"
            "`!cmds moderation`\n"
            "`!cmds buyer`\n"
            "`!cmds flow`\n\n"
            "**New in v43:** sales analytics + stock intelligence."
        )
        await ctx.reply(embed=embed_page("Veil Commands", desc), mention_author=False)

async def setup(bot):
    await bot.add_cog(CommandCenterCog(bot))
