
import re
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = Path("data/app.db")

def connect():
    DB_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(DB_PATH)

def table_exists(con, table):
    row = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return bool(row)

def columns(con, table):
    try:
        return [row[1] for row in con.execute(f"PRAGMA table_info({table})").fetchall()]
    except Exception:
        return []

def parse_price(value):
    if value is None:
        return None
    text = str(value).replace(",", ".")
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except Exception:
        return None

def money(value):
    if value is None:
        return "unknown"
    return f"${value:,.2f}"

def now_utc():
    return datetime.utcnow()

def period_bounds(period):
    period = str(period or "today").lower().strip()
    now = now_utc()

    if period in {"today", "day", "daily"}:
        start = datetime(now.year, now.month, now.day)
    elif period in {"week", "weekly", "7d", "7days"}:
        start = now - timedelta(days=7)
    elif period in {"month", "monthly", "30d", "30days"}:
        start = now - timedelta(days=30)
    elif period in {"all", "alltime", "total"}:
        return None, now, "all time"
    else:
        start = datetime(now.year, now.month, now.day)
        period = "today"

    return start, now, period

def parse_dt(value):
    if not value:
        return None
    text = str(value).replace("Z", "")
    try:
        return datetime.fromisoformat(text)
    except Exception:
        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]:
            try:
                return datetime.strptime(text[:19], fmt)
            except Exception:
                pass
    return None

def init_safe():
    with connect() as con:
        con.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                guild_id TEXT,
                ticket_channel_id TEXT,
                ticket_channel_name TEXT,
                buyer_id TEXT,
                buyer_name TEXT,
                staff_id TEXT,
                staff_name TEXT,
                product TEXT,
                status TEXT NOT NULL,
                vouch_status TEXT NOT NULL DEFAULT 'pending'
            )
        ''')
        con.commit()

def fetch_orders(guild_id=None, period="all"):
    init_safe()
    start, end, label = period_bounds(period)
    rows = []

    with connect() as con:
        if not table_exists(con, "orders"):
            return [], label

        cols = columns(con, "orders")
        wanted = [
            "id", "created_at", "completed_at", "guild_id", "ticket_channel_id", "ticket_channel_name",
            "buyer_id", "buyer_name", "staff_id", "staff_name", "product", "status", "vouch_status"
        ]

        existing = [c for c in wanted if c in cols]
        query = f"SELECT {', '.join(existing)} FROM orders"
        params = []
        where = []

        if guild_id and "guild_id" in cols:
            where.append("guild_id=?")
            params.append(str(guild_id))

        if where:
            query += " WHERE " + " AND ".join(where)

        query += " ORDER BY id DESC"

        for row in con.execute(query, params).fetchall():
            item = dict(zip(existing, row))
            dt = parse_dt(item.get("completed_at") or item.get("created_at"))
            if start and dt and dt < start:
                continue
            if start and not dt:
                continue
            rows.append(item)

    return rows, label

def fetch_products(include_disabled=True):
    try:
        from services import product_service
        product_service.init_products()
        if hasattr(product_service, "get_all_products"):
            return product_service.get_all_products(include_disabled=include_disabled)
    except Exception:
        pass

    with connect() as con:
        if not table_exists(con, "products"):
            return []
        cols = columns(con, "products")
        selected = "*"
        try:
            rows = con.execute(f"SELECT {selected} FROM products").fetchall()
            return [dict(zip(cols, row)) for row in rows]
        except Exception:
            return []

def product_price_index():
    products = fetch_products(include_disabled=True)
    index = {}
    for p in products:
        name = str(p.get("name") or "").lower().strip()
        short = name
        price = parse_price(p.get("price"))
        if price is None:
            continue
        if name:
            index[name] = price
        if short:
            index[short] = price
    return index

def estimate_order_revenue(orders):
    prices = product_price_index()
    total = 0.0
    known = 0
    unknown = 0

    for order in orders:
        product = str(order.get("product") or "").lower().strip()
        price = None

        if product in prices:
            price = prices[product]
        else:
            for name, value in prices.items():
                if product and (product in name or name in product):
                    price = value
                    break

        if price is None:
            unknown += 1
        else:
            total += price
            known += 1

    return total, known, unknown

def sales_summary(guild_id=None, period="today"):
    orders, label = fetch_orders(guild_id, period)
    completed = [o for o in orders if str(o.get("status") or "").lower() in {"completed", "complete", "done", "shipped"}]
    pending_vouch = [o for o in completed if str(o.get("vouch_status") or "").lower() == "pending"]
    vouched = [o for o in completed if str(o.get("vouch_status") or "").lower() == "received"]

    revenue, known_prices, unknown_prices = estimate_order_revenue(completed)

    return {
        "period": label,
        "orders": completed,
        "completed_count": len(completed),
        "pending_vouch": len(pending_vouch),
        "vouched": len(vouched),
        "estimated_revenue": revenue,
        "known_prices": known_prices,
        "unknown_prices": unknown_prices,
    }

def count_by(items, key):
    counts = {}
    for item in items:
        value = str(item.get(key) or "unknown").strip() or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return sorted(counts.items(), key=lambda x: (-x[1], x[0].lower()))

def top_items(guild_id=None, period="all", limit=10):
    orders, label = fetch_orders(guild_id, period)
    completed = [o for o in orders if str(o.get("status") or "").lower() in {"completed", "complete", "done", "shipped"}]
    return count_by(completed, "product")[:limit], label

def staff_stats(guild_id=None, period="all", limit=10):
    orders, label = fetch_orders(guild_id, period)
    completed = [o for o in orders if str(o.get("status") or "").lower() in {"completed", "complete", "done", "shipped"}]
    rows = count_by(completed, "staff_name")[:limit]
    return rows, label

def buyer_history(guild_id, buyer_id=None, buyer_name=None, limit=10):
    orders, label = fetch_orders(guild_id, "all")
    filtered = []
    for o in orders:
        if buyer_id and str(o.get("buyer_id")) == str(buyer_id):
            filtered.append(o)
        elif buyer_name and buyer_name.lower() in str(o.get("buyer_name") or "").lower():
            filtered.append(o)
    return filtered[:limit]

def recent_orders(guild_id=None, limit=10):
    orders, label = fetch_orders(guild_id, "all")
    completed = [o for o in orders if str(o.get("status") or "").lower() in {"completed", "complete", "done", "shipped"}]
    return completed[:limit]

def low_stock(threshold=5, limit=20):
    products = fetch_products(include_disabled=False)
    rows = []
    for p in products:
        try:
            stock = int(p.get("stock") or 0)
        except Exception:
            stock = 0
        enabled = int(p.get("enabled") or 1)
        if enabled == 1 and stock <= threshold:
            rows.append(p)
    rows.sort(key=lambda p: (int(p.get("stock") or 0), str(p.get("game_slug") or ""), str(p.get("name") or "").lower()))
    return rows[:limit]

def stock_value():
    products = fetch_products(include_disabled=False)
    total = 0.0
    known = 0
    unknown = 0
    units = 0
    by_game = {}

    for p in products:
        try:
            stock = int(p.get("stock") or 0)
        except Exception:
            stock = 0

        if stock <= 0:
            continue

        units += stock
        game = str(p.get("game_slug") or p.get("raw_game") or "other")
        by_game.setdefault(game, {"units": 0, "value": 0.0, "known": 0, "unknown": 0})
        by_game[game]["units"] += stock

        price = parse_price(p.get("price"))
        if price is None:
            unknown += 1
            by_game[game]["unknown"] += 1
            continue

        value = price * stock
        total += value
        known += 1
        by_game[game]["value"] += value
        by_game[game]["known"] += 1

    return {
        "products": len(products),
        "units": units,
        "estimated_value": total,
        "known_prices": known,
        "unknown_prices": unknown,
        "by_game": by_game,
    }
