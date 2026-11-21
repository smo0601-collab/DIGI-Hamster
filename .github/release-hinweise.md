
---

### Welche Datei brauche ich?

| Datei | Wofür |
|---|---|
| **`DiGi-Hami-Update-v….bin`** | **Update über die Web-Oberfläche:** *System → Firmware-Update → Update-Datei auswählen*. Einstellungen, WLAN und Animationen bleiben erhalten. |
| `DiGi-Hami-Komplett-v….bin` | Komplett-Firmware für USB, ab Adresse `0x0` (esptool oder [esptool-js](https://espressif.github.io/esptool-js/)) |
| `DiGi-Hami-Animationen-v….bin` | Animationen (Dateisystem) für USB, ab Adresse `0x2D0000`. Ersetzt alle Animationen auf dem Gerät. |
| `DiGi-Hami-Arduino-Sketch-v….zip` | Sketch für die Arduino IDE (Partition Scheme **Custom**), Anleitung liegt bei |

Neu flashen per USB:

```
esptool --chip esp32c3 --baud 921600 write-flash 0x0 DiGi-Hami-Komplett-v….bin 0x2D0000 DiGi-Hami-Animationen-v….bin
```
