import logging
import re
import sqlite3
import subprocess
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

import app.config as config
from app.db import get_conn, init_db, seed_from_catalog_json
from app.images import delete_image, process_and_save
from app.models import (
    TINTS,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    StatusResponse,
)
from app.publish import publish as run_publish, publish_stream

logger = logging.getLogger(__name__)

app = FastAPI(title="Mysma Catalog API")


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
def on_startup():
    init_db()
    count = seed_from_catalog_json()
    if count > 0:
        logger.info("Seeded %d products from catalog.json", count)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^\w\s-]", "", s).strip().lower()
    return re.sub(r"[\s_-]+", "-", s)


def _row_to_response(row: sqlite3.Row) -> ProductResponse:
    return ProductResponse(
        slug=row["slug"],
        name=row["name"],
        category=row["category"],
        price=row["price"],
        short=row["short"],
        long=row["long"],
        materials=row["materials"],
        care=row["care"],
        tint=row["tint"],
        photo=row["photo"],
        sold=bool(row["sold"]),
        sort_order=row["sort_order"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# ---------------------------------------------------------------------------
# DB dependency
# ---------------------------------------------------------------------------

def get_db():
    conn = get_conn()
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/products", response_model=list[ProductResponse])
def list_products(conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute(
        "SELECT * FROM products ORDER BY sort_order ASC, name ASC"
    ).fetchall()
    return [_row_to_response(r) for r in rows]


@app.post("/api/products", response_model=ProductResponse, status_code=201)
def create_product(body: ProductCreate, conn: sqlite3.Connection = Depends(get_db)):
    # Derive slug
    base_slug = slugify(body.name)
    slug = base_slug
    existing = conn.execute(
        "SELECT slug FROM products WHERE slug = ?", (slug,)
    ).fetchone()
    if existing:
        counter = 2
        while True:
            candidate = f"{base_slug}-{counter}"
            row = conn.execute(
                "SELECT slug FROM products WHERE slug = ?", (candidate,)
            ).fetchone()
            if row is None:
                slug = candidate
                break
            counter += 1

    # Auto-assign tint if not provided
    tint = body.tint
    if tint is None:
        total = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        tint = TINTS[total % 4]

    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """
        INSERT INTO products
            (slug, name, category, price, short, long, materials, care,
             tint, photo, sold, sort_order, created_at, updated_at)
        VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 0, ?, ?, ?)
        """,
        (
            slug, body.name, body.category, body.price,
            body.short, body.long, body.materials, body.care,
            tint, body.sort_order, now, now,
        ),
    )
    conn.commit()

    row = conn.execute("SELECT * FROM products WHERE slug = ?", (slug,)).fetchone()
    return _row_to_response(row)


@app.get("/api/products/{slug}", response_model=ProductResponse)
def get_product(slug: str, conn: sqlite3.Connection = Depends(get_db)):
    row = conn.execute("SELECT * FROM products WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Product '{slug}' not found")
    return _row_to_response(row)


@app.put("/api/products/{slug}", response_model=ProductResponse)
def update_product(
    slug: str, body: ProductUpdate, conn: sqlite3.Connection = Depends(get_db)
):
    row = conn.execute("SELECT * FROM products WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Product '{slug}' not found")

    # Build SET clause only for provided fields
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return _row_to_response(row)

    # Convert bool sold → int
    if "sold" in updates:
        updates["sold"] = 1 if updates["sold"] else 0

    now = datetime.now(timezone.utc).isoformat()
    updates["updated_at"] = now

    set_clause = ", ".join(f"{col} = ?" for col in updates)
    values = list(updates.values()) + [slug]

    conn.execute(
        f"UPDATE products SET {set_clause} WHERE slug = ?", values
    )
    conn.commit()

    updated = conn.execute("SELECT * FROM products WHERE slug = ?", (slug,)).fetchone()
    return _row_to_response(updated)


@app.delete("/api/products/{slug}")
def delete_product(slug: str, conn: sqlite3.Connection = Depends(get_db)):
    row = conn.execute("SELECT slug FROM products WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Product '{slug}' not found")
    conn.execute("DELETE FROM products WHERE slug = ?", (slug,))
    conn.commit()
    return {"deleted": slug}


@app.get("/api/status", response_model=StatusResponse)
def get_status(conn: sqlite3.Connection = Depends(get_db)):
    total = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]

    last_publish = conn.execute(
        "SELECT published_at FROM publish_log ORDER BY id DESC LIMIT 1"
    ).fetchone()

    if last_publish is None:
        unpublished_count = total
        last_published_at = None
    else:
        last_published_at = last_publish["published_at"]
        unpublished_count = conn.execute(
            "SELECT COUNT(*) FROM products WHERE updated_at > ?",
            (last_published_at,),
        ).fetchone()[0]

    return StatusResponse(
        unpublished_count=unpublished_count,
        last_published_at=last_published_at,
        total_products=total,
    )


@app.post("/api/products/{slug}/photo", response_model=ProductResponse)
async def upload_photo(
    slug: str,
    file: UploadFile = File(...),
    conn: sqlite3.Connection = Depends(get_db),
):
    """Accept a photo upload, process it with Pillow, store it, update the product record."""
    row = conn.execute("SELECT * FROM products WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Product '{slug}' not found")

    # Read bytes and process
    image_bytes = await file.read()
    config.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    dest = config.IMAGES_DIR / f"{slug}.jpg"
    process_and_save(image_bytes, dest)

    # Update product photo field (site-relative path matching build_site.py)
    photo_path = f"assets/products/{slug}.jpg"
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE products SET photo = ?, updated_at = ? WHERE slug = ?",
        (photo_path, now, slug),
    )
    conn.commit()

    updated = conn.execute("SELECT * FROM products WHERE slug = ?", (slug,)).fetchone()
    return _row_to_response(updated)


@app.post("/api/publish")
def publish_site():
    """Export catalog, rebuild site, git commit+push."""
    try:
        result = run_publish()
        return result
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Build failed: {e.stderr}")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Publish failed: {e}")


@app.post("/api/publish/stream")
def publish_site_stream():
    """Stream publish progress as SSE events."""
    return StreamingResponse(publish_stream(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Static files (must be mounted last — API routes take priority)
# ---------------------------------------------------------------------------

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
