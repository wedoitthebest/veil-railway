import discord
from discord import app_commands
from discord.ext import commands
from services.access_control import is_allowed
from services.pin_service import remember_pin, forget_pin, get_pin, list_channel_pins
from services.log_service import log_event

SCAM_WARNING_NAME="scam-warning"
DEFAULT_DISCOUNT_ROLE_ID="1464261528881725595"
PIN_CHOICES=[app_commands.Choice(name="scam-warning",value="scam-warning"),app_commands.Choice(name="rules-safety",value="rules-safety")]

def staff_allowed(member):
    return is_allowed(member.id) or member.guild_permissions.manage_messages or member.guild_permissions.administrator

async def deny(interaction):
    await interaction.response.send_message("Only staff can use pinned-message commands.",ephemeral=True)

def scam_warning_embed(discount_role_id=DEFAULT_DISCOUNT_ROLE_ID):
    embed=discord.Embed(
        title="IMPORTANT",
        description=("**If anyone DMs you trying to sell items or advertise their shop, report it to staff immediately.**\n\n"
                     f"Valid reports can be rewarded with the <@&{discount_role_id}> role, giving you a **5% permanent discount**.\n\n"
                     "**Most unsolicited DMs are scams.** Do not send payment, do not click suspicious links, and do not trust users claiming to be staff outside official tickets."),
        color=0xE06C75)
    embed.add_field(name="What to do",value="Open a ticket or contact staff with screenshots and the user ID.",inline=False)
    embed.add_field(name="Stay safe",value="Only buy through official Veil tickets and verified staff.",inline=False)
    embed.set_footer(text="Veil's Grocery Store • Safety Notice")
    return embed

def rules_safety_embed():
    embed=discord.Embed(title="Server Safety Rules",description=("**Keep all orders inside official tickets.**\n\nDo not buy from random DMs, do not share private account details, and report suspicious messages to staff."),color=0x7C3CFF)
    embed.set_footer(text="Veil's Grocery Store • Pinned Notice")
    return embed

def build_pin_embed(name):
    return scam_warning_embed() if name=="scam-warning" else rules_safety_embed() if name=="rules-safety" else None

async def delete_remembered_pin(channel,name):
    info=get_pin(channel.guild.id,channel.id,name); deleted=False
    if info:
        try:
            msg=await channel.fetch_message(int(info["message_id"]))
            await msg.delete(); deleted=True
        except Exception:
            pass
    forget_pin(channel.guild.id,channel.id,name)
    return deleted

async def post_and_pin(channel,embed,name):
    msg=await channel.send(embed=embed)
    try:
        await msg.pin(reason=f"Veil pinned message: {name}")
    except Exception:
        pass
    remember_pin(channel.guild.id,channel.id,name,msg.id)
    return msg

class PinnedMessagesCog(commands.Cog):
    def __init__(self,bot): self.bot=bot

    @app_commands.command(name="safetypin",description="Post or update the pinned scam-warning safety embed.")
    @app_commands.describe(channel="Optional channel to post the safety pin in.")
    async def safetypin(self,interaction:discord.Interaction,channel:discord.TextChannel=None):
        if not staff_allowed(interaction.user): await deny(interaction); return
        await interaction.response.defer(ephemeral=True)
        target=channel or interaction.channel
        if not isinstance(target,discord.TextChannel):
            await interaction.followup.send("This command needs a text channel.",ephemeral=True); return
        await delete_remembered_pin(target,SCAM_WARNING_NAME)
        msg=await post_and_pin(target,scam_warning_embed(),SCAM_WARNING_NAME)
        await log_event(interaction.guild,"setup","Safety Pin Posted",{"Channel":target.mention,"Message ID":msg.id},actor=interaction.user)
        await interaction.followup.send(f"Safety warning pinned in {target.mention}.",ephemeral=True)

    @app_commands.command(name="pinmsg",description="Post or update a preset pinned message.")
    @app_commands.describe(name="Pinned message preset.",channel="Optional channel to post in.")
    @app_commands.choices(name=PIN_CHOICES)
    async def pinmsg(self,interaction:discord.Interaction,name:app_commands.Choice[str],channel:discord.TextChannel=None):
        if not staff_allowed(interaction.user): await deny(interaction); return
        await interaction.response.defer(ephemeral=True)
        preset=name.value; target=channel or interaction.channel
        if not isinstance(target,discord.TextChannel):
            await interaction.followup.send("This command needs a text channel.",ephemeral=True); return
        embed=build_pin_embed(preset)
        await delete_remembered_pin(target,preset)
        msg=await post_and_pin(target,embed,preset)
        await log_event(interaction.guild,"setup","Pinned Message Posted",{"Name":preset,"Channel":target.mention,"Message ID":msg.id},actor=interaction.user)
        await interaction.followup.send(f"`{preset}` pinned in {target.mention}.",ephemeral=True)

    @app_commands.command(name="unpinmsg",description="Remove a remembered pinned message.")
    @app_commands.describe(name="Pinned message preset.",channel="Optional channel to remove from.")
    @app_commands.choices(name=PIN_CHOICES)
    async def unpinmsg(self,interaction:discord.Interaction,name:app_commands.Choice[str],channel:discord.TextChannel=None):
        if not staff_allowed(interaction.user): await deny(interaction); return
        await interaction.response.defer(ephemeral=True)
        preset=name.value; target=channel or interaction.channel
        if not isinstance(target,discord.TextChannel):
            await interaction.followup.send("This command needs a text channel.",ephemeral=True); return
        deleted=await delete_remembered_pin(target,preset)
        await log_event(interaction.guild,"setup","Pinned Message Removed",{"Name":preset,"Channel":target.mention,"Deleted":deleted},actor=interaction.user)
        await interaction.followup.send(f"`{preset}` {'removed' if deleted else 'was not found, but record was cleared'} in {target.mention}.",ephemeral=True)

    @app_commands.command(name="pinlist",description="Show remembered Veil pinned messages in a channel.")
    @app_commands.describe(channel="Optional channel to inspect.")
    async def pinlist(self,interaction:discord.Interaction,channel:discord.TextChannel=None):
        if not staff_allowed(interaction.user): await deny(interaction); return
        target=channel or interaction.channel
        if not isinstance(target,discord.TextChannel):
            await interaction.response.send_message("This command needs a text channel.",ephemeral=True); return
        pins=list_channel_pins(interaction.guild.id,target.id)
        if not pins:
            await interaction.response.send_message(f"No Veil pinned-message records for {target.mention}.",ephemeral=True); return
        embed=discord.Embed(title=f"Veil Pins — #{target.name}",description="\n".join(f"• `{p['name']}` — message `{p['message_id']}`" for p in pins)[:3900],color=0x7C3CFF)
        await interaction.response.send_message(embed=embed,ephemeral=True)

async def setup(bot): await bot.add_cog(PinnedMessagesCog(bot))
