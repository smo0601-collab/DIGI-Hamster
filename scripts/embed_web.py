"""
DiGi Hami - Web-Oberflaeche in die Firmware einbetten
=====================================================

Komprimiert web/index.html mit gzip und schreibt das Ergebnis als
C-Array nach src/web_index.h. Laeuft automatisch vor jedem Build
(platformio.ini -> extra_scripts = pre:scripts/embed_web.py) und
kann auch direkt aufgerufen werden:

    python scripts/embed_web.py
"""
import gzip
import os

try:
    Import("env")  # noqa: F821  (von PlatformIO/pioarduino bereitgestellt)
    ROOT = env.subst("$PROJECT_DIR")  # noqa: F821
except NameError:
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SRC = os.path.join(ROOT, "web", "index.html")
DST = os.path.join(ROOT, "src", "web_index.h")


def embed():
    if not os.path.exists(SRC):
        print("embed_web: web/index.html fehlt - ueberspringe")
        return
    if os.path.exists(DST) and os.path.getmtime(DST) >= os.path.getmtime(SRC):
        return  # aktuell
    with open(SRC, "rb") as f:
        raw = f.read()
    gz = gzip.compress(raw, compresslevel=9, mtime=0)
    lines = []
    for i in range(0, len(gz), 20):
        lines.append("  " + ", ".join("0x%02x" % b for b in gz[i:i + 20]) + ",")
    with open(DST, "w", newline="\n") as f:
        f.write("// AUTOMATISCH ERZEUGT aus web/index.html - nicht von Hand bearbeiten!\n")
        f.write("// (scripts/embed_web.py)\n#pragma once\n#include <Arduino.h>\n\n")
        f.write("const uint32_t INDEX_HTML_GZ_LEN = %d;\n" % len(gz))
        f.write("const uint8_t INDEX_HTML_GZ[] PROGMEM = {\n")
        f.write("\n".join(lines))
        f.write("\n};\n")
    print("embed_web: web/index.html -> src/web_index.h (%d -> %d Bytes gzip)" % (len(raw), len(gz)))


embed()
