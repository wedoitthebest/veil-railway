
from database import queries
from database.models import init_database

GAME_LABELS = {
    "aotr": "AOTR",
    "gpo": "GPO",
    "sbtd": "SBTD",
    "da-hood": "Da Hood",
    "other": "Other",
}

def normalize_game_slug(value):
    text = str(value or "").lower().strip().replace("_", "-")
    aliases = {
        "dahood": "da-hood",
        "da hood": "da-hood",
        "sponge": "sbtd",
        "spongebob": "sbtd",
        "spongebob-tower-defense": "sbtd",
        "grandpiece": "gpo",
        "grand-piece": "gpo",
        "grand-piece-online": "gpo",
        "attack-on-titan-revolution": "aotr",
    }
    return aliases.get(text, text)

def game_label(slug):
    return GAME_LABELS.get(normalize_game_slug(slug), str(slug).replace("-", " ").title())

def init_products():
    init_database()

def add_product(category, name, stock, price, delivery_type="Manual", description="", emoji="🛒"):
    return queries.create_product(category, name, stock, price, delivery_type, description, emoji)

def edit_product(product_id, field, value):
    if field in ["stock", "low_stock_at"]:
        value = int(value)
    if field == "enabled":
        value = 1 if str(value).lower() in ["1", "true", "yes", "on", "enabled"] else 0
    return queries.update_product(product_id, **{field: value})

def route_product(product_id, slug):
    slug = normalize_game_slug(slug)
    return queries.route_product(product_id, slug, game_label(slug))

def route_products_by_keyword(keyword, slug):
    slug = normalize_game_slug(slug)
    return queries.route_products_by_keyword(keyword, slug, game_label(slug))

def get_unrouted_products():
    return queries.list_unrouted_products()

def delete_product(product_id):
    return queries.delete_product(product_id)

def restock(product_id, amount):
    return queries.restock_product(product_id, int(amount))

def decrement(product_id, amount=1):
    return queries.decrement_product(product_id, int(amount))

def get_product(product_id):
    return queries.get_product(product_id)

def get_all_products(include_disabled=False):
    return queries.list_products(include_disabled=include_disabled)

def get_products_by_game(game_slug, include_disabled=False):
    return queries.list_products_by_game(normalize_game_slug(game_slug), include_disabled=include_disabled)

def get_game_slugs():
    return queries.list_game_slugs()

def get_grouped_products():
    return queries.grouped_products()

def find_product(name):
    return queries.find_product(name)

def upsert_external_product(product):
    return queries.upsert_external_product(product)

def disable_missing_external(source, external_ids):
    return queries.disable_missing_external(source, external_ids)

def add_delivery_item(product_id, content):
    product = get_product(product_id)
    if not product:
        return False, "Product not found"
    item_id = queries.add_stock_item(product_id, content)
    queries.restock_product(product_id, 1)
    return True, item_id

def delivery_item_counts(product_id):
    product = get_product(product_id)
    if not product:
        return None
    return {"unused": queries.count_unused_stock_items(product_id), "used": queries.count_used_stock_items(product_id)}

def reserve_delivery_item(product_id, buyer_id):
    item = queries.get_next_unused_stock_item(product_id)
    if not item:
        return None
    queries.mark_stock_item_used(item["id"], buyer_id)
    return item
