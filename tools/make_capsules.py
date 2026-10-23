"""Every Steam store and library image from one piece of key art.

    python tools/make_capsules.py keyart.png --title "MY GAME"
    python tools/make_capsules.py keyart.png --logo logo.png --out steam/store

keyart: your best wide image, ideally 3840x2160 or larger, no text on it.
--logo: a transparent PNG of your game's logo. Without one, --title is drawn
        in a plain bold font (fine for testing, replace it before review).
--focus X Y: where the interesting part of the art is (0..1), used when a
        capsule crops to a different shape. Default 0.5 0.5.

Adapted from the script that made O'BLOCK's store art (Steam app 5357680).
Steamworks rejects images of the wrong size outright, so the sizes below are
exact. Rules Valve enforces on review (Steamworks > Store graphics docs):
  * capsules show artwork and the product name only: no review quotes,
    awards, prices or "update" banners;
  * the name on the art must match the product name in Steamworks exactly
    (O'BLOCK's DLC failed review for "SUPPORTER PACK" vs the store name
    "Complete Supporter Pack");
  * the library hero has NO text or logo: Steam draws the library logo on top.
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# name: (width, height, kind)
# kind: "logo" = art + logo, "art" = art only, "logo_only" = transparent logo,
#       "icon" = square icon
SIZES = {
    # Store page
    "header_capsule": (920, 430, "logo"),
    "small_capsule": (462, 174, "logo"),
    "main_capsule": (1232, 706, "logo"),
    "vertical_capsule": (748, 896, "logo"),
    "page_background": (1438, 810, "art"),
    # Library
    "library_capsule": (600, 900, "logo"),
    "library_header": (920, 430, "logo"),
    "library_hero": (3840, 1240, "art"),
    "library_logo": (1280, 720, "logo_only"),
    # Community / client icons (Steamworks > App Admin > General / Client Images)
    "community_icon": (184, 184, "icon"),
    "client_icon": (32, 32, "icon"),
    # Events and announcements (cover required for a Major Update post)
    "event_cover": (800, 450, "logo"),
    "event_header": (1920, 622, "art"),
}


def font(px):
    for name in ["DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf", "consolab.ttf"]:
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    return ImageFont.load_default(px)


def text_logo(title):
    """A plain logo from text: white with a soft glow and a hard shadow."""
    f = font(200)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    l, t, r, b = probe.textbbox((0, 0), title, font=f)
    pad = 60
    img = Image.new("RGBA", (r - l + pad * 2, b - t + pad * 2), (0, 0, 0, 0))
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).text((pad - l, pad - t), title, font=f, fill=(255, 204, 77, 255))
    glow = glow.filter(ImageFilter.GaussianBlur(18))
    img = Image.alpha_composite(img, glow)
    d = ImageDraw.Draw(img)
    d.text((pad - l + 8, pad - t + 8), title, font=f, fill=(0, 0, 0, 255))
    d.text((pad - l, pad - t), title, font=f, fill=(246, 246, 240, 255))
    return img


def cover(img, w, h, focus):
    """Crop to the target aspect around the focus point, then scale."""
    iw, ih = img.size
    target = w / h
    if iw / ih > target:
        cw, ch = int(ih * target), ih
    else:
        cw, ch = iw, int(iw / target)
    x = int((iw - cw) * focus[0])
    y = int((ih - ch) * focus[1])
    return img.crop((x, y, x + cw, y + ch)).resize((w, h), Image.LANCZOS)


def shade(img, vertical):
    """A dark gradient behind where the logo goes, so it reads on any art."""
    w, h = img.size
    n = h if vertical else w
    ramp = Image.new("L", (1, n) if vertical else (n, 1))
    for i in range(n):
        f = i / max(1, n - 1)
        ramp.putpixel((0, i) if vertical else (i, 0), int(255 * (0.8 * (1 - f) + 0.1 * f)))
    black = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    black.putalpha(ramp.resize((w, h)))
    return Image.alpha_composite(img.convert("RGBA"), black)


def fit(item, max_w, max_h):
    s = min(max_w / item.width, max_h / item.height)
    return item.resize((max(1, int(item.width * s)), max(1, int(item.height * s))), Image.LANCZOS)


def make(name, w, h, kind, art, logo, focus):
    if kind == "logo_only":
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        lg = fit(logo, w * 0.9, h * 0.8)
        canvas.alpha_composite(lg, ((w - lg.width) // 2, (h - lg.height) // 2))
        return canvas
    if kind == "icon":
        return cover(art, w, h, focus).convert("RGBA")
    img = cover(art, w, h, focus).convert("RGBA")
    if kind == "art":
        return img
    tall = h > w
    img = shade(img, vertical=tall)
    if tall:
        lg = fit(logo, w * 0.88, h * 0.3)
        img.alpha_composite(lg, ((w - lg.width) // 2, int(h * 0.06)))
    else:
        small = w < 500
        lg = fit(logo, w * (0.9 if small else 0.55), h * (0.75 if small else 0.5))
        x = (w - lg.width) // 2 if small else int(w * 0.05)
        img.alpha_composite(lg, (x, (h - lg.height) // 2))
    return img


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("keyart")
    ap.add_argument("--logo")
    ap.add_argument("--title", default="MY GAME")
    ap.add_argument("--focus", nargs=2, type=float, default=[0.5, 0.5])
    ap.add_argument("--out", default=os.path.join("steam", "store"))
    a = ap.parse_args()

    art = Image.open(a.keyart).convert("RGB")
    if art.width < 3840 or art.height < 1240:
        print(f"note: key art is {art.width}x{art.height}; the library hero is 3840x1240, so it will be upscaled")
    logo = Image.open(a.logo).convert("RGBA") if a.logo else text_logo(a.title)
    os.makedirs(a.out, exist_ok=True)
    for name, (w, h, kind) in SIZES.items():
        img = make(name, w, h, kind, art, logo, a.focus)
        path = os.path.join(a.out, f"{name}_{w}x{h}.png")
        (img if kind == "logo_only" else img.convert("RGB")).save(path)
        print(f"{path}  {w}x{h}")
    # Windows wants an .ico for the shortcut / client icon.
    icon = make("icon", 256, 256, "icon", art, logo, a.focus)
    ico = os.path.join(a.out, "client_icon.ico")
    icon.save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)])
    print(ico)


if __name__ == "__main__":
    main()
