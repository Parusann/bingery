"""One-off generator for the PWA app icons.

Run from the repo root:  python scripts/gen_pwa_icons.py
Writes icon-192.png, icon-512.png, icon-maskable-512.png into frontend/public.
Not part of the app or the build — just regenerates the static icons.
"""
import os

from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join("frontend", "public")
BG = (8, 5, 16, 255)        # #080510 — app theme background
FG = (230, 166, 128, 255)   # #e6a680 — amber accent


def _font(px: int):
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, px)
        except Exception:
            continue
    return ImageFont.load_default()


def make(size: int, name: str, scale: float = 0.62) -> None:
    img = Image.new("RGBA", (size, size), BG)
    d = ImageDraw.Draw(img)
    font = _font(int(size * scale))
    t = "B"
    box = d.textbbox((0, 0), t, font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    d.text(((size - w) / 2 - box[0], (size - h) / 2 - box[1]), t, fill=FG, font=font)
    img.save(os.path.join(OUT, name))
    print("wrote", os.path.join(OUT, name))


if __name__ == "__main__":
    make(192, "icon-192.png")
    make(512, "icon-512.png")
    # Maskable: keep the glyph well inside the safe zone (smaller scale).
    make(512, "icon-maskable-512.png", scale=0.42)
