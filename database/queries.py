
from database.models import connect, init_database

PRODUCT_COLUMNS = (
    "id,category,name,price,stock,delivery_type,description,emoji,enabled,"
    "sold_count,low_stock_at,created_at,updated_at,source,external_id,external_url,game_slug,raw_game,last_synced_at,source_payload"
)

PRODUCT_KEYS = [
    "id", "category", "name", "price", "stock", "delivery_type",
    "description", "emoji", "enabled", "sold_count", "low_stock_at",
    "created_at", "updated_at", "source", "external_id", "external_url",
    "game_slug", "raw_game", "last_synced_at", "source_payload"
]

def row_to_product(row):
    if not row:
        return None
    return dict(zip(PRODUCT_KEYS, row))

def row_to_stock_item(row):
    if not row:
        return None
    keys = ["id", "product_id", "content", "used", "used_by", "used_at", "created_at"]
    return dict(zip(keys, row))

def create_product(category, name, stock, price, delivery_type="Manual", description="", emoji="🛒"):
    init_database()
    with connect() as con:
        cur = con.execute(
            '''
            INSERT INTO products(category,name,stock,price,delivery_type,description,emoji,source)
            VALUES(?,?,?,?,?,?,?,'manual')
            ''',
            (category, name, int(stock), str(price), delivery_type, description, emoji)
        )
        con.commit()
        return cur.lastrowid

def upsert_external_product(product):
    init_database()
    external_id = str(product.get("external_id") or "").strip()
    source = str(product.get("source") or "eldorado").strip() or "eldorado"

    if not external_id:
        raise ValueError("external_id required")

    values = {
        "category": product.get("category") or "Other",
        "name": product.get("name") or "Eldorado Listing",
        "price": str(product.get("price") or "Ask"),
        "stock": int(product.get("stock") or 0),
        "delivery_type": product.get("delivery_type") or "Manual",
        "description": product.get("description") or "",
        "emoji": product.get("emoji") or "🛒",
        "enabled": 1 if product.get("enabled", True) else 0,
        "source": source,
        "external_id": external_id,
        "external_url": product.get("external_url") or "",
        "game_slug": product.get("game_slug") or "",
        "raw_game": product.get("raw_game") or product.get("category") or "",
        "source_payload": product.get("source_payload") or "",
    }

    with connect() as con:
        existing = con.execute(
            "SELECT id FROM products WHERE source=? AND external_id=? LIMIT 1",
            (source, external_id)
        ).fetchone()

        if existing:
            product_id = existing[0]
            con.execute(
                '''
                UPDATE products
                SET category=?, name=?, price=?, stock=?, delivery_type=?, description=?, emoji=?,
                    enabled=?, external_url=?, game_slug=?, raw_game=?, source_payload=?,
                    last_synced_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                ''',
                (
                    values["category"], values["name"], values["price"], values["stock"],
                    values["delivery_type"], values["description"], values["emoji"],
                    values["enabled"], values["external_url"], values["game_slug"],
                    values["raw_game"], values["source_payload"], product_id
                )
            )
        else:
            cur = con.execute(
                '''
                INSERT INTO products(
                    category,name,price,stock,delivery_type,description,emoji,enabled,
                    source,external_id,external_url,game_slug,raw_game,source_payload,last_synced_at
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
                ''',
                (
                    values["category"], values["name"], values["price"], values["stock"],
                    values["delivery_type"], values["description"], values["emoji"],
                    values["enabled"], values["source"], values["external_id"],
                    values["external_url"], values["game_slug"], values["raw_game"],
                    values["source_payload"]
                )
            )
            product_id = cur.lastrowid

        con.commit()
        return product_id

def disable_missing_external(source, external_ids):
    init_database()
    ids = {str(x) for x in external_ids if str(x).strip()}
    with connect() as con:
        rows = con.execute("SELECT id, external_id FROM products WHERE source=?", (source,)).fetchall()
        disabled = 0
        for product_id, external_id in rows:
            if str(external_id) not in ids:
                con.execute(
                    "UPDATE products SET enabled=0, stock=0, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (product_id,)
                )
                disabled += 1
        con.commit()
    return disabled

def list_products(include_disabled=False):
    init_database()
    with connect() as con:
        if include_disabled:
            rows = con.execute(f"SELECT {PRODUCT_COLUMNS} FROM products ORDER BY category,name").fetchall()
        else:
            rows = con.execute(f"SELECT {PRODUCT_COLUMNS} FROM products WHERE enabled=1 ORDER BY category,name").fetchall()
    return [row_to_product(row) for row in rows]

def list_products_by_game(game_slug, include_disabled=False):
    init_database()
    with connect() as con:
        if include_disabled:
            rows = con.execute(f"SELECT {PRODUCT_COLUMNS} FROM products WHERE game_slug=? ORDER BY stock DESC,name", (game_slug,)).fetchall()
        else:
            rows = con.execute(f"SELECT {PRODUCT_COLUMNS} FROM products WHERE game_slug=? AND enabled=1 ORDER BY stock DESC,name", (game_slug,)).fetchall()
    return [row_to_product(row) for row in rows]

def list_game_slugs():
    init_database()
    with connect() as con:
        rows = con.execute(
            "SELECT DISTINCT game_slug FROM products WHERE enabled=1 AND game_slug IS NOT NULL AND game_slug != '' ORDER BY game_slug"
        ).fetchall()
    return [r[0] for r in rows]

def get_product(product_id):
    init_database()
    with connect() as con:
        row = con.execute(f"SELECT {PRODUCT_COLUMNS} FROM products WHERE id=?", (int(product_id),)).fetchone()
    return row_to_product(row)

def find_product_by_name(name):
    init_database()
    term = str(name).strip()
    with connect() as con:
        row = con.execute(f"SELECT {PRODUCT_COLUMNS} FROM products WHERE lower(name)=lower(?) ORDER BY id DESC LIMIT 1", (term,)).fetchone()
        if row:
            return row_to_product(row)
        row = con.execute(f"SELECT {PRODUCT_COLUMNS} FROM products WHERE lower(name) LIKE lower(?) ORDER BY length(name) ASC, id DESC LIMIT 1", (f"%{term}%",)).fetchone()
    return row_to_product(row)

def find_product(identifier):
    text = str(identifier).strip()
    if text.isdigit():
        return get_product(int(text))
    return find_product_by_name(text)

def update_product(product_id, **fields):
    init_database()
    allowed = {
        "category", "name", "price", "stock", "delivery_type", "description", "emoji",
        "enabled", "low_stock_at", "external_url", "game_slug", "raw_game"
    }
    updates = []
    values = []
    for key, value in fields.items():
        if key in allowed:
            updates.append(f"{key}=?")
            values.append(value)
    if not updates:
        return False
    updates.append("updated_at=CURRENT_TIMESTAMP")
    values.append(int(product_id))
    with connect() as con:
        con.execute(f"UPDATE products SET {', '.join(updates)} WHERE id=?", values)
        con.commit()
    return True

def route_product(product_id, game_slug, category):
    return update_product(product_id, game_slug=game_slug, category=category, raw_game=category)

def route_products_by_keyword(keyword, game_slug, category):
    init_database()
    kw = f"%{str(keyword).lower()}%"
    with connect() as con:
        rows = con.execute("SELECT id FROM products WHERE lower(name) LIKE ? OR lower(description) LIKE ?", (kw, kw)).fetchall()
        ids = [r[0] for r in rows]
        for product_id in ids:
            con.execute(
                "UPDATE products SET game_slug=?, category=?, raw_game=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (game_slug, category, category, product_id)
            )
        con.commit()
    return ids

def list_unrouted_products():
    init_database()
    with connect() as con:
        rows = con.execute(
            f"SELECT {PRODUCT_COLUMNS} FROM products WHERE enabled=1 AND (game_slug IS NULL OR game_slug='' OR game_slug='other') ORDER BY stock DESC,name"
        ).fetchall()
    return [row_to_product(row) for row in rows]

def delete_product(product_id):
    init_database()
    with connect() as con:
        con.execute("DELETE FROM product_stock_items WHERE product_id=?", (int(product_id),))
        con.execute("DELETE FROM products WHERE id=?", (int(product_id),))
        con.commit()
    return True

def restock_product(product_id, amount):
    init_database()
    with connect() as con:
        con.execute("UPDATE products SET stock=stock+?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (int(amount), int(product_id)))
        con.commit()
    return True

def decrement_product(product_id, amount=1):
    init_database()
    product = get_product(product_id)
    if not product:
        return False, "Product not found"
    if int(product["enabled"]) != 1:
        return False, "Product disabled"
    if int(product["stock"]) < int(amount):
        return False, "Not enough stock"
    with connect() as con:
        con.execute("UPDATE products SET stock=stock-?, sold_count=sold_count+?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (int(amount), int(amount), int(product_id)))
        con.commit()
    return True, "Stock updated"

def grouped_products():
    products = list_products()
    grouped = {}
    for product in products:
        grouped.setdefault(product["category"], []).append(product)
    return grouped

def add_stock_item(product_id, content):
    init_database()
    with connect() as con:
        cur = con.execute("INSERT INTO product_stock_items(product_id, content, used) VALUES(?,?,0)", (int(product_id), str(content)))
        con.commit()
        return cur.lastrowid

def count_unused_stock_items(product_id):
    init_database()
    with connect() as con:
        return con.execute("SELECT COUNT(*) FROM product_stock_items WHERE product_id=? AND used=0", (int(product_id),)).fetchone()[0]

def count_used_stock_items(product_id):
    init_database()
    with connect() as con:
        return con.execute("SELECT COUNT(*) FROM product_stock_items WHERE product_id=? AND used=1", (int(product_id),)).fetchone()[0]

def get_next_unused_stock_item(product_id):
    init_database()
    with connect() as con:
        row = con.execute("SELECT id,product_id,content,used,used_by,used_at,created_at FROM product_stock_items WHERE product_id=? AND used=0 ORDER BY id ASC LIMIT 1", (int(product_id),)).fetchone()
    return row_to_stock_item(row)

def mark_stock_item_used(item_id, used_by):
    init_database()
    with connect() as con:
        con.execute("UPDATE product_stock_items SET used=1, used_by=?, used_at=CURRENT_TIMESTAMP WHERE id=?", (str(used_by), int(item_id)))
        con.commit()
    return True
