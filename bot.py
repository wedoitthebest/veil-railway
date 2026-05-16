import os, re, time, discord
from collections import defaultdict
from discord.ext import commands
from dotenv import load_dotenv
from db import init_db, cfg, save, log, hist
from eldorado_sync import sync_eldorado_products

load_dotenv()
TOKEN=os.getenv("DISCORD_TOKEN")
PREFIX=os.getenv("BOT_PREFIX","!")

intents=discord.Intents.default()
intents.guilds=True
intents.message_content=True
intents.members=True
bot=commands.Bot(command_prefix=PREFIX,intents=intents)

ELDORADO_URL = "https://www.eldorado.gg/users/012"
ticket_cooldowns = defaultdict(float)

def clean(n):
    n=str(n).lower().strip()
    n=re.sub(r"[^a-z0-9-]+","-",n)
    return re.sub(r"-+","-",n).strip("-") or "channel"

def role_color(v):
    try: return discord.Color(int(str(v).replace("#",""),16))
    except Exception: return discord.Color(0x7c3cff)

def make_embed(data):
    e=discord.Embed(title=data.get("title","Veil"),description=data.get("description",""),color=int(data.get("color",8133887)))
    if data.get("footer"): e.set_footer(text=data["footer"])
    return e

def eldorado_embed():
    e=discord.Embed(
        title="Verified Marketplace Reputation",
        description=f"Veil's Grocery Store v1 uses external marketplace history as an additional trust signal.\n\n**Eldorado Seller Profile:** [012]({ELDORADO_URL})\n\nUse this profile to review public seller reputation, previous feedback, and account history before opening a ticket.",
        color=0x7C3CFF
    )
    e.add_field(name="What this proves",value="Public seller presence, marketplace feedback, and external reputation history.",inline=False)
    e.add_field(name="Recommended check",value="Compare the profile link, reviews, and seller activity before ordering.",inline=False)
    e.set_footer(text="Veil Reputation • Eldorado profile linked for transparency")
    return e

async def ensure_roles(guild, items):
    out={}
    for r in items:
        name=r["name"] if isinstance(r,dict) else str(r)
        role=discord.utils.get(guild.roles,name=name)
        if not role:
            kwargs={}
            if isinstance(r,dict):
                kwargs["color"]=role_color(r.get("color"))
                kwargs["hoist"]=bool(r.get("hoist"))
            role=await guild.create_role(name=name,**kwargs)
            log("INFO",f"Created role {name}")
        out[name]=role
    return out

def private_overwrites(guild, staff):
    ow={guild.default_role: discord.PermissionOverwrite(view_channel=False)}
    for role in staff:
        ow[role]=discord.PermissionOverwrite(view_channel=True,send_messages=True,read_message_history=True)
    return ow

def user_has_open_ticket(guild,user_id):
    marker=f"veil-ticket-owner:{user_id}"
    for channel in guild.text_channels:
        if channel.name.startswith("ticket-") and channel.topic and marker in channel.topic:
            return channel
    return None



# === VEIL FINAL COG LOADER v38 ===
async def veil_setup_hook():
    extensions = [
        "cogs.admin_access",
        "cogs.audit_hardening",
        "cogs.server_setup",
        "cogs.message_polish",
        "cogs.pinned_messages",
        "cogs.eldorado_stock",
        "cogs.ticket_ops",
        "cogs.ticket_buttons",
        "cogs.ticket_inactivity",
        "cogs.ticket_moderation",
        "cogs.ticket_buyer",
        "cogs.orders",
        "cogs.products",
        "cogs.product_search",
        "cogs.analytics",
        "cogs.launch_admin",
        "cogs.command_center",
        "cogs.stability",
        "cogs.welcome",
    ]

    loaded = []
    failed = []

    for extension in extensions:
        try:
            await bot.load_extension(extension)
            loaded.append(extension)
            print(f"[COG] Loaded {extension}")
        except Exception as exc:
            failed.append((extension, str(exc)))
            print(f"[COG ERROR] {extension}: {exc}")

    bot.veil_loaded_extensions = loaded
    bot.veil_failed_extensions = failed

    # === VEIL SLASH SYNC v46 ===
    try:
        synced = await bot.tree.sync()
        print(f"[SYNC] Synced {len(synced)} slash commands globally.")
    except Exception as exc:
        print(f"[SYNC ERROR] {exc}")
    # === END VEIL SLASH SYNC v46 ===


bot.setup_hook = veil_setup_hook
# === END VEIL FINAL COG LOADER v38 ===


def main():
    init_db()
    if not TOKEN or TOKEN=="PASTE_YOUR_BOT_TOKEN_HERE":
        raise RuntimeError("Missing DISCORD_TOKEN. Edit .env first.")
    bot.run(TOKEN)

if __name__=="__main__": main()



VOUCHER_ROLE_NAME = "Voucher"

def veil_staff_check(member):
    staff_names = ["Store Owner", "Store Manager", "Shelf Keeper", "Owner", "Admin", "Moderator"]
    return member.guild_permissions.manage_channels or any(role.name in staff_names for role in member.roles)

def veil_ticket_owner_id_v13(channel):
    topic = channel.topic or ""
    marker = "veil-ticket-owner:"
    if marker not in topic:
        return None
    try:
        return int(topic.split(marker, 1)[1].split()[0].strip())
    except Exception:
        return None

async def veil_get_or_create_voucher_role(guild):
    role = discord.utils.get(guild.roles, name=VOUCHER_ROLE_NAME)
    if role:
        return role
    return await guild.create_role(
        name=VOUCHER_ROLE_NAME,
        color=discord.Color(0x7C3CFF),
        hoist=False,
        mentionable=False,
        reason="Veil voucher system"
    )

def veil_find_vouch_channel(guild):
    for name in ["vouches", "reviews", "proofs"]:
        channel = discord.utils.get(guild.text_channels, name=name)
        if channel:
            return channel
    for channel in guild.text_channels:
        if "vouch" in channel.name or "review" in channel.name:
            return channel
    return None

def veil_valid_vouch_message(message):
    content = message.content.lower().strip()
    if not content.startswith("vouch "):
        return False
    if len(message.content.strip()) < 15:
        return False
    return True

def veil_vouch_dm_embed(guild, product):
    channel = veil_find_vouch_channel(guild)
    channel_text = channel.mention if channel else "#vouches"

    embed = discord.Embed(
        title="⭐ Leave Your Review",
        description=(
            "Your order has been marked as complete.\n\n"
            f"You temporarily received the **{VOUCHER_ROLE_NAME}** role so you can leave **one** review.\n\n"
            f"Please post your vouch in {channel_text}.\n\n"
            "**Format:**\n"
            "`vouch @seller bought PRODUCT - short feedback`\n\n"
            "**Example:**\n"
            f"`vouch @StoreOwner bought {product or 'AOTR items'} - fast delivery and smooth service`\n\n"
            "After your vouch is sent, the role will be removed automatically."
        ),
        color=0x7C3CFF
    )
    embed.set_footer(text="Veil Marketplace • Review Reminder")
    return embed


