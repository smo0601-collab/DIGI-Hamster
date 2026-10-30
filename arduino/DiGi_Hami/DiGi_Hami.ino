// ============================================================================
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
// ============================================================================
//  DiGi Hami v2 - digitaler Schreibtisch-Hamster
//  ESP32-C3 Super Mini + GC9A01 1,28" Rund-Display (240x240)
//
//  * fluessige GIF-Wiedergabe (LovyanGFX + DMA, AnimatedGIF "cooked"-Modus)
//  * Web-Oberflaeche: GIFs hochladen/verwalten, Playlist, Helligkeit,
//    Geschwindigkeit, Drehung, Nachtruhe, WLAN, Firmware-Update (OTA)
//  * Einrichtung per Access Point + Captive Portal (QR-Code auf dem Display)
//  * BOOT-Taste: kurz = naechste Animation, 2 s = Info, 10 s = WLAN-Reset
// ============================================================================
#include <Arduino.h>
#include <LittleFS.h>
#include "config.h"
#include "display.h"
#include "net.h"
#include "player.h"
#include "settings.h"

LGFX tft;

// ---------------------------------------------------------------------------
//  BOOT-Taste
// ---------------------------------------------------------------------------
static void buttonLoop() {
  static bool last = true;
  static uint32_t downAt = 0;
  static bool infoShown = false, resetShown = false;
  bool up = digitalRead(BTN_PIN);
  uint32_t now = millis();
  if (!up && last) {
    downAt = now;
    infoShown = resetShown = false;
  }
  if (!up) {
    uint32_t held = now - downAt;
    if (held > 10000 && !resetShown) {
      resetShown = true;
      playerShowMessage("WLAN-Reset", "Zugangsdaten", "geloescht", 3000);
      cfg.wifiSsid = "";
      cfg.wifiPass = "";
      settingsSaveWifi();
      delay(1500);
      ESP.restart();
    } else if (held > 2000 && !infoShown) {
      infoShown = true;
      netShowInfo();
    }
  }
  if (up && !last) {
    uint32_t held = now - downAt;
    if (held > 40 && held < 1000) playerNext();
  }
  last = up;
}

// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.printf("\n\n=== DiGi Hami v%s ===\n", HAMI_VERSION);

  pinMode(BTN_PIN, INPUT_PULLUP);

  if (!LittleFS.begin(true)) Serial.println("[FS] LittleFS konnte nicht gestartet werden!");
  if (!LittleFS.exists(GIF_DIR)) LittleFS.mkdir(GIF_DIR);
  Serial.printf("[FS] %u / %u KB belegt\n", (unsigned)(LittleFS.usedBytes() / 1024),
                (unsigned)(LittleFS.totalBytes() / 1024));

  settingsLoad();

  tft.init();
  tft.setColorDepth(16);
  tft.fillScreen(TFT_BLACK);
  Serial.println("[TFT] GC9A01 initialisiert");

  playerBegin();
  netBegin();
  playerEnableTurbo();
  playerStartTask();   // Animation laeuft ab jetzt in eigenem Task
  Serial.printf("[Sys] Freier Heap: %u Bytes\n", ESP.getFreeHeap());
}

void loop() {
  netLoop();
  buttonLoop();

  static uint32_t lastNight = 0;
  if (millis() - lastNight > 5000) {
    lastNight = millis();
    netEvaluateNight();
  }
  delay(1);
}
