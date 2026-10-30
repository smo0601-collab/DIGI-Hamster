// Einstellungen (persistiert als JSON im NVS)
#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include <vector>

enum PlayMode : uint8_t { MODE_SINGLE = 0, MODE_SEQUENCE = 1, MODE_SHUFFLE = 2 };
enum NightAction : uint8_t { NIGHT_OFF = 0, NIGHT_DIM = 1, NIGHT_GIF = 2 };

struct Settings {
  // Allgemein
  String name = "Hami";                // Name des Hamsters (Web-UI, Startbild)
  String hostname = "digihami";        // -> http://digihami.local
  // Wiedergabe
  uint8_t brightness = 100;            // 5..100 %
  uint16_t speed = 100;                // 25..300 % Abspielgeschwindigkeit
  uint8_t rotation = 0;                // 0..3 (x 90 Grad)
  uint8_t mode = MODE_SEQUENCE;        // PlayMode
  uint16_t interval = 3;               // Minuten pro Animation (Playlist)
  String current = "hami_rennt.gif";   // aktuelle / feste Animation
  std::vector<String> skip;            // NICHT in der Playlist
  // Nachtruhe
  bool nightEnabled = false;
  uint16_t nightStart = 22 * 60;       // Minuten seit Mitternacht
  uint16_t nightEnd = 7 * 60;
  uint8_t nightAction = NIGHT_GIF;     // NightAction
  uint8_t nightDim = 15;               // % beim Dimmen
  String nightGif = "hami_schlaeft.gif";
  String tz = "CET-1CEST,M3.5.0,M10.5.0/3";
  uint8_t txPower = 0;                 // WLAN-Sendeleistung in 0,25 dBm; 0 = Standard (config.h)
  // WLAN (getrennt gespeichert, wird nie per API ausgegeben)
  String wifiSsid;
  String wifiPass;
  // Kilometerzaehler
  double odoTotal = 0;                 // Meter
  double odoToday = 0;                 // Meter
  int odoDay = -1;                     // Tag im Jahr fuer "heute"

  bool inPlaylist(const String& file) const;
  void toJson(JsonObject o) const;
  // Uebernimmt Felder aus JSON (nur vorhandene). Gibt true zurueck bei Aenderung.
  bool fromJson(JsonVariantConst o);
};

extern Settings cfg;

void settingsLoad();
void settingsSave();
void settingsSaveWifi();
void settingsSaveOdo();
void settingsFactoryReset();
