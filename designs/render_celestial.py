#!/usr/bin/env python3
"""Render 'Celestial Terminal' — the aesthetic plate for the Odysseus wrapper app.

A navigator's star-chart on a night field: a faint coordinate grid, a patient
scatter of stars, and — woven in subtly — two bright stars (one cold, one warm)
joined by a single hairline that points toward a lone warm pole: the bearing home.
Supersampled 2x then downscaled for crisp edges. Pure PIL.
"""
import math
import os
import random

from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONTS = ("/home/robert/.config/Claude/local-agent-mode-sessions/skills-plugin/"
         "023ffcbe-b5e5-44cf-b821-e3d9dce9aefb/7062840c-29fc-4380-a5c5-8934961e3bd6/"
         "skills/canvas-design/canvas-fonts")

S = 2                      # supersample factor
W, H = 1600 * S, 2200 * S
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "celestial-terminal.png")

# palette
VOID = (11, 14, 20)
VOID2 = (8, 10, 15)
GRID = (31, 39, 51)
HAIR = (40, 50, 66)
TXT = (242, 244, 248)
TXT2 = (154, 164, 178)
TXT3 = (92, 102, 119)
BRASS = (224, 169, 94)
CYAN = (91, 182, 201)

random.seed(7)


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size * S)


def tracked(d, xy, text, fnt, fill, tracking=0, anchor="la"):
    """Draw letter-spaced text. Returns total width."""
    x, y = xy
    widths = []
    for ch in text:
        w = d.textlength(ch, font=fnt)
        widths.append(w)
    total = sum(widths) + tracking * S * (len(text) - 1)
    if anchor == "ma":
        x -= total / 2
    elif anchor == "ra":
        x -= total
    cx = x
    for ch, w in zip(text, widths):
        d.text((cx, y), ch, font=fnt, fill=fill, anchor="la")
        cx += w + tracking * S
    return total


def glow(img, cx, cy, r, color, layers=14, max_alpha=120):
    """Soft radial glow via stacked translucent discs."""
    gl = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(gl)
    for i in range(layers, 0, -1):
        rr = r * i / layers
        a = int(max_alpha * (1 - i / layers) ** 2)
        gd.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=color + (a,))
    img.alpha_composite(gl)


def star(d, cx, cy, r, color, spikes=True):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    if spikes:
        for ln in (((cx - r * 3.4, cy), (cx + r * 3.4, cy)),
                   ((cx, cy - r * 3.4), (cx, cy + r * 3.4))):
            d.line(ln, fill=color + (160,) if len(color) == 3 else color, width=max(1, int(0.6 * S)))


img = Image.new("RGBA", (W, H), VOID + (255,))
d = ImageDraw.Draw(img)

# 1) vignette — slightly darker toward the edges (night settling)
vg = Image.new("L", (W, H), 0)
vd = ImageDraw.Draw(vg)
vd.ellipse([-W * 0.25, -H * 0.18, W * 1.25, H * 1.18], fill=40)
vg = vg.filter(ImageFilter.GaussianBlur(220 * S))
dark = Image.new("RGBA", (W, H), VOID2 + (255,))
img = Image.composite(img, dark, vg)
d = ImageDraw.Draw(img)

# margins / plate frame
M = 120 * S
d.rectangle([M, M, W - M, H - M], outline=HAIR, width=max(1, int(0.8 * S)))
inset = 26 * S
d.rectangle([M + inset, M + inset, W - M - inset, H - M - inset], outline=GRID, width=1)

# 2) coordinate grid inside the plate
gx0, gy0, gx1, gy1 = M + inset, M + inset, W - M - inset, H - M - inset
mono_s = font("JetBrainsMono-Regular.ttf", 11)
cols = 9
rows = 13
for i in range(1, cols):
    x = gx0 + (gx1 - gx0) * i / cols
    d.line([(x, gy0), (x, gy1)], fill=GRID, width=1)
for j in range(1, rows):
    y = gy0 + (gy1 - gy0) * j / rows
    d.line([(gx0, y), (gx1, y)], fill=GRID, width=1)
# faint tick labels along the top + left (RA / Dec feel)
for i in range(1, cols):
    x = gx0 + (gx1 - gx0) * i / cols
    d.text((x, gy0 - 18 * S), f"{i*2:02d}h", font=mono_s, fill=TXT3, anchor="ma")
for j in range(1, rows):
    y = gy0 + (gy1 - gy0) * j / rows
    d.text((gx0 - 14 * S, y), f"{60 - j*8:+03d}", font=mono_s, fill=TXT3, anchor="rm")

# 3) patient star scatter (the night sky)
for _ in range(520):
    x = random.uniform(gx0 + 10 * S, gx1 - 10 * S)
    y = random.uniform(gy0 + 10 * S, gy1 - 10 * S)
    r = random.choice([0.6, 0.7, 0.9, 1.1, 1.4]) * S
    b = random.randint(60, 150)
    col = (b, b + 6, b + 14)
    d.ellipse([x - r, y - r, x + r, y + r], fill=col)

# 4) a faint concentric "scan" ring, low in the field
sx, sy = gx0 + (gx1 - gx0) * 0.30, gy0 + (gy1 - gy0) * 0.72
for k in range(1, 7):
    rr = 70 * S * k
    bbox = [sx - rr, sy - rr, sx + rr, sy + rr]
    ring = Image.new("RGBA", img.size, (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    rd.ellipse(bbox, outline=CYAN + (max(6, 38 - k * 5),), width=1)
    img.alpha_composite(ring)
    d = ImageDraw.Draw(img)

# 5) THE constellation — a quiet seven-star figure; two of them are the pair.
#    Coordinates in plate space (fractions of the grid), hand-placed.
def P(fx, fy):
    return (gx0 + (gx1 - gx0) * fx, gy0 + (gy1 - gy0) * fy)

dipper = [P(0.62, 0.16), P(0.74, 0.205), P(0.80, 0.30), P(0.70, 0.355),
          P(0.585, 0.40), P(0.50, 0.32), P(0.585, 0.255)]
# faint constellation lines between the minor figure
for a, b in zip(dipper, dipper[1:]):
    d.line([a, b], fill=HAIR, width=max(1, int(0.8 * S)))
for (x, y) in dipper:
    d.ellipse([x - 2.2 * S, y - 2.2 * S, x + 2.2 * S, y + 2.2 * S], fill=(190, 198, 210))

# the pair: cold star (alpha) and warm star (beta)
cold = P(0.585, 0.40)
warm = P(0.50, 0.32)
# the warm POLE they bear toward — alone, upper field (home / the lamp)
pole = P(0.40, 0.115)

# bearing line: from cold -> warm -> extended to the pole (single hairline)
img = img.convert("RGBA")
bl = Image.new("RGBA", img.size, (0, 0, 0, 0))
bd = ImageDraw.Draw(bl)
bd.line([cold, warm], fill=BRASS + (150,), width=max(1, int(1.0 * S)))
# extend warm->pole as a dotted bearing
n = 46
for t in range(n):
    if t % 2:
        continue
    x = warm[0] + (pole[0] - warm[0]) * t / n
    y = warm[1] + (pole[1] - warm[1]) * t / n
    bd.ellipse([x - 1.1 * S, y - 1.1 * S, x + 1.1 * S, y + 1.1 * S], fill=BRASS + (120,))
img.alpha_composite(bl)
d = ImageDraw.Draw(img)

glow(img, cold[0], cold[1], 54 * S, CYAN, max_alpha=128)
glow(img, warm[0], warm[1], 48 * S, BRASS, max_alpha=128)
glow(img, pole[0], pole[1], 62 * S, BRASS, max_alpha=100)
d = ImageDraw.Draw(img)
star(d, cold[0], cold[1], 4.2 * S, CYAN)
star(d, warm[0], warm[1], 4.0 * S, BRASS)
star(d, pole[0], pole[1], 5.2 * S, BRASS)

# tiny clinical labels for the pair + pole (felt, not announced)
lab = font("JetBrainsMono-Regular.ttf", 13)
d.text((cold[0] + 12 * S, cold[1] - 4 * S), "α  19h51 +08°", font=lab, fill=TXT2, anchor="lm")
d.text((warm[0] + 12 * S, warm[1] - 4 * S), "β  18h36 +38°", font=lab, fill=TXT2, anchor="lm")
d.text((pole[0] + 14 * S, pole[1] - 2 * S), "ITHACA · pol.", font=lab, fill=BRASS, anchor="lm")

# 6) header band
hd = font("Jura-Light.ttf", 34)
tracked(d, (gx0, M + inset - 70 * S), "CELESTIAL TERMINAL", hd, TXT, tracking=14)
mono = font("JetBrainsMono-Regular.ttf", 14)
d.text((gx1, M + inset - 64 * S), "PLATE I · ODYSSEUS FLEET", font=mono, fill=TXT3, anchor="ra")

# 7) quiet anchor in the lower field (raised into the void for balance): the
#    subtle Greek word, set between two short hairlines.
ny = gy0 + (gy1 - gy0) * 0.66
serif = font("InstrumentSerif-Regular.ttf", 74)
sub = font("JetBrainsMono-Regular.ttf", 14)
half = 150 * S
d.line([(W / 2 - half, ny - 26 * S), (W / 2 + half, ny - 26 * S)], fill=HAIR, width=1)
tracked(d, (W / 2, ny), "N O S T O S", serif, TXT, tracking=12, anchor="ma")
tracked(d, (W / 2, ny + 96 * S), "TWO LIGHTS · ONE BEARING · TOWARD HOME",
        sub, TXT3, tracking=8, anchor="ma")
d.line([(W / 2 - half, ny + 132 * S), (W / 2 + half, ny + 132 * S)], fill=HAIR, width=1)

# corner registration marks (plate authenticity)
reg = font("JetBrainsMono-Regular.ttf", 11)
d.text((gx0, gy1 + 8 * S), "λ 0B0E14", font=reg, fill=TXT3, anchor="lt")
d.text((gx1, gy1 + 8 * S), "obs. local · no telemetry", font=reg, fill=TXT3, anchor="rt")

# downscale (supersample → crisp)
img = img.convert("RGB").resize((W // S, H // S), Image.LANCZOS)
img.save(OUT, "PNG")
print("wrote", OUT, img.size)
