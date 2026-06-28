"""Publish pipeline: export catalog → build site → git commit + push."""
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import app.config as config
from app.db import get_conn


def export_catalog() -> int:
    """Export all products from SQLite to .tmp/catalog.json.
    Returns product count."""
    config.TMP_DIR.mkdir(parents=True, exist_ok=True)

    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM products ORDER BY sort_order ASC, name ASC"
        ).fetchall()
    finally:
        conn.close()

    products = []
    for row in rows:
        products.append({
            "slug": row["slug"],
            "name": row["name"],
            "category": row["category"],
            "price": row["price"],
            "short": row["short"],
            "long": row["long"],
            "materials": row["materials"],
            "care": row["care"],
            "tint": row["tint"],
            "photo": row["photo"],
            "sold": bool(row["sold"]),
        })

    config.CATALOG_JSON.write_text(
        json.dumps(products, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return len(products)


def copy_images() -> int:
    """Copy all images from app/data/images/ to site/assets/products/.
    Returns count of files copied."""
    if not config.IMAGES_DIR.exists():
        return 0

    config.SITE_ASSETS_PRODUCTS.mkdir(parents=True, exist_ok=True)

    count = 0
    for src in config.IMAGES_DIR.iterdir():
        if src.is_file():
            shutil.copy2(src, config.SITE_ASSETS_PRODUCTS / src.name)
            count += 1

    return count


def run_build() -> subprocess.CompletedProcess:
    """Run tools/build_site.py as a subprocess. Raises RuntimeError if it fails."""
    result = subprocess.run(
        ["python", "tools/build_site.py"],
        cwd=str(config.ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return result


def git_commit_and_push(product_count: int) -> None:
    """Stage site/ and .tmp/catalog.json, commit, push."""
    subprocess.run(
        ["git", "add", "site/", ".tmp/catalog.json"],
        cwd=str(config.ROOT),
        check=True,
    )

    commit_result = subprocess.run(
        ["git", "commit", "-m", f"catalog: publish via app [{product_count} products]"],
        cwd=str(config.ROOT),
        capture_output=True,
        text=True,
    )
    # Exit code 1 with "nothing to commit" is treated as success
    if commit_result.returncode != 0:
        if "nothing to commit" not in commit_result.stdout and "nothing to commit" not in commit_result.stderr:
            raise subprocess.CalledProcessError(
                commit_result.returncode,
                commit_result.args,
                commit_result.stdout,
                commit_result.stderr,
            )

    subprocess.run(
        ["git", "push"],
        cwd=str(config.ROOT),
        check=True,
    )


def log_publish(product_count: int) -> None:
    """Record this publish in publish_log with current UTC time and product_count."""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO publish_log (published_at, product_count) VALUES (?, ?)",
            (now, product_count),
        )
        conn.commit()
    finally:
        conn.close()


def publish() -> dict:
    """Run the full publish pipeline. Returns a status dict."""
    product_count = export_catalog()
    copy_images()
    build_result = run_build()
    git_commit_and_push(product_count)
    log_publish(product_count)

    published_at = datetime.now(timezone.utc).isoformat()
    return {
        "product_count": product_count,
        "published_at": published_at,
        "build_output": build_result.stdout,
    }


def _sse(msg: str, step: str, done: bool) -> str:
    return f"data: {json.dumps({'msg': msg, 'step': step, 'done': done})}\n\n"


def publish_stream():
    """Generator that yields SSE events for each publish step."""
    yield _sse("Exporting catalog…", "export", False)
    count = export_catalog()
    yield _sse(f"Exported {count} products", "export", True)

    yield _sse("Copying images…", "images", False)
    img_count = copy_images()
    yield _sse(f"Copied {img_count} images", "images", True)

    yield _sse("Building site…", "build", False)
    run_build()
    yield _sse("Site built", "build", True)

    yield _sse("Pushing to git…", "git", False)
    git_commit_and_push(count)
    yield _sse("Pushed", "git", True)

    log_publish(count)
    yield _sse("Published! Netlify deploying (~2 min)", "done", True)
