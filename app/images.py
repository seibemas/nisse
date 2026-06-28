"""Image upload processing: resize, compress, save as JPEG."""
from pathlib import Path
from PIL import Image
import io

MAX_DIMENSION = 1600   # max px on longest side
JPEG_QUALITY = 85


def process_and_save(image_bytes: bytes, dest_path: Path) -> Path:
    """
    Resize image so longest side <= MAX_DIMENSION (aspect-preserved),
    convert to RGB (handles RGBA/PNG transparency), save as JPEG at JPEG_QUALITY.
    Returns dest_path.
    """
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.open(io.BytesIO(image_bytes))

    # Resize only if the image exceeds MAX_DIMENSION — never upscale
    w, h = img.size
    if w > MAX_DIMENSION or h > MAX_DIMENSION:
        img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)

    # Convert to RGB (handles RGBA, P, L, CMYK, etc.)
    if img.mode != "RGB":
        img = img.convert("RGB")

    img.save(dest_path, format="JPEG", quality=JPEG_QUALITY)
    return dest_path


def delete_image(slug: str, images_dir: Path) -> bool:
    """Delete the stored image for a slug if it exists. Returns True if deleted."""
    path = Path(images_dir) / f"{slug}.jpg"
    if path.exists():
        path.unlink()
        return True
    return False
