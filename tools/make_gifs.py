#!/usr/bin/env python3
"""
DiGi Hami - Generator fuer die Hamster-im-Rad-Animationen
=========================================================

Erzeugt alle GIFs in ../data/gifs/ prozedural (keine externen Grafiken).
Optimiert fuer das runde GC9A01-Display (240x240):

* alles Wichtige liegt innerhalb des Kreises (r = 120 px)
* das Laufrad fuellt den Kreis aus - passend zum 3D-gedruckten Rad
* nahtlose Loops (Rad-Drehung und Laufzyklus gehen exakt auf)
* eine gemeinsame Palette + "unveraenderte Pixel = transparent"
  -> kleine Dateien, die gut ins Flash passen

Aufruf:  python3 tools/make_gifs.py            (alle)
         python3 tools/make_gifs.py run sleep  (nur bestimmte)

Benoetigt: Pillow, numpy
"""
import math
import os
import random
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W = 240          # Displaygroesse
S = 3            # Supersampling-Faktor (Kantenglaettung)
C = W / 2        # Mittelpunkt
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "gifs")

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def font(size):
    for p in FONT_PATHS:
        if os.path.exists(p):
            return ImageFont.truetype(p, int(size * S))
    return ImageFont.load_default()


def hexc(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


# --------------------------------------------------------------------------
#  Farbthemen
# --------------------------------------------------------------------------
FUR_GOLD = dict(
    fur="#EDA35E", shade="#D3843F", far="#C47A3E", cream="#FFF3E0",
    line="#4A2C1A", pink="#F49AA6", ear="#F8B8C0", eye="#24160D",
    stripe=None,
)
FUR_SNOW = dict(
    fur="#F7F6F3", shade="#DCDAD6", far="#C9C6C1", cream="#FFFFFF",
    line="#3E3A44", pink="#F3A0AE", ear="#F6BEC6", eye="#1C1A22",
    stripe="#8F8E99",
)
FUR_CHOC = dict(
    fur="#8A5A3B", shade="#6E452C", far="#5E3B26", cream="#E9CDB0",
    line="#2A170C", pink="#E98E9C", ear="#E7A4AE", eye="#120A06",
    stripe=None,
)

WHEEL_AMBER = dict(
    bg_in="#FCEBCB", bg_out="#FCEBCB", band="#CF7F1F", rung="#FFD47E",
    rung_l="#8A4F12", spoke="#F2A63C", spoke_l="#8A4F12", hub="#FFD47E",
    rim="#E8952A", bokeh=None,
)
WHEEL_MINT = dict(
    bg_in="#DDF2F8", bg_out="#DDF2F8", band="#2E9C84", rung="#9DEBD6",
    rung_l="#1E5E50", spoke="#5CCBB0", spoke_l="#1E5E50", hub="#9DEBD6",
    rim="#3DB397", bokeh=None,
)
WHEEL_NIGHT = dict(
    bg_in="#2A3463", bg_out="#0D1230", band="#6B4C2A", rung="#B08A55",
    rung_l="#2E1F10", spoke="#8C6838", spoke_l="#2E1F10", hub="#B08A55",
    rim="#7A5730", bokeh=None,
)
WHEEL_BERRY = dict(
    bg_in="#FBE0EA", bg_out="#FBE0EA", band="#B2406E", rung="#FFB3CF",
    rung_l="#5E1734", spoke="#E36A99", spoke_l="#5E1734", hub="#FFB3CF",
    rim="#D2568A", bokeh=None,
)

R_EDGE = 119.5   # Aussenkante
R_TRACK = 103.0  # Laufflaeche (Innenkante der Sprossen)
R_FEET = 100.5   # Bodenpunkt des Hamsters (knapp ueber den Sprossen)
R_RUNG = 116.0   # Aussenkante der Sprossen
N_RUNGS = 24     # 15 Grad Abstand
N_SPOKES = 6     # 60 Grad Symmetrie


# --------------------------------------------------------------------------
#  Hintergrund + Rad
# --------------------------------------------------------------------------
_bg_cache = {}


def background(theme, night_stars=None, t=0.0):
    key = id(theme)
    if key not in _bg_cache:
        n = W * S
        yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
        d = np.sqrt((xx - n / 2) ** 2 + (yy - n * 0.42) ** 2) / (n * 0.62)
        d = np.clip(d, 0, 1) ** 1.3
        a = np.array(hexc(theme["bg_in"])[:3], np.float32)
        b = np.array(hexc(theme["bg_out"])[:3], np.float32)
        img = a[None, None, :] * (1 - d[..., None]) + b[None, None, :] * d[..., None]
        base = Image.fromarray(img.astype(np.uint8), "RGB").convert("RGBA")
        if theme.get("bokeh"):
            rnd = random.Random(7)
            lay = Image.new("RGBA", base.size, (0, 0, 0, 0))
            dr = ImageDraw.Draw(lay)
            for _ in range(9):
                x, y = rnd.uniform(30, 210), rnd.uniform(20, 150)
                r = rnd.uniform(8, 22)
                dr.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S], fill=theme["bokeh"])
            lay = lay.filter(ImageFilter.GaussianBlur(4 * S))
            base = Image.alpha_composite(base, lay)
        _bg_cache[key] = base
    img = _bg_cache[key].copy()
    if night_stars:
        dr = ImageDraw.Draw(img)
        for (x, y, r, ph) in night_stars:
            k = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * 2 * math.pi + ph))
            col = (255, 246, 210, int(255 * k))
            rr = r * (0.7 + 0.5 * k)
            star(dr, x, y, rr, col, points=4, inner=0.35)
    return img


def star(dr, x, y, r, col, points=5, inner=0.45, rot=-90):
    pts = []
    for i in range(points * 2):
        rad = r if i % 2 == 0 else r * inner
        a = math.radians(rot + i * 180 / points)
        pts.append(((x + rad * math.cos(a)) * S, (y + rad * math.sin(a)) * S))
    dr.polygon(pts, fill=col)


def ring(dr, r_out, r_in, col):
    """Gefuellter Ring ueber zwei Ellipsen mit Breite."""
    w = (r_out - r_in) * S
    r = (r_out + r_in) / 2
    dr.ellipse([(C - r) * S, (C - r) * S, (C + r) * S, (C + r) * S], outline=col, width=int(round(w)))


def wheel_back(img, theme, rot_deg):
    """Hinterer Teil: Laufband, Speichen, Nabe."""
    dr = ImageDraw.Draw(img)
    ring(dr, R_EDGE, R_TRACK - 1, hexc(theme["band"]))
    # Speichen
    for i in range(N_SPOKES):
        a = math.radians(rot_deg + i * 360 / N_SPOKES)
        x0, y0 = C + 12 * math.cos(a), C + 12 * math.sin(a)
        x1, y1 = C + (R_TRACK - 2) * math.cos(a), C + (R_TRACK - 2) * math.sin(a)
        dr.line([x0 * S, y0 * S, x1 * S, y1 * S], fill=hexc(theme["spoke"]), width=int(5 * S))
    # Nabe
    for r, col in ((15, theme["spoke_l"]), (12.5, theme["hub"]), (4.5, theme["spoke_l"])):
        dr.ellipse([(C - r) * S, (C - r) * S, (C + r) * S, (C + r) * S], fill=hexc(col))
    # Innenkante des Laufbands
    ring(dr, R_TRACK + 0.8, R_TRACK - 1.6, hexc(theme["rung_l"]))


def wheel_rungs(img, theme, rot_deg):
    dr = ImageDraw.Draw(img)
    half = 3.6  # Grad
    for i in range(N_RUNGS):
        a0 = rot_deg + i * 360 / N_RUNGS
        pts_o, pts_i = [], []
        for k in range(5):
            a = math.radians(a0 - half + 2 * half * k / 4)
            pts_o.append(((C + R_RUNG * math.cos(a)) * S, (C + R_RUNG * math.sin(a)) * S))
            pts_i.append(((C + (R_TRACK + 0.5) * math.cos(a)) * S, (C + (R_TRACK + 0.5) * math.sin(a)) * S))
        poly = pts_o + pts_i[::-1]
        dr.polygon(poly, fill=hexc(theme["rung"]), outline=hexc(theme["rung_l"]), width=int(1.4 * S))
    # Aussenring (Rand des 3D-Rads)
    ring(dr, R_EDGE + 1, R_RUNG - 0.5, hexc(theme["rim"]))
    ring(dr, R_RUNG + 0.4, R_RUNG - 1.0, hexc(theme["rung_l"]))


# --------------------------------------------------------------------------
#  Hamster-Zeichenwerkzeug (lokale Koordinaten, Ursprung = Bodenpunkt)
# --------------------------------------------------------------------------
LAYER = 240   # lokale Ebenengroesse (in 240er-Einheiten)
ANCHOR = (120, 175)  # Bodenpunkt in der Ebene (Platz nach oben fuer Huete)


class Pen:
    def __init__(self, k):
        self.k = k
        n = int(LAYER * S * k)
        self.img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
        self.dr = ImageDraw.Draw(self.img)

    def P(self, x, y):
        return ((ANCHOR[0] + x) * S * self.k, (ANCHOR[1] + y) * S * self.k)

    def ell(self, cx, cy, rx, ry, col, grow=0.0, angle=0):
        rx, ry = rx + grow, ry + grow
        if angle == 0:
            x0, y0 = self.P(cx - rx, cy - ry)
            x1, y1 = self.P(cx + rx, cy + ry)
            self.dr.ellipse([x0, y0, x1, y1], fill=col)
        else:
            pts = []
            ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
            for i in range(48):
                t = 2 * math.pi * i / 48
                ex, ey = rx * math.cos(t), ry * math.sin(t)
                pts.append(self.P(cx + ex * ca - ey * sa, cy + ex * sa + ey * ca))
            self.dr.polygon(pts, fill=col)

    def cap(self, x0, y0, x1, y1, w, col, grow=0.0):
        w = w + 2 * grow
        a, b = self.P(x0, y0), self.P(x1, y1)
        self.dr.line([a, b], fill=col, width=max(1, int(w * S * self.k)))
        r = w / 2
        for (x, y) in ((x0, y0), (x1, y1)):
            self.ell(x, y, r, r, col)

    def line(self, pts, col, w):
        self.dr.line([self.P(*p) for p in pts], fill=col, width=max(1, int(w * S * self.k)), joint="curve")

    def arc(self, cx, cy, r, a0, a1, col, w):
        pts = []
        for i in range(17):
            a = math.radians(a0 + (a1 - a0) * i / 16)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        self.line(pts, col, w)


OUTLINE = 2.4


def leg_pos(phase, hip_x, amp, lift):
    x = hip_x + amp * math.cos(phase)
    y = -lift * max(0.0, -math.sin(phase))
    return x, y


def hamster_side(k, fur, phase=0.0, amp=8.0, lift=7.0, bob=2.0, mood="run",
                 ear_back=False, mouth_open=False, eye_style="open"):
    """Hamster seitlich (Blick nach rechts). Gibt RGBA-Ebene zurueck."""
    pen = Pen(k)
    L, F, SH, FAR = hexc(fur["line"]), hexc(fur["fur"]), hexc(fur["shade"]), hexc(fur["far"])
    CR, PK, EAR, EYE = hexc(fur["cream"]), hexc(fur["pink"]), hexc(fur["ear"]), hexc(fur["eye"])
    dy = -bob * abs(math.sin(phase)) if mood == "run" else 0.0
    hip_f, hip_b = 22, -20

    # Beinpositionen (diagonale Paare)
    if mood == "run":
        nf = leg_pos(phase, hip_f, amp, lift)
        ff = leg_pos(phase + math.pi, hip_f - 4, amp, lift)
        nb = leg_pos(phase + math.pi + 0.35, hip_b, amp, lift)
        fb = leg_pos(phase + 0.35, hip_b - 4, amp, lift)
    else:
        nf, ff, nb, fb = (hip_f + 3, 0), (hip_f - 3, 0), (hip_b + 2, 0), (hip_b - 4, 0)

    def leg(hx, foot, colleg, colfoot):
        fx, fy = foot
        pen.cap(hx, -14 + dy, fx, fy - 4, 10, L, grow=OUTLINE)
        pen.ell(fx + 2, fy - 3, 7, 4.2, L, grow=OUTLINE)
        pen.cap(hx, -14 + dy, fx, fy - 4, 10, colleg)
        pen.ell(fx + 2, fy - 3, 7, 4.2, colfoot)

    # hintere (ferne) Beine
    leg(hip_f - 4, ff, FAR, hexc(fur["pink"], 255))
    leg(hip_b - 4, fb, FAR, hexc(fur["pink"], 255))

    ear_dx = -6 if ear_back else 0
    ear_dy = 3 if ear_back else -1.2 * math.cos(2 * phase) if mood == "run" else 0

    # Silhouette: Umriss-Durchgang, dann Fuell-Durchgang
    def silhouette(grow, col_body, col_head):
        pen.ell(-41, -29 + dy, 6.5, 6.5, col_body, grow)             # Schwanz
        pen.ell(25 + ear_dx, -64 + dy + ear_dy, 9.5, 9.5, col_head, grow)  # Ohr
        pen.ell(0, -30 + dy, 41, 27.5, col_body, grow)              # Koerper
        pen.ell(35, -42 + dy, 24.5, 23.5, col_head, grow)           # Kopf
        pen.ell(48, -34 + dy, 14.5, 11.5, col_head, grow)           # Schnauze

    silhouette(OUTLINE, L, L)
    silhouette(0, F, F)
    # Ruecken-Schattierung
    pen.ell(-6, -40 + dy, 30, 12, SH)
    pen.ell(-4, -36 + dy, 33, 14, F)
    if fur.get("stripe"):
        pen.ell(-4, -52 + dy, 26, 3.2, hexc(fur["stripe"]), angle=0)
    # Bauch + Gesicht
    pen.ell(6, -16 + dy, 29, 12, CR)
    pen.ell(49, -32 + dy, 13, 9.5, CR)
    pen.ell(25 + ear_dx, -64 + dy + ear_dy, 5.2, 5.2, EAR)
    # Auge
    if eye_style == "open":
        pen.ell(40, -47 + dy, 4.8, 5.2, EYE)
        pen.ell(41.6, -49 + dy, 1.8, 1.8, (255, 255, 255, 255))
    elif eye_style == "wide":
        pen.ell(40, -47 + dy, 6.2, 6.6, (255, 255, 255, 255))
        pen.ell(40, -47 + dy, 6.2, 6.6, L, grow=0)
        pen.ell(40, -47 + dy, 4.8, 5.2, (255, 255, 255, 255))
        pen.ell(41, -47 + dy, 2.8, 3.0, EYE)
    elif eye_style == "closed":
        pen.arc(40, -49 + dy, 4.5, 20, 160, L, 1.8)
    elif eye_style == "dizzy":
        pts = []
        for i in range(40):
            t = i / 39 * 3.2 * math.pi + phase * 3
            r = 0.6 + 4.8 * i / 39
            pts.append((40 + r * math.cos(t), -47 + dy + r * math.sin(t)))
        pen.line(pts, L, 1.4)
    # Nase, Wange, Mund, Schnurrhaare
    pen.ell(59.5, -38 + dy, 3.4, 3.0, PK)
    pen.ell(43, -30 + dy, 7, 4.6, hexc(fur["pink"], 130))
    if mouth_open:
        pen.ell(54, -26 + dy, 3.4, 3.0, L)
        pen.ell(54, -25.2 + dy, 2.2, 1.6, PK)
    else:
        pen.arc(55.5, -31 + dy, 3, 40, 140, L, 1.4)
    for (ex, ey) in ((72, -42), (73, -36), (71, -30)):
        pen.line([(56, -35 + dy), (ex, ey + dy)], hexc(fur["line"], 150), 0.9)

    # vordere (nahe) Beine
    leg(hip_b, nb, F, PK)
    leg(hip_f, nf, F, PK)
    return pen.img


def hamster_curled(k, fur, breath=0.0):
    """Schlafender Hamster, eingerollt."""
    pen = Pen(k)
    L, F, SH = hexc(fur["line"]), hexc(fur["fur"]), hexc(fur["shade"])
    CR, PK, EAR = hexc(fur["cream"]), hexc(fur["pink"]), hexc(fur["ear"])
    sy = 1 + 0.045 * breath
    sx = 1 - 0.015 * breath
    by = -27 * sy

    def sil(g, col):
        pen.ell(-38, -14, 6.5, 6.5, col, g)                 # Schwanz
        pen.ell(0, by, 42 * sx, 27 * sy, col, g)            # Koerper
        pen.ell(30, -22 * sy, 20, 18 * sy, col, g)          # Kopf (eingezogen)
    sil(OUTLINE, L)
    sil(0, F)
    pen.ell(-6, by - 8, 32 * sx, 12, SH)
    pen.ell(-4, by - 4, 35 * sx, 14, F)
    if fur.get("stripe"):
        pen.ell(-4, by - 21 * sy, 25, 3, hexc(fur["stripe"]))
    # Ohr liegt angelegt auf dem Koerper (eigener Umriss)
    pen.ell(20, -41 * sy, 9, 6.5, L, grow=OUTLINE, angle=-25)
    pen.ell(20, -41 * sy, 9, 6.5, F, angle=-25)
    pen.ell(20.5, -41 * sy, 5.2, 3.4, EAR, angle=-25)
    pen.ell(38, -16 * sy, 11, 8, CR)
    pen.arc(32, -28 * sy, 5, 20, 160, L, 1.9)          # geschlossenes Auge
    pen.ell(36, -18 * sy, 6, 4, hexc(fur["pink"], 120))
    pen.ell(47, -21 * sy, 3, 2.6, PK)
    # Pfoetchen unter dem Kinn
    pen.ell(40, -6, 5.5, 3.8, L, grow=OUTLINE)
    pen.ell(40, -6, 5.5, 3.8, PK)
    pen.ell(-18, -3, 7, 4, L, grow=OUTLINE)
    pen.ell(-18, -3, 7, 4, PK)
    return pen.img


def hamster_front(k, fur, cheek=0.0, blink=False, seed_dy=0.0, seed_size=1.0, chew=0.0, wave=None):
    """Hamster von vorne, sitzend, mit Sonnenblumenkern."""
    pen = Pen(k)
    L, F, SH = hexc(fur["line"]), hexc(fur["fur"]), hexc(fur["shade"])
    CR, PK, EAR, EYE = hexc(fur["cream"]), hexc(fur["pink"]), hexc(fur["ear"]), hexc(fur["eye"])
    cr = 9 + 6 * cheek  # Backentaschen-Radius

    def sil(g, col):
        pen.ell(-19, -3, 10, 4.8, col, g)
        pen.ell(19, -3, 10, 4.8, col, g)
        pen.ell(-25, -104, 11.5, 11.5, col, g)
        pen.ell(25, -104, 11.5, 11.5, col, g)
        pen.ell(0, -38, 40, 36, col, g)
        pen.ell(0, -79, 32, 30, col, g)
        pen.ell(-27 - cheek * 2, -70, cr, cr * 0.9, col, g)
        pen.ell(27 + cheek * 2, -70, cr, cr * 0.9, col, g)
    sil(OUTLINE, L)
    sil(0, F)
    pen.ell(-19, -3, 10, 4.8, PK)
    pen.ell(19, -3, 10, 4.8, PK)
    pen.ell(-25, -104, 6.2, 6.2, EAR)
    pen.ell(25, -104, 6.2, 6.2, EAR)
    if fur.get("stripe"):
        pen.ell(0, -100, 3.2, 8, hexc(fur["stripe"]))
    pen.ell(0, -32, 28, 27, CR)
    pen.ell(0, -67, 19, 13, CR)
    # Augen
    for ex in (-12.5, 12.5):
        if blink:
            pen.arc(ex, -86, 4.6, 20, 160, L, 1.9)
        else:
            pen.ell(ex, -84, 4.9, 5.4, EYE)
            pen.ell(ex + 1.6, -86, 1.9, 1.9, (255, 255, 255, 255))
    # Baeckchen
    pen.ell(-24 - cheek * 2, -70, 6 + 2 * cheek, 4.2, hexc(fur["pink"], 140))
    pen.ell(24 + cheek * 2, -70, 6 + 2 * cheek, 4.2, hexc(fur["pink"], 140))
    pen.ell(0, -73.5, 3.6, 2.9, PK)
    pen.arc(-2.6, -69 + chew, 2.6, 20, 160, L, 1.3)
    pen.arc(2.6, -69 + chew, 2.6, 20, 160, L, 1.3)
    # Sonnenblumenkern + Pfoten
    if seed_size > 0.05:
        sz = seed_size
        sy = -56 + seed_dy
        pen.ell(0, sy, 6.2 * sz, 11 * sz, L, grow=1.6)
        pen.ell(0, sy, 6.2 * sz, 11 * sz, hexc("#3B3A40"))
        for sx in (-2.6 * sz, 0, 2.6 * sz):
            pen.line([(sx, sy - 8 * sz), (sx, sy + 8 * sz)], hexc("#E9E6DF"), 1.0)
    for px in ((-8.5, 8.5) if wave is None else (-8.5,)):
        pen.ell(px, -53 + seed_dy, 5.4, 5, L, grow=OUTLINE * 0.8)
        pen.ell(px, -53 + seed_dy, 5.4, 5, PK)
    if wave is not None:
        # erhobener Arm (rechts im Bild), wave = -1..1
        a = math.radians(-58 + 22 * wave)
        sx0, sy0 = 27, -50
        hx, hy = sx0 + 27 * math.cos(a), sy0 + 27 * math.sin(a)
        pen.cap(sx0, sy0, hx, hy, 11, L, grow=OUTLINE)
        pen.ell(hx, hy, 6.4, 6.8, L, grow=OUTLINE)
        pen.cap(sx0, sy0, hx, hy, 11, F)
        pen.ell(hx, hy, 6.4, 6.8, PK)
        for j in (-1, 0, 1):
            fa = a + j * 0.45
            pen.ell(hx + 6.5 * math.cos(fa), hy + 6.5 * math.sin(fa), 1.9, 1.9, PK)
    return pen.img


def place(frame, layer, k, x, y, angle):
    """Hamster-Ebene so einfuegen, dass der Bodenpunkt bei (x,y) liegt."""
    lay = layer.rotate(angle, resample=Image.BICUBIC, expand=False) if angle else layer
    n = lay.size[0]
    cx = cy = n / 2
    ax, ay = ANCHOR[0] * S * k, ANCHOR[1] * S * k
    a = math.radians(angle)
    dx, dy = ax - cx, ay - cy
    rx = cx + dx * math.cos(a) + dy * math.sin(a)
    ry = cy - dx * math.sin(a) + dy * math.cos(a)
    frame.alpha_composite(lay, (int(round(x * S - rx)), int(round(y * S - ry))))


def on_track(theta_deg, r=R_FEET):
    """Position auf der Laufflaeche; theta=0 ist ganz unten, positiv = nach rechts/vorne."""
    t = math.radians(theta_deg)
    return C + r * math.sin(t), C + r * math.cos(t)


def finish(img, ov=None, wheel_aa=True):
    """Runter skalieren + runde Maske (Ecken schwarz).

    img = Hintergrund + Rad (bei wheel_aa=False ohne Kantenglaettung -> viel
    kleinere GIFs, auf 265 ppi praktisch unsichtbar), ov = Hamster/Effekte
    (immer geglaettet)."""
    if wheel_aa:
        im = img.convert("RGB").resize((W, W), Image.LANCZOS).convert("RGBA")
    else:
        im = img.convert("RGB").resize((W, W), Image.NEAREST).convert("RGBA")
    if ov is not None:
        im.alpha_composite(ov.resize((W, W), Image.LANCZOS))
    im = im.convert("RGB")
    mask = Image.new("L", (W * 4, W * 4), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, W * 4 - 1, W * 4 - 1], fill=255)
    mask = mask.resize((W, W), Image.LANCZOS)
    black = Image.new("RGB", (W, W), (0, 0, 0))
    return Image.composite(im, black, mask)


# --------------------------------------------------------------------------
#  GIF-Encoder: gemeinsame Palette + Transparenz fuer unveraenderte Pixel
# --------------------------------------------------------------------------
def save_gif(frames, durations, name, colors=96):
    path = os.path.join(OUT, name)
    # gemeinsame Palette aus einer Stichprobe der Frames
    step = max(1, len(frames) // 12)
    sample = frames[::step]
    sheet = Image.new("RGB", (W * len(sample), W))
    for i, f in enumerate(sample):
        sheet.paste(f, (i * W, 0))
    pal_img = sheet.quantize(colors=colors - 1, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = pal_img.getpalette()[: (colors - 1) * 3]
    T = colors - 1                      # Transparenz-Index
    full_pal = pal + [255, 0, 255] + [0, 0, 0] * (256 - colors)
    pal_img.putpalette(full_pal)

    idx0 = [np.array(f.quantize(palette=pal_img, dither=Image.Dither.NONE)) for f in frames]
    # identische Folge-Frames zusammenfassen (Dauer addieren)
    idx, durs = [], []
    for a_, d_ in zip(idx0, durations):
        if idx and np.array_equal(a_, idx[-1]):
            durs[-1] += d_
        else:
            idx.append(a_)
            durs.append(d_)
    durations = durs
    out = []
    prev = None
    for i, a in enumerate(idx):
        b = a.copy()
        if prev is not None:
            b[a == prev] = T
        prev = a
        im = Image.fromarray(b.astype(np.uint8), "P")
        im.putpalette(full_pal)
        im.info["transparency"] = T
        out.append(im)
    # erster Frame: keine Transparenz noetig, aber gleicher Index
    out[0].save(path, save_all=True, append_images=out[1:], duration=durations, loop=0,
                transparency=T, disposal=1, optimize=False, background=0)
    # Kontrolle: decodieren und gegen Original pruefen
    chk = Image.open(path)
    err = 0
    ref_pal = np.array(full_pal[: colors * 3]).reshape(-1, 3)
    for i in range(len(idx)):
        chk.seek(i)
        got = np.array(chk.convert("RGB"), np.int32)
        want = ref_pal[idx[i]].astype(np.int32)
        err = max(err, int(np.abs(got - want).max()))
    if shutil.which("gifsicle"):
        subprocess.run(["gifsicle", "-O3", "--no-comments", "-b", path], check=False)
    size = os.path.getsize(path)
    print(f"  {name:22s} {len(idx):3d} Frames  {size/1024:7.1f} KB  (max. Abweichung {err})")
    return path


# --------------------------------------------------------------------------
#  Szenen
# --------------------------------------------------------------------------
def scene_run(fur, wheel, name, frames=18, rot_total=60, legs_per_loop=3, k=1.24,
              sprint=False, delay=55, colors=64):
    imgs = []
    leg_amp = 2 * math.pi * R_TRACK * (rot_total / 360) / frames / 2 * (frames / legs_per_loop) / 2
    # Bodengeschwindigkeit pro Frame = Bogen/Frame; Kontakt-Halbzyklus legt 2*amp zurueck
    surf = 2 * math.pi * R_TRACK * rot_total / 360 / frames
    half_cycle_frames = frames / legs_per_loop / 2
    amp = surf * half_cycle_frames / 2 / k
    amp = min(amp, 12.5)
    rnd = random.Random(3)
    for f in range(frames):
        t = f / frames
        rot = rot_total * t
        phase = 2 * math.pi * legs_per_loop * t
        img = background(wheel)
        wheel_back(img, wheel, rot)
        wheel_rungs(img, wheel, rot)
        theta = 9 if sprint else 6
        x, y = on_track(theta)
        ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
        if sprint:
            d = ImageDraw.Draw(ov)
            for j in range(5):
                yy = 150 + j * 12 + 3 * math.sin(phase + j)
                x1 = 52 + 10 * ((f * 3 + j * 7) % 5)
                ln = 30 + 10 * ((f + j) % 3)
                d.rounded_rectangle([(x1 - ln) * S, (yy - 1.6) * S, x1 * S, (yy + 1.6) * S],
                                    radius=2 * S, fill=(255, 255, 255, 200))
        ham = hamster_side(k, fur, phase=phase, amp=amp, lift=7 if not sprint else 9,
                           bob=0, ear_back=sprint, mouth_open=sprint)
        place(ov, ham, k, x, y, theta + (3 if sprint else 0))
        if sprint:
            d = ImageDraw.Draw(ov)
            # Schweisstropfen
            sx, sy = 168, 108 + 2 * math.sin(phase * 2)
            d.ellipse([(sx - 4) * S, (sy - 2) * S, (sx + 4) * S, (sy + 7) * S], fill=hexc("#7FD3FF"))
            d.polygon([(sx - 3.6) * S, (sy + 1) * S, sx * S, (sy - 8) * S, (sx + 3.6) * S, (sy + 1) * S],
                      fill=hexc("#7FD3FF"))
            d.ellipse([(sx - 1.6) * S, (sy + 1) * S, (sx + 0.4) * S, (sy + 3.4) * S], fill=(255, 255, 255, 255))
        imgs.append(finish(img, ov, wheel_aa=False))
    return save_gif(imgs, [delay] * frames, name, colors)


def scene_sleep(fur, name, frames=24, delay=110):
    rnd = random.Random(11)
    stars = []
    while len(stars) < 16:
        x, y = rnd.uniform(28, 212), rnd.uniform(22, 120)
        if (x - C) ** 2 + (y - C) ** 2 > 105 ** 2:
            continue
        if math.hypot(x - 78, y - 62) < 30:
            continue
        stars.append((x, y, rnd.uniform(2.2, 4.2), rnd.uniform(0, 2 * math.pi)))
    k = 1.25
    fZ = [font(s) for s in (13, 17, 22)]
    imgs = []
    for f in range(frames):
        t = f / frames
        img = background(WHEEL_NIGHT, stars, t)
        d = ImageDraw.Draw(img)
        # Mond
        d.ellipse([60 * S, 44 * S, 96 * S, 80 * S], fill=hexc("#FFF2B8"))
        d.ellipse([72 * S, 38 * S, 104 * S, 72 * S], fill=hexc("#232C58"))
        glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse([50 * S, 34 * S, 106 * S, 90 * S], fill=(255, 240, 180, 40))
        glow = glow.filter(ImageFilter.GaussianBlur(6 * S))
        img = Image.alpha_composite(glow, img) if False else Image.alpha_composite(img, glow)
        wheel_back(img, WHEEL_NIGHT, 7)
        wheel_rungs(img, WHEEL_NIGHT, 7)
        breath = math.sin(2 * math.pi * t)
        ham = hamster_curled(k, fur, breath)
        x, y = on_track(0)
        place(img, ham, k, x, y, 0)
        # Zzz
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        dl = ImageDraw.Draw(lay)
        for j in range(3):
            p = (t + j / 3) % 1.0
            zx = 168 + 26 * p + 4 * math.sin(p * 6)
            zy = 150 - 70 * p
            a = int(255 * min(1, p * 4) * (1 - p) ** 0.8)
            fnt = fZ[min(2, int(p * 3))]
            dl.text((zx * S, zy * S), "Z", font=fnt, fill=(235, 240, 255, a), anchor="mm")
        img = Image.alpha_composite(img, lay)
        imgs.append(finish(img))
    return save_gif(imgs, [delay] * frames, name, colors=80)


def scene_snack(fur, wheel, name, frames=32, delay=90):
    k = 1.12
    imgs = []
    rnd = random.Random(5)
    crumbs = [(rnd.uniform(-14, 14), rnd.uniform(0, 1), rnd.uniform(1.0, 1.8)) for _ in range(5)]
    for f in range(frames):
        t = f / frames
        img = background(wheel)
        wheel_back(img, wheel, 0)
        wheel_rungs(img, wheel, 0)
        # Knabber-Rhythmus: 4 Bisse pro Loop, Backen fuellen sich und leeren sich
        bite = 0.5 + 0.5 * math.sin(2 * math.pi * 4 * t)
        cheek = 0.5 - 0.5 * math.cos(2 * math.pi * t)
        blink = f in (20, 21)
        ham = hamster_front(k, fur, cheek=cheek, blink=blink, seed_dy=-2.2 * bite,
                            seed_size=1.0, chew=0.8 * bite)
        x, y = on_track(0)
        place(img, ham, k, x, y + 1, 0)
        # kleine Herzen
        p = t
        hy = 92 - 30 * p
        a = int(255 * math.sin(math.pi * p))
        heart(img, 172 + 6 * math.sin(p * 9), hy, 7, (240, 90, 120, a))
        imgs.append(finish(img))
    return save_gif(imgs, [delay] * frames, name, colors=96)


def heart(img, x, y, r, col):
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.ellipse([(x - r) * S, (y - r * 0.8) * S, x * S, (y + r * 0.2) * S], fill=col)
    d.ellipse([x * S, (y - r * 0.8) * S, (x + r) * S, (y + r * 0.2) * S], fill=col)
    d.polygon([(x - r * 0.97) * S, (y - 0.1 * r) * S, (x + r * 0.97) * S, (y - 0.1 * r) * S, x * S, (y + r * 1.05) * S],
              fill=col)
    img.alpha_composite(lay)


def ease(u):
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, u)))


def scene_loop(fur, wheel, name):
    """Der Klassiker: zu schnell gelaufen, einmal rundherum, kurz benommen, weiter."""
    k = 1.24
    seq = []        # (rot_speed, mode, extra)
    base = 2.5      # Grad pro Frame (normales Laufen)
    # 1) normal laufen
    base = 3.4
    for i in range(8):
        seq.append(("run", base, i))
    # 2) beschleunigen
    for i in range(9):
        seq.append(("fast", base * (1 + 1.4 * i / 8), i))
    # 3) Ueberschlag: Hamster wird mitgerissen
    n_flip = 14
    for i in range(n_flip):
        seq.append(("flip", base * 2.6, i))
    # 4) auslaufen + benommen
    n_dizzy = 20
    for i in range(n_dizzy):
        seq.append(("dizzy", base * 2.4 * max(0.0, 1 - i / 7) ** 2, i))
    # 5) wieder anlaufen
    for i in range(6):
        seq.append(("restart", base * (i + 1) / 6, i))
    # Gesamtdrehung auf Vielfaches von 60 Grad bringen (Korrektur in Phase 4)
    total = sum(s for (_, s, _) in seq)
    rem = (60 - total % 60) % 60
    dz = [j for j, s in enumerate(seq) if s[0] == "dizzy" and s[1] > 0]
    wsum = sum(seq[j][1] for j in dz)
    for j in dz:
        m, s, i = seq[j]
        seq[j] = (m, s * (1 + rem / wsum), i)

    imgs, durs = [], []
    rot = 0.0
    phase = 0.0
    star_f = font(12)
    for (mode, spd, i) in seq:
        img = background(wheel)
        wheel_back(img, wheel, rot)
        wheel_rungs(img, wheel, rot)
        ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
        legs_rate = spd / base * (2 * math.pi / 6)
        if mode in ("run", "fast", "restart"):
            phase += legs_rate
            ham = hamster_side(k, fur, phase=phase, amp=8.0, lift=7 + (2 if mode == "fast" else 0),
                               bob=2.2, eye_style="wide" if (mode == "fast" and i > 5) else "open",
                               mouth_open=(mode == "fast" and i > 5), ear_back=(mode == "fast" and i > 8))
            x, y = on_track(6)
            place(ov, ham, k, x, y, 6)
            if mode == "fast" and i > 5:
                d = ImageDraw.Draw(ov)
                d.text((176 * S, 96 * S), "!", font=font(24), fill=hexc("#D83B3B"), anchor="mm")
        elif mode == "flip":
            u = ease((i + 1) / n_flip)
            th = 6 + 360 * u          # rundherum mitgerissen
            phase += legs_rate
            ham = hamster_side(k, fur, phase=phase, amp=10, lift=10, bob=0, eye_style="wide",
                               mouth_open=True, ear_back=True)
            x, y = on_track(th)
            place(ov, ham, k, x, y, th)
        else:  # dizzy
            wob = 5 * math.sin(i * 0.9) * max(0, 1 - i / n_dizzy)
            ham = hamster_side(k, fur, phase=i * 0.7, mood="sit", eye_style="dizzy")
            x, y = on_track(2)
            place(ov, ham, k, x, y, 2 + wob)
            d = ImageDraw.Draw(ov)
            for j in range(3):
                a = i * 0.55 + j * 2 * math.pi / 3
                sx = 150 + 26 * math.cos(a)
                sy = 116 + 8 * math.sin(a)
                star(d, sx, sy, 6, hexc("#FFD23F"), 5, 0.45)
                star(d, sx, sy, 2.6, hexc("#FFF7C2"), 5, 0.45)
        rot += spd
        imgs.append(finish(img, ov, wheel_aa=False))
        durs.append(55 if mode != "dizzy" else 80)
    print(f"    (Gesamtdrehung {rot:.2f} Grad)")
    return save_gif(imgs, durs, name, colors=64)


def scene_wave(fur, wheel, name, frames=28, delay=80):
    """Begruessung: Hamster von vorne winkt (fuer Boot/Startbildschirm)."""
    k = 1.12
    imgs = []
    for f in range(frames):
        t = f / frames
        img = background(wheel)
        wheel_back(img, wheel, 0)
        wheel_rungs(img, wheel, 0)
        wave = math.sin(2 * math.pi * 2 * t)
        ham = hamster_front(k, fur, cheek=0.15, blink=f in (16, 17), seed_size=0.0, chew=0, wave=wave)
        x, y = on_track(0)
        place(img, ham, k, x, y + 1, 0)
        # "Hallo!"
        a = int(255 * min(1, t * 5))
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(lay).text((120 * S, 62 * S), "Hallo!", font=font(22), fill=(110, 60, 20, a), anchor="mm")
        img = Image.alpha_composite(img, lay)
        imgs.append(finish(img))
    return save_gif(imgs, [delay] * frames, name, colors=96)


SCENES = {
    "run":    lambda: scene_run(FUR_GOLD, WHEEL_AMBER, "hami_rennt.gif"),
    "sprint": lambda: scene_run(FUR_GOLD, WHEEL_AMBER, "hami_sprint.gif", frames=18, rot_total=120,
                                legs_per_loop=4, sprint=True, delay=45),
    "snow":   lambda: scene_run(FUR_SNOW, WHEEL_MINT, "schneeflocke_rennt.gif"),
    "choc":   lambda: scene_run(FUR_CHOC, WHEEL_BERRY, "../../extras/schoko_rennt.gif"),  # Extra
    "snack":  lambda: scene_snack(FUR_GOLD, WHEEL_AMBER, "hami_snack.gif"),
    "sleep":  lambda: scene_sleep(FUR_GOLD, "hami_schlaeft.gif"),
    "loop":   lambda: scene_loop(FUR_GOLD, WHEEL_AMBER, "hami_ueberschlag.gif"),
    "hello":  lambda: scene_wave(FUR_GOLD, WHEEL_AMBER, "hami_hallo.gif"),
}

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import more_scenes  # Putzen, Gaehnen, Kaffee, Hantel, Halloween, Weihnachten
    SCENES.update(more_scenes.MORE)
    os.makedirs(OUT, exist_ok=True)
    which = sys.argv[1:] or list(SCENES)
    print("Erzeuge GIFs nach", os.path.normpath(OUT))
    for w in which:
        SCENES[w]()
