"""
DiGi Hami - weitere Animationen (Putzen, Gaehnen, Kaffee, Hantel,
Halloween, Weihnachten). Wird von make_gifs.py importiert.
"""
import math
import random

from PIL import Image, ImageDraw

import make_gifs as M
from make_gifs import S, OUTLINE, Pen, hexc, place, on_track, finish, save_gif, background, wheel_back, \
    wheel_rungs, star, FUR_GOLD, WHEEL_AMBER

WHEEL_HALLOWEEN = dict(
    bg_in="#3B2160", bg_out="#140A28", band="#8A3B0F", rung="#F28C28",
    rung_l="#2A1206", spoke="#B8561A", spoke_l="#2A1206", hub="#F28C28",
    rim="#B24E12", bokeh=None,
)
WHEEL_XMAS = dict(
    bg_in="#24466F", bg_out="#0B1830", band="#A31616", rung="#FFFFFF",
    rung_l="#6E0B0B", spoke="#D32F2F", spoke_l="#6E0B0B", hub="#FFFFFF",
    rim="#C62828", bokeh=None,
)


def ease(u):
    u = max(0.0, min(1.0, u))
    return 0.5 - 0.5 * math.cos(math.pi * u)


def outlined_ell(pen, x, y, rx, ry, col, L, angle=0):
    pen.ell(x, y, rx, ry, L, grow=OUTLINE, angle=angle)
    pen.ell(x, y, rx, ry, col, angle=angle)


def poly(pen, pts, col, L=None, w=OUTLINE):
    P = [pen.P(*p) for p in pts]
    if L is not None:
        pen.dr.polygon(P, fill=L)
        pen.dr.line(P + [P[0]], fill=L, width=max(1, int(w * 2 * S * pen.k)), joint="curve")
    pen.dr.polygon(P, fill=col)


# ---------------------------------------------------------------------------
#  Gegenstaende (lokale Koordinaten des Hamsters)
# ---------------------------------------------------------------------------
def draw_mug(pen, mx, my, L):
    # Henkel
    pen.dr.ellipse([*pen.P(mx + 6, my - 7), *pen.P(mx + 20, my + 7)], outline=L, width=int(6.5 * S * pen.k))
    pen.dr.ellipse([*pen.P(mx + 7.5, my - 5.5), *pen.P(mx + 18.5, my + 5.5)], outline=hexc("#F4F1EC"),
                   width=int(3 * S * pen.k))
    poly(pen, [(mx - 12, my - 12), (mx + 12, my - 12), (mx + 10, my + 12), (mx - 10, my + 12)], hexc("#F4F1EC"), L)
    pen.ell(mx, my - 12, 12, 3.4, L, grow=1.0)
    pen.ell(mx, my - 12, 11, 2.8, hexc("#6B3E1F"))
    pen.ell(mx, my + 1, 4.2, 3.6, hexc("#F06292"))  # Herz-Aufdruck (vereinfacht)
    pen.ell(mx - 2.4, my - 0.6, 2.6, 2.4, hexc("#F06292"))
    pen.ell(mx + 2.4, my - 0.6, 2.6, 2.4, hexc("#F06292"))


def draw_dumbbell(pen, dx, dy, L):
    pen.cap(dx - 32, dy, dx + 32, dy, 4.2, L, grow=1.2)
    pen.cap(dx - 32, dy, dx + 32, dy, 4.2, hexc("#9EA4AE"))
    for sx in (-1, 1):
        for off, h in ((30, 13), (37, 10)):
            x = dx + sx * off
            poly(pen, [(x - 3.5, dy - h), (x + 3.5, dy - h), (x + 3.5, dy + h), (x - 3.5, dy + h)],
                 hexc("#3D4450"), L, w=1.2)


def draw_pumpkin(pen, px, py, L, glow):
    outlined_ell(pen, px, py, 17, 14, hexc("#F28C28"), L)
    for dx in (-8, 0, 8):
        pen.ell(px + dx, py, 4.5, 13, hexc("#E07A16"))
    pen.ell(px, py, 3.2, 13, hexc("#F59A3A"))
    pen.cap(px + 1, py - 14, px + 3, py - 19, 3.4, hexc("#3E7B27"))
    g = hexc("#FFE36E") if glow > 0.5 else hexc("#FFC23A")
    poly(pen, [(px - 9, py - 4), (px - 4, py - 4), (px - 6.5, py - 9)], g)
    poly(pen, [(px + 4, py - 4), (px + 9, py - 4), (px + 6.5, py - 9)], g)
    poly(pen, [(px - 9, py + 2), (px - 5, py + 6), (px - 2, py + 3), (px + 2, py + 6), (px + 5, py + 3),
               (px + 9, py + 2), (px + 5, py + 9), (px - 5, py + 9)], g)


def draw_gift(pen, gx, gy, L):
    poly(pen, [(gx - 13, gy - 9), (gx + 13, gy - 9), (gx + 13, gy + 12), (gx - 13, gy + 12)], hexc("#2E7D32"), L)
    poly(pen, [(gx - 15, gy - 15), (gx + 15, gy - 15), (gx + 15, gy - 8), (gx - 15, gy - 8)], hexc("#388E3C"), L, 1.6)
    poly(pen, [(gx - 2.5, gy - 15), (gx + 2.5, gy - 15), (gx + 2.5, gy + 12), (gx - 2.5, gy + 12)], hexc("#FFD54F"))
    pen.ell(gx - 6, gy - 18, 6, 3.6, hexc("#FFD54F"), angle=-20)
    pen.ell(gx + 6, gy - 18, 6, 3.6, hexc("#FFD54F"), angle=20)


# ---------------------------------------------------------------------------
#  Hamster von vorne mit Mimik, Armen und Accessoires
# ---------------------------------------------------------------------------
def hami_front(k, fur, eyes="open", mouth="w", yawn=0.0, paws=None, hold=None, hat=None, scarf=None,
               headband=False, cheek=0.15, blush=1.0):
    pen = Pen(k)
    L, F = hexc(fur["line"]), hexc(fur["fur"])
    CR, PK, EAR, EYE = hexc(fur["cream"]), hexc(fur["pink"]), hexc(fur["ear"]), hexc(fur["eye"])
    cr = 9 + 6 * cheek
    chest = [(-8.5, -53), (8.5, -53)]
    paws = paws or chest
    shoulders = [(-24, -52), (24, -52)]

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
    pen.ell(0, -32, 28, 27, CR)
    pen.ell(0, -67, 19, 13, CR)
    if scarf:
        c1, c2 = hexc(scarf[0]), hexc(scarf[1])
        pen.cap(-27, -52, 27, -52, 11, L, grow=OUTLINE)
        pen.cap(-27, -52, 27, -52, 11, c1)
        for x in range(-22, 26, 10):
            pen.line([(x, -57), (x + 4, -47)], c2, 2.6)
        pen.cap(14, -50, 20, -28, 9, L, grow=OUTLINE)
        pen.cap(14, -50, 20, -28, 9, c1)
        pen.line([(15, -42), (20, -40)], c2, 2.4)
    # Augen
    for ex in (-12.5, 12.5):
        if eyes == "open":
            pen.ell(ex, -84, 4.9, 5.4, EYE)
            pen.ell(ex + 1.6, -86, 1.9, 1.9, (255, 255, 255, 255))
        elif eyes == "closed":
            pen.arc(ex, -86, 4.6, 20, 160, L, 1.9)
        elif eyes == "happy":
            pen.arc(ex, -82, 4.6, 200, 340, L, 2.0)
        elif eyes == "half":
            pen.ell(ex, -83, 4.9, 4.4, EYE)
            pen.ell(ex, -87.5, 6.2, 3.6, F)
            pen.line([(ex - 5.5, -85.2), (ex + 5.5, -85.2)], L, 1.6)
        elif eyes == "squeeze":
            s = 1 if ex < 0 else -1
            pen.line([(ex - 4 * s, -88), (ex + 4 * s, -84), (ex - 4 * s, -80)], L, 1.9)
    if blush:
        pen.ell(-24 - cheek * 2, -70, 6 + 2 * cheek, 4.2, hexc(fur["pink"], int(140 * blush)))
        pen.ell(24 + cheek * 2, -70, 6 + 2 * cheek, 4.2, hexc(fur["pink"], int(140 * blush)))
    pen.ell(0, -73.5 - 1.5 * yawn, 3.6, 2.9, PK)
    if yawn > 0.05:
        ry = 2.5 + 8.5 * yawn
        pen.ell(0, -63 + 1.5 * yawn, 5 + 3 * yawn, ry, L, grow=0.8)
        pen.ell(0, -63 + 1.5 * yawn, 5 + 3 * yawn, ry, hexc("#7A2630"))
        pen.ell(0, -63 + 1.5 * yawn + ry * 0.45, 3.6 + 2 * yawn, ry * 0.45, hexc("#F48FA0"))
    elif mouth == "open":
        pen.ell(0, -65, 3.2, 2.8, L)
        pen.ell(0, -64.4, 2.1, 1.5, PK)
    else:
        pen.arc(-2.6, -69, 2.6, 20, 160, L, 1.3)
        pen.arc(2.6, -69, 2.6, 20, 160, L, 1.3)
    if headband:
        pen.cap(-31, -93, 31, -93, 7.5, L, grow=OUTLINE)
        pen.cap(-31, -93, 31, -93, 7.5, hexc("#E53935"))
        pen.line([(-30, -93), (-41, -86)], hexc("#E53935"), 3.2)
        pen.line([(-30, -93), (-40, -97)], hexc("#E53935"), 3.2)
        pen.line([(-25, -91.5), (25, -91.5)], hexc("#FFFFFF", 160), 1.2)
    if hat == "santa":
        poly(pen, [(-33, -101), (31, -106), (30, -126), (16, -146), (36, -152), (10, -130), (-10, -122)],
             hexc("#D32F2F"), L)
        outlined_ell(pen, 36, -150, 6.5, 6.5, hexc("#FFFFFF"), L)
        pen.cap(-33, -103, 31, -107, 10, L, grow=OUTLINE)
        pen.cap(-33, -103, 31, -107, 10, hexc("#FAFAFA"))
    elif hat == "witch":
        poly(pen, [(-19, -110), (21, -110), (14, -130), (16, -146), (32, -160), (6, -150), (-4, -132)],
             hexc("#2B1B3D"), L)
        pen.ell(0, -108, 40, 7.5, L, grow=OUTLINE)
        pen.ell(0, -108, 40, 7.5, hexc("#3A2552"))
        poly(pen, [(-18, -117), (19, -117), (20.5, -111), (-19.5, -111)], hexc("#8E44AD"))
        poly(pen, [(-4, -118), (4, -118), (4, -110), (-4, -110)], hexc("#F4C542"))
        poly(pen, [(-2, -116), (2, -116), (2, -112), (-2, -112)], hexc("#8E44AD"))
    # Gegenstand in den Pfoten
    if hold:
        hold(pen, L)
    # Arme + Pfoten
    for i, (px, py) in enumerate(paws):
        dx0, dy0 = chest[i]
        if math.hypot(px - dx0, py - dy0) > 9:
            sx, sy = shoulders[i]
            pen.cap(sx, sy, px, py, 10.5, L, grow=OUTLINE)
            pen.cap(sx, sy, px, py, 10.5, F)
        outlined_ell(pen, px, py, 5.6, 5.2, PK, L)
    return pen.img


def to_screen(x, y, k, lx, ly):
    return x + lx * k, y + ly * k


# ---------------------------------------------------------------------------
#  Szenen
# ---------------------------------------------------------------------------
K = 1.12


def scene_groom(fur=FUR_GOLD, wheel=WHEEL_AMBER, name="../../extras/mehr/hami_putzt.gif", frames=24, delay=70):
    imgs = []
    for f in range(frames):
        t = f / frames
        a = 2 * math.pi * 2 * t
        img = background(wheel)
        wheel_back(img, wheel, 0)
        wheel_rungs(img, wheel, 0)
        # Pfoten reiben kreisend ueber Schnauze und Baeckchen
        paws = [(-11 + 3.5 * math.cos(a), -68 + 4 * math.sin(a)),
                (11 - 3.5 * math.cos(a), -68 + 4 * math.sin(a + math.pi))]
        ham = hami_front(K, fur, eyes="happy", paws=paws, cheek=0.1)
        x, y = on_track(0)
        place(img, ham, K, x, y + 1, 3 * math.sin(2 * math.pi * t))
        d = ImageDraw.Draw(img)
        for j, (sx, sy) in enumerate(((70, 70), (172, 84), (160, 52))):
            p = (t * 2 + j / 3) % 1
            r = 7 * math.sin(math.pi * p)
            if r > 0.6:
                star(d, sx, sy, r, hexc("#FFF3B0"), 4, 0.3)
        imgs.append(finish(img))
    return save_gif(imgs, [delay] * frames, name, colors=80)


def scene_yawn(fur=FUR_GOLD, wheel=WHEEL_AMBER, name="../../extras/mehr/hami_gaehnt.gif", frames=32, delay=90):
    imgs = []
    for f in range(frames):
        t = f / frames
        if t < 0.15:
            o = 0.0
        elif t < 0.45:
            o = ease((t - 0.15) / 0.3)
        elif t < 0.6:
            o = 1.0
        elif t < 0.78:
            o = 1 - ease((t - 0.6) / 0.18)
        else:
            o = 0.0
        shake = 1.5 * math.sin(f * 2.1) if 0.45 <= t < 0.6 else 0
        ry = -53 - 56 * o
        paws = [(-8.5 - 30 * o, ry), (8.5 + 30 * o, ry)]
        eyes = "squeeze" if o > 0.55 else ("closed" if o > 0.2 or f in (28, 29) else "open")
        ham = hami_front(K, fur, eyes=eyes, yawn=o, paws=paws, cheek=0.1)
        img = background(wheel)
        wheel_back(img, wheel, 0)
        wheel_rungs(img, wheel, 0)
        x, y = on_track(0)
        place(img, ham, K, x + shake, y + 1, 0)
        imgs.append(finish(img))
    return save_gif(imgs, [delay] * frames, name, colors=80)


def scene_coffee(fur=FUR_GOLD, wheel=WHEEL_AMBER, name="../../extras/mehr/hami_kaffee.gif", frames=36, delay=90):
    imgs = []
    for f in range(frames):
        t = f / frames
        sip = ease((t - 0.3) / 0.12) - ease((t - 0.6) / 0.12)
        my = -50 - 14 * sip
        eyes = "happy" if sip > 0.4 else ("open" if 0.72 < t < 0.95 else "half")
        if f in (10, 11):
            eyes = "closed"
        ham = hami_front(K, fur, eyes=eyes, paws=[(-12, my + 2), (10, my + 4)],
                         hold=lambda pen, L, my=my: draw_mug(pen, 0, my, L), cheek=0.12)
        img = background(wheel)
        wheel_back(img, wheel, 0)
        wheel_rungs(img, wheel, 0)
        x, y = on_track(0)
        place(img, ham, K, x, y + 1, 0)
        # Dampf
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        dl = ImageDraw.Draw(lay)
        mx, mtop = to_screen(x, y + 1, K, 0, my - 14)
        for j in range(3):
            p = (t * 2 + j / 3) % 1
            al = int(200 * math.sin(math.pi * p) * (1 - sip))
            if al < 10:
                continue
            pts = []
            for i in range(12):
                u = i / 11
                yy = mtop - 4 - u * 18 - p * 22
                xx = mx + (j - 1) * 6 + 3.5 * math.sin(u * 5 + p * 6 + j)
                pts.append((xx * S, yy * S))
            dl.line(pts, fill=(255, 255, 255, al), width=int(2.2 * S), joint="curve")
        img = Image.alpha_composite(img, lay)
        if 0.72 < t < 0.95:  # wach!
            d = ImageDraw.Draw(img)
            p = (t - 0.72) / 0.23
            star(d, 74, 76, 7 * math.sin(math.pi * p), hexc("#FFE36E"), 4, 0.3)
            star(d, 166, 70, 6 * math.sin(math.pi * p), hexc("#FFE36E"), 4, 0.3)
        imgs.append(finish(img))
    return save_gif(imgs, [delay] * frames, name, colors=96)


def scene_workout(fur=FUR_GOLD, wheel=WHEEL_AMBER, name="../../extras/mehr/hami_hantel.gif", frames=28, delay=70):
    imgs = []
    for f in range(frames):
        t = f / frames
        u = 0.5 - 0.5 * math.cos(2 * math.pi * 2 * t)  # zwei Wiederholungen
        dy = -50 - 80 * u
        top = u > 0.75
        ham = hami_front(K, fur, eyes="squeeze" if top else "open", mouth="open" if top else "w",
                         paws=[(-23, dy), (23, dy)], hold=lambda pen, L, dy=dy: draw_dumbbell(pen, 0, dy, L),
                         headband=True, cheek=0.35 * u, blush=0.6 + 0.6 * u)
        img = background(wheel)
        wheel_back(img, wheel, 0)
        wheel_rungs(img, wheel, 0)
        x, y = on_track(0)
        place(img, ham, K, x, y + 1 + 1.5 * u, 0)
        d = ImageDraw.Draw(img)
        if u > 0.4:  # Schweisstropfen
            sx, sy = 160, 120 + 10 * ((t * 4) % 1)
            d.ellipse([(sx - 3.6) * S, (sy - 1.5) * S, (sx + 3.6) * S, (sy + 6) * S], fill=hexc("#7FD3FF"))
            d.polygon([(sx - 3.2) * S, (sy + 1) * S, sx * S, (sy - 7) * S, (sx + 3.2) * S, (sy + 1) * S],
                      fill=hexc("#7FD3FF"))
        imgs.append(finish(img))
    return save_gif(imgs, [delay] * frames, name, colors=96)


def bat(d, x, y, flap, sc=1.0):
    w = 15 * sc
    tip = -7 * sc if flap else 5 * sc
    col = hexc("#1A0F24")
    d.polygon([((x - w) * S, (y + tip) * S), ((x - w * 0.55) * S, (y - 2 * sc) * S), ((x - 3 * sc) * S, y * S),
               ((x - w * 0.6) * S, (y + 4 * sc) * S)], fill=col)
    d.polygon([((x + w) * S, (y + tip) * S), ((x + w * 0.55) * S, (y - 2 * sc) * S), ((x + 3 * sc) * S, y * S),
               ((x + w * 0.6) * S, (y + 4 * sc) * S)], fill=col)
    d.ellipse([(x - 4 * sc) * S, (y - 4 * sc) * S, (x + 4 * sc) * S, (y + 5 * sc) * S], fill=col)
    d.polygon([((x - 3.5 * sc) * S, (y - 2 * sc) * S), ((x - 2.5 * sc) * S, (y - 7 * sc) * S),
               ((x - 1 * sc) * S, (y - 3 * sc) * S)], fill=col)
    d.polygon([((x + 3.5 * sc) * S, (y - 2 * sc) * S), ((x + 2.5 * sc) * S, (y - 7 * sc) * S),
               ((x + 1 * sc) * S, (y - 3 * sc) * S)], fill=col)


def scene_halloween(fur=FUR_GOLD, name="../../extras/mehr/hami_halloween.gif", frames=24, delay=100):
    wheel = WHEEL_HALLOWEEN
    rnd = random.Random(31)
    stars = [(rnd.uniform(110, 210), rnd.uniform(30, 110), rnd.uniform(1.8, 3.2), rnd.uniform(0, 6.3))
             for _ in range(8)]
    imgs = []
    for f in range(frames):
        t = f / frames
        img = background(wheel, stars, t)
        d = ImageDraw.Draw(img)
        glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse([44 * S, 38 * S, 104 * S, 98 * S], fill=(255, 220, 140, 50))
        img = Image.alpha_composite(img, glow)
        d = ImageDraw.Draw(img)
        d.ellipse([54 * S, 48 * S, 94 * S, 88 * S], fill=hexc("#FFE9A8"))
        d.ellipse([62 * S, 58 * S, 70 * S, 64 * S], fill=hexc("#F2D88A"))
        wheel_back(img, wheel, 0)
        wheel_rungs(img, wheel, 0)
        flick = 0.5 + 0.5 * math.sin(f * 1.7) * math.sin(f * 0.6 + 1)
        ham = hami_front(K, fur, eyes="closed" if f in (14, 15) else "open", hat="witch",
                         paws=[(-15, -50), (15, -50)], hold=lambda pen, L: draw_pumpkin(pen, 0, -50, L, flick),
                         cheek=0.1)
        x, y = on_track(0)
        place(img, ham, K, x, y + 1, 0)
        d = ImageDraw.Draw(img)
        for j, (yy, ph, sc) in enumerate(((58, 0.0, 1.0), (92, 0.5, 0.75))):
            p = (t + ph) % 1
            bx = -20 + 280 * p
            by = yy + 8 * math.sin(p * 2 * math.pi * 2 + j)
            bat(d, bx, by, (f + j) % 2 == 0, sc)
        imgs.append(finish(img))
    return save_gif(imgs, [delay] * frames, name, colors=96)


def scene_xmas(fur=FUR_GOLD, name="../../extras/mehr/hami_weihnachten.gif", frames=30, delay=100):
    wheel = WHEEL_XMAS
    rnd = random.Random(12)
    flakes = [(rnd.uniform(10, 230), rnd.uniform(0, 260), rnd.uniform(1.2, 2.6), rnd.uniform(0, 6.3),
               rnd.choice((1, 2))) for _ in range(34)]
    imgs = []
    for f in range(frames):
        t = f / frames
        img = background(wheel)
        wheel_back(img, wheel, 0)
        wheel_rungs(img, wheel, 0)
        ham = hami_front(K, fur, eyes="closed" if f in (20, 21) else "happy" if 8 <= f < 16 else "open",
                         hat="santa", scarf=("#2E7D32", "#C8E6C9"), paws=[(-15, -44), (15, -44)],
                         hold=lambda pen, L: draw_gift(pen, 0, -42, L), cheek=0.15)
        x, y = on_track(0)
        place(img, ham, K, x, y + 1, 0)
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        dl = ImageDraw.Draw(lay)
        for (fx, fy, r, ph, sp) in flakes:
            yy = (fy + t * 260 * sp) % 260 - 10
            xx = fx + 5 * math.sin(t * 2 * math.pi * sp + ph)
            dl.ellipse([(xx - r) * S, (yy - r) * S, (xx + r) * S, (yy + r) * S], fill=(255, 255, 255, 235))
        img = Image.alpha_composite(img, lay)
        imgs.append(finish(img))
    return save_gif(imgs, [delay] * frames, name, colors=96)


MORE = {
    "putzt": lambda: scene_groom(),
    "gaehnt": lambda: scene_yawn(),
    "kaffee": lambda: scene_coffee(),
    "hantel": lambda: scene_workout(),
    "halloween": lambda: scene_halloween(),
    "weihnachten": lambda: scene_xmas(),
}
