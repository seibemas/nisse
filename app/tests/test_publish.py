"""Unit tests for app.publish — mock all external calls, never touch real git/FS."""
import importlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest

import app.config as config
import app.db as db_module
import app.publish as publish_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(tmp_path: Path) -> Path:
    """Create and return a fresh SQLite DB at tmp_path/mysma.db."""
    db_path = tmp_path / "mysma.db"
    with mock.patch.object(config, "DB_PATH", db_path):
        importlib.reload(db_module)
        db_module.init_db()
    return db_path


def _insert_product(conn: sqlite3.Connection, slug: str, sold: int = 0, photo: str | None = None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO products
            (slug, name, category, price, short, long, materials, care,
             tint, photo, sold, sort_order, created_at, updated_at)
        VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """,
        (
            slug, f"Product {slug}", "Jewelry", "$10",
            "Short desc.", "Long desc.", "Materials.", "Care.",
            "teal", photo, sold, now, now,
        ),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# test_export_catalog
# ---------------------------------------------------------------------------

def test_export_catalog(tmp_path):
    """Insert 2 products, export, verify JSON structure and sold as bool."""
    db_path = tmp_path / "mysma.db"
    catalog_json = tmp_path / "catalog.json"

    with mock.patch.object(config, "DB_PATH", db_path), \
         mock.patch.object(config, "CATALOG_JSON", catalog_json), \
         mock.patch.object(config, "TMP_DIR", tmp_path):
        importlib.reload(db_module)
        db_module.init_db()

        conn = db_module.get_conn()
        _insert_product(conn, "ring-alpha", sold=0, photo=None)
        _insert_product(conn, "ring-beta", sold=1, photo="assets/products/ring-beta.jpg")
        conn.close()

        importlib.reload(publish_module)
        count = publish_module.export_catalog()

    assert count == 2
    assert catalog_json.exists()

    data = json.loads(catalog_json.read_text(encoding="utf-8"))
    assert len(data) == 2

    slugs = {p["slug"] for p in data}
    assert slugs == {"ring-alpha", "ring-beta"}

    alpha = next(p for p in data if p["slug"] == "ring-alpha")
    assert alpha["sold"] is False       # integer 0 → Python bool False → JSON false
    assert alpha["photo"] is None

    beta = next(p for p in data if p["slug"] == "ring-beta")
    assert beta["sold"] is True         # integer 1 → Python bool True → JSON true
    assert beta["photo"] == "assets/products/ring-beta.jpg"

    # Ensure JSON encodes booleans correctly (not 0/1)
    raw = catalog_json.read_text(encoding="utf-8")
    assert '"sold": false' in raw
    assert '"sold": true' in raw


# ---------------------------------------------------------------------------
# test_export_catalog_empty
# ---------------------------------------------------------------------------

def test_export_catalog_empty(tmp_path):
    """Empty DB produces [] JSON."""
    db_path = tmp_path / "mysma.db"
    catalog_json = tmp_path / "catalog.json"

    with mock.patch.object(config, "DB_PATH", db_path), \
         mock.patch.object(config, "CATALOG_JSON", catalog_json), \
         mock.patch.object(config, "TMP_DIR", tmp_path):
        importlib.reload(db_module)
        db_module.init_db()

        importlib.reload(publish_module)
        count = publish_module.export_catalog()

    assert count == 0
    assert catalog_json.exists()
    data = json.loads(catalog_json.read_text(encoding="utf-8"))
    assert data == []


# ---------------------------------------------------------------------------
# test_copy_images_no_dir
# ---------------------------------------------------------------------------

def test_copy_images_no_dir(tmp_path):
    """If IMAGES_DIR doesn't exist, copy_images() returns 0 with no error."""
    nonexistent = tmp_path / "does_not_exist"
    dest = tmp_path / "site_assets"

    with mock.patch.object(config, "IMAGES_DIR", nonexistent), \
         mock.patch.object(config, "SITE_ASSETS_PRODUCTS", dest):
        importlib.reload(publish_module)
        count = publish_module.copy_images()

    assert count == 0
    # dest should NOT have been created
    assert not dest.exists()


# ---------------------------------------------------------------------------
# test_copy_images
# ---------------------------------------------------------------------------

def test_copy_images(tmp_path):
    """Files in IMAGES_DIR are copied to SITE_ASSETS_PRODUCTS."""
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    (images_dir / "product-a.jpg").write_bytes(b"JPEG_A")
    (images_dir / "product-b.jpg").write_bytes(b"JPEG_B")

    dest_dir = tmp_path / "site" / "assets" / "products"

    with mock.patch.object(config, "IMAGES_DIR", images_dir), \
         mock.patch.object(config, "SITE_ASSETS_PRODUCTS", dest_dir):
        importlib.reload(publish_module)
        count = publish_module.copy_images()

    assert count == 2
    assert (dest_dir / "product-a.jpg").exists()
    assert (dest_dir / "product-b.jpg").read_bytes() == b"JPEG_B"


# ---------------------------------------------------------------------------
# test_log_publish
# ---------------------------------------------------------------------------

def test_log_publish(tmp_path):
    """log_publish(6) inserts a row with product_count=6 into publish_log."""
    db_path = tmp_path / "mysma.db"

    with mock.patch.object(config, "DB_PATH", db_path):
        importlib.reload(db_module)
        db_module.init_db()

        importlib.reload(publish_module)
        publish_module.log_publish(6)

        conn = db_module.get_conn()
        rows = conn.execute("SELECT * FROM publish_log").fetchall()
        conn.close()

    assert len(rows) == 1
    assert rows[0]["product_count"] == 6
    assert rows[0]["published_at"]  # non-empty ISO timestamp


# ---------------------------------------------------------------------------
# test_publish_integration
# ---------------------------------------------------------------------------

def test_publish_integration(tmp_path):
    """Full publish() run with run_build and git_commit_and_push patched out."""
    db_path = tmp_path / "mysma.db"
    catalog_json = tmp_path / "catalog.json"
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    (images_dir / "product-a.jpg").write_bytes(b"JPEG_A")
    dest_dir = tmp_path / "site" / "assets" / "products"

    # Patch all external side-effects and paths
    fake_build_result = MagicMock()
    fake_build_result.stdout = "Build OK"

    with mock.patch.object(config, "DB_PATH", db_path), \
         mock.patch.object(config, "CATALOG_JSON", catalog_json), \
         mock.patch.object(config, "TMP_DIR", tmp_path), \
         mock.patch.object(config, "IMAGES_DIR", images_dir), \
         mock.patch.object(config, "SITE_ASSETS_PRODUCTS", dest_dir):

        importlib.reload(db_module)
        db_module.init_db()

        # Insert one product
        conn = db_module.get_conn()
        _insert_product(conn, "test-ring", sold=0)
        conn.close()

        importlib.reload(publish_module)

        with patch.object(publish_module, "run_build", return_value=fake_build_result) as mock_build, \
             patch.object(publish_module, "git_commit_and_push") as mock_git:

            result = publish_module.publish()

    # Verify return dict has correct keys
    assert "product_count" in result
    assert "published_at" in result
    assert "build_output" in result
    assert result["product_count"] == 1
    assert result["build_output"] == "Build OK"

    # catalog.json was written
    assert catalog_json.exists()
    data = json.loads(catalog_json.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["slug"] == "test-ring"

    # image was copied
    assert (dest_dir / "product-a.jpg").exists()

    # publish_log was updated
    conn2 = sqlite3.connect(str(db_path))
    conn2.row_factory = sqlite3.Row
    rows = conn2.execute("SELECT * FROM publish_log").fetchall()
    conn2.close()
    assert len(rows) == 1
    assert rows[0]["product_count"] == 1

    # External calls were made
    mock_build.assert_called_once()
    mock_git.assert_called_once_with(1)
