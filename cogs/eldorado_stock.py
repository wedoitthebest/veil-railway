
import os
import asyncio
import discord
from discord.ext import commands

from eldorado_sync import sync_eldorado_products
from services import product_service
from services.access_control import is_allowed
from services.stock_board_service import ensure_stock_channels, rebuild_all_boards, rebuild_game_board, game_label

class EldoradoStockCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._startup_done = False
        product_service.init_products()

    @commands.Cog.listener()
    async def on_ready(self):
        if self._startup_done:
            return
        self._startup_done = True

        mode = os.getenv("VEIL_REBUILD_STOCK_ON_START", "1").strip().lower()
        if mode not in {"1", "true", "yes", "on"}:
            print("[STOCK] Startup rebuild disabled.")
            return

        await asyncio.sleep(3)

        for guild in self.bot.guilds:
            try:
                await rebuild_all_boards(guild)
                print(f"[STOCK] Startup rebuilt stock boards for {guild.name}")
            except Exception as exc:
                print(f"[STOCK ERROR] Startup board rebuild failed for {guild.name}: {exc}")

    @commands.command(name="stocksetup", aliases=["ssu"])
    async def stock_setup(self, ctx):
        if not is_allowed(ctx.author.id):
            await ctx.reply("You are not allowed to run stock setup.", mention_author=False)
            return
        made = await ensure_stock_channels(ctx.guild)
        await ctx.reply(f"Stock channels ready. Created: `{', '.join(made) if made else 'none'}`", mention_author=False)

    @commands.command(name="estock", aliases=["eldostock", "syncstock"])
    async def eldorado_stock(self, ctx):
        if not is_allowed(ctx.author.id):
            await ctx.reply("You are not allowed to sync Eldorado stock.", mention_author=False)
            return

        status = await ctx.reply("Syncing Eldorado listings and rebuilding stock boards...", mention_author=False)

        try:
            result = sync_eldorado_products()
        except Exception as exc:
            await status.edit(content=f"Eldorado sync failed: `{exc}`")
            return

        deleted_total, posted, per_channel = await rebuild_all_boards(ctx.guild)

        await status.edit(
            content=(
                f"Eldorado sync complete.\n"
                f"Imported/updated: `{result.get('count', 0)}` listings\n"
                f"Disabled missing: `{result.get('disabled_missing', 0)}`\n"
                f"Old stock messages deleted: `{deleted_total}`\n"
                f"Stock boards posted: `{posted}`\n"
                f"Routing: `{per_channel}`"
            )
        )

    @commands.command(name="stockboard", aliases=["sb", "persistviews"])
    async def stock_board_only(self, ctx, game: str = None):
        if not is_allowed(ctx.author.id):
            await ctx.reply("You are not allowed to rebuild stock boards.", mention_author=False)
            return

        if game:
            slug = product_service.normalize_game_slug(game)
            result = await rebuild_game_board(ctx.guild, slug)
            await ctx.reply(
                f"{game_label(slug)} board rebuilt. Deleted `{result['deleted']}`, posted `{result['posted']}`, products `{result['products']}`.",
                mention_author=False
            )
            return

        deleted_total, posted, per_channel = await rebuild_all_boards(ctx.guild)
        await ctx.reply(
            f"Stock boards rebuilt. Deleted `{deleted_total}` old messages, posted `{posted}` boards. Routing: `{per_channel}`",
            mention_author=False
        )

    @commands.command(name="eroute")
    async def eldorado_route_list(self, ctx):
        if not is_allowed(ctx.author.id):
            await ctx.reply("You are not allowed to view routing.", mention_author=False)
            return

        products = product_service.get_unrouted_products()
        if not products:
            await ctx.reply("No active `other` / unrouted products found.", mention_author=False)
            return

        from services.stock_board_service import short_name

        lines = []
        for p in products[:20]:
            lines.append(f"`#{p['id']}` **{short_name(p)}** — stock `{p['stock']}` — price `{p['price']}`")

        embed = discord.Embed(title="Eldorado Unrouted Products", description="\n".join(lines)[:3900], color=0x7C3CFF)
        embed.set_footer(text="Use !egame PRODUCT_ID aotr/gpo/sbtd/da-hood or !eall keyword game")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="egame")
    async def eldorado_set_game(self, ctx, product_id: int, game: str):
        if not is_allowed(ctx.author.id):
            await ctx.reply("You are not allowed to route products.", mention_author=False)
            return
        slug = product_service.normalize_game_slug(game)
        ok = product_service.route_product(product_id, slug)
        if not ok:
            await ctx.reply("Product not found or route failed.", mention_author=False)
            return
        await rebuild_game_board(ctx.guild, slug)
        await ctx.reply(f"Product `#{product_id}` routed to `{product_service.game_label(slug)}` and board refreshed.", mention_author=False)

    @commands.command(name="eall")
    async def eldorado_set_game_by_keyword(self, ctx, keyword: str, game: str):
        if not is_allowed(ctx.author.id):
            await ctx.reply("You are not allowed to route products.", mention_author=False)
            return
        slug = product_service.normalize_game_slug(game)
        ids = product_service.route_products_by_keyword(keyword, slug)
        await rebuild_game_board(ctx.guild, slug)
        await ctx.reply(f"Routed `{len(ids)}` products matching `{keyword}` to `{product_service.game_label(slug)}` and board refreshed.", mention_author=False)

async def setup(bot):
    await bot.add_cog(EldoradoStockCog(bot))
