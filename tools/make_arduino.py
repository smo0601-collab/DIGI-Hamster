#!/usr/bin/env python3
"""
DiGi Hami - Arduino-IDE-Sketch aus den PlatformIO-Quellen erzeugen
==================================================================

Kopiert src/ + data/ nach arduino/DiGi_Hami/, damit beide Varianten immer
denselben Code haben:

    src/main.cpp      -> arduino/DiGi_Hami/DiGi_Hami.ino
    src/*.h, *.cpp    -> arduino/DiGi_Hami/
    data/gifs/*.gif   -> arduino/DiGi_Hami/data/gifs/

Vorher die Web-Oberflaeche einbetten:  python3 scripts/embed_web.py
"""
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
DST = os.path.join(ROOT, "arduino", "DiGi_Hami")

HEADER = """// ============================================================================
//  DiGi Hami v2 - Arduino-IDE-Version
//  (automatisch erzeugt aus src/main.cpp - Anleitung: ANLEITUNG.md)
//
//  Werkzeuge-Menue:
//    Board ............... ESP32C3 Dev Module
//    USB CDC On Boot ..... Enabled
//    Partition Scheme .... No OTA (2MB APP/2MB SPIFFS)
//  Bibliotheken (Bibliotheksverwalter):
//    LovyanGFX, AnimatedGIF, ArduinoJson
//  Einstellungen (Pins, Helligkeit, SPI-Takt ...): config.h
// ============================================================================
"""


def main():
    if os.path.isdir(DST):
        for n in os.listdir(DST):
            p = os.path.join(DST, n)
            if n.endswith((".h", ".cpp", ".ino")):
                os.remove(p)
    os.makedirs(DST, exist_ok=True)
    for n in sorted(os.listdir(SRC)):
        s = os.path.join(SRC, n)
        if n == "main.cpp":
            with open(s, encoding="utf-8") as f:
                code = f.read()
            with open(os.path.join(DST, "DiGi_Hami.ino"), "w", encoding="utf-8", newline="\n") as f:
                f.write(HEADER + code)
        elif n.endswith((".h", ".cpp")):
            shutil.copy(s, DST)
    gd = os.path.join(DST, "data", "gifs")
    if os.path.isdir(gd):
        shutil.rmtree(gd)
    shutil.copytree(os.path.join(ROOT, "data", "gifs"), gd)
    # Mit "No OTA" hat die Arduino-Variante ~1,9 MB Platz -> zusaetzliche Animationen gleich mitnehmen
    mehr = os.path.join(ROOT, "extras", "mehr")
    if os.path.isdir(mehr):
        for n in sorted(os.listdir(mehr)):
            if n.endswith(".gif"):
                shutil.copy(os.path.join(mehr, n), gd)
    print("Arduino-Sketch aktualisiert:", DST)


if __name__ == "__main__":
    main()
