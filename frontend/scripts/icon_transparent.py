"""Убирает белую подложку у PNG-иконки (RGBA) для Windows .ico."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


def remove_white_matte(image: Image.Image, *, threshold: int = 245) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if r >= threshold and g >= threshold and b >= threshold:
                pixels[x, y] = (r, g, b, 0)
    return rgba


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: icon_transparent.py <src.png> <dest.png>", file=sys.stderr)
        return 2

    src = Path(sys.argv[1])
    dest = Path(sys.argv[2])
    if not src.is_file():
        print(f"missing source: {src}", file=sys.stderr)
        return 1

    out = remove_white_matte(Image.open(src))
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.save(dest, format="PNG")
    corner = out.getpixel((0, 0))
    print(f"saved {dest} corner_alpha={corner[3]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
