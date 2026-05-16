
import discord
from discord.ext import commands

from services.access_control import is_allowed
from services.embed_theme import success, apply_preset
from services.log_service import log_event
from services.audit_service import run_deep_audit, summary_counts

try:
    from cogs.server_setup import ensure_roles, ensure_structure, clean_known_markers
except Exception:
    ensure_roles = None
    ensure_structure = None
    clean_known_markers = None

try:
    from cogs.message_polish import EMBEDS, find_channel, purge_polish_messages
except Exception:
    EMBEDS = {}
    find_channel = None
    purge_polish_messages = None

try:
    from eldorado_sync import sync_eldorado_products
except Exception:
    sync_eldorado_products = None

try:
    from services.stock_board_service import rebuild_all_boards, ensure_stock_channels
except Exception:
    rebuild_all_boards = None
    ensure_stock_channels = None

class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="Deep Audit", style=discord.ButtonStyle.secondary)
    async def audit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_allowed(interaction.user.id):
            await interaction.response.send_message("Not allowed.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        results = await run_deep_audit(interaction.guild)
        ok_count, warn_count, fail_count = summary_counts(results)
        await interaction.followup.send(f"Audit complete: ✅ {ok_count}, ⚠️ {warn_count}, ❌ {fail_count}. Use `!deepaudit` for details.", ephemeral=True)

    @discord.ui.button(label="Sync Stock", style=discord.ButtonStyle.success)
    async def sync_stock(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_allowed(interaction.user.id):
            await interaction.response.send_message("Not allowed.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        imported = 0
        if sync_eldorado_products:
            result = sync_eldorado_products()
            imported = result.get("count", 0)
        if rebuild_all_boards:
            await rebuild_all_boards(interaction.guild)
        await log_event(interaction.guild, "stock", "🛒 Admin Panel Stock Sync", {"Imported": imported}, actor=interaction.user)
        await interaction.followup.send(f"Stock synced and boards rebuilt. Imported `{imported}`.", ephemeral=True)

    @discord.ui.button(label="Refresh Boards", style=discord.ButtonStyle.primary)
    async def refresh_boards(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_allowed(interaction.user.id):
            await interaction.response.send_message("Not allowed.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        posted = 0
        if rebuild_all_boards:
            _, posted, _ = await rebuild_all_boards(interaction.guild)
        await log_event(interaction.guild, "stock", "🛒 Admin Panel Board Refresh", {"Boards posted": posted}, actor=interaction.user)
        await interaction.followup.send(f"Stock boards rebuilt. Posted `{posted}`.", ephemeral=True)

    @discord.ui.button(label="Post Messages", style=discord.ButtonStyle.primary)
    async def post_messages(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_allowed(interaction.user.id):
            await interaction.response.send_message("Not allowed.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        posted = 0
        if EMBEDS and find_channel:
            for key, factory in EMBEDS.items():
                channel = find_channel(interaction.guild, key)
                if channel:
                    if purge_polish_messages:
                        await purge_polish_messages(channel)
                    await channel.send(embed=factory())
                    posted += 1
        await log_event(interaction.guild, "setup", "📌 Admin Panel Messages Posted", {"Posted": posted}, actor=interaction.user)
        await interaction.followup.send(f"Posted {posted} server embeds.", ephemeral=True)

class LaunchAdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="launch")
    async def launch(self, ctx, preset: str = None):
        if not is_allowed(ctx.author.id):
            await ctx.reply("You are not allowed to use this command.", mention_author=False)
            return

        status = await ctx.reply("Launching full Veil setup...", mention_author=False)

        roles_created = roles_updated = cats_created = channels_created = deleted = posted = boards = imported = 0
        warnings = []
        applied_preset = None

        try:
            if preset:
                ok, result = apply_preset(preset)
                if ok:
                    applied_preset = result
                else:
                    warnings.append(result)

            if ensure_roles:
                made, updated = await ensure_roles(ctx.guild)
                roles_created = len(made)
                roles_updated = len(updated)
            else:
                warnings.append("role setup unavailable")

            if ensure_structure:
                cats, channels = await ensure_structure(ctx.guild)
                cats_created = len(cats)
                channels_created = len(channels)
            else:
                warnings.append("channel setup unavailable")

            if clean_known_markers:
                deleted = await clean_known_markers(ctx.guild)

            if EMBEDS and find_channel:
                for key, factory in EMBEDS.items():
                    channel = find_channel(ctx.guild, key)
                    if channel:
                        if purge_polish_messages:
                            await purge_polish_messages(channel)
                        await channel.send(embed=factory())
                        posted += 1

            if ensure_stock_channels:
                await ensure_stock_channels(ctx.guild)

            if sync_eldorado_products:
                try:
                    result = sync_eldorado_products()
                    imported = result.get("count", 0)
                except Exception as exc:
                    warnings.append(f"Eldorado sync failed: {exc}")

            if rebuild_all_boards:
                try:
                    _, board_posts, _ = await rebuild_all_boards(ctx.guild)
                    boards = board_posts
                except Exception as exc:
                    warnings.append(f"stock board rebuild failed: {exc}")

            audit_results = await run_deep_audit(ctx.guild)
            ok_count, warn_count, fail_count = summary_counts(audit_results)

            embed = success(
                "🚀 Veil Launch Complete",
                (
                    f"**Image preset:** `{applied_preset or 'unchanged'}`\n"
                    f"**Roles created:** `{roles_created}`\n"
                    f"**Roles updated:** `{roles_updated}`\n"
                    f"**Categories created:** `{cats_created}`\n"
                    f"**Channels created:** `{channels_created}`\n"
                    f"**Old bot messages cleaned:** `{deleted}`\n"
                    f"**Polished embeds posted:** `{posted}`\n"
                    f"**Eldorado listings imported:** `{imported}`\n"
                    f"**Stock boards posted:** `{boards}`\n\n"
                    f"**Audit:** ✅ `{ok_count}` • ⚠️ `{warn_count}` • ❌ `{fail_count}`"
                )
            )

            if warnings:
                embed.add_field(name="Warnings", value="\n".join(f"• {w}" for w in warnings)[:1000], inline=False)

            await status.edit(content=None, embed=embed)

            await log_event(
                ctx.guild,
                "setup",
                "🚀 Launch Complete",
                {
                    "Preset": applied_preset or "unchanged",
                    "Roles created": roles_created,
                    "Channels created": channels_created,
                    "Messages posted": posted,
                    "Eldorado imported": imported,
                    "Boards posted": boards,
                    "Audit OK": ok_count,
                    "Audit warnings": warn_count,
                    "Audit failures": fail_count,
                },
                actor=ctx.author,
            )

        except Exception as exc:
            await status.edit(content=f"Launch failed: `{exc}`")
            await log_event(ctx.guild, "error", "❌ Launch Failed", {"Error": exc}, actor=ctx.author)

    @commands.command(name="audit")
    async def audit(self, ctx):
        if not is_allowed(ctx.author.id):
            await ctx.reply("You are not allowed to use this command.", mention_author=False)
            return
        results = await run_deep_audit(ctx.guild)
        ok_count, warn_count, fail_count = summary_counts(results)
        embed = discord.Embed(
            title="🧾 Veil Audit Summary",
            description=f"✅ `{ok_count}` ok\n⚠️ `{warn_count}` warnings\n❌ `{fail_count}` failures\n\nUse `!deepaudit` for full details.",
            color=0xE06C75 if fail_count else (0xFFD166 if warn_count else 0x44D69F)
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="admin")
    async def admin(self, ctx):
        if not is_allowed(ctx.author.id):
            await ctx.reply("You are not allowed to use this command.", mention_author=False)
            return
        embed = discord.Embed(
            title="🛠️ Veil Admin Panel",
            description="Use the buttons for common maintenance.",
            color=0x7C3CFF
        )
        embed.set_footer(text="Buttons expire after 2 minutes.")
        await ctx.reply(embed=embed, view=AdminPanelView(), mention_author=False)

async def setup(bot):
    await bot.add_cog(LaunchAdminCog(bot))
