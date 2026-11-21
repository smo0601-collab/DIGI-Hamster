# DiGi Hami v2 mit der Arduino IDE

Dieser Ordner enthält DiGi Hami v2 als fertigen **Arduino-Sketch** (`DiGi_Hami/`). Der Code ist identisch mit der PlatformIO-Version, nur so angeordnet, wie die Arduino IDE es erwartet:

```
DiGi_Hami/
├── DiGi_Hami.ino      Hauptprogramm (setup/loop, BOOT-Taste)
├── config.h           ← Einstellungen: Pins, SPI-Takt, Backlight-Pin, WLAN-Sendeleistung
├── display.h          Display-Treiber (LovyanGFX, GC9A01)
├── player.cpp/.h      GIF-Wiedergabe
├── net.cpp/.h         WLAN, Web-Server, API
├── settings.cpp/.h    Einstellungen speichern
├── web_index.h        Web-Oberfläche (fertig eingebettet)
├── partitions.csv     Speicheraufteilung (wird mit „Custom“ automatisch benutzt)
└── data/gifs/         die 13 vorinstallierten Animationen (~1 MB)
```

Getestet mit **Arduino-ESP32-Core 3.3.12**. Mit diesem Core kompiliert der Sketch ohne Warnungen: 1,31 MB Programm, 140 KB RAM.

---

## 1. Arduino IDE vorbereiten (einmalig)

1. **Arduino IDE 2** installieren (ab Version 2.2.1): https://www.arduino.cc/en/software
2. **ESP32-Boards hinzufügen:** *Datei → Einstellungen → Zusätzliche Boardverwalter-URLs*:
   ```
   https://espressif.github.io/arduino-esp32/package_esp32_index.json
   ```
   Dann *Werkzeuge → Board → Boardverwalter*, nach **esp32** suchen und **„esp32 by Espressif Systems“** installieren, **Version 3.x** (nicht 2.x!).
3. **Bibliotheken installieren:** *Werkzeuge → Bibliotheken verwalten*, jeweils suchen und installieren:
   | Bibliothek | Autor | Version |
   |---|---|---|
   | **LovyanGFX** | lovyan03 | neueste (mindestens 1.2.19) |
   | **AnimatedGIF** | Larry Bank | neueste (mindestens 2.2.0) |
   | **ArduinoJson** | Benoit Blanchon | 7.x |

   > Die Arduino IDE fragt manchmal, ob abhängige Bibliotheken mit installiert werden sollen, dann „Alle installieren“. **Nicht** zusätzlich „Adafruit GC9A01A“ oder „TFT_eSPI“ nötig.

4. **LittleFS-Upload-Plugin** (für die Animationen):
   - Die `.vsix`-Datei von https://github.com/earlephilhower/arduino-littlefs-upload/releases herunterladen.
   - Windows: in `C:\Users\<Name>\.arduinoIDE\plugins\` legen (Ordner `plugins` ggf. anlegen).
   - macOS / Linux: in `~/.arduinoIDE/plugins/` legen.
   - Arduino IDE neu starten.

   Ohne Plugin geht es auch: Dann lädst du die GIFs später einfach über die Web-Oberfläche hoch (siehe Schritt 4b).

---

## 2. Sketch öffnen und Werkzeuge einstellen

1. Den Ordner `DiGi_Hami` an einen beliebigen Ort kopieren (z. B. in deinen Sketchbook-Ordner) und `DiGi_Hami.ino` öffnen.
   Der Ordner muss genau so heißen wie die `.ino`-Datei.
2. ESP32-C3 per USB-C anstecken und im Menü **Werkzeuge** einstellen:

| Einstellung | Wert |
|---|---|
| **Board** | **ESP32C3 Dev Module** |
| **Port** | der Port des Boards (z. B. `COM5` bzw. `/dev/ttyACM0`) |
| **USB CDC On Boot** | **Enabled** ← wichtig, sonst kein Serial-Monitor |
| **Partition Scheme** | **Custom** ← wichtig |
| CPU Frequency | 160MHz (WiFi) |
| Flash Size | 4MB |
| Flash Mode | QIO (bei Startproblemen: DIO) |
| Upload Speed | 921600 |

> **Warum „Custom“?** Damit nimmt die Arduino IDE die Datei `partitions.csv` aus dem Sketch-Ordner: zwei Firmware-Plätze à 1,375 MB (für Updates über die Web-Oberfläche) und 1,19 MB für Animationen. Auch das LittleFS-Plugin richtet sich automatisch danach. Mit den Standardschemata passt die Firmware (~1,31 MB) nicht oder es gibt keine Updates über WLAN.
>
> **Vorher mit „No OTA“ geflasht?** Dann einmal mit „Custom“ hochladen **und** danach „Upload LittleFS“ ausführen; das Dateisystem liegt jetzt an einer anderen Stelle. Selbst hochgeladene GIFs vorher sichern.

---

## 3. Hochladen

1. **Hochladen** klicken (Pfeil nach rechts). Der erste Durchlauf dauert ein paar Minuten, weil LovyanGFX groß ist.
2. Bei „No serial port“ oder hängendem Upload: **BOOT** gedrückt halten, **RESET** kurz drücken, BOOT loslassen, nochmal hochladen.

## 4a. Animationen hochladen (mit Plugin)

1. **Serial-Monitor schließen** (sonst schlägt der Upload fehl).
2. `Strg + Umschalt + P` (macOS: `⌘ + Umschalt + P`) drücken, **„Upload LittleFS to Pico/ESP8266/ESP32“** eingeben und auswählen.
3. Warten bis „Completed upload“. Das Plugin lädt den Ordner `data/` (mit `gifs/`) aufs Board.

> Das ersetzt alle Dateien auf dem Board, auch per Browser hochgeladene GIFs.

## 4b. Animationen hochladen (ohne Plugin)

Beim ersten Start formatiert die Firmware den Speicher selbst. Das Display zeigt dann „Keine Animation“. Richte das WLAN ein (Schritt 5) und zieh die GIFs aus `DiGi_Hami/data/gifs/` in der Web-Oberfläche ins Upload-Feld.

---

## 5. Einrichten

Ab hier ist alles wie in der Haupt-Anleitung (`../README.md`, Abschnitt 4):
WLAN `DiGi-Hami-XXXX` per QR-Code verbinden, dein Netzwerk wählen, danach erreichst du den Hamster unter **http://digihami.local**.

Serial-Monitor auf **115200 Baud** zeigt z. B.:
```
=== DiGi Hami v2.0.0 ===
[FS] 951 / 1920 KB belegt
[TFT] GC9A01 initialisiert
[GIF] Spiele hami_hallo.gif (240x240)
[Net] Verbunden mit MeinWLAN, IP 192.168.178.57, RSSI -58
```

---

## Spätere Updates

Ab jetzt brauchst du die Arduino IDE für Updates nicht mehr: Lade unter GitHub → *Releases* die Datei `DiGi-Hami-Update-v….bin` herunter und spiel sie in der Web-Oberfläche unter *System → Firmware-Update* ein.

Eigene Änderungen am Sketch kannst du genauso einspielen: *Sketch → Kompilierte Binärdatei exportieren* erzeugt `DiGi_Hami.ino.bin` im Sketch-Ordner, die wählst du in der Web-Oberfläche aus.

## Einstellungen ändern

Statt Build-Flags (wie bei PlatformIO) änderst du in der Arduino IDE direkt **`config.h`**:

| Zeile in `config.h` | Wirkung |
|---|---|
| `#define TFT_BL -1` → `10` | BLK an GPIO10 → echte Helligkeitsregelung |
| `#define TFT_SPI_HZ 40000000` → `80000000` | flüssiger, braucht kurze Kabel |
| `#define TFT_INVERT 1` → `0` | falls Farben invertiert sind |
| `#define TFT_BGR 0` → `1` | falls Rot und Blau vertauscht sind |
| `#define WIFI_TX_POWER WIFI_POWER_8_5dBm` | Sendeleistung (Standard ist der C3-Super-Mini-Fix) |
| Pins `TFT_SCLK`, `TFT_MOSI` … | falls du anders verkabelt hast |

## Typische Fehler

| Meldung | Lösung |
|---|---|
| `LovyanGFX.hpp: No such file or directory` | Bibliothek LovyanGFX fehlt → Schritt 1.3 |
| `'class WiFiClass' has no member …` / `NetworkClient` unbekannt | ESP32-Core 2.x installiert → auf **3.x** aktualisieren |
| `Sketch too big` | Partition Scheme auf **Custom** stellen (nutzt `partitions.csv` aus dem Sketch-Ordner) |
| Update-Bereich in der Web-Oberfläche fehlt | Gerät wurde mit „No OTA“ geflasht → einmal mit **Custom** hochladen + „Upload LittleFS“ |
| `error: 'GIF_DRAW_COOKED' was not declared` | AnimatedGIF zu alt → aktualisieren |
| Animation ruckelt | Unter *System → Gerät* stehen Bildrate und ms/Frame. Liegen die ms/Frame über der GIF-Framedauer (~50 ms), ist der Dekoder am Limit: `TFT_SPI_HZ` auf 80 MHz (kurze Kabel), oder im Tab *Wiedergabe* das Tempo senken |
| Web-Oberfläche lädt langsam | Beim ersten Aufruf lädt der Browser die Vorschaubilder einmalig, danach kommen sie aus dem Cache. Bei schwachem Signal unter *System → WLAN → Sendeleistung* eine höhere Stufe wählen |
| Browser fragt nach Benutzer/Passwort | Benutzer `admin`, Passwort aus *System → Zugriffsschutz*; vergessen → BOOT-Taste 10 s halten |
| Kein Text im Serial-Monitor | **USB CDC On Boot: Enabled** |
| Display zeigt „Keine Animation“ | Schritt 4a oder 4b |
| Upload LittleFS: „Partition entry not found“ | Sketch einmal normal hochladen, Partition Scheme prüfen, Serial-Monitor schließen |

## Hinweis für Entwickler

Der Sketch wird aus den PlatformIO-Quellen erzeugt:
```bash
python3 scripts/embed_web.py      # Web-Oberfläche -> src/web_index.h
python3 tools/make_arduino.py     # src/ + data/ -> arduino/DiGi_Hami/
```
Änderungen also am besten in `src/` bzw. `web/` machen und danach den Sketch neu erzeugen.
