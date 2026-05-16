
import discord

from services.access_control import is_allowed
from services.ticket_panel import update_ticket_panel, is_ticket_channel
from services.log_service import log_event

def staff_allowed(member):
    if is_allowed(member.id):
        return True
    names = ["Owner", "Store Manager", "Support", "Store Owner", "Shelf Keeper", "Admin", "Moderator"]
    return member.guild_permissions.manage_channels or any(role.name in names for role in getattr(member, "roles", []))

class TicketActionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def guard(self, interaction: discord.Interaction):
        if not interaction.guild or not interaction.channel:
            await interaction.response.send_message("Invalid ticket context.", ephemeral=True)
            return False
        if not is_ticket_channel(interaction.channel):
            await interaction.response.send_message("This button only works inside tickets.", ephemeral=True)
            return False
        if not staff_allowed(interaction.user):
            await interaction.response.send_message("Only staff can use ticket action buttons.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.primary, custom_id="veil_ticket_claim")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction):
            return
        await update_ticket_panel(interaction.channel, status="claimed", staff=interaction.user, note="Ticket claimed from button.")
        await log_event(interaction.guild, "ticket", "🎫 Ticket Claimed", {"Ticket": interaction.channel.mention}, actor=interaction.user)
        await interaction.response.send_message("Ticket claimed.", ephemeral=True)

    @discord.ui.button(label="Paid", style=discord.ButtonStyle.success, custom_id="veil_ticket_paid")
    async def paid(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction):
            return
        await update_ticket_panel(interaction.channel, status="paid", staff=interaction.user, note="Payment marked as received from button.")
        await log_event(interaction.guild, "ticket", "💳 Payment Marked", {"Ticket": interaction.channel.mention}, actor=interaction.user)
        await interaction.response.send_message("Payment marked.", ephemeral=True)

    @discord.ui.button(label="Delivering", style=discord.ButtonStyle.primary, custom_id="veil_ticket_delivering")
    async def delivering(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction):
            return
        await update_ticket_panel(interaction.channel, status="delivering", staff=interaction.user, note="Delivery started from button.")
        await log_event(interaction.guild, "ticket", "📦 Delivery Started", {"Ticket": interaction.channel.mention}, actor=interaction.user)
        await interaction.response.send_message("Delivery marked.", ephemeral=True)

    @discord.ui.button(label="Ship", style=discord.ButtonStyle.success, custom_id="veil_ticket_ship")
    async def ship(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        try:
            from services.order_flow import complete_order_flow
            result = await complete_order_flow(
                guild=interaction.guild,
                channel=interaction.channel,
                staff=interaction.user,
                product_query="your order",
                close_delay=15,
            )
            if result.get("ok"):
                await interaction.followup.send(f"Order completed: `{result.get('product')}`.", ephemeral=True)
            else:
                await interaction.followup.send(f"Could not ship: `{result.get('error')}`", ephemeral=True)
        except Exception as exc:
            await interaction.followup.send(f"Ship failed: `{exc}`", ephemeral=True)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="veil_ticket_close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        try:
            await update_ticket_panel(interaction.channel, status="closed", staff=interaction.user, note="Ticket closed from button.")
            await log_event(interaction.guild, "ticket", "🔒 Ticket Closed", {"Ticket": interaction.channel.name, "Method": "Button"}, actor=interaction.user)
            await interaction.followup.send("Ticket closes in 5 seconds.", ephemeral=True)

            import asyncio
            await asyncio.sleep(5)
            await interaction.channel.delete(reason=f"Closed by {interaction.user}")
        except Exception as exc:
            await interaction.followup.send(f"Close failed: `{exc}`", ephemeral=True)

async def send_ticket_actions(channel):
    embed = discord.Embed(
        title="🛠️ Staff Actions",
        description=(
            "Use these buttons to run the order flow without typing commands.\n\n"
            "**Flow:** Claim → Paid → Delivering → Ship → Close"
        ),
        color=0x7C3CFF,
    )
    embed.set_footer(text="Veil's Grocery Store • Staff Controls")
    return await channel.send(embed=embed, view=TicketActionView())
