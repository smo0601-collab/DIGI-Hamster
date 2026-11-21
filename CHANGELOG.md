# Änderungen

## v2.3.0

**Neu**
- **Uhr mit Datum:** große Uhrzeit, Wochentag und Datum im Hamsterrad, die Sekunden füllen die Sprossen, unten läuft Hami
- Uhr-Modus in der Web-Oberfläche (*Wiedergabe → Uhr*): **Aus**, **Im Wechsel** mit den Animationen (Standard, 60 s) oder **Immer**
- Knopf **Uhr zeigen** in der Web-Oberfläche, Vorschau zeigt die Uhr mit an
- neuer API-Aufruf `POST /api/clock`

Update über die Web-Oberfläche mit `DiGi-Hami-Update-v2.3.0.bin` (ab v2.2.0 mit „Custom“-Partitionen).

## v2.2.0

**Neu**
- Firmware-Updates über die Web-Oberfläche auch für die Arduino-IDE-Variante: gemeinsame `partitions.csv` mit zwei Firmware-Plätzen (Arduino IDE: *Partition Scheme „Custom“*)
- Die Web-Oberfläche prüft die Update-Datei vor dem Hochladen: erkennt DiGi-Hami-Firmware und ihre Version, lehnt Komplett-Datei, Animationen-Image und Firmware für andere Chips ab
- Releases auf GitHub mit `DiGi-Hami-Update-v….bin`, Komplett-Firmware, Animationen-Image und Arduino-Sketch; werden automatisch veröffentlicht, wenn die Version steigt
- 13 Animationen vorinstalliert (inkl. Putzen, Gähnen, Kaffee, Training, Halloween, Weihnachten); der Überschlag liegt in `extras/`

**Wichtig:** Geräte mit älterem Speicherlayout (Arduino „No OTA“ oder v2.0/v2.1 per PlatformIO) einmal per USB neu flashen, inkl. Dateisystem. Danach gehen Updates über WLAN.

## v2.1.0

**Neu**
- Zugriffsschutz für die Web-Oberfläche: Benutzer `admin`, Passwort unter *System → Zugriffsschutz* festlegen (ab Werk leer = kein Schutz). Schützt Seite, API, Uploads, Firmware-Update und GIF-Dateien.
- BOOT-Taste 10 s löscht jetzt zusätzlich das Web-Passwort (falls vergessen).
- Neuer API-Aufruf `POST /api/password`.

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
