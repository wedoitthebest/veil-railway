
# v42 wrapper imports v41 behavior from existing file if any command overwrote it.
# Full implementation is replaced only for blacklist gate around ticket opening.

import math
import re
import discord

from services import product_service
from services.embed_theme import image_for
from services.ticket_buyer_service import buyer_block_reason, set_cooldown, send_buyer_checklist

STOCK_CATEGORY = "STOCK"
GAME_CHANNELS = {"aotr": "aotr-stock", "gpo": "gpo-stock", "sbtd": "sbtd-stock", "da-hood": "da-hood-stock", "other": "other-stock"}
GAME_LABELS = {"aotr": "AOTR", "gpo": "GPO", "sbtd": "SBTD", "da-hood": "Da Hood", "other": "Other"}
STAFF_ROLES = ["Store Owner", "Store Manager", "Shelf Keeper", "Owner", "Admin", "Moderator", "Support"]

def clean_channel_name(value):
    value = str(value).lower().strip()
    value = re.sub(r"[^a-z0-9-]+", "-", value)
    return re.sub(r"-+", "-", value).strip("-") or "stock"

def stock_channel_name(slug):
    return GAME_CHANNELS.get(slug, f"{clean_channel_name(slug)}-stock")

def game_label(slug):
    return GAME_LABELS.get(slug, str(slug).replace("-", " ").title())

def remove_wrapping_emojis(name):
    name = re.sub(r"^[^\w\d]+", "", str(name)).strip()
    name = re.sub(r"[^\w\d]+$", "", name).strip()
    return name

def short_name(product):
    name = str(product.get("name") or "Listing").strip()
    name = remove_wrapping_emojis(name)
    patterns = [
        r"\bcheapest\b", r"\binstant\s+delivery\b", r"\bfast\s*&\s*secure\s*delivery\b",
        r"\bfast\s+and\s+secure\s+delivery\b", r"\bfast\s*&\s*secure\b", r"\bfast\s+and\s+secure\b",
        r"\bfast\s+delivery\b", r"\bsecure\s+delivery\b", r"\binstant\b", r"\bdelivery\b",
        r"\baotr\b", r"\bgpo\b", r"\bsbtd\b", r"\bspongebob\s+tower\s+defense\b",
        r"\bgrand\s+piece\s+online\b", r"\bda\s*hood\b", r"\bdahood\b", r"\bcheap\b",
        r"\btrusted\b", r"\bsafe\b",
    ]
    for pattern in patterns:
        name = re.sub(pattern, "", name, flags=re.IGNORECASE)
    name = name.replace("|", " ").replace("⚡", " ").replace("🦺", " ")
    name = re.sub(r"\s*[-–—]\s*$", "", name)
    name = re.sub(r"^\s*[-–—]\s*", "", name)
    name = re.sub(r"\s{2,}", " ", name).strip(" -–—•|")
    name = remove_wrapping_emojis(name)
    return (name or str(product.get("name") or "Listing").strip())[:92]

def stock_text(product):
    stock = int(product.get("stock") or 0)
    if stock <= 0:
        return "sold out"
    if stock == 1:
        return "1 left"
    if stock >= 1000000:
        return "large stock"
    return f"{stock} left"

def product_line(product):
    return f"• **{short_name(product)}** — `{stock_text(product)}` — **{product.get('price') or 'Ask'}**"

def split_lines_for_embed(lines, max_len=1000):
    chunks, current = [], []
    for line in lines:
        test = "\n".join(current + [line])
        if len(test) > max_len and current:
            chunks.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        chunks.append("\n".join(current))
    return chunks

def product_options(products):
    return [
        discord.SelectOption(label=(short_name(p)[:90] or "Item"), description=f"{stock_text(p)} • {p.get('price') or 'Ask'}"[:100], value=str(p["id"]))
        for p in products[:25]
    ]

class ItemSelect(discord.ui.Select):
    def __init__(self, game_slug, products, index):
        start = index * 25
        chunk = products[start:start + 25]
        super().__init__(
            placeholder=f"Select {game_label(game_slug)} item {start + 1}-{start + len(chunk)}",
            min_values=1,
            max_values=1,
            options=product_options(chunk),
            custom_id=f"veil_item_select_{game_slug}_{index}",
        )

    async def callback(self, interaction: discord.Interaction):
        block = buyer_block_reason(interaction.user.id)
        if block:
            await interaction.response.send_message(block, ephemeral=True)
            return

        try:
            product_id = int(self.values[0])
        except Exception:
            await interaction.response.send_message("Invalid product selection.", ephemeral=True)
            return

        product = product_service.get_product(product_id)
        if not product:
            await interaction.response.send_message("That item no longer exists.", ephemeral=True)
            return
        if int(product.get("stock") or 0) <= 0:
            await interaction.response.send_message("That item is currently sold out.", ephemeral=True)
            return

        channel, error = await create_product_ticket(interaction.guild, interaction.user, product)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        set_cooldown(interaction.user.id)
        await interaction.response.send_message(f"Ticket created: {channel.mention}", ephemeral=True)

class ItemSelectView(discord.ui.View):
    def __init__(self, game_slug, products):
        super().__init__(timeout=None)
        active = [p for p in products if int(p.get("enabled") or 0) == 1 and int(p.get("stock") or 0) > 0][:125]
        for idx in range(max(0, min(5, math.ceil(len(active) / 25)))):
            chunk = active[idx * 25:(idx + 1) * 25]
            if chunk:
                self.add_item(ItemSelect(game_slug, active, idx))

def user_has_open_ticket(guild, user_id):
    marker = f"veil-ticket-owner:{user_id}"
    for channel in guild.text_channels:
        if channel.name.startswith("ticket-") and channel.topic and marker in channel.topic:
            return channel
    return None

async def create_product_ticket(guild, user, product):
    block = buyer_block_reason(user.id)
    if block:
        return None, block

    existing = user_has_open_ticket(guild, user.id)
    if existing:
        return None, f"You already have an open ticket: {existing.mention}. Close that ticket before opening another."

    game_slug = product.get("game_slug") or "other"
    category = discord.utils.get(guild.categories, name="🎟️ TICKETS") or discord.utils.get(guild.categories, name="TICKETS")
    if not category:
        category = await guild.create_category("🎟️ TICKETS")

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True),
    }
    for role_name in STAFF_ROLES:
        role = discord.utils.get(guild.roles, name=role_name)
        if role:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_messages=True)

    item_name = short_name(product)
    channel_name = f"ticket-{clean_channel_name(game_label(game_slug))}-{clean_channel_name(user.name)[:12]}"
    channel = await guild.create_text_channel(
        channel_name,
        category=category,
        overwrites=overwrites,
        topic=f"veil-ticket-owner:{user.id} product-id:{product['id']} game-slug:{game_slug} opened-at:{int(__import__('time').time())}"
    )

    embed = discord.Embed(title="🧾 Order Ticket", description=f"Welcome {user.mention}.\n\nThis ticket is linked to a selected stock item.", color=0x7C3CFF)
    embed.add_field(name="Game", value=f"`{game_label(game_slug)}`", inline=True)
    embed.add_field(name="Item", value=f"`{item_name}`", inline=True)
    embed.add_field(name="Price", value=f"`{product.get('price') or 'Ask'}`", inline=True)
    embed.add_field(name="Stock", value=f"`{stock_text(product)}`", inline=True)
    embed.add_field(name="Status", value="`Waiting for buyer details`", inline=False)
    embed.add_field(name="Buyer format", value="`Quantity + payment method + delivery username/info + notes`", inline=False)
    embed.add_field(name="Staff flow", value="Use the staff buttons or `!cl` → `!p` → `!d` → `!ship`.", inline=False)
    embed.set_footer(text="Veil's Grocery Store • Order Panel")
    img = image_for(game_slug)
    if img:
        embed.set_image(url=img)

    await channel.send(content=user.mention, embed=embed)
    await send_buyer_checklist(channel, item_name)

    try:
        from services.ticket_actions import send_ticket_actions
        await send_ticket_actions(channel)
    except Exception as exc:
        await channel.send(f"Staff action buttons failed to load: `{exc}`")

    try:
        from services.log_service import log_event
        await log_event(guild, "ticket", "🎫 Ticket Opened", {"Ticket": channel.mention, "Buyer": user.mention, "Product": item_name, "Game": game_slug}, actor=user)
    except Exception:
        pass
    return channel, None

def make_stock_embeds(slug, products):
    label = game_label(slug)
    active = [p for p in products if int(p.get("enabled") or 0) == 1]
    active.sort(key=lambda p: (-(int(p.get("stock") or 0)), short_name(p).lower()))
    embed = discord.Embed(title=f"🛒 {label} Stock", color=0x7C3CFF)
    img = image_for(slug)
    if img:
        embed.set_image(url=img)
    if not active:
        embed.description = "No active stock found right now."
        embed.set_footer(text="Veil's Grocery Store")
        return [embed]
    chunks = split_lines_for_embed([product_line(p) for p in active], max_len=1000)
    if len(chunks) <= 24:
        embed.description = f"**{len(active)} listings available**\nSelect an item below to open an order ticket."
        for idx, chunk in enumerate(chunks):
            embed.add_field(name="Available Items" if idx == 0 else f"Available Items {idx + 1}", value=chunk, inline=False)
        embed.set_footer(text="Veil's Grocery Store • Select an item to order")
        return [embed]
    embeds = []
    lines = [product_line(p) for p in active]
    per_page = 18
    total_pages = max(1, math.ceil(len(lines) / per_page))
    for idx in range(total_pages):
        page = discord.Embed(title=f"🛒 {label} Stock", description="\n".join(lines[idx * per_page:(idx + 1) * per_page])[:3900], color=0x7C3CFF)
        if idx == 0 and img:
            page.set_image(url=img)
        page.set_footer(text=f"Veil's Grocery Store • Page {idx + 1}/{total_pages}")
        embeds.append(page)
    return embeds

async def ensure_stock_channels(guild):
    category = discord.utils.get(guild.categories, name="🛒 STOCK") or discord.utils.get(guild.categories, name=STOCK_CATEGORY)
    if not category:
        category = await guild.create_category("🛒 STOCK")
    made = []
    for slug, channel_name in GAME_CHANNELS.items():
        channel = discord.utils.get(guild.text_channels, name=channel_name)
        if not channel:
            channel = await guild.create_text_channel(channel_name, category=category)
            made.append(channel.name)
        elif channel.category != category:
            try:
                await channel.edit(category=category)
            except Exception:
                pass
    return made

def is_stock_bot_message(msg):
    if "VEIL_STOCK_BOARD:" in (msg.content or ""):
        return True
    return bool(msg.embeds and any(((e.title or "").startswith("🛒 ") and (e.title or "").endswith(" Stock")) or "VEIL_STOCK_BOARD" in ((e.footer.text if e.footer else "") or "") for e in msg.embeds))

async def purge_old_stock_messages(channel):
    deleted = 0
    async for msg in channel.history(limit=180):
        if msg.author.bot and is_stock_bot_message(msg):
            try:
                await msg.delete()
                deleted += 1
            except Exception:
                pass
    return deleted

async def rebuild_game_board(guild, slug):
    await ensure_stock_channels(guild)
    channel = discord.utils.get(guild.text_channels, name=stock_channel_name(slug))
    if not channel:
        return {"deleted": 0, "posted": 0, "products": 0}
    products = product_service.get_products_by_game(slug)
    deleted = await purge_old_stock_messages(channel)
    posted = 0
    active_products = [p for p in products if int(p.get("enabled") or 0) == 1 and int(p.get("stock") or 0) > 0]
    for idx, embed in enumerate(make_stock_embeds(slug, products)):
        view = ItemSelectView(slug, active_products) if idx == 0 and active_products else None
        await channel.send(embed=embed, view=view)
        posted += 1
    return {"deleted": deleted, "posted": posted, "products": len(products)}

async def rebuild_all_boards(guild):
    await ensure_stock_channels(guild)
    slugs = set(product_service.get_game_slugs())
    slugs.update(["aotr", "gpo", "sbtd", "da-hood", "other"])
    deleted_total, posted, per_channel = 0, 0, {}
    for slug in sorted(slugs):
        result = await rebuild_game_board(guild, slug)
        deleted_total += result["deleted"]
        posted += result["posted"]
        per_channel[slug] = result["products"]
    return deleted_total, posted, per_channel

def ticket_game_slug(channel):
    topic = channel.topic or ""
    marker = "game-slug:"
    if marker not in topic:
        return None
    try:
        return topic.split(marker, 1)[1].split()[0].strip()
    except Exception:
        return None
