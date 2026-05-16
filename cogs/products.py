
import discord
from discord.ext import commands

from services import product_service
from utils.embeds import (
    product_embed,
    stock_overview_embed,
    success_embed,
    error_embed,
    warning_embed,
)

STAFF_ROLES = ["Store Owner", "Store Manager", "Shelf Keeper", "Owner", "Admin", "Moderator"]

def is_staff(member):
    return member.guild_permissions.manage_channels or any(role.name in STAFF_ROLES for role in member.roles)

def clean_name(value):
    import re
    value = str(value).lower().strip()
    value = re.sub(r"[^a-z0-9-]+", "-", value)
    return re.sub(r"-+", "-", value).strip("-") or "ticket"

def user_has_open_ticket(guild, user_id):
    marker = f"veil-ticket-owner:{user_id}"
    for channel in guild.text_channels:
        if channel.name.startswith("ticket-") and channel.topic and marker in channel.topic:
            return channel
    return None

async def create_product_ticket(guild, user, product):
    existing = user_has_open_ticket(guild, user.id)
    if existing:
        return None, f"You already have an open ticket: {existing.mention}"

    category = discord.utils.get(guild.categories, name="TICKETS")
    if not category:
        category = await guild.create_category("TICKETS", overwrites={})

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True),
    }

    for role_name in STAFF_ROLES:
        role = discord.utils.get(guild.roles, name=role_name)
        if role:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_messages=True)

    channel_name = f"ticket-{clean_name(product['category'])}-{clean_name(user.name)[:12]}"
    channel = await guild.create_text_channel(
        channel_name,
        category=category,
        overwrites=overwrites,
        topic=f"veil-ticket-owner:{user.id} product-id:{product['id']}"
    )

    embed = discord.Embed(
        title="🛒 Product Ticket",
        description=(
            f"Welcome {user.mention}.\n\n"
            f"**Product:** `{product['name']}`\n"
            f"**Category:** `{product['category']}`\n"
            f"**Price:** `{product['price']}`\n"
            f"**Stock:** `{product['stock']}`\n"
            f"**Delivery:** `{product['delivery_type']}`\n\n"
            "Staff will assist you shortly.\n\n"
            "Useful staff commands:\n"
            "`!cl` claim • `!p` paid • `!d` delivering • `!cp` complete"
        ),
        color=0x7C3CFF
    )
    embed.set_footer(text=f"Veil's Grocery Store • Product ID {product['id']}")

    await channel.send(content=user.mention, embed=embed)
    return channel, None

class BuyProductButton(discord.ui.Button):
    def __init__(self, product_id):
        super().__init__(
            label="Buy",
            style=discord.ButtonStyle.success,
            custom_id=f"veil_product_buy_{product_id}"
        )
        self.product_id = int(product_id)

    async def callback(self, interaction: discord.Interaction):
        product = product_service.get_product(self.product_id)

        if not product or not product.get("enabled"):
            await interaction.response.send_message("This product is not available anymore.", ephemeral=True)
            return

        if int(product.get("stock", 0)) <= 0:
            await interaction.response.send_message("This product is currently sold out.", ephemeral=True)
            return

        channel, error = await create_product_ticket(interaction.guild, interaction.user, product)

        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        await interaction.response.send_message(f"Ticket created: {channel.mention}", ephemeral=True)

class ProductBuyView(discord.ui.View):
    def __init__(self, product_id):
        super().__init__(timeout=None)
        self.add_item(BuyProductButton(product_id))

class ProductsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        product_service.init_products()

    @commands.command(name="ap")
    async def add_product(self, ctx, category: str, name: str, stock: int, price: str, *, description: str = ""):
        if not is_staff(ctx.author):
            await ctx.reply("Only staff can add products.", mention_author=False)
            return

        product_id = product_service.add_product(
            category=category,
            name=name,
            stock=stock,
            price=price,
            delivery_type="Manual",
            description=description,
            emoji="🛒"
        )

        await ctx.reply(
            embed=success_embed(
                "Product Added",
                f"`#{product_id}` **{name}** added under `{category}` with stock `{stock}` and price `{price}`."
            ),
            mention_author=False
        )

    @commands.command(name="ep")
    async def edit_product(self, ctx, product_id: int, field: str, *, value: str):
        if not is_staff(ctx.author):
            await ctx.reply("Only staff can edit products.", mention_author=False)
            return

        allowed = ["category", "name", "price", "stock", "delivery_type", "description", "emoji", "enabled", "low_stock_at"]

        if field not in allowed:
            await ctx.reply(f"Invalid field. Allowed: `{', '.join(allowed)}`", mention_author=False)
            return

        ok = product_service.edit_product(product_id, field, value)

        if not ok:
            await ctx.reply(embed=error_embed("Edit Failed", "No update was applied."), mention_author=False)
            return

        await ctx.reply(embed=success_embed("Product Updated", f"`#{product_id}` `{field}` updated."), mention_author=False)

    @commands.command(name="dp")
    async def delete_product(self, ctx, product_id: int):
        if not is_staff(ctx.author):
            await ctx.reply("Only staff can delete products.", mention_author=False)
            return

        product = product_service.get_product(product_id)

        if not product:
            await ctx.reply(embed=error_embed("Not Found", f"Product `#{product_id}` does not exist."), mention_author=False)
            return

        product_service.delete_product(product_id)

        await ctx.reply(embed=success_embed("Product Deleted", f"`#{product_id}` **{product['name']}** deleted."), mention_author=False)

    @commands.command(name="rp")
    async def restock_product(self, ctx, product_id: int, amount: int):
        if not is_staff(ctx.author):
            await ctx.reply("Only staff can restock products.", mention_author=False)
            return

        product = product_service.get_product(product_id)

        if not product:
            await ctx.reply(embed=error_embed("Not Found", f"Product `#{product_id}` does not exist."), mention_author=False)
            return

        product_service.restock(product_id, amount)
        updated = product_service.get_product(product_id)

        await ctx.reply(
            embed=success_embed(
                "Product Restocked",
                f"`#{product_id}` **{updated['name']}** now has stock `{updated['stock']}`."
            ),
            mention_author=False
        )

    @commands.command(name="si")
    async def add_stock_item(self, ctx, product_id: int, *, content: str):
        if not is_staff(ctx.author):
            await ctx.reply("Only staff can add delivery stock items.", mention_author=False)
            return

        product = product_service.get_product(product_id)

        if not product:
            await ctx.reply(embed=error_embed("Not Found", f"Product `#{product_id}` does not exist."), mention_author=False)
            return

        ok, result = product_service.add_delivery_item(product_id, content)

        if not ok:
            await ctx.reply(embed=error_embed("Stock Item Failed", result), mention_author=False)
            return

        # Do not echo the secret content publicly.
        await ctx.reply(
            embed=success_embed(
                "Delivery Stock Added",
                f"Stored one hidden delivery item for `#{product_id}` **{product['name']}**.\n\nStock item ID: `{result}`\nVisible stock increased by `1`."
            ),
            mention_author=False
        )

    @commands.command(name="sis", aliases=["stockitems"])
    async def stock_items(self, ctx, product_id: int):
        if not is_staff(ctx.author):
            await ctx.reply("Only staff can view stock item counts.", mention_author=False)
            return

        product = product_service.get_product(product_id)
        counts = product_service.delivery_item_counts(product_id)

        if not product or counts is None:
            await ctx.reply(embed=error_embed("Not Found", f"Product `#{product_id}` does not exist."), mention_author=False)
            return

        await ctx.reply(
            embed=success_embed(
                "Delivery Stock Items",
                (
                    f"**Product:** `#{product_id}` **{product['name']}**\n"
                    f"**Unused hidden items:** `{counts['unused']}`\n"
                    f"**Used hidden items:** `{counts['used']}`\n"
                    f"**Visible stock:** `{product['stock']}`"
                )
            ),
            mention_author=False
        )

    @commands.command(name="stock")
    async def stock(self, ctx):
        grouped = product_service.get_grouped_products()
        await ctx.reply(embed=stock_overview_embed(grouped), mention_author=False)

    @commands.command(name="panel")
    async def panel(self, ctx, channel_name: str = "stock"):
        if not is_staff(ctx.author):
            await ctx.reply("Only staff can post product panels.", mention_author=False)
            return

        channel = discord.utils.get(ctx.guild.text_channels, name=channel_name)

        if not channel:
            await ctx.reply(embed=error_embed("Channel Not Found", f"`#{channel_name}` was not found."), mention_author=False)
            return

        products = product_service.get_all_products()

        if not products:
            await ctx.reply(embed=warning_embed("No Products", "Use `!ap` to add products first."), mention_author=False)
            return

        count = 0

        for product in products[:25]:
            await channel.send(embed=product_embed(product), view=ProductBuyView(product["id"]))
            count += 1

        await ctx.reply(embed=success_embed("Storefront Posted", f"Posted `{count}` product panels in {channel.mention}."), mention_author=False)

    @commands.command(name="buy")
    async def buy(self, ctx, product_id: int):
        product = product_service.get_product(product_id)

        if not product or not product.get("enabled"):
            await ctx.reply("This product is not available.", mention_author=False)
            return

        if int(product.get("stock", 0)) <= 0:
            await ctx.reply("This product is sold out.", mention_author=False)
            return

        channel, error = await create_product_ticket(ctx.guild, ctx.author, product)

        if error:
            await ctx.reply(error, mention_author=False)
            return

        await ctx.reply(f"Ticket created: {channel.mention}", mention_author=False)

async def setup(bot):
    await bot.add_cog(ProductsCog(bot))
