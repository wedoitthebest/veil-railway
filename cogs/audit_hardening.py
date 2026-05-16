
import os
import platform
import discord
from discord.ext import commands

from services.access_control import is_allowed
from services.audit_service import run_deep_audit, format_results, summary_counts
from services.log_service import log_event

class AuditHardeningCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._startup_logged = False

    @commands.Cog.listener()
    async def on_ready(self):
        if self._startup_logged:
            return
        self._startup_logged = True

        print("[HEALTH] Veil startup health check running...")

        for guild in self.bot.guilds:
            try:
                results = await run_deep_audit(guild)
                ok_count, warn_count, fail_count = summary_counts(results)
                await log_event(
                    guild,
                    "health",
                    "🩺 Startup Health Report",
                    {
                        "Guild": guild.name,
                        "OK": ok_count,
                        "Warnings": warn_count,
                        "Failures": fail_count,
                        "Python": platform.python_version(),
                        "Discord.py": discord.__version__,
                    },
                    send=True,
                )
                print(f"[HEALTH] {guild.name}: ok={ok_count} warn={warn_count} fail={fail_count}")
            except Exception as exc:
                print(f"[HEALTH ERROR] {guild.name}: {exc}")

    @commands.command(name="deepaudit", aliases=["hardaudit", "auditdeep"])
    async def deep_audit(self, ctx):
        if not is_allowed(ctx.author.id):
            await ctx.reply("You are not allowed to run audits.", mention_author=False)
            return

        status = await ctx.reply("Running deep audit...", mention_author=False)
        results = await run_deep_audit(ctx.guild)
        ok_count, warn_count, fail_count = summary_counts(results)

        embed = discord.Embed(
            title="🧾 Deep Veil Audit",
            description=format_results(results),
            color=0xE06C75 if fail_count else (0xFFD166 if warn_count else 0x44D69F)
        )
        embed.add_field(name="Summary", value=f"✅ `{ok_count}` ok\n⚠️ `{warn_count}` warnings\n❌ `{fail_count}` failures", inline=False)
        embed.set_footer(text="Veil Audit • fix failures before adding more features")
        await status.edit(content=None, embed=embed)

        await log_event(
            ctx.guild,
            "audit",
            "🧾 Deep Audit Run",
            {
                "OK": ok_count,
                "Warnings": warn_count,
                "Failures": fail_count,
                "Channel": ctx.channel.mention,
            },
            actor=ctx.author,
        )

    @commands.command(name="health", aliases=["healthcheck"])
    async def health(self, ctx):
        if not is_allowed(ctx.author.id):
            await ctx.reply("You are not allowed to view health.", mention_author=False)
            return

        env_checks = []
        for key in ["DISCORD_TOKEN", "ELDORADO_EMAIL", "ELDORADO_PASSWORD"]:
            env_checks.append(f"{'✅' if os.getenv(key) else '❌'} `{key}`")

        embed = discord.Embed(
            title="🩺 Veil Health",
            description=(
                f"**Bot:** `{self.bot.user}`\n"
                f"**Guilds:** `{len(self.bot.guilds)}`\n"
                f"**Latency:** `{round(self.bot.latency * 1000)}ms`\n"
                f"**Python:** `{platform.python_version()}`\n"
                f"**discord.py:** `{discord.__version__}`\n\n"
                "**Environment:**\n"
                + "\n".join(env_checks)
            ),
            color=0x4DA3FF
        )
        embed.set_footer(text="Use !deepaudit for the full check.")
        await ctx.reply(embed=embed, mention_author=False)

        await log_event(
            ctx.guild,
            "health",
            "🩺 Manual Health Check",
            {"Latency": f"{round(self.bot.latency * 1000)}ms", "Channel": ctx.channel.mention},
            actor=ctx.author,
        )

    @commands.command(name="logtest")
    async def log_test(self, ctx):
        if not is_allowed(ctx.author.id):
            await ctx.reply("You are not allowed to test logs.", mention_author=False)
            return

        sent = await log_event(
            ctx.guild,
            "system",
            "🧪 Log Test",
            {"Result": "If you can see this in logs, structured logging works.", "Channel": ctx.channel.mention},
            actor=ctx.author,
        )
        await ctx.reply(f"Log test {'sent to log channel' if sent else 'saved to file only; no log channel found'}." , mention_author=False)

async def setup(bot):
    await bot.add_cog(AuditHardeningCog(bot))
