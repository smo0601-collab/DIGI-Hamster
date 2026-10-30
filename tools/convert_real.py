#!/usr/bin/env python3
"""
DiGi Hami - echtes Hamster-Video / GIF fuer das runde Display aufbereiten
=========================================================================

Macht aus einem Video oder GIF (z. B. Handyvideo deines Hamsters) ein
kompaktes 240x240-GIF:
  * mittig quadratisch zuschneiden, auf 240x240 skalieren
  * alles ausserhalb des runden Displays schwarz (spart Platz)
  * eine globale Palette + "kaum veraenderte Pixel = transparent"
    (verlustbehaftet, wie bei Videos ueblich) -> passt in den Flash

Aufruf:
  python3 tools/convert_real.py EINGABE.(mp4|mov|gif) AUSGABE.gif [--start 0] [--len 3]
      [--fps 12] [--colors 160] [--thr 700] [--zoom 1.0] [--smooth 0.6]

Videos brauchen ffmpeg im PATH. Benoetigt: Pillow, numpy
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageFilter

W = 240


def load_frames(path, start, length, fps, zoom, smooth=0.6):
    frames, durs = [], []
    if path.lower().endswith(".gif"):
        im = Image.open(path)
        t = 0
        for i in range(im.n_frames):
            im.seek(i)
            d = im.info.get("duration", 100) or 100
            if t >= start * 1000 and t < (start + length) * 1000:
                frames.append(im.convert("RGB"))
                durs.append(d)
            t += d
    else:
        tmp = tempfile.mkdtemp()
        subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(start), "-t", str(length), "-i", path,
                        "-vf", f"fps={fps}", os.path.join(tmp, "f%04d.png")], check=True)
        for n in sorted(os.listdir(tmp)):
            frames.append(Image.open(os.path.join(tmp, n)).convert("RGB"))
            durs.append(round(1000 / fps))
        shutil.rmtree(tmp)
    out = []
    for f in frames:
        w, h = f.size
        s = min(w, h) / zoom
        box = ((w - s) / 2, (h - s) / 2, (w + s) / 2, (h + s) / 2)
        g = f.resize((W, W), Image.LANCZOS, box=box)
        if smooth:
            # Rauschen/Dithering der Quelle entfernen -> deutlich kleinere GIFs
            g = g.filter(ImageFilter.MedianFilter(3)).filter(ImageFilter.GaussianBlur(smooth))
        out.append(g)
    return out, durs


def encode(frames, durs, path, colors, thr):
    yy, xx = np.mgrid[0:W, 0:W]
    outside = ((xx - W / 2 + .5) ** 2 + (yy - W / 2 + .5) ** 2) > (W / 2 + 1) ** 2
    # Palette aus allen Frames (ohne Aussenbereich) + reserviertes Schwarz
    step = max(1, len(frames) // 16)
    sheet = Image.new("RGB", (W * len(frames[::step]), W))
    for i, f in enumerate(frames[::step]):
        sheet.paste(f, (i * W, 0))
    pq = sheet.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = np.array(pq.getpalette()[: colors * 3]).reshape(-1, 3)
    pal = np.vstack([pal, [[0, 0, 0]]])
    black = len(pal) - 1
    T = len(pal)
    full = list(pal.flatten()) + [255, 0, 255]
    full += [0] * (768 - len(full))
    ref = Image.new("P", (1, 1))
    ref.putpalette(full)
    wts = np.array([2, 4, 3])
    out, prev = [], None
    for f in frames:
        idx = np.array(f.quantize(palette=pq, dither=Image.Dither.NONE)).astype(np.int32)
        idx[outside] = black
        if prev is not None:
            d = (((pal[idx] - pal[prev]) ** 2) * wts).sum(-1)
            keep = (idx != prev) & (d < thr)
            idx[keep] = prev[keep]
            enc = idx.copy()
            enc[idx == prev] = T
        else:
            enc = idx.copy()
        prev = idx
        im = Image.fromarray(enc.astype(np.uint8), "P")
        im.putpalette(full)
        out.append(im)
    out[0].save(path, save_all=True, append_images=out[1:], duration=durs, loop=0,
                transparency=T, disposal=1, optimize=False)
    if shutil.which("gifsicle"):
        subprocess.run(["gifsicle", "-O3", "-b", path], check=False)
    print(f"{path}: {len(frames)} Frames, {os.path.getsize(path) / 1024:.0f} KB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--len", type=float, default=3)
    ap.add_argument("--fps", type=float, default=12)
    ap.add_argument("--colors", type=int, default=160)
    ap.add_argument("--thr", type=int, default=700)
    ap.add_argument("--zoom", type=float, default=1.0)
    ap.add_argument("--smooth", type=float, default=0.6, help="Entrauschen (0 = aus)")
    a = ap.parse_args()
    fr, du = load_frames(a.src, a.start, a.len, a.fps, a.zoom, a.smooth)
    if not fr:
        sys.exit("Keine Frames gefunden")
    encode(fr, du, a.dst, a.colors, a.thr)
