"""Tests for app/images.py — no real image files needed, all images created in memory."""
import io

import pytest
from PIL import Image

from app.images import MAX_DIMENSION, delete_image, process_and_save


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_image_bytes(width: int, height: int, mode: str = "RGB", fmt: str = "JPEG") -> bytes:
    """Create an in-memory image and return its raw bytes."""
    img = Image.new(mode, (width, height), color=(128, 64, 32) if mode == "RGB" else (128, 64, 32, 255) if mode == "RGBA" else 128)
    buf = io.BytesIO()
    # PNG supports RGBA; JPEG does not
    save_fmt = "PNG" if mode in ("RGBA", "P", "L") else fmt
    img.save(buf, format=save_fmt)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_process_jpeg(tmp_path):
    """A 2000×1500 JPEG should be resized so longest side <= 1600."""
    image_bytes = _make_image_bytes(2000, 1500, mode="RGB", fmt="JPEG")
    dest = tmp_path / "output.jpg"

    result = process_and_save(image_bytes, dest)

    assert result == dest
    assert dest.exists()

    with Image.open(dest) as img:
        assert img.format == "JPEG"
        w, h = img.size
        assert max(w, h) <= MAX_DIMENSION


def test_process_png_rgba(tmp_path):
    """An RGBA PNG should be converted to RGB JPEG without error."""
    image_bytes = _make_image_bytes(100, 100, mode="RGBA")
    dest = tmp_path / "rgba_output.jpg"

    process_and_save(image_bytes, dest)

    assert dest.exists()
    with Image.open(dest) as img:
        assert img.format == "JPEG"
        assert img.mode == "RGB"


def test_no_upscale(tmp_path):
    """A 400×300 image should not be enlarged — dimensions stay the same."""
    image_bytes = _make_image_bytes(400, 300, mode="RGB", fmt="JPEG")
    dest = tmp_path / "small_output.jpg"

    process_and_save(image_bytes, dest)

    assert dest.exists()
    with Image.open(dest) as img:
        assert img.size == (400, 300)


def test_delete_image(tmp_path):
    """delete_image should remove the file and return True."""
    slug = "my-product"
    img_file = tmp_path / f"{slug}.jpg"
    img_file.write_bytes(b"fake jpeg data")

    result = delete_image(slug, tmp_path)

    assert result is True
    assert not img_file.exists()


def test_delete_image_missing(tmp_path):
    """delete_image on a nonexistent slug should return False without raising."""
    result = delete_image("does-not-exist", tmp_path)
    assert result is False
