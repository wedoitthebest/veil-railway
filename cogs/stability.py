
import discord
from discord.ext import commands

from services.access_control import is_allowed
from services.command_registry import (
    scan_commands,
    command_map_lines,
    duplicate_lines,
    runtime_command_lines,
    runtime_duplicates,
)
from services.log_service import log_event

def chunk_text(text, limit=3800):
    text = str(text or "")
    if len(text) <= limit:
        return [text]

    pages = []
    current = []
    current_len = 0

    for line in text.splitlines():
        extra = len(line) + 1
        if current and current_len + extra > limit:
            pages.append("\n".join(current))
            current = [line]
            current_len = extra
        else:
            current.append(line)
            current_len += extra

    if current:
        pages.append("\n".join(current))

    return pages or [""]

def chunk_lines(lines, limit=3800):
    pages = []
    current = []
    current_len = 0

    for line in lines:
        line = str(line)
        extra = len(line) + 1
        if current and current_len + extra > limit:
            pages.append("\n".join(current))
            current = [line]
            current_len = extra
        else:
            current.append(line)
            current_len += extra

    if current:
        pages.append("\n".join(current))

    return pages or [""]

class StabilityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._startup_checked = False

    @commands.Cog.listener()
    async def on_ready(self):
        if self._startup_checked:
            return
        self._startup_checked = True

        try:
            report = scan_commands()
            dupes = report.get("duplicates", {})
            wrong = report.get("wrong_owners", [])
            errors = report.get("errors", [])
            runtime_dupes = runtime_duplicates(self.bot)

            print(f"[STABILITY] Commands scanned: {len(report.get('commands', []))}")
            print(f"[STABILITY] Source duplicates: {len(dupes)}")
            print(f"[STABILITY] Wrong owners: {len(wrong)}")
            print(f"[STABILITY] Runtime duplicates: {len(runtime_dupes)}")

            for guild in self.bot.guilds:
                if dupes or wrong or errors or runtime_dupes:
                    await log_event(
                        guild,
                        "system",
                        "⚠️ Command Stability Warning",
                        {
                            "Source duplicates": len(dupes),
                            "Wrong owners": len(wrong),
                            "Runtime duplicates": len(runtime_dupes),
                            "Scan errors": len(errors),
                            "Action": "Run !conflicts and fix before adding features.",
                        },
                        send=True,
                    )
                else:
                    await log_event(
                        guild,
                        "system",
                        "✅ Command Stability OK",
                        {"Commands scanned": len(report.get("commands", [])), "Runtime commands": len(list(self.bot.commands))},
                        send=True,
                    )
        except Exception as exc:
            print(f"[STABILITY ERROR] {exc}")

    @commands.command(name="cmdmap", aliases=["commandmap"])
    async def cmd_map(self, ctx, mode: str = "source"):
        if not is_allowed(ctx.author.id):
            await ctx.reply("You are not allowed to view command maps.", mention_author=False)
            return

        if mode.lower() == "runtime":
            lines = runtime_command_lines(self.bot)
            title = "🧭 Runtime Command Map"
        else:
            report = scan_commands()
            lines = command_map_lines(report)
            title = "🧭 Source Command Map"

        pages = chunk_lines(lines)
        for idx, page in enumerate(pages[:5], start=1):
            embed = discord.Embed(title=f"{title} {idx}/{len(pages)}", description=page, color=0x7C3CFF)
            embed.set_footer(text="Use !cmdmap runtime to see loaded commands.")
            if idx == 1:
                await ctx.reply(embed=embed, mention_author=False)
            else:
                await ctx.send(embed=embed)

    @commands.command(name="conflicts", aliases=["dupes", "commandconflicts"])
    async def conflicts(self, ctx):
        if not is_allowed(ctx.author.id):
            await ctx.reply("You are not allowed to view conflicts.", mention_author=False)
            return

        report = scan_commands()
        lines = duplicate_lines(report)

        runtime_dupes = runtime_duplicates(self.bot)
        if runtime_dupes:
            lines.append("\n**Runtime duplicates:**")
            for name, refs in runtime_dupes.items():
                lines.append(f"`!{name}` → " + " | ".join(refs))
        else:
            lines.append("\nRuntime duplicates: none.")

        pages = chunk_lines(lines)
        for idx, page in enumerate(pages[:4], start=1):
            fail = bool(report.get("duplicates") or report.get("wrong_owners") or runtime_dupes)
            embed = discord.Embed(
                title=f"{'⚠️' if fail else '✅'} Command Conflict Report {idx}/{len(pages)}",
                description=page,
                color=0xE06C75 if fail else 0x44D69F,
            )
            embed.set_footer(text="Source scan saved to logs/command_registry_report.json")
            if idx == 1:
                await ctx.reply(embed=embed, mention_author=False)
            else:
                await ctx.send(embed=embed)

        await log_event(
            ctx.guild,
            "system",
            "Command Conflict Scan",
            {
                "Source duplicates": len(report.get("duplicates", {})),
                "Wrong owners": len(report.get("wrong_owners", [])),
                "Runtime duplicates": len(runtime_dupes),
                "Scan errors": len(report.get("errors", [])),
            },
            actor=ctx.author,
        )

    @commands.command(name="cogs", aliases=["loadedcogs"])
    async def cogs(self, ctx):
        if not is_allowed(ctx.author.id):
            await ctx.reply("You are not allowed to view cogs.", mention_author=False)
            return

        loaded_ext = getattr(self.bot, "veil_loaded_extensions", [])
        failed_ext = getattr(self.bot, "veil_failed_extensions", [])
        loaded_cogs = sorted(self.bot.cogs.keys())

        loaded_text = "\n".join(f"✅ `{x}`" for x in loaded_ext) if loaded_ext else "`unknown`"
        failed_text = "\n".join(f"❌ `{name}` — {err}" for name, err in failed_ext) if failed_ext else "`none`"
        cogs_text = "\n".join(f"• `{x}`" for x in loaded_cogs) if loaded_cogs else "`none`"

        desc = (
            "**Loaded extensions:**\n"
            f"{loaded_text}\n\n"
            "**Failed extensions:**\n"
            f"{failed_text}\n\n"
            "**Loaded cog classes:**\n"
            f"{cogs_text}"
        )

        pages = chunk_text(desc)
        for idx, page in enumerate(pages, start=1):
            embed = discord.Embed(title=f"🧩 Cog Status {idx}/{len(pages)}", description=page, color=0x7C3CFF)
            if idx == 1:
                await ctx.reply(embed=embed, mention_author=False)
            else:
                await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(StabilityCog(bot))
