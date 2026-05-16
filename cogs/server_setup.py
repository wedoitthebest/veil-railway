
import discord
from discord.ext import commands

try:
    from services.embed_theme import base_embed, success, warning
except Exception:
    def base_embed(title, description="", color=0x7C3CFF, image_key=None, footer="Veil's Grocery Store"):
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_footer(text=footer)
        return embed
    def success(title, description="", image_key=None):
        return base_embed(title, description, 0x44D69F)
    def warning(title, description="", image_key=None):
        return base_embed(title, description, 0xFFD166)

try:
    from services.stock_board_service import ensure_stock_channels, rebuild_all_boards
except Exception:
    ensure_stock_channels = None
    rebuild_all_boards = None

STAFF_ROLE_NAMES = ["Owner", "Store Manager", "Support", "Store Owner", "Shelf Keeper", "Admin", "Moderator"]

ROLE_SPECS = [
    {
        "name": "Owner",
        "color": 0xFFD166,
        "hoist": True,
        "mentionable": False,
        "permissions": discord.Permissions(administrator=True),
    },
    {
        "name": "Store Manager",
        "color": 0x7C3CFF,
        "hoist": True,
        "mentionable": False,
        "permissions": discord.Permissions(
            manage_channels=True,
            manage_roles=True,
            manage_messages=True,
            read_messages=True,
            send_messages=True,
            attach_files=True,
            embed_links=True,
            read_message_history=True,
            use_external_emojis=True,
        ),
    },
    {
        "name": "Support",
        "color": 0x44D69F,
        "hoist": True,
        "mentionable": False,
        "permissions": discord.Permissions(
            manage_messages=True,
            read_messages=True,
            send_messages=True,
            attach_files=True,
            embed_links=True,
            read_message_history=True,
            use_external_emojis=True,
        ),
    },
    {
        "name": "Customer",
        "color": 0x99AAB5,
        "hoist": False,
        "mentionable": False,
        "permissions": discord.Permissions(read_messages=True, send_messages=True, read_message_history=True),
    },
    {
        "name": "Voucher",
        "color": 0x7C3CFF,
        "hoist": False,
        "mentionable": False,
        "permissions": discord.Permissions(read_messages=True, send_messages=True, read_message_history=True),
    },
    {
        "name": "Star Shopper",
        "color": 0xFFD166,
        "hoist": False,
        "mentionable": False,
        "permissions": discord.Permissions(read_messages=True, send_messages=True, read_message_history=True),
    },
    {
        "name": "Muted",
        "color": 0x2F3136,
        "hoist": False,
        "mentionable": False,
        "permissions": discord.Permissions(read_messages=True, read_message_history=True),
    },
]

SERVER_STRUCTURE = [
    {
        "category": "📌 INFO",
        "channels": [
            ("welcome", "text", "read_only"),
            ("announcements", "text", "read_only"),
            ("rules", "text", "read_only"),
            ("benefits", "text", "read_only"),
        ],
    },
    {
        "category": "🛒 STOCK",
        "channels": [
            ("aotr-stock", "text", "read_only"),
            ("gpo-stock", "text", "read_only"),
            ("sbtd-stock", "text", "read_only"),
            ("da-hood-stock", "text", "read_only"),
            ("other-stock", "text", "read_only"),
        ],
    },
    {
        "category": "🎫 ORDERING",
        "channels": [
            ("order-here", "text", "read_only"),
            ("payments", "text", "read_only"),
            ("support", "text", "public_write"),
        ],
    },
    {
        "category": "⭐ SOCIAL PROOF",
        "channels": [
            ("vouches", "text", "voucher_only"),
            ("reviews", "text", "read_only"),
            ("proofs", "text", "read_only"),
        ],
    },
    {
        "category": "💬 COMMUNITY",
        "channels": [
            ("general", "text", "public_write"),
            ("questions", "text", "public_write"),
        ],
    },
    {
        "category": "🔒 STAFF",
        "channels": [
            ("staff-chat", "text", "staff_only"),
            ("logs", "text", "staff_only"),
            ("ticket-logs", "text", "staff_only"),
            ("stock-logs", "text", "staff_only"),
        ],
    },
    {
        "category": "🎟️ TICKETS",
        "channels": [],
    },
]

def staff_roles(guild):
    return [role for role in guild.roles if role.name in STAFF_ROLE_NAMES]

def has_staff_role(member):
    return member.guild_permissions.administrator or any(role.name in STAFF_ROLE_NAMES for role in member.roles)

def can_setup(member):
    return member.guild_permissions.administrator or member.guild_permissions.manage_guild or has_staff_role(member)

async def ensure_role(guild, spec):
    existing = discord.utils.get(guild.roles, name=spec["name"])
    if existing:
        try:
            await existing.edit(
                color=discord.Color(spec["color"]),
                hoist=spec["hoist"],
                mentionable=spec["mentionable"],
                permissions=spec["permissions"],
                reason="Veil full server setup role refresh",
            )
        except Exception:
            pass
        return existing, False

    role = await guild.create_role(
        name=spec["name"],
        color=discord.Color(spec["color"]),
        hoist=spec["hoist"],
        mentionable=spec["mentionable"],
        permissions=spec["permissions"],
        reason="Veil full server setup",
    )
    return role, True

def base_overwrites(guild, mode):
    everyone = guild.default_role
    muted = discord.utils.get(guild.roles, name="Muted")
    voucher = discord.utils.get(guild.roles, name="Voucher")
    staff = staff_roles(guild)

    overwrites = {}

    if mode == "read_only":
        overwrites[everyone] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=False,
            read_message_history=True,
            add_reactions=False,
        )
    elif mode == "public_write":
        overwrites[everyone] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True,
        )
    elif mode == "staff_only":
        overwrites[everyone] = discord.PermissionOverwrite(view_channel=False)
    elif mode == "voucher_only":
        overwrites[everyone] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=False,
            read_message_history=True,
        )
        if voucher:
            overwrites[voucher] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                add_reactions=True,
            )
    else:
        overwrites[everyone] = discord.PermissionOverwrite(view_channel=True, read_message_history=True)

    if muted:
        overwrites[muted] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=False,
            add_reactions=False,
            attach_files=False,
            create_public_threads=False,
            create_private_threads=False,
        )

    for role in staff:
        overwrites[role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_messages=True,
            attach_files=True,
            embed_links=True,
            add_reactions=True,
        )

    return overwrites

async def ensure_category(guild, name):
    category = discord.utils.get(guild.categories, name=name)
    if category:
        return category, False

    category = await guild.create_category(name, reason="Veil full server setup")
    return category, True

async def ensure_text_channel(guild, category, name, mode):
    channel = discord.utils.get(guild.text_channels, name=name)

    if not channel:
        channel = await guild.create_text_channel(
            name,
            category=category,
            overwrites=base_overwrites(guild, mode),
            reason="Veil full server setup",
        )
        return channel, True

    try:
        await channel.edit(
            category=category,
            overwrites=base_overwrites(guild, mode),
            reason="Veil full server setup permission refresh",
        )
    except Exception:
        pass

    return channel, False

async def ensure_structure(guild):
    made_categories = []
    made_channels = []

    for cat_spec in SERVER_STRUCTURE:
        category, created = await ensure_category(guild, cat_spec["category"])
        if created:
            made_categories.append(category.name)

        for channel_name, channel_type, mode in cat_spec["channels"]:
            if channel_type != "text":
                continue
            channel, ch_created = await ensure_text_channel(guild, category, channel_name, mode)
            if ch_created:
                made_channels.append(channel.name)

    return made_categories, made_channels

async def ensure_roles(guild):
    made = []
    updated = []

    for spec in ROLE_SPECS:
        role, created = await ensure_role(guild, spec)
        if created:
            made.append(role.name)
        else:
            updated.append(role.name)

    return made, updated

async def clean_known_markers(guild):
    markers = ["veil-v23-msg:", "VEIL_STOCK_BOARD:", "VEIL_MSG:"]
    deleted = 0

    for channel in guild.text_channels:
        try:
            async for msg in channel.history(limit=75):
                content = msg.content or ""
                has_content_marker = any(marker in content for marker in markers)
                has_footer_marker = msg.embeds and any(
                    (((e.footer.text if e.footer else "") or "").startswith("VEIL_MSG:")
                    or "VEIL_STOCK_BOARD" in ((e.footer.text if e.footer else "") or ""))
                    for e in msg.embeds
                )
                if msg.author.bot and (has_content_marker or has_footer_marker):
                    try:
                        await msg.delete()
                        deleted += 1
                    except Exception:
                        pass
        except Exception:
            pass

    return deleted

def setup_summary_embed(created_roles, updated_roles, created_categories, created_channels, deleted_messages):
    embed = success(
        "✅ Veil Server Setup Complete",
        (
            "The server structure has been created or refreshed.\n\n"
            f"**Roles created:** `{len(created_roles)}`\n"
            f"**Roles updated:** `{len(updated_roles)}`\n"
            f"**Categories created:** `{len(created_categories)}`\n"
            f"**Channels created:** `{len(created_channels)}`\n"
            f"**Old marked messages cleaned:** `{deleted_messages}`\n\n"
            "**Next commands:**\n"
            "`!msgs` — post polished server embeds\n"
            "`!estock` — sync Eldorado and build stock boards\n"
            "`!cmds short` — view the main command shortcuts"
        )
    )

    if created_channels:
        embed.add_field(name="New channels", value=", ".join(f"`#{x}`" for x in created_channels[:20])[:1000], inline=False)
    if created_roles:
        embed.add_field(name="New roles", value=", ".join(f"`{x}`" for x in created_roles[:20])[:1000], inline=False)

    return embed

class FullServerSetupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="setupall", aliases=["vsetup", "fullsetup", "setupserver"])
    async def setup_all(self, ctx):
        if not can_setup(ctx.author):
            await ctx.reply("Only admins or store staff can run full setup.", mention_author=False)
            return

        status = await ctx.reply("Running full Veil server setup...", mention_author=False)

        try:
            created_roles, updated_roles = await ensure_roles(ctx.guild)
            created_categories, created_channels = await ensure_structure(ctx.guild)
            deleted_messages = await clean_known_markers(ctx.guild)

            if ensure_stock_channels:
                try:
                    await ensure_stock_channels(ctx.guild)
                except Exception:
                    pass

            embed = setup_summary_embed(
                created_roles,
                updated_roles,
                created_categories,
                created_channels,
                deleted_messages,
            )
            await status.edit(content=None, embed=embed)

        except Exception as exc:
            await status.edit(content=f"Setup failed: `{exc}`")

    @commands.command(name="vroles", aliases=["fixroles"])
    async def setup_roles(self, ctx):
        if not can_setup(ctx.author):
            await ctx.reply("Only admins or store staff can run role setup.", mention_author=False)
            return

        made, updated = await ensure_roles(ctx.guild)
        await ctx.reply(
            embed=success(
                "Roles Ready",
                f"Created `{len(made)}` roles and refreshed `{len(updated)}` roles.\n\nCreated: `{', '.join(made) if made else 'none'}`"
            ),
            mention_author=False,
        )

    @commands.command(name="vchannels", aliases=["fixchannels"])
    async def setup_channels(self, ctx):
        if not can_setup(ctx.author):
            await ctx.reply("Only admins or store staff can run channel setup.", mention_author=False)
            return

        cats, channels = await ensure_structure(ctx.guild)
        await ctx.reply(
            embed=success(
                "Channels Ready",
                f"Created `{len(cats)}` categories and `{len(channels)}` channels.\n\nChannels: `{', '.join(channels[:30]) if channels else 'none'}`"
            ),
            mention_author=False,
        )

    @commands.command(name="vperms", aliases=["fixperms"])
    async def setup_permissions(self, ctx):
        if not can_setup(ctx.author):
            await ctx.reply("Only admins or store staff can repair permissions.", mention_author=False)
            return

        await ensure_roles(ctx.guild)
        cats, channels = await ensure_structure(ctx.guild)
        await ctx.reply(
            embed=success(
                "Permissions Repaired",
                "Core channel permissions have been refreshed for public, staff, ticket, stock, and vouch areas."
            ),
            mention_author=False,
        )

    @commands.command(name="vclean", aliases=["cleanservermarkers"])
    async def clean_markers(self, ctx):
        if not can_setup(ctx.author):
            await ctx.reply("Only admins or store staff can clean markers.", mention_author=False)
            return

        deleted = await clean_known_markers(ctx.guild)
        await ctx.reply(f"Deleted `{deleted}` old marked bot messages.", mention_author=False)

    @commands.command(name="serverplan", aliases=["setupplan"])
    async def server_plan(self, ctx):
        embed = base_embed(
            "Veil Full Server Layout",
            (
                "**Roles**\n"
                "Owner • Store Manager • Support • Customer • Voucher • Star Shopper • Muted\n\n"
                "**Categories**\n"
                "📌 INFO • 🛒 STOCK • 🎫 ORDERING • ⭐ SOCIAL PROOF • 💬 COMMUNITY • 🔒 STAFF • 🎟️ TICKETS\n\n"
                "**Core flow**\n"
                "`!setupall` → `!msgs` → `!estock` → server ready."
            )
        )
        await ctx.reply(embed=embed, mention_author=False)

async def setup(bot):
    await bot.add_cog(FullServerSetupCog(bot))
