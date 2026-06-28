"""
create_icons.py — Generate PWA icons for Nisse.

Creates:
  app/static/icons/icon-192.png
  app/static/icons/icon-512.png

Each icon: magenta (#A82E97) rounded-rect background, white "M" centered.
Run from the project root:  python app/create_icons.py
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import sys

ICON_DIR = Path(__file__).parent / "static" / "icons"
ICON_DIR.mkdir(parents=True, exist_ok=True)

MAGENTA = (168, 46, 151, 255)
WHITE   = (255, 255, 255, 255)


def draw_m(draw: ImageDraw.ImageDraw, size: int, color):
    """Draw a simple bold 'M' using polygon points — no font dependency."""
    s = size
    # Scale unit: 1/10 of size
    u = s / 10

    # Stroke width proportional to size
    sw = max(int(u * 1.1), 4)

    # M shape: five key x positions (left edge, left inner, center, right inner, right edge)
    # and three y positions (top, bottom, midpoint-of-diagonals)
    x0 = int(u * 2.0)      # far left
    x1 = int(u * 3.1)      # left inner top
    xm = int(s / 2)        # center
    x2 = int(u * 6.9)      # right inner top
    x3 = int(u * 8.0)      # far right

    y0 = int(u * 2.0)      # top
    ym = int(u * 5.5)      # valley (middle)
    y1 = int(u * 8.0)      # bottom

    pts = [
        (x0, y0),   # top-left
        (x1, y0),   # top-left inner (stem top)
        (xm, ym),   # center valley
        (x2, y0),   # top-right inner (stem top)
        (x3, y0),   # top-right
        (x3, y1),   # bottom-right outer
        (x2, y1),   # bottom-right inner
        (x2, int(u * 4.3)),   # right diagonal lower
        (xm, int(u * 6.8)),   # center lower
        (x1, int(u * 4.3)),   # left diagonal lower
        (x1, y1),   # bottom-left inner
        (x0, y1),   # bottom-left outer
    ]
    draw.polygon(pts, fill=color)


def make_icon(size: int, path: Path):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded rectangle background
    radius = size // 5
    draw.rounded_rectangle([(0, 0), (size - 1, size - 1)], radius=radius, fill=MAGENTA)

    # Draw "M"
    draw_m(draw, size, WHITE)

    # Convert to RGB for PNG compatibility with PWA
    bg = Image.new("RGB", (size, size), (168, 46, 151))
    bg.paste(img, mask=img.split()[3])
    bg.save(str(path), "PNG", optimize=True)
    print(f"  Created {path} ({size}x{size})")


def main():
    print("Generating Nisse PWA icons...")
    make_icon(192, ICON_DIR / "icon-192.png")
    make_icon(512, ICON_DIR / "icon-512.png")
    print("Done.")


if __name__ == "__main__":
    main()
