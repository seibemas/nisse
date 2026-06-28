"""Tests for the FastAPI CRUD API — always use tmp_path, never touch real DB."""
import importlib
import io
from unittest import mock

import pytest
from PIL import Image

import app.config as config


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path):
    db = tmp_path / "test.db"
    with mock.patch.object(config, "DB_PATH", db), \
         mock.patch.object(config, "IMAGES_DIR", tmp_path / "images"):
        import app.db as db_module
        importlib.reload(db_module)
        import app.main as main_module
        importlib.reload(main_module)
        from app.main import app as fastapi_app
        from fastapi.testclient import TestClient
        with TestClient(fastapi_app) as c:
            yield c


# ---------------------------------------------------------------------------
# Helper: minimal valid product payload
# ---------------------------------------------------------------------------

def _product_payload(**overrides):
    base = {
        "name": "Test Ring",
        "category": "Jewelry",
        "price": "$42",
        "short": "A short description.",
        "long": "A longer description of the product.",
        "materials": "Sterling silver",
        "care": "Keep dry.",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_list_products_empty(client):
    resp = client.get("/api/products")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_product(client):
    payload = _product_payload()
    resp = client.post("/api/products", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    # Slug auto-derived from name
    assert data["slug"] == "test-ring"
    # Tint auto-assigned (first product → TINTS[0] = "teal")
    assert data["tint"] == "teal"
    assert data["name"] == "Test Ring"
    assert data["category"] == "Jewelry"
    assert data["price"] == "$42"
    assert data["sold"] is False
    assert data["sort_order"] == 0
    assert "created_at" in data
    assert "updated_at" in data


def test_create_duplicate_slug(client):
    payload = _product_payload(name="Test Ring")
    resp1 = client.post("/api/products", json=payload)
    assert resp1.status_code == 201
    assert resp1.json()["slug"] == "test-ring"

    resp2 = client.post("/api/products", json=payload)
    assert resp2.status_code == 201
    assert resp2.json()["slug"] == "test-ring-2"


def test_get_product(client):
    create_resp = client.post("/api/products", json=_product_payload())
    assert create_resp.status_code == 201
    slug = create_resp.json()["slug"]

    resp = client.get(f"/api/products/{slug}")
    assert resp.status_code == 200
    assert resp.json()["slug"] == slug
    assert resp.json()["name"] == "Test Ring"


def test_get_product_not_found(client):
    resp = client.get("/api/products/does-not-exist")
    assert resp.status_code == 404


def test_update_product(client):
    create_resp = client.post("/api/products", json=_product_payload())
    assert create_resp.status_code == 201
    slug = create_resp.json()["slug"]

    # Partial update — only name and sold
    resp = client.put(f"/api/products/{slug}", json={"name": "Updated Ring", "sold": True})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Ring"
    assert data["sold"] is True
    # Slug must stay unchanged even though name changed
    assert data["slug"] == slug
    # Untouched fields should be unchanged
    assert data["price"] == "$42"
    assert data["category"] == "Jewelry"


def test_delete_product(client):
    create_resp = client.post("/api/products", json=_product_payload())
    assert create_resp.status_code == 201
    slug = create_resp.json()["slug"]

    del_resp = client.delete(f"/api/products/{slug}")
    assert del_resp.status_code == 200
    assert del_resp.json() == {"deleted": slug}

    # Subsequent GET should 404
    get_resp = client.get(f"/api/products/{slug}")
    assert get_resp.status_code == 404


def test_status_unpublished_count(client):
    # Initially no products
    status = client.get("/api/status").json()
    assert status["total_products"] == 0
    assert status["unpublished_count"] == 0
    assert status["last_published_at"] is None

    # Create one product
    client.post("/api/products", json=_product_payload())

    status = client.get("/api/status").json()
    assert status["total_products"] == 1
    # No publish_log entries → unpublished_count == total
    assert status["unpublished_count"] == 1
    assert status["last_published_at"] is None


def test_upload_photo(client):
    """Upload a photo for an existing product and verify the photo field is updated."""
    # Create a product first
    create_resp = client.post("/api/products", json=_product_payload())
    assert create_resp.status_code == 201
    slug = create_resp.json()["slug"]

    # Create a tiny in-memory JPEG
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), color=(255, 0, 0)).save(buf, format="JPEG")
    buf.seek(0)

    resp = client.post(
        f"/api/products/{slug}/photo",
        files={"file": ("test.jpg", buf, "image/jpeg")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["photo"] == f"assets/products/{slug}.jpg"


def test_upload_photo_not_found(client):
    """Uploading a photo for a nonexistent product should return 404."""
    buf = io.BytesIO()
    Image.new("RGB", (50, 50), color=(0, 255, 0)).save(buf, format="JPEG")
    buf.seek(0)

    resp = client.post(
        "/api/products/does-not-exist/photo",
        files={"file": ("test.jpg", buf, "image/jpeg")},
    )
    assert resp.status_code == 404
