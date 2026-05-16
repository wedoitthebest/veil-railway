
import discord

BRAND_COLOR = 0x7C3CFF
SUCCESS_COLOR = 0x44D69F
WARN_COLOR = 0xFFD166
ERROR_COLOR = 0xE06C75

def base_embed(title, description="", color=BRAND_COLOR):
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text="Veil's Grocery Store")
    return embed

def success_embed(title, description=""):
    return base_embed(title, description, SUCCESS_COLOR)

def error_embed(title, description=""):
    return base_embed(title, description, ERROR_COLOR)

def warning_embed(title, description=""):
    return base_embed(title, description, WARN_COLOR)

def product_embed(product):
    stock = int(product.get("stock", 0))
    low_at = int(product.get("low_stock_at", 2))

    if stock <= 0:
        status = "Sold Out"
    elif stock <= low_at:
        status = "Low Stock"
    else:
        status = "Available"

    embed = base_embed(
        f"{product.get('emoji', '🛒')} {product.get('name', 'Product')}",
        product.get("description") or "Open a ticket to purchase."
    )
    embed.add_field(name="Category", value=f"`{product.get('category', 'Other')}`", inline=True)
    embed.add_field(name="Price", value=f"`{product.get('price', 'Ask')}`", inline=True)
    embed.add_field(name="Stock", value=f"`{stock}`", inline=True)
    embed.add_field(name="Delivery", value=f"`{product.get('delivery_type', 'Manual')}`", inline=True)
    embed.add_field(name="Status", value=f"`{status}`", inline=True)
    embed.add_field(name="Sold", value=f"`{product.get('sold_count', 0)}`", inline=True)
    embed.set_footer(text=f"Veil's Grocery Store • Product ID {product.get('id')}")
    return embed

def stock_overview_embed(grouped):
    if not grouped:
        return warning_embed("🛒 Store Stock", "No products found.")

    lines = []

    for category, products in grouped.items():
        lines.append(f"**{category}**")
        for product in products[:10]:
            stock = int(product.get("stock", 0))
            price = product.get("price", "Ask")
            emoji = product.get("emoji", "🛒")
            lines.append(f"{emoji} `#{product['id']}` **{product['name']}** — `{stock}` left — `{price}`")
        lines.append("")

    return base_embed("🛒 Veil Store Stock", "\n".join(lines)[:3900])
