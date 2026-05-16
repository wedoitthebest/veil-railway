
import discord

from services import product_service

AUTO_DELIVERY_TYPES = {"text", "key", "account", "link"}

def is_auto_delivery(product):
    delivery_type = str(product.get("delivery_type", "Manual")).strip().lower()
    return delivery_type in AUTO_DELIVERY_TYPES

def delivery_embed(product, item_content):
    embed = discord.Embed(
        title="📦 Your Veil Delivery",
        description=(
            "Your order has been completed.\n\n"
            f"**Product:** `{product['name']}`\n"
            f"**Category:** `{product['category']}`\n"
            f"**Delivery Type:** `{product.get('delivery_type', 'Manual')}`\n\n"
            "**Delivery:**\n"
            f"```text\n{item_content}\n```\n\n"
            "Do not share this delivery with anyone except staff if support is needed."
        ),
        color=0x44D69F
    )
    embed.set_footer(text="Veil's Grocery Store • Delivery")
    return embed

async def deliver_if_available(member, product):
    if not is_auto_delivery(product):
        return {
            "mode": "manual",
            "delivered": False,
            "message": "Manual delivery product"
        }

    item = product_service.reserve_delivery_item(product["id"], member.id)
    if not item:
        return {
            "mode": "auto",
            "delivered": False,
            "message": "No stored delivery item available"
        }

    await member.send(embed=delivery_embed(product, item["content"]))

    return {
        "mode": "auto",
        "delivered": True,
        "message": "Delivery item sent by DM",
        "stock_item_id": item["id"]
    }
