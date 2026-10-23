"""Achievement icons for Steam: a 256x256 earned icon and a locked one for
each achievement, plus a contact sheet to check them at a glance.

    python tools/make_ach_icons.py steam/achievements.json
    python tools/make_ach_icons.py steam/achievements.json --art keyart.png

steam/achievements.json is a list of
    {"id": "ACH_WIN_ONE_GAME", "name": "Winner", "glyph": "1", "color": "#ffcc4d"}
`id` must be the API name you set in Steamworks > Stats & Achievements, and
the same string the game passes to Steam::unlock. `glyph` is 1 to 4
characters drawn on the badge; `image` (optional) is a picture to use as the
badge instead, cropped square.

--art: one source image used as the background of every badge (darkened
and cropped), so the set looks like your game. Without it badges are flat.

Steam's sizes: 256x256, JPG or PNG, one "achieved" and one "unachieved" per
achievement (Steamworks shows the unachieved one until it unlocks), so
upload both. Adapted from the script that drew O'BLOCK's badges (there it
draws at 32px and scales up with no smoothing, for crisp pixel art).
"""
import argparse
import json
import os

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

S = 256


def font(px):
    for name in ["DejaVuSans-Bold.ttf", "consolab.ttf", "arialbd.ttf", "Arial Bold.ttf"]:
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    return ImageFont.load_default(px)


def rgb(hexstr):
    h = hexstr.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def square(img):
    return ImageOps.fit(img.convert("RGB"), (S, S), Image.LANCZOS)


def badge(a, art, base_dir):
    col = rgb(a.get("color", "#ffcc4d"))
    if a.get("image"):
        return square(Image.open(os.path.join(base_dir, a["image"])))
    if art is not None:
        img = ImageEnhance.Brightness(square(art)).enhance(0.35)
    else:
        img = Image.new("RGB", (S, S), (10, 10, 14))
    d = ImageDraw.Draw(img)
    d.rectangle([4, 4, S - 5, S - 5], outline=col, width=8)
    d.rectangle([20, 20, S - 21, S - 21], outline=tuple(int(c * 0.45) for c in col), width=4)
    text = a.get("glyph") or a["name"][:2].upper()
    size = {1: 150, 2: 110, 3: 80}.get(len(text), 60)
    f = font(size)
    l, t, r, b = d.textbbox((0, 0), text, font=f)
    x, y = (S - (r - l)) / 2 - l, (S - (b - t)) / 2 - t
    d.text((x + 6, y + 6), text, font=f, fill=(0, 0, 0))
    d.text((x, y), text, font=f, fill=(245, 245, 240))
    return img


def locked(img):
    """Grey and dark, so the unearned state reads at 64px in the overlay."""
    g = ImageOps.grayscale(img).convert("RGB")
    return ImageEnhance.Brightness(g).enhance(0.45)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("list")
    ap.add_argument("--art")
    ap.add_argument("--out", default=os.path.join("steam", "achievements", "out"))
    a = ap.parse_args()

    achs = json.load(open(a.list, encoding="utf-8"))
    art = Image.open(a.art) if a.art else None
    os.makedirs(a.out, exist_ok=True)
    base = os.path.dirname(os.path.abspath(a.list))
    for ach in achs:
        on = badge(ach, art, base)
        on.save(os.path.join(a.out, f"{ach['id']}.jpg"), quality=95)
        locked(on).save(os.path.join(a.out, f"{ach['id']}_locked.jpg"), quality=95)

    cols = min(10, max(1, len(achs)))
    rows = (len(achs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 72, rows * 144), (0, 0, 0))
    for i, ach in enumerate(achs):
        x, y = (i % cols) * 72 + 4, (i // cols) * 144 + 4
        sheet.paste(Image.open(os.path.join(a.out, f"{ach['id']}.jpg")).resize((64, 64)), (x, y))
        sheet.paste(Image.open(os.path.join(a.out, f"{ach['id']}_locked.jpg")).resize((64, 64)), (x, y + 68))
    sheet.save(os.path.join(a.out, "_sheet.png"))
    print(f"{len(achs)} achievements -> {a.out}")


if __name__ == "__main__":
    main()
