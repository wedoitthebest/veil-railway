import discord
from discord.ext import commands

ELDORADO_URL = "https://www.eldorado.gg/users/012"

def clean(n):
    import re
    n = str(n).lower().strip()
    n = re.sub(r"[^a-z0-9-]+", "-", n)
    return re.sub(r"-+", "-", n).strip("-") or "channel"

def find_channel(guild, names):
    wanted = [clean(n) for n in names]
    for channel in guild.text_channels:
        if clean(channel.name) in wanted:
            return channel
    return None

def welcome_server_embed(member):
    embed = discord.Embed(
        title="🌌 Welcome to Veil Marketplace",
        description=(
            f"Welcome {member.mention}.\n\n"
            "Make your money worth it at **Veil**.\n\n"
            "🛒 **Items available:**\n"
            "`AOTR` // `GPO` // `SBTD` // `Da Hood`\n\n"
            "🎟 Open a ticket in `#tickets`\n"
            "⭐ Reviews & referrals in `#vouches`\n"
            "📢 Stocks in `#stock`"
        ),
        color=0x7C3CFF
    )
    embed.set_footer(text="Veil Marketplace")
    return embed

def welcome_dm_embed(member):
    embed = discord.Embed(
        title="Welcome to Veil Marketplace",
        description=(
            "Thanks for joining **Veil**.\n\n"
            "**Quick start:**\n"
            "• Check stock channels first\n"
            "• Review payment methods\n"
            "• Check reviews/referrals\n"
            "• Open a ticket when ready to buy\n\n"
            "**Current items:**\n"
            "`AOTR` // `GPO` // `SBTD` // `Da Hood`\n\n"
            f"**Eldorado reputation:**\n{ELDORADO_URL}"
        ),
        color=0x7C3CFF
    )
    embed.set_footer(text="Fast support • Clean service • Public reputation")
    return embed

class WelcomeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        try:
            role = (
                discord.utils.get(member.guild.roles, name="Shop Member")
                or discord.utils.get(member.guild.roles, name="Member")
            )
            if role:
                await member.add_roles(role, reason="Veil auto member role")
        except Exception:
            pass

        try:
            channel = find_channel(member.guild, ["welcome", "welcomes", "join", "general"])
            if channel:
                await channel.send(embed=welcome_server_embed(member))
        except Exception:
            pass

        try:
            await member.send(embed=welcome_dm_embed(member))
        except Exception:
            pass

    @commands.command(name="testwelcome")
    @commands.has_permissions(administrator=True)
    async def test_welcome(self, ctx):
        await ctx.send(embed=welcome_server_embed(ctx.author))

    @commands.command(name="testdmwelcome")
    @commands.has_permissions(administrator=True)
    async def test_dm_welcome(self, ctx):
        try:
            await ctx.author.send(embed=welcome_dm_embed(ctx.author))
            await ctx.send("DM welcome sent.")
        except Exception as exc:
            await ctx.send(f"Could not DM you: `{exc}`")

async def setup(bot):
    await bot.add_cog(WelcomeCog(bot))
