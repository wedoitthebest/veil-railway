
import sqlite3
from pathlib import Path

DB_PATH = Path("data/app.db")

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)

def _columns(con, table):
    return {row[1] for row in con.execute(f"PRAGMA table_info({table})").fetchall()}

def _ensure_column(con, table, name, ddl):
    if name not in _columns(con, table):
        con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")

def init_database():
    with connect() as con:
        con.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                name TEXT NOT NULL,
                price TEXT NOT NULL,
                stock INTEGER NOT NULL DEFAULT 0,
                delivery_type TEXT NOT NULL DEFAULT 'Manual',
                description TEXT NOT NULL DEFAULT '',
                emoji TEXT NOT NULL DEFAULT '🛒',
                enabled INTEGER NOT NULL DEFAULT 1,
                sold_count INTEGER NOT NULL DEFAULT 0,
                low_stock_at INTEGER NOT NULL DEFAULT 2,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        con.execute('''
            CREATE TABLE IF NOT EXISTS product_stock_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                used_by TEXT,
                used_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(product_id) REFERENCES products(id)
            )
        ''')

        _ensure_column(con, "products", "source", "TEXT NOT NULL DEFAULT 'manual'")
        _ensure_column(con, "products", "external_id", "TEXT")
        _ensure_column(con, "products", "external_url", "TEXT")
        _ensure_column(con, "products", "game_slug", "TEXT")
        _ensure_column(con, "products", "raw_game", "TEXT")
        _ensure_column(con, "products", "last_synced_at", "TEXT")
        _ensure_column(con, "products", "source_payload", "TEXT")

        con.execute("CREATE INDEX IF NOT EXISTS idx_products_source_external ON products(source, external_id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_products_game_slug ON products(game_slug)")
        con.commit()
