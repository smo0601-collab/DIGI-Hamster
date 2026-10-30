#include "settings.h"
#include <Preferences.h>
#include "config.h"

Settings cfg;
static Preferences prefs;

static const char* NS = "hami";

bool Settings::inPlaylist(const String& file) const {
  for (auto& s : skip)
    if (s == file) return false;
  return true;
}

void Settings::toJson(JsonObject o) const {
  o["name"] = name;
  o["hostname"] = hostname;
  o["brightness"] = brightness;
  o["speed"] = speed;
  o["rotation"] = rotation;
  o["mode"] = mode;
  o["interval"] = interval;
  o["current"] = current;
  JsonArray a = o["skip"].to<JsonArray>();
  for (auto& s : skip) a.add(s);
  JsonObject n = o["night"].to<JsonObject>();
  n["enabled"] = nightEnabled;
  n["start"] = nightStart;
  n["end"] = nightEnd;
  n["action"] = nightAction;
  n["dim"] = nightDim;
  n["gif"] = nightGif;
  o["tz"] = tz;
  o["txPower"] = txPower;
}

template <typename T>
static bool setIf(JsonVariantConst v, T& dst, T lo, T hi) {
  if (v.isNull()) return false;
  T nv = v.as<T>();
  if (nv < lo) nv = lo;
  if (nv > hi) nv = hi;
  if (nv == dst) return false;
  dst = nv;
  return true;
}

static bool setStr(JsonVariantConst v, String& dst, size_t maxLen) {
  if (v.isNull() || !v.is<const char*>()) return false;
  String s = v.as<const char*>();
  s.trim();
  if (s.length() > maxLen) s = s.substring(0, maxLen);
  if (s == dst) return false;
  dst = s;
  return true;
}

static String cleanHostname(const String& in) {
  String out;
  for (char c : in) {
    if (isalnum((unsigned char)c)) out += (char)tolower(c);
    else if ((c == '-' || c == '_' || c == ' ') && out.length() && out[out.length() - 1] != '-') out += '-';
  }
  while (out.endsWith("-")) out.remove(out.length() - 1);
  if (out.isEmpty()) out = DEFAULT_HOSTNAME;
  return out.substring(0, 31);
}

bool Settings::fromJson(JsonVariantConst o) {
  bool ch = false;
  ch |= setStr(o["name"], name, 24);
  if (!o["hostname"].isNull()) {
    String h = cleanHostname(o["hostname"].as<String>());
    if (h != hostname) { hostname = h; ch = true; }
  }
  ch |= setIf<uint8_t>(o["brightness"], brightness, 5, 100);
  ch |= setIf<uint16_t>(o["speed"], speed, 25, 300);
  ch |= setIf<uint8_t>(o["rotation"], rotation, 0, 3);
  ch |= setIf<uint8_t>(o["mode"], mode, 0, 2);
  ch |= setIf<uint16_t>(o["interval"], interval, 1, 1440);
  ch |= setStr(o["current"], current, MAX_NAME_LEN);
  if (o["skip"].is<JsonArrayConst>()) {
    std::vector<String> ns;
    for (JsonVariantConst v : o["skip"].as<JsonArrayConst>())
      if (v.is<const char*>() && ns.size() < 64) ns.push_back(v.as<const char*>());
    if (ns != skip) { skip = ns; ch = true; }
  }
  JsonVariantConst n = o["night"];
  if (!n.isNull()) {
    if (!n["enabled"].isNull() && n["enabled"].as<bool>() != nightEnabled) {
      nightEnabled = n["enabled"].as<bool>();
      ch = true;
    }
    ch |= setIf<uint16_t>(n["start"], nightStart, 0, 1439);
    ch |= setIf<uint16_t>(n["end"], nightEnd, 0, 1439);
    ch |= setIf<uint8_t>(n["action"], nightAction, 0, 2);
    ch |= setIf<uint8_t>(n["dim"], nightDim, 1, 100);
    ch |= setStr(n["gif"], nightGif, MAX_NAME_LEN);
  }
  ch |= setStr(o["tz"], tz, 63);
  if (!o["txPower"].isNull()) {
    uint8_t v = o["txPower"].as<uint8_t>();
    // erlaubte Stufen: 0 (Standard), 8,5 / 11 / 13 / 15 / 17 / 19,5 dBm
    if ((v == 0 || v == 34 || v == 44 || v == 52 || v == 60 || v == 68 || v == 78) && v != txPower) {
      txPower = v;
      ch = true;
    }
  }
  return ch;
}

void settingsLoad() {
  prefs.begin(NS, true);
  String js = prefs.getString("cfg", "");
  cfg.wifiSsid = prefs.getString("ssid", "");
  cfg.wifiPass = prefs.getString("pass", "");
  cfg.odoTotal = prefs.getDouble("odoT", 0);
  cfg.odoToday = prefs.getDouble("odoD", 0);
  cfg.odoDay = prefs.getInt("odoDay", -1);
  prefs.end();
  if (js.length()) {
    JsonDocument doc;
    if (!deserializeJson(doc, js)) cfg.fromJson(doc.as<JsonVariantConst>());
  } else {
    // Erststart: Schlaf- und Begruessungs-Animation nicht in der Playlist
    cfg.skip = {"hami_schlaeft.gif", "hami_hallo.gif"};
  }
}

void settingsSave() {
  JsonDocument doc;
  cfg.toJson(doc.to<JsonObject>());
  String js;
  serializeJson(doc, js);
  prefs.begin(NS, false);
  prefs.putString("cfg", js);
  prefs.end();
}

void settingsSaveWifi() {
  prefs.begin(NS, false);
  prefs.putString("ssid", cfg.wifiSsid);
  prefs.putString("pass", cfg.wifiPass);
  prefs.end();
}

void settingsSaveOdo() {
  prefs.begin(NS, false);
  prefs.putDouble("odoT", cfg.odoTotal);
  prefs.putDouble("odoD", cfg.odoToday);
  prefs.putInt("odoDay", cfg.odoDay);
  prefs.end();
}

void settingsFactoryReset() {
  prefs.begin(NS, false);
  prefs.clear();
  prefs.end();
}
