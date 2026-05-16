
import discord
from discord.ext import commands

from services.access_control import is_allowed
from services.embed_theme import (
    base_embed,
    add_fields,
    set_image,
    clear_image,
    load_banner_config,
    VALID_IMAGE_KEYS,
    apply_preset,
    IMAGE_PRESETS,
)

BAD_VISIBLE_MARKERS = ["veil-v23-msg:", "VEIL_STOCK_BOARD:", "VEIL_MSG:"]

KNOWN_TITLES = [
    "🛒 Welcome to Veil's Grocery Store",
    "⭐ Reviews & Referrals",
    "💳 Payment Options",
    "🎁 Benefits",
    "🎫 How to Order",
    "🛡️ Store Rules & Safety",
    "📌 Store Information",
]

CHANNEL_MAP = {
    "welcome": ["welcome", "join", "start-here"],
    "vouches": ["vouches", "reviews", "proofs"],
    "payments": ["payments", "payment"],
    "benefits": ["benefits", "perks"],
    "tickets": ["order-here", "ticket", "tickets", "support"],
    "rules": ["rules", "avoid-ban", "safety"],
    "announcements": ["announcements", "announcement"],
}

def find_channel(guild, key):
    names = CHANNEL_MAP.get(key, [key])
    for name in names:
        channel = discord.utils.get(guild.text_channels, name=name)
        if channel:
            return channel
    for channel in guild.text_channels:
        lowered = channel.name.lower()
        for name in names:
            if name in lowered:
                return channel
    return None

def is_old_bot_message(msg):
    content = msg.content or ""
    if any(marker in content for marker in BAD_VISIBLE_MARKERS):
        return True
    if msg.embeds:
        for embed in msg.embeds:
            title = embed.title or ""
            footer = (embed.footer.text if embed.footer else "") or ""
            if title in KNOWN_TITLES:
                return True
            if any(marker in footer for marker in BAD_VISIBLE_MARKERS):
                return True
    return False

async def purge_polish_messages(channel, limit=120):
    deleted = 0
    async for msg in channel.history(limit=limit):
        if msg.author.bot and is_old_bot_message(msg):
            try:
                await msg.delete()
                deleted += 1
            except Exception:
                pass
    return deleted

def welcome_embed():
    embed = base_embed(
        "🛒 Welcome to Veil's Grocery Store",
        (
            "Clean stock, fast support, and organized ticket-based ordering.\n\n"
            "**Available games:**\n"
            "AOTR • GPO • SBTD • Da Hood\n\n"
            "Check the stock channels and open a ticket when ready."
        ),
        image_key="welcome"
    )
    add_fields(embed, [
        ("Order flow", "Stock channel → Item select → Ticket → Payment → Delivery → Vouch", False),
        ("Support", "Use `#support` or open a ticket for order questions.", False),
    ])
    return embed

def vouches_embed():
    embed = base_embed(
        "⭐ Reviews & Referrals",
        (
            "Buyers can vouch after a completed order.\n\n"
            "**Format:**\n"
            "`vouch @seller bought PRODUCT - feedback`\n\n"
            "The **Voucher** role is temporary. After one valid vouch, it becomes **Star Shopper**."
        ),
        image_key="vouches"
    )
    add_fields(embed, [
        ("Rules", "No fake vouches, spam, repeated reviews, or copied proof.", False),
        ("Referrals", "Referral rewards require staff-confirmed proof.", False),
    ])
    return embed

def payments_embed():
    embed = base_embed(
        "💳 Payment Options",
        (
            "Staff confirms the exact payment method and amount inside your ticket.\n\n"
            "**Common methods:**\n"
            "PayPal • Crypto • Cash App • Apple Pay • Venmo • Zelle"
        ),
        image_key="payments"
    )
    add_fields(embed, [
        ("Important", "Only send payment after staff confirms the order details.", False),
        ("Safety", "Double-check usernames, wallets, amounts, and notes before sending.", False),
    ])
    return embed

def benefits_embed():
    return base_embed(
        "🎁 Benefits",
        (
            "**Voucher**\n"
            "Temporary access to leave one review after an order.\n\n"
            "**Star Shopper**\n"
            "Permanent role after a valid vouch.\n\n"
            "**Referrals**\n"
            "Discounts may be given after confirmed referral proof."
        ),
        image_key="benefits"
    )

def tickets_embed():
    embed = base_embed(
        "🎫 How to Order",
        (
            "1. Check the game stock channel.\n"
            "2. Select the item from the dropdown.\n"
            "3. Ticket opens with item details.\n"
            "4. Confirm quantity and payment method.\n"
            "5. After delivery, leave a vouch."
        ),
        image_key="tickets"
    )
    add_fields(embed, [
        ("Best ticket format", "`Quantity + payment method + any notes`", False),
        ("Do not spam tickets", "Open a ticket only when ready to buy or ask a real question.", False),
    ])
    return embed

def rules_embed():
    embed = base_embed(
        "🛡️ Store Rules & Safety",
        (
            "This server is for allowed marketplace orders only.\n\n"
            "**Not allowed:**\n"
            "Scams • spam • fake proof • illegal items • harassment • Discord ToS violations"
        ),
        image_key="rules"
    )
    add_fields(embed, [
        ("Risk", "Use marketplace items responsibly and understand game/platform rules.", False),
        ("Staff decisions", "Staff may close tickets, remove spam, or ban bad actors.", False),
    ])
    return embed

def announcement_embed():
    return base_embed(
        "📌 Store Information",
        (
            "Stock, payment methods, prices, and availability can change.\n\n"
            "Use stock channels for the current list and tickets for orders."
        ),
        image_key="announcements"
    )

EMBEDS = {
    "welcome": welcome_embed,
    "vouches": vouches_embed,
    "payments": payments_embed,
    "benefits": benefits_embed,
    "tickets": tickets_embed,
    "rules": rules_embed,
    "announcements": announcement_embed,
}

class MessagePolishCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def allowed(self, ctx):
        return is_allowed(ctx.author.id)

    @commands.command(name="cleanmsgs", aliases=["msgclean", "cleanmarkers"])
    async def clean_messages(self, ctx):
        if not self.allowed(ctx):
            await ctx.reply("You are not allowed to use this command.", mention_author=False)
            return
        total = 0
        checked = 0
        for channel in ctx.guild.text_channels:
            deleted = await purge_polish_messages(channel, limit=120)
            total += deleted
            checked += 1
        await ctx.reply(f"Cleaned `{total}` old/automated bot messages across `{checked}` channels.", mention_author=False)

    @commands.command(name="msgs", aliases=["postmsgs", "refreshmsgs"])
    async def post_messages(self, ctx):
        if not self.allowed(ctx):
            await ctx.reply("You are not allowed to use this command.", mention_author=False)
            return
        posted = []
        missing = []
        for key, embed_factory in EMBEDS.items():
            channel = find_channel(ctx.guild, key)
            if not channel:
                missing.append(key)
                continue
            await purge_polish_messages(channel, limit=120)
            await channel.send(embed=embed_factory())
            posted.append(f"{key} → #{channel.name}")
        response = "**Posted polished embeds:**\n" + "\n".join(f"• {item}" for item in posted)
        if missing:
            response += "\n\n**Missing channels:**\n" + "\n".join(f"• {item}" for item in missing)
        await ctx.reply(response[:1900], mention_author=False)

    @commands.command(name="msg", aliases=["postmsg"])
    async def post_single_message(self, ctx, key: str):
        if not self.allowed(ctx):
            await ctx.reply("You are not allowed to use this command.", mention_author=False)
            return
        key = str(key).lower().strip()
        if key not in EMBEDS:
            await ctx.reply(f"Unknown message key. Available: `{', '.join(EMBEDS.keys())}`", mention_author=False)
            return
        channel = find_channel(ctx.guild, key)
        if not channel:
            await ctx.reply(f"No matching channel found for `{key}`.", mention_author=False)
            return
        await purge_polish_messages(channel, limit=120)
        await channel.send(embed=EMBEDS[key]())
        await ctx.reply(f"Posted polished `{key}` embed in {channel.mention}.", mention_author=False)

    @commands.command(name="setimage", aliases=["setbanner"])
    async def set_banner_image(self, ctx, key: str, url: str):
        if not self.allowed(ctx):
            await ctx.reply("You are not allowed to use this command.", mention_author=False)
            return
        ok, result = set_image(key, url)
        if not ok:
            await ctx.reply(result, mention_author=False)
            return
        await ctx.reply(f"Image set for `{result}`. Run `!msgs` or `!stockboard`.", mention_author=False)

    @commands.command(name="imagepreset", aliases=["presetimages"])
    async def image_preset(self, ctx, preset: str):
        if not self.allowed(ctx):
            await ctx.reply("You are not allowed to use this command.", mention_author=False)
            return
        ok, result = apply_preset(preset)
        if not ok:
            await ctx.reply(result, mention_author=False)
            return
        await ctx.reply(f"Applied `{result}` image preset. Run `!msgs` and `!stockboard`.", mention_author=False)

    @commands.command(name="clearimage", aliases=["clearbanner"])
    async def clear_banner_image(self, ctx, key: str):
        if not self.allowed(ctx):
            await ctx.reply("You are not allowed to use this command.", mention_author=False)
            return
        ok = clear_image(key)
        await ctx.reply(f"Image for `{key}` {'cleared' if ok else 'was not set'}.", mention_author=False)

    @commands.command(name="imagekeys", aliases=["imgs", "banners"])
    async def image_keys(self, ctx):
        if not self.allowed(ctx):
            await ctx.reply("You are not allowed to use this command.", mention_author=False)
            return
        current = load_banner_config()
        configured = "\n".join(f"`{k}` → {v}" for k, v in current.items()) or "No images configured yet."
        embed = base_embed(
            "🖼️ Embed Image Keys",
            (
                "**Available keys:**\n"
                f"`{', '.join(VALID_IMAGE_KEYS)}`\n\n"
                "**Presets:**\n"
                f"`{', '.join(IMAGE_PRESETS.keys())}`\n\n"
                "**Set preset:**\n"
                "`!imagepreset dark`\n"
                "`!imagepreset neon`\n"
                "`!imagepreset clean`\n\n"
                "**Set custom image:**\n"
                "`!setimage aotr https://image-url`\n\n"
                "**Configured:**\n"
                f"{configured}"
            )
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="previewimage", aliases=["previewbanner"])
    async def preview_image(self, ctx, key: str):
        if not self.allowed(ctx):
            await ctx.reply("You are not allowed to use this command.", mention_author=False)
            return
        data = load_banner_config()
        key = key.lower().strip()
        url = data.get(key)
        if not url:
            await ctx.reply(f"No saved image for `{key}`.", mention_author=False)
            return
        embed = base_embed(f"Image Preview: {key}", url)
        embed.set_image(url=url)
        await ctx.reply(embed=embed, mention_author=False)

async def setup(bot):
    await bot.add_cog(MessagePolishCog(bot))
