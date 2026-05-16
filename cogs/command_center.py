
import discord
from discord import app_commands
from discord.ext import commands

from services.access_control import is_allowed

CATEGORIES = [
    app_commands.Choice(name="all", value="all"),
    app_commands.Choice(name="short", value="short"),
    app_commands.Choice(name="setup", value="setup"),
    app_commands.Choice(name="pinned", value="pinned"),
    app_commands.Choice(name="images", value="images"),
    app_commands.Choice(name="stock", value="stock"),
    app_commands.Choice(name="tickets", value="tickets"),
    app_commands.Choice(name="moderation", value="moderation"),
    app_commands.Choice(name="analytics", value="analytics"),
    app_commands.Choice(name="access", value="access"),
    app_commands.Choice(name="stability", value="stability"),
    app_commands.Choice(name="buyer", value="buyer"),
]

def allowed_user(user):
    try:
        return is_allowed(user.id) or user.guild_permissions.manage_channels or user.guild_permissions.administrator
    except Exception:
        return False

def embed_page(title, description):
    embed = discord.Embed(title=title, description=description[:3900], color=0x7C3CFF)
    embed.set_footer(text="Veil's Grocery Store • Command Menu")
    return embed

def command_pages():
    return {
        "short": (
            "**Main Commands**\n"
            "`/cmds` — command menu\n"
            "`/launch dark` — setup / refresh server\n"
            "`/health` — quick bot health\n"
            "`/deepaudit` — full server audit\n"
            "`/conflicts` — command conflict scan\n"
            "`/estock` — sync stock and rebuild boards\n"
            "`/safetypin` — pinned scam warning\n"
            "`/flow` — staff order checklist\n"
            "`/sales today` — sales summary\n"
            "`/lowstock` — low stock check"
        ),
        "setup": (
            "**Setup / Admin**\n"
            "`/launch dark` `/launch neon` `/launch clean`\n"
            "`/admin`\n"
            "`/audit`\n"
            "`/deepaudit`\n"
            "`/health`\n"
            "`/logtest`\n"
            "`/cogs`\n"
            "`/conflicts`\n"
            "`/cmdmap`\n"
            "`/cmdmap runtime`"
        ),
        "pinned": (
            "**Pinned Safety Messages**\n"
            "`/safetypin` — post/update scam warning in current channel\n"
            "`/safetypin channel:#channel` — post/update in selected channel\n"
            "`/pinmsg name:scam-warning` — post scam-warning preset\n"
            "`/pinmsg name:rules-safety` — post rules-safety preset\n"
            "`/unpinmsg name:scam-warning` — remove remembered pin\n"
            "`/pinlist` — show remembered pins\n\n"
            "**Recommended:** run `/safetypin` in public channels."
        ),
        "images": (
            "**Images / Embeds**\n"
            "`/setimage welcome URL`\n"
            "`/setimage announcements URL`\n"
            "`/setimage payments URL`\n"
            "`/setimage benefits URL`\n"
            "`/setimage rules URL`\n"
            "`/setimage tickets URL`\n"
            "`/setimage vouches URL`\n"
            "`/setimage aotr URL`\n"
            "`/setimage gpo URL`\n"
            "`/setimage sbtd URL`\n"
            "`/setimage da-hood URL`\n"
            "`/setimage other URL`\n"
            "`/previewimage key`\n"
            "`/imagekeys`\n"
            "`/imagepreset dark|neon|clean`\n"
            "`/msgs` — refresh server embeds"
        ),
        "stock": (
            "**Eldorado / Stock**\n"
            "`/estock`\n"
            "`/eldostock`\n"
            "`/syncstock`\n"
            "`/stockboard`\n"
            "`/sb`\n"
            "`/persistviews`\n"
            "`/stocksetup`\n"
            "`/ssu`\n"
            "`/find item`\n"
            "`/eroute`\n"
            "`/egame product_id game`\n"
            "`/eall keyword game`"
        ),
        "tickets": (
            "**Tickets / Order Flow**\n"
            "`/flow`\n"
            "`/claim` / `/cl`\n"
            "`/paid` / `/p`\n"
            "`/delivering` / `/d`\n"
            "`/ship`\n"
            "`/complete`\n"
            "`/done`\n"
            "`/finish`\n"
            "`/fill`\n"
            "`/sent`\n"
            "`/ok`\n"
            "`/closeticket` / `/ct` / `/close`\n"
            "`/transcript` / `/tr`\n"
            "`/cancelorder` / `/co`\n\n"
            "**Ticket buttons:** Claim, Paid, Delivering, Ship, Close\n"
            "**Buyer buttons:** I Paid, Ask Staff, Cancel Order"
        ),
        "moderation": (
            "**Ticket Moderation**\n"
            "`/lockticket reason`\n"
            "`/unlockticket reason`\n"
            "`/rename new-name`\n"
            "`/renameticket new-name`\n"
            "`/addbuyer @user`\n"
            "`/removebuyer @user`\n"
            "`/note text`\n"
            "`/blacklist @user reason`\n"
            "`/unblacklist @user`\n"
            "`/blacklistcheck @user`\n"
            "`/blacklistlist`"
        ),
        "analytics": (
            "**Analytics / Stats**\n"
            "`/analytics`\n"
            "`/sales today`\n"
            "`/sales week`\n"
            "`/sales month`\n"
            "`/sales all`\n"
            "`/topitems`\n"
            "`/topsold`\n"
            "`/lowstock`\n"
            "`/lowstock 2`\n"
            "`/stockvalue`\n"
            "`/inventoryvalue`\n"
            "`/stockworth`\n"
            "`/buyerhistory @user`\n"
            "`/orderhistory`\n"
            "`/recentorders`\n"
            "`/staffstats week`\n"
            "`/staffsales week`\n"
            "`/orderstats` `/os` `/stats`"
        ),
        "access": (
            "**Access Control**\n"
            "`/addowner user_id`\n"
            "`/removeowner user_id`\n"
            "`/owners`\n"
            "`/allowid user_id`\n"
            "`/denyid user_id`\n"
            "`/allowedids`\n\n"
            "Only the main owner can add more owners."
        ),
        "stability": (
            "**Stability / Debug**\n"
            "`/conflicts`\n"
            "`/cmdmap`\n"
            "`/cmdmap runtime`\n"
            "`/cogs`\n"
            "`/health`\n"
            "`/deepaudit`\n"
            "`/logtest`"
        ),
        "buyer": (
            "**Buyer Experience**\n"
            "Buyers get:\n"
            "• checklist inside ticket\n"
            "• I Paid button\n"
            "• Ask Staff button\n"
            "• Cancel Order button\n\n"
            "Anti-spam:\n"
            "• one open ticket per buyer\n"
            "• ticket cooldown\n"
            "• inactivity warning\n"
            "• inactivity auto-close\n"
            "• blacklist blocks tickets"
        ),
    }

def all_menu_text():
    return (
        "**Command Categories**\n"
        "`/cmds category:short` — best commands\n"
        "`/cmds category:setup` — launch/audit/admin\n"
        "`/cmds category:pinned` — safety pins\n"
        "`/cmds category:images` — set banner images\n"
        "`/cmds category:stock` — Eldorado/stock\n"
        "`/cmds category:tickets` — order/ticket flow\n"
        "`/cmds category:moderation` — locks/blacklist/notes\n"
        "`/cmds category:analytics` — sales/stats\n"
        "`/cmds category:access` — owner IDs\n"
        "`/cmds category:stability` — debug tools\n"
        "`/cmds category:buyer` — buyer flow\n\n"
        "**Most used:** `/launch dark`, `/estock`, `/safetypin`, `/setimage`, `/flow`, `/ship`, `/sales today`"
    )

class CommandCenterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_menu(self, target, category="all", ephemeral=False):
        category = str(category or "all").lower().strip()
        pages = command_pages()

        if category == "all":
            embed = embed_page("Veil Commands", all_menu_text())
        elif category in pages:
            embed = embed_page(f"Commands: {category}", pages[category])
        else:
            embed = embed_page("Veil Commands", all_menu_text())

        if isinstance(target, discord.Interaction):
            if target.response.is_done():
                await target.followup.send(embed=embed, ephemeral=ephemeral)
            else:
                await target.response.send_message(embed=embed, ephemeral=ephemeral)
        else:
            await target.reply(embed=embed, mention_author=False)

    @app_commands.command(name="cmds", description="Show Veil command categories and commands.")
    @app_commands.describe(category="Command category to show.")
    @app_commands.choices(category=CATEGORIES)
    async def slash_cmds(self, interaction: discord.Interaction, category: app_commands.Choice[str] = None):
        if not allowed_user(interaction.user):
            await interaction.response.send_message("You are not allowed to view Veil commands.", ephemeral=True)
            return
        await self.send_menu(interaction, category.value if category else "all", ephemeral=True)

    @commands.command(name="cmds", aliases=["commands", "helpme"])
    async def prefix_cmds(self, ctx, page: str = "all"):
        if not is_allowed(ctx.author.id):
            await ctx.reply("You are not allowed to view Veil commands.", mention_author=False)
            return
        await self.send_menu(ctx, page)

async def setup(bot):
    await bot.add_cog(CommandCenterCog(bot))
