"""Génère les visuels de marque (logo incrusté, logo d'intro, photo de profil). À relancer si tu changes les couleurs."""
from PIL import Image, ImageDraw, ImageFont

import config as C

F = C.ASSETS / "fonts"
OUT = C.ASSETS / "brand"
RED = "#" + C.BRAND.get("colors", {}).get("red", "E10600")
BLK = "#" + C.BRAND.get("colors", {}).get("black", "0E0E0E")
YEL = "#" + C.BRAND.get("colors", {}).get("yellow", "FFD400")


def font(name, size):
    return ImageFont.truetype(str(F / name), size)


def text_box(draw, txt, fnt, spacing=0):
    if spacing:
        w = sum(draw.textbbox((0, 0), ch, font=fnt)[2] for ch in txt) + spacing * (len(txt) - 1)
        b = draw.textbbox((0, 0), txt, font=fnt)
        return w, b[3] - b[1], b[1]
    b = draw.textbbox((0, 0), txt, font=fnt)
    return b[2] - b[0], b[3] - b[1], b[1]


def draw_spaced(draw, xy, txt, fnt, fill, spacing):
    x, y = xy
    for ch in txt:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textbbox((0, 0), ch, font=fnt)[2] + spacing


def logo(scale=1.0, with_bar=True):
    """Bloc rouge « NPC » + bloc noir « SOCIETY », façon logo de chaîne d'info."""
    f1, f2 = font("ArchivoBlack-Regular.ttf", int(64 * scale)), font("BarlowCondensed-Bold.ttf", int(54 * scale))
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    w1, h1, o1 = text_box(tmp, "NPC", f1)
    sp = int(6 * scale)
    w2, h2, o2 = text_box(tmp, "SOCIETY", f2, sp)
    px, py = int(18 * scale), int(14 * scale)
    H = h1 + 2 * py
    bar = int(7 * scale) if with_bar else 0
    W = w1 + 2 * px + w2 + 2 * px
    img = Image.new("RGBA", (W, H + bar), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w1 + 2 * px, H], fill=RED)
    d.text((px, py - o1), "NPC", font=f1, fill="white")
    d.rectangle([w1 + 2 * px, 0, W, H], fill=BLK)
    draw_spaced(d, (w1 + 3 * px, (H - h2) / 2 - o2), "SOCIETY", f2, "white", sp)
    if bar:
        d.rectangle([0, H, W, H + bar], fill=YEL)
    return img


def profile():
    S = 1080
    img = Image.new("RGB", (S, S), RED)
    d = ImageDraw.Draw(img)
    f1, f2 = font("ArchivoBlack-Regular.ttf", 330), font("BarlowCondensed-Bold.ttf", 150)
    w1, h1, o1 = text_box(d, "NPC", f1)
    sp = 14
    w2, h2, o2 = text_box(d, "SOCIETY", f2, sp)
    gap, pad = 70, 30
    total = h1 + gap + h2 + 2 * pad
    y0 = (S - total) / 2
    d.text(((S - w1) / 2, y0 - o1), "NPC", font=f1, fill="white")
    y = y0 + h1 + gap
    d.rectangle([0, y, S, y + h2 + 2 * pad], fill=BLK)
    draw_spaced(d, ((S - w2) / 2, y + pad - o2), "SOCIETY", f2, "white", sp)
    d.rectangle([0, y + h2 + 2 * pad, S, y + h2 + 2 * pad + 14], fill=YEL)
    return img


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    logo(1.0).save(OUT / "logo_bug.png")
    logo(2.2).save(OUT / "logo_big.png")
    profile().save(OUT / "photo_profil.png")
    print("Visuels générés dans", OUT)
