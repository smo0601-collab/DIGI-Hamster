#!/usr/bin/env python3
"""
DiGi Hami - Grafiken fuer die Uhr erzeugen  ->  src/clock_assets.h
==================================================================

* drei geglaettete Schriften im VLW-Format (LovyanGFX loadFont):
    CLOCK_FONT_TIME  grosse Ziffern fuer die Uhrzeit
    CLOCK_FONT_DAY   Wochentag (fett)
    CLOCK_FONT_DATE  Datum (normal, mit Umlauten fuer "Maerz")
* kleine Laufanimation des Hamsters (GIF, transparenter Hintergrund,
  jedes Bild vollstaendig) + Position auf dem Display

Aufruf:  python3 tools/make_clock_assets.py
Benoetigt: Pillow, numpy, DejaVu-Schriften (DejaVuSans.ttf / -Bold.ttf)
"""
import io
import math
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_gifs as M  # noqa: E402

ROOT = os.path.dirname(HERE)
DST = os.path.join(ROOT, "src", "clock_assets.h")

FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "C:/Windows/Fonts", "/Library/Fonts"]
CREAM = (0xFC, 0xEB, 0xCB)   # Innenflaeche des Rads (WHEEL_AMBER bg)
HAM_K = 0.82                 # Groesse des Hamsters
HAM_THETA = 6                # Position auf der Laufflaeche (Grad)
HAM_FRAMES = 8


def find_font(name):
    for d in FONT_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    sys.exit("Schrift nicht gefunden: " + name)


def vlw(ttf, size, chars):
    """Erzeugt eine VLW-Schrift (Processing-Format, 8 bit Alpha)."""
    font = ImageFont.truetype(ttf, size)
    ascent, descent = font.getmetrics()
    glyphs = []
    for ch in sorted(set(chars), key=ord):
        adv = int(round(font.getlength(ch)))
        if ch == " ":
            glyphs.append((ord(ch), 0, 0, adv, 0, 0, b""))
            continue
        x0, y0, x1, y1 = font.getbbox(ch, anchor="ls")
        w, h = x1 - x0, y1 - y0
        img = Image.new("L", (w, h), 0)
        from PIL import ImageDraw
        ImageDraw.Draw(img).text((-x0, -y0), ch, font=font, fill=255, anchor="ls")
        glyphs.append((ord(ch), h, w, adv, -y0, x0, img.tobytes()))
    out = io.BytesIO()
    out.write(struct.pack(">6i", len(glyphs), 11, size, 0, ascent, descent))
    for (u, h, w, adv, dy, dx, _) in glyphs:
        out.write(struct.pack(">7i", u, h, w, adv, dy, dx, 0))
    for g in glyphs:
        out.write(g[6])
    return out.getvalue()


def hamster_gif():
    """Laufender Hamster auf Creme, Creme -> transparent, auf Inhalt beschnitten."""
    S = M.S
    frames = []
    for f in range(HAM_FRAMES):
        img = Image.new("RGBA", (240 * S, 240 * S), CREAM + (255,))
        ham = M.hamster_side(HAM_K, M.FUR_GOLD, phase=2 * math.pi * f / HAM_FRAMES, amp=7.0, lift=6, bob=0)
        x, y = M.on_track(HAM_THETA)
        M.place(img, ham, HAM_K, x, y, HAM_THETA)
        frames.append(np.array(img.convert("RGB").resize((240, 240), Image.LANCZOS)))
    diff = np.zeros((240, 240), bool)
    for a in frames:
        diff |= np.any(np.abs(a.astype(int) - np.array(CREAM)) > 6, axis=2)
    ys, xs = np.nonzero(diff)
    x0, y0, x1, y1 = xs.min() - 1, ys.min() - 1, xs.max() + 2, ys.max() + 2
    crops = [Image.fromarray(a[y0:y1, x0:x1]) for a in frames]
    # gemeinsame Palette, Index 0 = transparent (Creme)
    sheet = Image.new("RGB", (crops[0].width * len(crops), crops[0].height))
    for i, c in enumerate(crops):
        sheet.paste(c, (i * c.width, 0))
    pq = sheet.quantize(colors=31, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = pq.getpalette()[:31 * 3]
    full = list(CREAM) + pal + [0] * (768 - 3 - len(pal))
    out = []
    for c, a in zip(crops, frames):
        idx = np.array(c.quantize(palette=pq, dither=Image.Dither.NONE)).astype(np.uint8) + 1
        cream = np.all(np.abs(np.array(c).astype(int) - np.array(CREAM)) <= 6, axis=2)
        idx[cream] = 0
        im = Image.fromarray(idx, "P")
        im.putpalette(full)
        out.append(im)
    buf = io.BytesIO()
    out[0].save(buf, "GIF", save_all=True, append_images=out[1:], duration=70, loop=0,
                transparency=0, disposal=2, optimize=False)
    return buf.getvalue(), int(x0), int(y0), int(x1 - x0), int(y1 - y0)


def c_array(name, data):
    lines = []
    for i in range(0, len(data), 20):
        lines.append("  " + ", ".join("0x%02x" % b for b in data[i:i + 20]) + ",")
    return ("const uint32_t %s_LEN = %d;\nconst uint8_t %s[] PROGMEM = {\n%s\n};\n\n"
            % (name, len(data), name, "\n".join(lines)))


def main():
    bold = find_font("DejaVuSans-Bold.ttf")
    reg = find_font("DejaVuSans.ttf")
    # nur die Zeichen, die die Uhr wirklich braucht (spart Flash)
    tage = "Sonntag Montag Dienstag Mittwoch Donnerstag Freitag Samstag"
    monate = "Januar Februar März April Mai Juni Juli August September Oktober November Dezember"
    f_time = vlw(bold, 46, "0123456789:- ")
    f_day = vlw(bold, 15, tage)
    f_date = vlw(reg, 15, monate + "0123456789. " + "Uhrzeit fehlt WLAN verbinden")
    gif, hx, hy, hw, hh = hamster_gif()
    with open(DST, "w", newline="\n") as f:
        f.write("// AUTOMATISCH ERZEUGT von tools/make_clock_assets.py - nicht von Hand bearbeiten!\n")
        f.write("#pragma once\n#include <Arduino.h>\n\n")
        f.write("// Laufender Hamster fuer die Uhr: Position und Groesse auf dem Display\n")
        f.write("#define CLOCK_HAM_X %d\n#define CLOCK_HAM_Y %d\n#define CLOCK_HAM_W %d\n#define CLOCK_HAM_H %d\n\n"
                % (hx, hy, hw, hh))
        f.write(c_array("CLOCK_HAMSTER_GIF", gif))
        f.write(c_array("CLOCK_FONT_TIME", f_time))
        f.write(c_array("CLOCK_FONT_DAY", f_day))
        f.write(c_array("CLOCK_FONT_DATE", f_date))
    print("clock_assets.h: Hamster %dx%d bei (%d,%d), GIF %d B, Schriften %d/%d/%d B"
          % (hw, hh, hx, hy, len(gif), len(f_time), len(f_day), len(f_date)))


if __name__ == "__main__":
    main()
