
import json
import time
from pathlib import Path
import discord

from services.ticket_panel import ticket_owner_id, update_ticket_panel, is_ticket_channel
from services.log_service import log_event
from services.blacklist_service import is_blacklisted

COOLDOWN_FILE = Path("data/ticket_cooldowns.json")
TICKET_COOLDOWN_SECONDS = 90

def load_cooldowns():
    COOLDOWN_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not COOLDOWN_FILE.exists():
        return {}
    try:
        return json.loads(COOLDOWN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_cooldowns(data):
    COOLDOWN_FILE.parent.mkdir(parents=True, exist_ok=True)
    COOLDOWN_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

def cooldown_left(user_id):
    data = load_cooldowns()
    last = float(data.get(str(user_id), 0))
    left = int(TICKET_COOLDOWN_SECONDS - (time.time() - last))
    return max(0, left)

def set_cooldown(user_id):
    data = load_cooldowns()
    data[str(user_id)] = time.time()
    save_cooldowns(data)

def clear_old_cooldowns():
    data = load_cooldowns()
    now = time.time()
    cleaned = {k: v for k, v in data.items() if now - float(v) < 86400}
    if cleaned != data:
        save_cooldowns(cleaned)

def buyer_block_reason(user_id):
    entry = is_blacklisted(user_id)
    if entry:
        return f"You are blocked from opening tickets. Reason: `{entry.get('reason')}`"
    left = cooldown_left(user_id)
    if left > 0:
        return f"Wait `{left}` seconds before opening another ticket."
    return None

def buyer_checklist_embed(product_name=None):
    embed = discord.Embed(
        title="🛒 Buyer Checklist",
        description=(
            "Please send the order details in this ticket.\n\n"
            "**Copy this format:**\n"
            "`Quantity:`\n"
            "`Payment method:`\n"
            "`Username / delivery info:`\n"
            "`Notes:`\n\n"
            "Do not send payment until staff confirms the final amount and payment method."
        ),
        color=0x7C3CFF,
    )
    if product_name:
        embed.add_field(name="Selected item", value=f"`{product_name}`", inline=False)
    embed.add_field(name="Buyer buttons", value="Use **I Paid** after payment, **Ask Staff** if you need help, or **Cancel Order** if you changed your mind.", inline=False)
    embed.set_footer(text="Veil's Grocery Store • Buyer Checklist")
    return embed

def buyer_is_owner(interaction):
    owner_id = ticket_owner_id(interaction.channel)
    return owner_id and int(owner_id) == int(interaction.user.id)

class BuyerActionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def guard(self, interaction):
        if not interaction.guild or not interaction.channel or not is_ticket_channel(interaction.channel):
            await interaction.response.send_message("This only works inside your order ticket.", ephemeral=True)
            return False
        if not buyer_is_owner(interaction):
            await interaction.response.send_message("Only the ticket buyer can use buyer buttons.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="I Paid", style=discord.ButtonStyle.success, custom_id="veil_buyer_paid")
    async def buyer_paid(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction):
            return
        await update_ticket_panel(interaction.channel, status="paid", staff=interaction.user, note="Buyer marked payment as sent. Staff must verify before delivery.")
        await log_event(interaction.guild, "ticket", "💳 Buyer Marked Paid", {"Ticket": interaction.channel.mention, "Buyer": interaction.user.mention}, actor=interaction.user)
        await interaction.response.send_message("Marked as paid. Staff will verify the payment before delivery.", ephemeral=True)
        await interaction.channel.send(f"{interaction.user.mention} marked the order as paid. Staff should verify payment before shipping.")

    @discord.ui.button(label="Ask Staff", style=discord.ButtonStyle.primary, custom_id="veil_buyer_ask_staff")
    async def ask_staff(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction):
            return
        await log_event(interaction.guild, "ticket", "❔ Buyer Requested Staff", {"Ticket": interaction.channel.mention, "Buyer": interaction.user.mention}, actor=interaction.user)
        await interaction.response.send_message("Staff has been notified in the ticket.", ephemeral=True)
        await interaction.channel.send(f"{interaction.user.mention} needs staff help.")

    @discord.ui.button(label="Cancel Order", style=discord.ButtonStyle.danger, custom_id="veil_buyer_cancel")
    async def cancel_order(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction):
            return
        await update_ticket_panel(interaction.channel, status="cancelled", staff=interaction.user, note="Buyer requested cancellation.")
        await log_event(interaction.guild, "ticket", "❌ Buyer Requested Cancellation", {"Ticket": interaction.channel.mention, "Buyer": interaction.user.mention}, actor=interaction.user)
        await interaction.response.send_message("Cancellation requested. Staff will review or close the ticket.", ephemeral=True)
        await interaction.channel.send(f"{interaction.user.mention} requested to cancel this order.")

async def send_buyer_checklist(channel, product_name=None):
    return await channel.send(embed=buyer_checklist_embed(product_name), view=BuyerActionView())
