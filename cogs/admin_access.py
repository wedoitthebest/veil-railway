
import discord
from discord.ext import commands

from services.access_control import (
    ROOT_OWNER_ID,
    is_root_owner,
    is_owner,
    is_allowed,
    add_owner,
    remove_owner,
    add_allowed,
    remove_allowed,
    load_data,
    global_admin_check,
)

class AdminAccessCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not getattr(bot, "_veil_access_check_added", False):
            bot.add_check(global_admin_check)
            bot._veil_access_check_added = True

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.reply("You are not allowed to use Veil staff commands.", mention_author=False)
            return
        raise error

    @commands.command(name="addowner")
    async def add_owner_cmd(self, ctx, user_id: int):
        if not is_root_owner(ctx.author.id):
            await ctx.reply("Only the root owner can add owner IDs.", mention_author=False)
            return

        data = add_owner(user_id)
        await ctx.reply(
            f"Owner added: `{user_id}`\nOwners: `{', '.join(str(x) for x in data['owner_ids'])}`",
            mention_author=False,
        )

    @commands.command(name="removeowner")
    async def remove_owner_cmd(self, ctx, user_id: int):
        if not is_root_owner(ctx.author.id):
            await ctx.reply("Only the root owner can remove owner IDs.", mention_author=False)
            return

        data, removed, reason = remove_owner(user_id)
        if reason:
            await ctx.reply(reason, mention_author=False)
            return

        await ctx.reply(
            f"{'Removed owner' if removed else 'Owner not found'}: `{user_id}`\nOwners: `{', '.join(str(x) for x in data['owner_ids'])}`",
            mention_author=False,
        )

    @commands.command(name="owners")
    async def owners_cmd(self, ctx):
        if not is_allowed(ctx.author.id):
            await ctx.reply("You are not allowed to view this.", mention_author=False)
            return

        data = load_data()
        embed = discord.Embed(
            title="👑 Veil Owners",
            description=(
                f"**Root owner:** `{ROOT_OWNER_ID}`\n\n"
                "**Owner IDs:**\n"
                + "\n".join(f"• `{x}`" for x in data["owner_ids"])
            ),
            color=0xFFD166,
        )
        embed.set_footer(text="Only the root owner can add/remove owners.")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="allowid")
    async def allow_id(self, ctx, user_id: int):
        if not is_owner(ctx.author.id):
            await ctx.reply("Only owners can add allowed command users.", mention_author=False)
            return

        data = add_allowed(user_id)
        await ctx.reply(
            f"Allowed `{user_id}`.\nCurrent allowed IDs: `{', '.join(str(x) for x in data['allowed_ids'])}`",
            mention_author=False,
        )

    @commands.command(name="denyid")
    async def deny_id(self, ctx, user_id: int):
        if not is_owner(ctx.author.id):
            await ctx.reply("Only owners can remove allowed command users.", mention_author=False)
            return

        data, removed, reason = remove_allowed(user_id)
        if reason:
            await ctx.reply(reason, mention_author=False)
            return

        await ctx.reply(
            f"{'Removed' if removed else 'Not found'} `{user_id}`.\nCurrent allowed IDs: `{', '.join(str(x) for x in data['allowed_ids'])}`",
            mention_author=False,
        )

    @commands.command(name="allowedids")
    async def allowed_ids(self, ctx):
        if not is_allowed(ctx.author.id):
            await ctx.reply("You are not allowed to view this.", mention_author=False)
            return

        data = load_data()
        embed = discord.Embed(
            title="🔐 Veil Command Access",
            description=(
                f"**Root owner:** `{ROOT_OWNER_ID}`\n\n"
                "**Owners:**\n"
                + "\n".join(f"• `{x}`" for x in data["owner_ids"])
                + "\n\n**Allowed staff/user IDs:**\n"
                + "\n".join(f"• `{x}`" for x in data["allowed_ids"])
            ),
            color=0x7C3CFF,
        )
        embed.set_footer(text="Owners can manage allowed IDs. Root owner can manage owners.")
        await ctx.reply(embed=embed, mention_author=False)

async def setup(bot):
    await bot.add_cog(AdminAccessCog(bot))
