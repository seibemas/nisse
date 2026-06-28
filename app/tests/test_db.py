"""Unit tests for app.db — always use tmp_path, never touch the real mysma.db."""
import json
import sqlite3
from pathlib import Path
from unittest import mock

import pytest

import app.config as config
import app.db as db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_CATALOG = [
    {
        "slug": "aurora-iris-ring",
        "name": "Aurora Iris Ring",
        "category": "Jewelry",
        "price": "$68",
        "short": "A slim gold band cradling a shifting green-teal stone.",
        "long": "Hand-set on a recycled-gold band, the Aurora Iris catches light.",
        "materials": "Recycled 14k gold-fill band · ethically sourced labradorite",
        "care": "Keep dry when you can; a soft cloth brings the glow back.",
        "tint": "teal",
        "photo": None,
        "sold": True,
    },
    {
        "slug": "moonlit-linen-wrap",
        "name": "Moonlit Linen Wrap",
        "category": "Clothing",
        "price": "$94",
        "short": "An airy stonewashed-linen wrap in deep amethyst.",
        "long": "Cut from breathable stonewashed linen and dyed a deep amethyst.",
        "materials": "100% European stonewashed linen · low-impact dye",
        "care": "Machine wash cold, line dry, warm iron if you like.",
        "tint": "indigo",
        "photo": None,
        "sold": False,
    },
]


@pytest.fixture()
def patched_paths(tmp_path):
    """Patch DB_PATH and CATALOG_JSON to point inside tmp_path for each test."""
    db_path = tmp_path / "mysma.db"
    catalog_path = tmp_path / "catalog.json"
    with mock.patch.object(config, "DB_PATH", db_path), \
         mock.patch.object(config, "CATALOG_JSON", catalog_path):
        yield {"db_path": db_path, "catalog_path": catalog_path, "tmp": tmp_path}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_init_db_creates_products_table(patched_paths):
    """init_db() must create the products table."""
    db.init_db()

    conn = sqlite3.connect(str(patched_paths["db_path"]))
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='products'"
    )
    assert cursor.fetchone() is not None, "products table was not created"
    conn.close()


def test_init_db_creates_publish_log_table(patched_paths):
    """init_db() must create the publish_log table."""
    db.init_db()

    conn = sqlite3.connect(str(patched_paths["db_path"]))
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='publish_log'"
    )
    assert cursor.fetchone() is not None, "publish_log table was not created"
    conn.close()


def test_seed_from_catalog_json_imports_products(patched_paths):
    """seed_from_catalog_json() with a valid catalog.json imports all rows correctly."""
    catalog_path = patched_paths["catalog_path"]
    catalog_path.write_text(json.dumps(SAMPLE_CATALOG), encoding="utf-8")

    count = db.seed_from_catalog_json()

    assert count == 2, f"Expected 2 products imported, got {count}"

    conn = sqlite3.connect(str(patched_paths["db_path"]))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM products ORDER BY sort_order").fetchall()
    conn.close()

    assert len(rows) == 2

    first = rows[0]
    assert first["slug"] == "aurora-iris-ring"
    assert first["name"] == "Aurora Iris Ring"
    assert first["category"] == "Jewelry"
    assert first["price"] == "$68"
    assert first["tint"] == "teal"
    assert first["photo"] is None
    assert first["sold"] == 1, "sold=True in JSON should map to 1 in DB"
    assert first["sort_order"] == 0

    second = rows[1]
    assert second["slug"] == "moonlit-linen-wrap"
    assert second["sold"] == 0, "sold=False in JSON should map to 0 in DB"
    assert second["sort_order"] == 1

    # created_at and updated_at must be non-empty ISO strings
    assert first["created_at"], "created_at should be set"
    assert first["updated_at"], "updated_at should be set"


def test_seed_from_catalog_json_no_catalog_returns_zero(patched_paths):
    """seed_from_catalog_json() returns 0 and doesn't error when catalog.json is absent."""
    # catalog_path does NOT exist — patched_paths only patches the path, doesn't create the file
    count = db.seed_from_catalog_json()
    assert count == 0


def test_seed_from_catalog_json_skips_when_db_exists(patched_paths):
    """seed_from_catalog_json() returns 0 without re-importing when DB already exists."""
    db_path = patched_paths["db_path"]
    catalog_path = patched_paths["catalog_path"]

    # Write a catalog with 2 products and seed once to create the DB
    catalog_path.write_text(json.dumps(SAMPLE_CATALOG), encoding="utf-8")
    first_count = db.seed_from_catalog_json()
    assert first_count == 2
    assert db_path.exists(), "DB should exist after first seed"

    # Now update catalog with a third product and call seed again — should be skipped
    extended = SAMPLE_CATALOG + [
        {
            "slug": "extra-item",
            "name": "Extra Item",
            "category": "Jewelry",
            "price": "$10",
            "short": "short",
            "long": "long",
            "materials": "mat",
            "care": "care",
            "tint": "lime",
            "photo": None,
            "sold": False,
        }
    ]
    catalog_path.write_text(json.dumps(extended), encoding="utf-8")

    second_count = db.seed_from_catalog_json()
    assert second_count == 0, "Should skip seeding when DB already exists"

    conn = sqlite3.connect(str(db_path))
    row_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    conn.close()
    assert row_count == 2, "DB should still have only 2 rows (not re-seeded)"
