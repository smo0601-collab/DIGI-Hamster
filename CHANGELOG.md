# Änderungen

## v2.0.0

Komplett neu geschriebene Firmware für ESP32-C3 Super Mini + GC9A01 (gleiche Verkabelung wie v1.0).

**Neu**
- Web-Oberfläche (Deutsch, Handy und PC, Hell- und Dunkelmodus): Animationen hochladen, abspielen, löschen; Playlist; Tempo, Helligkeit, Drehung; Nachtruhe; WLAN; Geräte-Infos
- Hochladen von GIFs, Bildern und **Handyvideos**: Umrechnung auf 240 × 240 direkt im Browser
- WLAN-Einrichtung per Hotspot, Captive Portal und QR-Code auf dem Display; erreichbar unter `http://digihami.local`
- 14 Animationen: rennt, sprintet, Überschlag, Snack, schläft, Hallo, Schneeflocke, echter Hamster, putzt sich, gähnt, Kaffeepause, Training, Halloween, Weihnachten (+ Extras)
- Nachtruhe mit Schlaf-Animation, Dimmen oder Display aus (Uhrzeit per NTP)
- Kilometerzähler, BOOT-Taste als Bedienknopf, Firmware-Update per WLAN (PlatformIO-Variante)
- Arduino-IDE-Sketch mit gleichem Code (`arduino/DiGi_Hami/`)
- Generator für eigene Animationen (`tools/make_gifs.py`) und Video-Umwandlung (`tools/convert_real.py`)

**Technik**
- LovyanGFX mit DMA statt Adafruit GFX; Animation läuft in eigenem FreeRTOS-Task mit Vorrang vor dem Webserver
- LittleFS statt SPIFFS
- Umgehung eines Fehlers in AnimatedGIF 2.2.0 (transparente Pixel im „cooked“-Modus); zweiter Zeichenpfad für GIFs mit lokalen Farbpaletten
- WLAN-Sendeleistung einstellbar (Standard 8,5 dBm wegen der Antenne der C3 Super Mini)
