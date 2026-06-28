# Nisse — Catalog App

Mobile-first PWA for managing the Mysma Boutique product catalog. Runs on a home server, installable to phone/tablet via Tailscale.

## Quick Start

```powershell
# Install dependencies
py -m pip install -r requirements.txt

# Start the server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in a browser.  
For remote access from phone/tablet, see [Tailscale setup below](#tailscale).

## Architecture

```
app/
  main.py       FastAPI app — all routes, static mount, startup hooks
  models.py     Pydantic schemas for request/response validation
  db.py         SQLite access layer (stdlib sqlite3, no ORM)
  images.py     Pillow resize/compress on photo upload
  publish.py    Export → build_site.py → git commit + push pipeline
  config.py     Paths and constants (single source of truth)
  data/
    mysma.db    SQLite database (gitignored — created on first run)
    images/     Processed product photos (gitignored)
  static/       PWA frontend (index.html, CSS, JS, manifest, SW)
  tests/        Pytest test suite
```

## API

| Method | Path | Description |
|---|---|---|
| GET | `/api/products` | List all products |
| POST | `/api/products` | Create product |
| GET | `/api/products/{slug}` | Get one product |
| PUT | `/api/products/{slug}` | Update product (partial) |
| DELETE | `/api/products/{slug}` | Delete product |
| POST | `/api/products/{slug}/photo` | Upload + process photo |
| GET | `/api/status` | Unpublished count + last publish time |
| POST | `/api/publish` | Run full publish pipeline |

## Publish Pipeline

`POST /api/publish` runs in sequence:
1. Export SQLite → `.tmp/catalog.json` (same schema `build_site.py` expects)
2. Copy `app/data/images/*` → `site/assets/products/`
3. `python tools/build_site.py`
4. `git add site/ .tmp/catalog.json && git commit && git push`
5. Log publish time to `publish_log` table

Netlify picks up the push and deploys (~2 min).

## Tailscale

Tailscale creates a private mesh network between your server, phone, and tablet.

**Server setup:**
1. Download Tailscale: https://tailscale.com/download
2. `tailscale up` → sign in
3. Start the app with `--host 0.0.0.0` (already the default above)
4. Find your Tailscale IP: `tailscale ip`

**Device setup (phone/tablet):**
1. Install the Tailscale app → sign in with the same account
2. Open `http://<tailscale-ip>:8000` in Safari (iOS) or Chrome (Android)
3. Add to Home Screen for the app-like experience

## Running Tests

```powershell
python -m pytest app/tests/ -v
```

26 tests across DB, API, image processing, and publish pipeline.

## Data

- `app/data/mysma.db` — SQLite database (created on first run; gitignored)
- `app/data/images/` — processed photos (gitignored)
- On first run, if `.tmp/catalog.json` exists from the old sync, it is automatically imported

## Gitignore additions needed

Add to `.gitignore`:
```
app/data/
app/.pytest_cache/
```
