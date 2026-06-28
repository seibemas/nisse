import json
import sqlite3
from datetime import datetime, timezone

import app.config as config


def get_conn() -> sqlite3.Connection:
    """Return a connection to the SQLite DB (creates DB_PATH parent dir if needed)."""
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the products table if it doesn't exist. Safe to call on every startup."""
    conn = get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                slug         TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                category     TEXT NOT NULL,
                price        TEXT NOT NULL,
                short        TEXT NOT NULL,
                long         TEXT NOT NULL,
                materials    TEXT NOT NULL,
                care         TEXT NOT NULL,
                tint         TEXT NOT NULL DEFAULT 'teal',
                photo        TEXT,
                sold         INTEGER NOT NULL DEFAULT 0,
                sort_order   INTEGER NOT NULL DEFAULT 0,
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS publish_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                published_at  TEXT NOT NULL,
                product_count INTEGER NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()


def seed_from_catalog_json() -> int:
    """If mysma.db doesn't exist yet AND .tmp/catalog.json exists, import all products.

    Returns count of products imported (0 if skipped or no catalog.json).
    """
    # Skip if DB already exists
    if config.DB_PATH.exists():
        return 0

    # Skip if no catalog.json
    if not config.CATALOG_JSON.exists():
        return 0

    with open(config.CATALOG_JSON, "r", encoding="utf-8") as f:
        products = json.load(f)

    now = datetime.now(timezone.utc).isoformat()

    init_db()
    conn = get_conn()
    try:
        for index, product in enumerate(products):
            conn.execute(
                """
                INSERT INTO products
                    (slug, name, category, price, short, long, materials, care,
                     tint, photo, sold, sort_order, created_at, updated_at)
                VALUES
                    (:slug, :name, :category, :price, :short, :long, :materials, :care,
                     :tint, :photo, :sold, :sort_order, :created_at, :updated_at)
                """,
                {
                    "slug": product["slug"],
                    "name": product["name"],
                    "category": product["category"],
                    "price": product["price"],
                    "short": product["short"],
                    "long": product["long"],
                    "materials": product["materials"],
                    "care": product["care"],
                    "tint": product.get("tint", "teal"),
                    "photo": product.get("photo"),
                    "sold": 1 if product.get("sold") else 0,
                    "sort_order": index,
                    "created_at": now,
                    "updated_at": now,
                },
            )
        conn.commit()
        return len(products)
    finally:
        conn.close()
