
import re
import discord
from discord.ext import commands

from services.access_control import is_allowed
from services.ticket_panel import is_ticket_channel, ticket_owner_id, update_ticket_panel
from services.log_service import log_event
from services.blacklist_service import blacklist_user, unblacklist_user, is_blacklisted, list_blacklisted

def staff_allowed(member):
    if is_allowed(member.id):
        return True
    names = ["Owner", "Store Manager", "Support", "Store Owner", "Shelf Keeper", "Admin", "Moderator"]
    return member.guild_permissions.manage_channels or any(role.name in names for role in getattr(member, "roles", []))

def clean_name(value):
    value = str(value or "").lower().strip()
    value = re.sub(r"[^a-z0-9-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:80] or "ticket"

def ticket_member_from_mention(ctx, member=None):
    return member

class TicketModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def guard_staff(self, ctx):
        return staff_allowed(ctx.author)

    @commands.command(name="lockticket", aliases=["tlock", "lockt"])
    async def lock_ticket(self, ctx, *, reason="Locked by staff."):
        if not is_ticket_channel(ctx.channel):
            await ctx.reply("Use this inside a ticket.", mention_author=False)
            return
        if not self.guard_staff(ctx):
            await ctx.reply("Only staff can lock tickets.", mention_author=False)
            return

        owner_id = ticket_owner_id(ctx.channel)
        member = ctx.guild.get_member(owner_id) if owner_id else None
        if not member:
            await ctx.reply("Ticket owner not found.", mention_author=False)
            return

        await ctx.channel.set_permissions(member, send_messages=False, view_channel=True, read_message_history=True)
        await update_ticket_panel(ctx.channel, status="waiting", staff=ctx.author, note=f"Ticket locked: {reason}")
        await log_event(ctx.guild, "ticket", "🔒 Ticket Locked", {"Ticket": ctx.channel.mention, "Buyer": member.mention, "Reason": reason}, actor=ctx.author)
        await ctx.reply(f"Ticket locked for {member.mention}.", mention_author=False)

    @commands.command(name="unlockticket", aliases=["tunlock", "unlockt"])
    async def unlock_ticket(self, ctx, *, reason="Unlocked by staff."):
        if not is_ticket_channel(ctx.channel):
            await ctx.reply("Use this inside a ticket.", mention_author=False)
            return
        if not self.guard_staff(ctx):
            await ctx.reply("Only staff can unlock tickets.", mention_author=False)
            return

        owner_id = ticket_owner_id(ctx.channel)
        member = ctx.guild.get_member(owner_id) if owner_id else None
        if not member:
            await ctx.reply("Ticket owner not found.", mention_author=False)
            return

        await ctx.channel.set_permissions(member, send_messages=True, view_channel=True, read_message_history=True, attach_files=True)
        await update_ticket_panel(ctx.channel, status="waiting", staff=ctx.author, note=f"Ticket unlocked: {reason}")
        await log_event(ctx.guild, "ticket", "🔓 Ticket Unlocked", {"Ticket": ctx.channel.mention, "Buyer": member.mention, "Reason": reason}, actor=ctx.author)
        await ctx.reply(f"Ticket unlocked for {member.mention}.", mention_author=False)

    @commands.command(name="renameticket", aliases=["rename", "rnt"])
    async def rename_ticket(self, ctx, *, name: str):
        if not is_ticket_channel(ctx.channel):
            await ctx.reply("Use this inside a ticket.", mention_author=False)
            return
        if not self.guard_staff(ctx):
            await ctx.reply("Only staff can rename tickets.", mention_author=False)
            return

        new_name = clean_name(name)
        if not new_name.startswith("ticket-"):
            new_name = "ticket-" + new_name

        old_name = ctx.channel.name
        await ctx.channel.edit(name=new_name[:90], reason=f"Ticket renamed by {ctx.author}")
        await log_event(ctx.guild, "ticket", "✏️ Ticket Renamed", {"Old": old_name, "New": new_name}, actor=ctx.author)
        await ctx.reply(f"Ticket renamed to `#{new_name}`.", mention_author=False)

    @commands.command(name="addbuyer", aliases=["adduser", "ticketadd"])
    async def add_buyer(self, ctx, member: discord.Member):
        if not is_ticket_channel(ctx.channel):
            await ctx.reply("Use this inside a ticket.", mention_author=False)
            return
        if not self.guard_staff(ctx):
            await ctx.reply("Only staff can add users to tickets.", mention_author=False)
            return

        await ctx.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True, attach_files=True)
        await log_event(ctx.guild, "ticket", "➕ User Added To Ticket", {"Ticket": ctx.channel.mention, "User": member.mention}, actor=ctx.author)
        await ctx.reply(f"Added {member.mention} to this ticket.", mention_author=False)

    @commands.command(name="removebuyer", aliases=["removeuser", "ticketremove"])
    async def remove_buyer(self, ctx, member: discord.Member):
        if not is_ticket_channel(ctx.channel):
            await ctx.reply("Use this inside a ticket.", mention_author=False)
            return
        if not self.guard_staff(ctx):
            await ctx.reply("Only staff can remove users from tickets.", mention_author=False)
            return

        owner_id = ticket_owner_id(ctx.channel)
        if owner_id and member.id == owner_id:
            await ctx.reply("Use `!ct` or `!lockticket` for the main buyer. Do not remove the ticket owner directly.", mention_author=False)
            return

        await ctx.channel.set_permissions(member, overwrite=None)
        await log_event(ctx.guild, "ticket", "➖ User Removed From Ticket", {"Ticket": ctx.channel.mention, "User": member.mention}, actor=ctx.author)
        await ctx.reply(f"Removed {member.mention} from this ticket.", mention_author=False)

    @commands.command(name="note", aliases=["staffnote", "tnote"])
    async def staff_note(self, ctx, *, note: str):
        if not is_ticket_channel(ctx.channel):
            await ctx.reply("Use this inside a ticket.", mention_author=False)
            return
        if not self.guard_staff(ctx):
            await ctx.reply("Only staff can add notes.", mention_author=False)
            return

        await log_event(ctx.guild, "ticket", "📝 Staff Note", {"Ticket": ctx.channel.mention, "Note": note}, actor=ctx.author)
        await update_ticket_panel(ctx.channel, staff=ctx.author, note=f"Staff note added to logs.")
        await ctx.reply("Staff note saved to logs.", mention_author=False)

    @commands.command(name="blacklist", aliases=["bl"])
    async def blacklist(self, ctx, member: discord.Member, *, reason="No reason provided."):
        if not self.guard_staff(ctx):
            await ctx.reply("Only staff can blacklist users.", mention_author=False)
            return

        entry = blacklist_user(member.id, reason, ctx.author.id, str(ctx.author))
        await log_event(ctx.guild, "access", "🚫 Buyer Blacklisted", {"User": member.mention, "Reason": reason}, actor=ctx.author)
        await ctx.reply(f"Blacklisted {member.mention}.\nReason: `{entry['reason']}`", mention_author=False)

    @commands.command(name="unblacklist", aliases=["unbl"])
    async def unblacklist(self, ctx, member: discord.Member):
        if not self.guard_staff(ctx):
            await ctx.reply("Only staff can unblacklist users.", mention_author=False)
            return

        removed = unblacklist_user(member.id)
        await log_event(ctx.guild, "access", "✅ Buyer Unblacklisted", {"User": member.mention, "Was blacklisted": bool(removed)}, actor=ctx.author)
        await ctx.reply(f"{member.mention} {'removed from blacklist' if removed else 'was not blacklisted'}.", mention_author=False)

    @commands.command(name="blacklistcheck", aliases=["blcheck"])
    async def blacklist_check(self, ctx, member: discord.Member):
        if not self.guard_staff(ctx):
            await ctx.reply("Only staff can check blacklist.", mention_author=False)
            return

        entry = is_blacklisted(member.id)
        if not entry:
            await ctx.reply(f"{member.mention} is not blacklisted.", mention_author=False)
            return

        embed = discord.Embed(
            title="🚫 Blacklist Check",
            description=(
                f"**User:** {member.mention}\n"
                f"**Reason:** `{entry.get('reason')}`\n"
                f"**Added:** `{entry.get('created_at')}`\n"
                f"**By:** `{entry.get('actor_name') or entry.get('actor_id')}`"
            ),
            color=0xE06C75,
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="blacklistlist", aliases=["bllist"])
    async def blacklist_list(self, ctx):
        if not self.guard_staff(ctx):
            await ctx.reply("Only staff can view blacklist.", mention_author=False)
            return

        entries = list_blacklisted()
        if not entries:
            await ctx.reply("Blacklist is empty.", mention_author=False)
            return

        lines = []
        for entry in entries[:25]:
            lines.append(f"`{entry.get('user_id')}` — {entry.get('reason')}")

        embed = discord.Embed(
            title="🚫 Buyer Blacklist",
            description="\n".join(lines)[:3900],
            color=0xE06C75,
        )
        embed.set_footer(text=f"Showing {min(len(entries), 25)} of {len(entries)} entries.")
        await ctx.reply(embed=embed, mention_author=False)

async def setup(bot):
    await bot.add_cog(TicketModerationCog(bot))
