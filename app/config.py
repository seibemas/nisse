from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # repo root
APP_DIR = ROOT / "app"
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "mysma.db"
IMAGES_DIR = DATA_DIR / "images"
TMP_DIR = ROOT / ".tmp"
SITE_ASSETS_PRODUCTS = ROOT / "site" / "assets" / "products"
CATALOG_JSON = TMP_DIR / "catalog.json"
TINTS = ["teal", "indigo", "lime", "magenta"]  # cycles for photoless cards
CATEGORIES = ["Jewelry", "Clothing", "Botanical wellness"]
