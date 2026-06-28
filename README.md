# Nisse

A mobile-first PWA for managing a small-business product catalog. Built to run on a home server or low-cost VPS, installable to your phone via Safari/Chrome "Add to Home Screen."

## What it does

- **Product list** — swipe a card left to mark sold, tap to edit
- **Editor** — name, price, category, description, materials, care notes, photo upload
- **Live preview** — see the public-facing product card as you edit
- **Publish pipeline** — one tap exports your catalog and triggers a site rebuild

## Quick start

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in a browser, or on your phone via your server's local IP.

## Architecture

```
app/
  main.py       FastAPI app — all routes, static file mount, startup hooks
  models.py     Pydantic schemas for request/response validation
  db.py         SQLite access layer (stdlib sqlite3, no ORM)
  images.py     Pillow resize/compress on photo upload
  publish.py    Export → site build → git push pipeline (adapt to your workflow)
  config.py     Paths and constants
  data/         SQLite database + processed images (gitignored)
  static/       PWA frontend (index.html, CSS, JS, manifest, service worker)
  tests/        Pytest suite
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
| POST | `/api/publish` | Run the publish pipeline |

## Publish pipeline

`POST /api/publish` is a hook for your own build/deploy workflow. Out of the box it:

1. Exports SQLite → `.tmp/catalog.json`
2. Copies processed images to your site's asset folder
3. Runs your site builder
4. Commits and pushes to trigger a deploy (e.g. Netlify, Vercel, Cloudflare Pages)

Edit `app/publish.py` to wire in your own stack.

## Remote access

Run with `--host 0.0.0.0` and use [Tailscale](https://tailscale.com) to access from your phone anywhere without opening firewall ports.

## Running tests

```bash
python -m pytest app/tests/ -v
```
