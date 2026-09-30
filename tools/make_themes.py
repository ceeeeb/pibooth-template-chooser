"""Generate themed pibooth-picture-template files for a Canon SELPHY postcard.

Each theme gives a draw.io file with two pages, 1 photo and 4 photos, on a
landscape 148 x 100 mm card rendered at 300 dpi (1749 x 1182 px). The
decoration is drawn here and embedded as images; captures and texts are
pibooth placeholders. Usage: make_themes.py FONT_DIR OUT_DIR
"""

import base64
import io
import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_DIR = sys.argv[1] if len(sys.argv) > 1 else "fonts"
W, H = 1749, 1182          # final page in pixels (300 dpi)
S = 2                      # supersampling factor for smooth drawing
UNIT = 3                   # pixels per draw.io unit (1/100 inch at 300 dpi)
CAPTURE_STYLE = "rounded=0;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;"
TEXT_STYLE = "text;html=1;align=center;verticalAlign=middle;whiteSpace=wrap;"


def font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size * S)


# --- drawing helpers (coordinates in final pixels, scaled by S) ------------

class Canvas:

    def __init__(self, color, mode="RGB"):
        self.image = Image.new(mode, (W * S, H * S), color)
        self.draw = ImageDraw.Draw(self.image)

    def p(self, points):
        return [(x * S, y * S) for x, y in points]

    def line(self, points, color, width):
        self.draw.line(self.p(points), fill=color, width=int(width * S), joint="curve")

    def polygon(self, points, fill=None, outline=None, width=1):
        self.draw.polygon(self.p(points), fill=fill)
        if outline:
            self.line(list(points) + [points[0]], outline, width)

    def ellipse(self, cx, cy, rx, ry, fill=None, outline=None, width=1):
        self.draw.ellipse([(cx - rx) * S, (cy - ry) * S, (cx + rx) * S, (cy + ry) * S],
                          fill=fill, outline=outline, width=int(width * S))

    def rect(self, x0, y0, x1, y1, fill=None, outline=None, width=1):
        self.draw.rectangle([x0 * S, y0 * S, x1 * S, y1 * S], fill=fill, outline=outline, width=int(width * S))

    def text(self, xy, text, fnt, color, anchor="mm", spacing=0):
        if not spacing:
            self.draw.text((xy[0] * S, xy[1] * S), text, font=fnt, fill=color, anchor=anchor)
            return
        widths = [fnt.getlength(c) + spacing * S for c in text]
        x = xy[0] * S - (sum(widths) - spacing * S) / 2
        for char, width in zip(text, widths):
            self.draw.text((x, xy[1] * S), char, font=fnt, fill=color, anchor="lm")
            x += width

    def final(self):
        return self.image.resize((W, H), Image.LANCZOS)


def bezier(p0, p1, p2, p3, steps=40):
    points = []
    for i in range(steps + 1):
        t = i / steps
        a, b, c, d = (1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t * t * (1 - t), t ** 3
        points.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
                       a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return points


def rotated_rect(cx, cy, w, h, degrees):
    """Corners of a rectangle turned counter-clockwise, as PIL rotates images."""
    a = math.radians(degrees)
    corners = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    return [(cx + x * math.cos(a) + y * math.sin(a), cy - x * math.sin(a) + y * math.cos(a)) for x, y in corners]


def star(cx, cy, outer, inner, turn=-90):
    return [(cx + (outer if i % 2 == 0 else inner) * math.cos(math.radians(turn + i * 36)),
             cy + (outer if i % 2 == 0 else inner) * math.sin(math.radians(turn + i * 36))) for i in range(10)]


def heart(cx, cy, size):
    points = []
    for i in range(120):
        t = 2 * math.pi * i / 120
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        points.append((cx + x * size / 32, cy + y * size / 32))
    return points


def leaf(base, tip, bulge):
    """Pointed leaf outline between two points."""
    dx, dy = tip[0] - base[0], tip[1] - base[1]
    nx, ny = -dy * bulge, dx * bulge
    mid = ((base[0] + tip[0]) / 2, (base[1] + tip[1]) / 2)
    side1 = bezier(base, (mid[0] + nx, mid[1] + ny), (mid[0] + nx, mid[1] + ny), tip, 20)
    side2 = bezier(tip, (mid[0] - nx, mid[1] - ny), (mid[0] - nx, mid[1] - ny), base, 20)
    return side1 + side2[1:]


def petal(center, angle, length, width):
    a = math.radians(angle)
    tip = (center[0] + length * math.cos(a), center[1] + length * math.sin(a))
    return leaf(center, tip, width)


def spiral(cx, cy, radius, turns, direction=1, start=0):
    points = []
    for i in range(80):
        t = i / 79
        r = radius * (1 - t * 0.85)
        a = start + direction * t * turns * 2 * math.pi
        points.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return points


def noise_texture(base, amount, seed, blur=1.5):
    rnd = random.Random(seed)
    img = Image.new("L", (W // 4, H // 4))
    img.putdata([rnd.randint(0, 255) for _ in range((W // 4) * (H // 4))])
    img = img.resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(blur))
    tint = Image.new("RGB", (W, H), base)
    light = Image.new("RGB", (W, H), tuple(min(255, c + amount) for c in base))
    dark = Image.new("RGB", (W, H), tuple(max(0, c - amount) for c in base))
    return Image.composite(light, dark, img).resize((W, H)) if amount else tint


def vignette(image, strength):
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).ellipse([-W * 0.25, -H * 0.3, W * 1.25, H * 1.3], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(160))
    dark = Image.new("RGB", (W, H), tuple(int(c * (1 - strength)) for c in (120, 80, 40)))
    return Image.composite(image, dark, mask)


# --- themes ----------------------------------------------------------------

class Theme:
    """A decorated layout: background, photo area, optional overlays above the
    photos, and the two footer text areas (names, date)."""

    name = ""
    photo = (0, 0, W, H)            # x, y, w, h in pixels
    rotation = 0                    # single photo rotation, counter-clockwise
    text1 = text2 = None            # x, y, w, h in pixels
    config = {}                     # suggested pibooth.cfg [PICTURE] values
    grid_gap = 18

    def background(self, photos):
        raise NotImplementedError

    def overlays(self):
        return []                    # list of (RGBA image, x, y)


class Hollywood(Theme):
    name = "hollywood"
    photo = (300, 150, 1150, 730)
    rotation = 3
    text1 = (560, 945, 630, 85)
    text2 = (660, 1040, 430, 60)
    config = {"footer_text1": "Patrice & Patricia", "footer_text2": "06-08-2022",
              "text_colors": ((255, 255, 255), (230, 200, 205)),
              "text_fonts": ("Montserrat-Bold.ttf", "Montserrat-SemiBold.ttf")}

    def background(self, photos):
        c = Canvas((8, 8, 10))
        for r in range(900, 0, -30):
            shade = int(8 + 34 * (1 - r / 900))
            c.ellipse(W / 2, H / 2, r * 1.3, r, fill=(shade, shade, shade + 3))
        rnd = random.Random(1)
        for _ in range(3200):
            x, y, size = rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(0.6, 2.6)
            tone = rnd.choice([(255, 255, 255), (245, 225, 230), (200, 200, 205)])
            c.ellipse(x, y, size, size, fill=tone)
        pink, dark_pink, light_pink = (217, 163, 168), (170, 118, 126), (236, 200, 203)
        for side in (0, 1):
            for i in range(9):
                x = 95 + (i % 2) * 55 if side == 0 else W - 95 - (i % 2) * 55
                y = 150 + i * 88
                r = 52 - (i % 3) * 6
                c.polygon(star(x, y, r, r * 0.45, -90 + i * 7), fill=pink, outline=dark_pink, width=3)
        for cx, cy in ((190, 1010), (W - 190, 1000)):
            c.polygon(star(cx, cy, 175, 72), fill=pink, outline=dark_pink, width=5)
            c.polygon(star(cx, cy, 138, 57), outline=light_pink, width=3)
            c.ellipse(cx, cy + 12, 26, 26, fill=light_pink, outline=dark_pink, width=3)
        x, y, w, h = self.photo
        frame = 30
        angle = self.rotation if photos == 1 else 0
        c.polygon(rotated_rect(x + w / 2, y + h / 2, w + 2 * frame, h + 2 * frame, angle), fill=(250, 250, 250))
        return c.final()


class BirthdayBlackGold(Theme):
    name = "anniversaire-noir-or"
    photo = (175, 40, 1400, 840)
    text1 = (690, 1082, 370, 62)
    text2 = (690, 1146, 370, 30)
    config = {"footer_text1": "MARINE", "footer_text2": "",
              "text_colors": ((255, 255, 255), (201, 164, 92)),
              "text_fonts": ("Montserrat-Bold.ttf", "Montserrat-SemiBold.ttf")}

    def background(self, photos):
        c = Canvas((10, 10, 10))
        rnd = random.Random(2)
        gold, pale_gold, white = (201, 164, 92), (232, 199, 122), (240, 240, 235)
        for _ in range(420):
            x = rnd.choice([rnd.uniform(0, 175), rnd.uniform(1575, W), rnd.uniform(0, W)])
            y = rnd.uniform(0, H)
            if 175 < x < 1575 and y < 890:
                continue
            color = rnd.choice([gold, pale_gold, white, gold])
            if rnd.random() < 0.5:
                a = rnd.uniform(0, math.pi)
                l = rnd.uniform(5, 13)
                c.line([(x - l * math.cos(a), y - l * math.sin(a)), (x + l * math.cos(a), y + l * math.sin(a))], color, 4)
            else:
                r = rnd.uniform(2, 5)
                c.ellipse(x, y, r, r, fill=color)
        balloons = [(85, 330, white), (70, 500, gold), (105, 660, white), (60, 820, gold),
                    (W - 80, 280, gold), (W - 95, 450, white), (W - 65, 610, gold), (W - 100, 780, white)]
        for bx, by, color in balloons:
            c.line(bezier((bx, by + 70), (bx - 20, by + 130), (bx + 20, by + 170), (bx, by + 240), 30), (120, 120, 120), 2)
            shade = tuple(int(v * 0.72) for v in color)
            c.ellipse(bx, by, 58, 70, fill=shade)
            c.ellipse(bx - 5, by - 6, 52, 63, fill=color)
            c.ellipse(bx - 20, by - 28, 12, 18, fill=tuple(min(255, v + 40) for v in color))
            c.polygon([(bx - 9, by + 76), (bx + 9, by + 76), (bx, by + 66)], fill=shade)
        c.text((W / 2, 905), "HAPPY", font("Montserrat-SemiBold.ttf", 44), gold, spacing=10)
        c.text((W / 2, 1000), "BIRTHDAY", font("Montserrat-Bold.ttf", 96), white)
        c.rect(690, 1080, 1060, 1146, fill=gold)
        return c.final()


class ArtDecoBlueGold(Theme):
    name = "art-deco-bleu-or"
    photo = (110, 105, 1530, 975)
    text1 = (1250, 905, 390, 95)
    text2 = (1250, 1015, 390, 60)
    config = {"footer_text1": "Sophie & Julien", "footer_text2": "26.04.2023",
              "text_colors": ((214, 170, 118), (255, 255, 255)),
              "text_fonts": ("Montserrat-Bold.ttf", "Montserrat-SemiBold.ttf")}

    def background(self, photos):
        c = Canvas((19, 38, 74))
        gold, deep = (190, 143, 90), (13, 28, 56)
        tile = 175
        for tx in range(-1, W // tile + 2):
            for ty in range(-1, H // tile + 2):
                x0, y0 = tx * tile, ty * tile
                cx, cy = x0 + tile / 2, y0 + tile / 2
                if (tx + ty) % 2 == 0:
                    c.polygon([(x0, y0), (cx, cy), (x0, y0 + tile)], fill=deep)
                    c.polygon([(x0 + tile, y0), (cx, cy), (x0 + tile, y0 + tile)], fill=deep)
                else:
                    c.polygon([(x0, y0), (cx, cy), (x0 + tile, y0)], fill=deep)
                    c.polygon([(x0, y0 + tile), (cx, cy), (x0 + tile, y0 + tile)], fill=deep)
                for k in (0, 1, 2):
                    inset = 14 + k * 22
                    c.polygon([(cx, y0 + inset), (x0 + tile - inset, cy), (cx, y0 + tile - inset), (x0 + inset, cy)],
                              outline=gold, width=3)
                c.line([(x0, y0), (x0 + tile, y0)], gold, 3)
                c.line([(x0, y0), (x0, y0 + tile)], gold, 3)
        return c.final()

    def overlays(self):
        c = Canvas((0, 0, 0, 0), "RGBA")
        gold, navy = (190, 143, 90, 255), (19, 38, 74, 255)
        x0, y0, x1, y1 = 1215, 870, 1675, 1105
        c.rect(x0, y0, x1, y1, fill=navy, outline=gold, width=6)
        c.rect(x0 + 16, y0 + 16, x1 - 16, y1 - 16, outline=gold, width=2)
        for cx, cy in ((x0 + 16, y0 + 16), (x1 - 16, y0 + 16), (x0 + 16, y1 - 16), (x1 - 16, y1 - 16)):
            c.polygon([(cx, cy - 12), (cx + 12, cy), (cx, cy + 12), (cx - 12, cy)], fill=gold)
        c.line([(x0 + 120, 1008), (x1 - 120, 1008)], gold, 2)
        image = c.final().crop((x0 - 4, y0 - 4, x1 + 5, y1 + 5))
        return [(image, x0 - 4, y0 - 4)]


class WeddingPinkHeart(Theme):
    name = "mariage-coeur-rose"
    photo = (22, 22, 1705, 930)
    text1 = (735, 835, 280, 105)
    text2 = (640, 1085, 470, 70)
    config = {"footer_text1": "Sylvie & Manu", "footer_text2": "6 mai 2023",
              "text_colors": ((40, 30, 35), (40, 30, 35)),
              "text_fonts": ("GreatVibes-Regular.ttf", "PlayfairDisplay.ttf")}

    def background(self, photos):
        c = Canvas((252, 250, 250))
        pink = (201, 138, 155)
        for side in (-1, 1):
            base_x = W / 2 + side * 190
            c.line(bezier((base_x, 1040), (base_x + side * 120, 990), (base_x + side * 260, 1070),
                          (base_x + side * 400, 1010), 60), pink, 3)
            for k, (dx, dy, r) in enumerate(((60, 20, 26), (180, 15, 30), (300, 22, 24))):
                cx = base_x + side * dx
                c.line(spiral(cx, 1010 + dy, r, 1.6, direction=side, start=math.pi / 2), pink, 3)
                c.ellipse(cx + side * (r + 18), 1052, 4, 4, fill=pink)
            c.line(bezier((base_x + side * 400, 1010), (base_x + side * 440, 980), (base_x + side * 470, 1040),
                          (base_x + side * 430, 1050), 30), pink, 3)
        return c.final()

    def overlays(self):
        c = Canvas((0, 0, 0, 0), "RGBA")
        pink = (201, 138, 155, 255)
        c.polygon(heart(W / 2, 905, 400), fill=(255, 255, 255, 255))
        c.line(heart(W / 2, 905, 400) + [heart(W / 2, 905, 400)[0]], pink, 5)
        c.line(heart(W / 2, 900, 340) + [heart(W / 2, 900, 340)[0]], pink, 2)
        image = c.final().crop((650, 700, 1100, 1110))
        return [(image, 650, 700)]


class WeddingBeigeFloral(Theme):
    name = "mariage-beige-floral"
    photo = (58, 45, 1430, 980)
    text1 = (525, 1043, 500, 58)
    text2 = (625, 1112, 300, 45)
    config = {"footer_text1": "Juliette & Clément", "footer_text2": "10.12.22",
              "text_colors": ((255, 255, 255), (120, 105, 95)),
              "text_fonts": ("Montserrat-SemiBold.ttf", "Montserrat-SemiBold.ttf")}

    def background(self, photos):
        c = Canvas((238, 228, 221))
        brown = (160, 138, 126)
        c.rect(515, 1038, 1035, 1106, fill=(140, 114, 99))
        for base, top, head_angle, scale in (((1640, 1160), (1630, 420), -95, 1.0), ((1600, 1160), (1560, 680), -80, 0.75)):
            stem = bezier(base, (base[0] + 40, base[1] - 250 * scale), (top[0] - 50, top[1] + 200 * scale), top, 50)
            c.line(stem, brown, 3)
            hx, hy = top
            for angle, length, width in ((head_angle - 38, 95, 0.32), (head_angle + 38, 95, 0.32),
                                         (head_angle - 12, 120, 0.28), (head_angle + 12, 120, 0.28)):
                c.line(petal((hx, hy), angle, length * scale, width), brown, 3)
            for t, side in ((0.35, 1), (0.55, -1), (0.72, 1)):
                px, py = stem[int(t * 50)]
                c.line(leaf((px, py), (px + side * 110 * scale, py - 150 * scale), 0.22), brown, 3)
                c.line([(px, py), (px + side * 70 * scale, py - 95 * scale)], brown, 2)
        return c.final()


class WeddingFloralGold(Theme):
    name = "mariage-floral-or"
    photo = (232, 78, 1290, 870)
    text1 = (480, 965, 790, 125)
    text2 = (730, 1090, 290, 50)
    config = {"footer_text1": "Flora & Hugo", "footer_text2": "22.07.2021",
              "text_colors": ((35, 30, 30), (35, 30, 30)),
              "text_fonts": ("GreatVibes-Regular.ttf", "PlayfairDisplay.ttf")}

    def background(self, photos):
        base = noise_texture((246, 243, 236), 5, 3, blur=2)
        c = Canvas((0, 0, 0))
        c.image = base.resize((W * S, H * S))
        c.draw = ImageDraw.Draw(c.image)
        gold, pale = (196, 158, 88), (214, 190, 140)
        for cx, cy, scale, turn in ((110, 90, 1.0, 20), (1530, 1040, 1.1, 200)):
            for k in range(7):
                c.line(petal((cx, cy), turn + k * 26, 150 * scale, 0.3), pale, 3)
                c.line(petal((cx, cy), turn + k * 26 + 13, 105 * scale, 0.25), gold, 2)
            c.ellipse(cx, cy, 16 * scale, 16 * scale, outline=gold, width=3)
        for start, c1, c2, end, width in (((1420, 20), (1560, 60), (1640, 110), (1740, 150), 16),
                                          ((20, 900), (120, 950), (180, 1070), (260, 1160), 18),
                                          ((1560, 80), (1500, 250), (1690, 380), (1620, 560), 6)):
            points = bezier(start, c1, c2, end, 60)
            for i in range(len(points) - 1):
                taper = math.sin(math.pi * i / (len(points) - 1))
                c.line([points[i], points[i + 1]], gold, max(1.5, width * taper))
        for i in range(6):
            x, y = 1650 - i * 55, 1080 - i * 70
            c.line(leaf((x, y), (x - 60, y - 70), 0.3), gold, 2)
        return c.final()


class WeddingMauve(Theme):
    name = "mariage-mauve"
    photo = (185, 160, 1385, 935)
    text1 = (520, 62, 710, 90)
    text2 = (720, 18, 310, 45)
    config = {"footer_text1": "Marion & Tom", "footer_text2": "10.12.22",
              "text_colors": ((255, 255, 255), (255, 255, 255)),
              "text_fonts": ("GreatVibes-Regular.ttf", "PlayfairDisplay.ttf")}

    def background(self, photos):
        c = Canvas((143, 107, 118))
        white = (245, 235, 238)
        x0, y0, x1, y1 = 150, 130, 1600, 1125
        for x in range(x0, x1, 18):
            c.line([(x, y0), (x + 9, y0)], white, 2)
            c.line([(x, y1), (x + 9, y1)], white, 2)
        for y in range(y0, y1, 18):
            c.line([(x0, y), (x0, y + 9)], white, 2)
            c.line([(x1, y), (x1, y + 9)], white, 2)
        for x in (500, 1250):
            c.ellipse(x, 105, 4, 4, fill=white)
        c.line([(505, 105), (590, 105)], white, 1)
        c.line([(1160, 105), (1245, 105)], white, 1)
        for cx, cy, scale, turn in ((1690, 200, 1.4, 120), (40, 900, 1.3, -40), (120, 1150, 0.9, -80)):
            for k in range(5):
                c.line(petal((cx, cy), turn + k * 32, 170 * scale, 0.33), white, 2.5)
                c.line(petal((cx, cy), turn + k * 32 + 16, 110 * scale, 0.22), white, 1.5)
        for i in range(5):
            x, y = 1600 + i * 25, 380 + i * 90
            c.line(leaf((x, y), (x + 90, y + 40), 0.3), white, 2)
        return c.final()


class VintagePostcard(Theme):
    name = "vintage-carte-postale"
    photo = (105, 178, 1450, 960)
    text1 = (545, 30, 660, 120)
    text2 = (1440, 104, 120, 30)
    config = {"footer_text1": "Magali & Fabien", "footer_text2": "25.06.2016",
              "text_colors": ((61, 36, 24), (70, 55, 50)),
              "text_fonts": ("Lobster-Regular.ttf", "Montserrat-SemiBold.ttf")}

    def background(self, photos):
        paper = vignette(noise_texture((214, 178, 118), 22, 4, blur=3), 0.45)
        c = Canvas((0, 0, 0))
        c.image = paper.resize((W * S, H * S))
        c.draw = ImageDraw.Draw(c.image)
        brown = (61, 36, 24)
        x, y, w, h = self.photo
        c.rect(x - 9, y - 9, x + w + 9, y + h + 9, fill=brown)
        c.line([(x - 9, y - 22), (x + w + 9, y - 22)], brown, 3)
        colors = [(236, 180, 170), (244, 238, 226), (104, 165, 138), (244, 238, 226)]
        band = 1600
        for k in range(-20, 30):
            y0 = k * 70
            c.polygon([(band, y0), (W, y0 - (W - band)), (W, y0 - (W - band) + 70), (band, y0 + 70)],
                      fill=colors[k % 4])
        for side in (-1, 1):
            tip_x = W / 2 + side * 345
            end_x = W / 2 + side * 460
            c.line([(tip_x, 88), (end_x, 88)], brown, 4)
            c.polygon([(tip_x, 88), (tip_x + side * 20, 78), (tip_x + side * 20, 98)], fill=brown)
            for f in (0, 14):
                c.line([(end_x - side * f, 88), (end_x + side * 14 - side * f, 76)], brown, 3)
                c.line([(end_x - side * f, 88), (end_x + side * 14 - side * f, 100)], brown, 3)
        ink = (70, 55, 50)
        cx, cy = 1500, 105
        c.ellipse(cx, cy, 88, 88, outline=ink, width=4)
        c.ellipse(cx, cy, 64, 64, outline=ink, width=2)
        for k in range(4):
            yy = cy - 42 + k * 28
            c.line([(1330 + i * 6, yy + 6 * math.sin(i / 3)) for i in range(14)], ink, 3)
        c.text((cx, cy - 42), "PAR AVION", font("Montserrat-SemiBold.ttf", 15), ink)
        c.text((cx, cy + 44), "PHOTOMATON", font("Montserrat-SemiBold.ttf", 13), ink)
        return c.final()


THEMES = [Hollywood(), BirthdayBlackGold(), ArtDecoBlueGold(), WeddingPinkHeart(),
          WeddingBeigeFloral(), WeddingFloralGold(), WeddingMauve(), VintagePostcard()]


# --- draw.io output --------------------------------------------------------

def data_uri(image, fmt):
    buffer = io.BytesIO()
    if fmt == "jpeg":
        image.convert("RGB").save(buffer, "JPEG", quality=90)
    else:
        image.save(buffer, "PNG", optimize=True)
    return "data:image/{},{}".format(fmt, base64.b64encode(buffer.getvalue()).decode())


def cell(page_id, index, value, style, x, y, w, h):
    return ('<mxCell id="{}-{}" value="{}" style="{}" vertex="1" parent="1">'
            '<mxGeometry x="{:.2f}" y="{:.2f}" width="{:.2f}" height="{:.2f}" as="geometry"/></mxCell>'
            ).format(page_id, index, value, style, x / UNIT, y / UNIT, w / UNIT, h / UNIT)


def page(theme, photos):
    page_id = "{}-{}".format(theme.name, photos)
    cells = ['<mxCell id="0" dpi="300"/>', '<mxCell id="1" parent="1"/>'.replace('parent="1"', 'parent="0"')]
    image_style = "shape=image;imageAspect=0;aspect=fixed;verticalLabelPosition=bottom;verticalAlign=top;image={};"
    cells.append(cell(page_id, 2, "", image_style.format(data_uri(theme.background(photos), "jpeg")), 0, 0, W, H))
    x, y, w, h = theme.photo
    if photos == 1:
        style = CAPTURE_STYLE + ("rotation={};".format(-theme.rotation) if theme.rotation else "")
        cells.append(cell(page_id, 3, "1", style, x, y, w, h))
    else:
        gap = theme.grid_gap
        cw, ch = (w - gap) / 2, (h - gap) / 2
        for number in range(4):
            cells.append(cell(page_id, 3 + number, str(number + 1), CAPTURE_STYLE,
                              x + (number % 2) * (cw + gap), y + (number // 2) * (ch + gap), cw, ch))
    index = 10
    for overlay, ox, oy in theme.overlays():
        cells.append(cell(page_id, index, "", image_style.format(data_uri(overlay, "png")),
                          ox, oy, overlay.width, overlay.height))
        index += 1
    for value, rect in (("footer_text1", theme.text1), ("footer_text2", theme.text2)):
        if rect:
            cells.append(cell(page_id, index, value, TEXT_STYLE, *rect))
            index += 1
    name = "1 photo" if photos == 1 else "4 photos"
    return ('<diagram id="{}" name="{}"><mxGraphModel dx="800" dy="600" grid="1" gridSize="5" page="1" '
            'pageScale="1" pageWidth="{:.2f}" pageHeight="{:.2f}"><root>{}</root></mxGraphModel></diagram>'
            ).format(page_id, name, W / UNIT, H / UNIT, "".join(cells))


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for theme in THEMES:
        content = ('<?xml version="1.0" encoding="UTF-8"?>\n<mxfile host="app.diagrams.net" type="device" pages="2">'
                   + page(theme, 1) + page(theme, 4) + '</mxfile>\n')
        with open(os.path.join(out_dir, theme.name + ".xml"), "w") as fp:
            fp.write(content)
        print(theme.name, len(content) // 1024, "Ko")


if __name__ == "__main__":
    main(sys.argv[2])
