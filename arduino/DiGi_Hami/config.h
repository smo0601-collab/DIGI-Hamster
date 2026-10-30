// ============================================================================
//  DiGi Hami v2 - Konfiguration
//  Hardware: ESP32-C3 Super Mini + GC9A01 1,28" rundes TFT (240x240, SPI)
// ============================================================================
#pragma once

#define HAMI_VERSION "2.0.0"

// ---------------------------------------------------------------------------
//  Display-Pins (identisch zu v1.0 -> bestehende Verkabelung passt)
//  GPIO2, GPIO8 und GPIO9 sind Strapping-Pins des C3 und werden bewusst
//  NICHT fuer das Display benutzt.
// ---------------------------------------------------------------------------
#ifndef TFT_SCLK
#define TFT_SCLK 4   // Display "SCL"
#endif
#ifndef TFT_MOSI
#define TFT_MOSI 6   // Display "SDA"
#endif
#ifndef TFT_CS
#define TFT_CS   7
#endif
#ifndef TFT_DC
#define TFT_DC   3
#endif
#ifndef TFT_RST
#define TFT_RST  1
#endif

// Optional: Hintergrundbeleuchtung (BLK) an einen GPIO legen, z. B. 10.
// -1 = BLK nicht angeschlossen (bzw. an 3V3). Die Helligkeit wird dann
// per Software (Farbwerte abdunkeln) geregelt.
#ifndef TFT_BL
#define TFT_BL   -1
#endif

// SPI-Takt. 40 MHz laeuft mit 10-cm-Dupont-Kabeln zuverlaessig.
// Mit kurzen/geloeteten Leitungen sind 80 MHz moeglich (fluessiger).
#ifndef TFT_SPI_HZ
#define TFT_SPI_HZ 40000000
#endif

// Farbinvertierung / Farbreihenfolge - nur aendern, wenn Farben falsch sind.
#ifndef TFT_INVERT
#define TFT_INVERT 1
#endif
#ifndef TFT_BGR
#define TFT_BGR 0
#endif

// BOOT-Taste der Super Mini (GPIO9, gegen GND). Zur Laufzeit nutzbar:
//   kurz   = naechste Animation
//   2 s    = Info-Bildschirm (IP-Adresse)
//   10 s   = WLAN-Zugangsdaten loeschen + Neustart
#ifndef BTN_PIN
#define BTN_PIN 9
#endif

// ---------------------------------------------------------------------------
//  Sonstiges
// ---------------------------------------------------------------------------
#define DISPLAY_W 240
#define DISPLAY_H 240
#define GIF_DIR   "/gifs"
#define MAX_NAME_LEN 40            // Dateiname ohne Pfad
#define AP_PREFIX "DiGi-Hami-"     // + 4 Hex-Zeichen der MAC
#define DEFAULT_HOSTNAME "digihami"
#define DEFAULT_TZ "CET-1CEST,M3.5.0,M10.5.0/3"   // Deutschland/Mitteleuropa
#define WIFI_CONNECT_TIMEOUT_MS 15000

// Sendeleistung. Viele ESP32-C3 Super Mini verbinden sich bei voller Leistung
// nicht (Antennen-Layout) - 8,5 dBm ist der bekannte Fix. Bei gutem Board und
// grosser Entfernung zum Router z. B. WIFI_POWER_15dBm probieren.
#ifndef WIFI_TX_POWER
#define WIFI_TX_POWER WIFI_POWER_8_5dBm
#endif
