
import discord
from discord.ext import commands

from services.access_control import is_allowed
from services import product_service
from services.stock_board_service import short_name, stock_text

class ProductSearchCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        product_service.init_products()

    @commands.command(name="find", aliases=["searchproduct", "fp"])
    async def find_product(self, ctx, *, query: str):
        if not is_allowed(ctx.author.id):
            await ctx.reply("You are not allowed to search products.", mention_author=False)
            return

        query_l = query.lower().strip()
        products = product_service.get_all_products(include_disabled=True)
        matches = []
        for p in products:
            hay = " ".join([
                str(p.get("id", "")),
                str(p.get("name", "")),
                str(p.get("category", "")),
                str(p.get("game_slug", "")),
                str(p.get("raw_game", "")),
            ]).lower()
            if query_l in hay:
                matches.append(p)

        matches = matches[:15]
        if not matches:
            await ctx.reply(f"No products found for `{query}`.", mention_author=False)
            return

        lines = []
        for p in matches:
            enabled = "on" if int(p.get("enabled") or 0) == 1 else "off"
            lines.append(
                f"`#{p['id']}` **{short_name(p)}** — `{p.get('game_slug') or 'other'}` — `{stock_text(p)}` — **{p.get('price') or 'Ask'}** — `{enabled}`"
            )

        embed = discord.Embed(
            title=f"🔎 Product Search: {query}",
            description="\n".join(lines)[:3900],
            color=0x7C3CFF
        )
        embed.set_footer(text="Use !ship item name in a ticket, or !egame ID game to route.")
        await ctx.reply(embed=embed, mention_author=False)

async def setup(bot):
    await bot.add_cog(ProductSearchCog(bot))
