#include "net.h"
#include <ArduinoJson.h>
#include <DNSServer.h>
#include <ESPmDNS.h>
#include <LittleFS.h>
#include <Update.h>
#include <WebServer.h>
#include <WiFi.h>
#include <esp_system.h>
#include "config.h"
#include "player.h"
#include "settings.h"
#include "web_index.h"   // generiert aus web/index.html (scripts/embed_web.py)

static WebServer server(80);
static DNSServer dns;
static NetState state = NET_CONNECTING;
static uint32_t connectStart = 0;
static uint32_t lastStaRetry = 0;
static uint32_t apSince = 0;
static bool apActive = false;
static bool mdnsUp = false;
static uint32_t restartAt = 0;
static String apName;

// Upload-Zustand
static File upFile;
static String upName, upError;
static size_t upBytes = 0;
static bool otaOk = false;
static String otaError;

static const char* TMP_UPLOAD = "/gifs/.upload.tmp";

// ---------------------------------------------------------------------------
//  Hilfen
// ---------------------------------------------------------------------------
NetState netState() { return state; }
String netApName() { return apName; }

String netIp() {
  if (WiFi.status() == WL_CONNECTED) return WiFi.localIP().toString();
  if (apActive) return WiFi.softAPIP().toString();
  return "";
}

bool netTimeValid() { return time(nullptr) > 1700000000; }

static void sendJson(JsonDocument& doc, int code = 200) {
  String out;
  serializeJson(doc, out);
  server.sendHeader("Cache-Control", "no-store");
  server.send(code, "application/json", out);
}

static void sendOk(const char* msg = "ok") {
  JsonDocument d;
  d["ok"] = true;
  d["msg"] = msg;
  sendJson(d);
}

static void sendErr(int code, const String& msg) {
  JsonDocument d;
  d["ok"] = false;
  d["error"] = msg;
  sendJson(d, code);
}

static bool readBody(JsonDocument& doc) {
  if (!server.hasArg("plain")) return false;
  return !deserializeJson(doc, server.arg("plain"));
}

// Dateinamen bereinigen: klein, a-z 0-9 - _ . ; Umlaute umschreiben
static String cleanName(const String& raw) {
  String in = raw;
  int slash = max(in.lastIndexOf('/'), in.lastIndexOf('\\'));
  if (slash >= 0) in = in.substring(slash + 1);
  in.replace("\xC3\xA4", "ae"); in.replace("\xC3\xB6", "oe"); in.replace("\xC3\xBC", "ue");
  in.replace("\xC3\x84", "ae"); in.replace("\xC3\x96", "oe"); in.replace("\xC3\x9C", "ue");
  in.replace("\xC3\x9F", "ss");
  in.toLowerCase();
  if (in.endsWith(".gif")) in = in.substring(0, in.length() - 4);
  String out;
  for (size_t i = 0; i < in.length(); i++) {
    char c = in[i];
    if (isalnum((unsigned char)c) || c == '-' || c == '_') out += c;
    else if ((c == ' ' || c == '.') && out.length() && !out.endsWith("_")) out += '_';
  }
  while (out.startsWith("_") || out.startsWith("-")) out.remove(0, 1);
  if (out.isEmpty()) out = "animation";
  if (out.length() > MAX_NAME_LEN - 4) out = out.substring(0, MAX_NAME_LEN - 4);
  return out + ".gif";
}

static bool validName(const String& n) {
  return n.length() > 4 && n.length() <= MAX_NAME_LEN && n.endsWith(".gif") && n.indexOf('/') < 0 &&
         !n.startsWith(".");
}

static void scheduleRestart(uint32_t ms) { restartAt = millis() + ms; }

static wifi_power_t txPower() { return cfg.txPower ? (wifi_power_t)cfg.txPower : WIFI_TX_POWER; }

// ---------------------------------------------------------------------------
//  mDNS / Zeit
// ---------------------------------------------------------------------------
static void startMdns() {
  if (mdnsUp) MDNS.end();
  mdnsUp = MDNS.begin(cfg.hostname.c_str());
  if (mdnsUp) {
    MDNS.addService("http", "tcp", 80);
    Serial.printf("[Net] mDNS: http://%s.local\n", cfg.hostname.c_str());
  }
}

static void startTime() {
  configTzTime(cfg.tz.c_str(), "pool.ntp.org", "time.google.com", "time.cloudflare.com");
}

// ---------------------------------------------------------------------------
//  AP-Modus (Einrichtung)
// ---------------------------------------------------------------------------
static void startAp() {
  if (apActive) return;
  WiFi.mode(cfg.wifiSsid.length() ? WIFI_AP_STA : WIFI_AP);
  WiFi.softAP(apName.c_str());   // offen - nur zur Einrichtung
  WiFi.setTxPower(txPower());
  delay(100);
  dns.setErrorReplyCode(DNSReplyCode::NoError);
  dns.start(53, "*", WiFi.softAPIP());
  apActive = true;
  apSince = millis();
  Serial.printf("[Net] Access Point \"%s\" aktiv, http://%s\n", apName.c_str(),
                WiFi.softAPIP().toString().c_str());
}

static void stopAp() {
  if (!apActive) return;
  dns.stop();
  WiFi.softAPdisconnect(true);
  WiFi.mode(WIFI_STA);
  apActive = false;
  Serial.println("[Net] Access Point beendet");
}

void netShowInfo() {
  if (WiFi.status() == WL_CONNECTED) {
    String url = "http://" + WiFi.localIP().toString() + "/";
    playerShowMessage(cfg.name + " ist online", WiFi.localIP().toString(), cfg.hostname + ".local", 8000, url);
  } else if (apActive) {
    String qr = "WIFI:T:nopass;S:" + apName + ";;";
    playerShowMessage("WLAN einrichten", apName, "dann 192.168.4.1", 30000, qr);
  } else {
    playerShowMessage("Kein WLAN", "verbinde ...", cfg.wifiSsid, 4000);
  }
}

// ---------------------------------------------------------------------------
//  Nachtruhe auswerten
// ---------------------------------------------------------------------------
void netEvaluateNight() {
  bool active = false;
  if (cfg.nightEnabled && netTimeValid()) {
    time_t now = time(nullptr);
    struct tm lt;
    localtime_r(&now, &lt);
    int m = lt.tm_hour * 60 + lt.tm_min;
    int s = cfg.nightStart, e = cfg.nightEnd;
    if (s == e) active = false;
    else if (s < e) active = (m >= s && m < e);
    else active = (m >= s || m < e);
  }
  playerSetNight(active);
}

// ---------------------------------------------------------------------------
//  HTTP-Handler
// ---------------------------------------------------------------------------
static void hIndex() {
  server.sendHeader("Content-Encoding", "gzip");
  server.sendHeader("Cache-Control", "no-cache");
  server.send_P(200, "text/html; charset=utf-8", (const char*)INDEX_HTML_GZ, INDEX_HTML_GZ_LEN);
}

static void hStatus() {
  JsonDocument d;
  d["version"] = HAMI_VERSION;
  d["name"] = cfg.name;
  d["hostname"] = cfg.hostname;
  d["uptime"] = millis() / 1000;
  d["heap"] = ESP.getFreeHeap();
  d["heapMin"] = ESP.getMinFreeHeap();
  d["fsTotal"] = LittleFS.totalBytes();
  d["fsUsed"] = LittleFS.usedBytes();
  d["current"] = playerCurrent();
  d["fps"] = round(playerFps() * 10) / 10.0;
  d["decodeMs"] = playerLastDecodeMs();
  d["turbo"] = playerTurbo();
  d["night"] = playerNightActive();
  d["mode"] = state == NET_STA ? "sta" : (state == NET_AP ? "ap" : "connecting");
  d["ap"] = apActive;
  d["apName"] = apName;
  d["ssid"] = cfg.wifiSsid;
  d["ip"] = WiFi.status() == WL_CONNECTED ? WiFi.localIP().toString() : String("");
  d["apIp"] = apActive ? WiFi.softAPIP().toString() : String("");
  d["rssi"] = WiFi.status() == WL_CONNECTED ? WiFi.RSSI() : 0;
  d["txPower"] = (int)WiFi.getTxPower();
  d["timeValid"] = netTimeValid();
  if (netTimeValid()) {
    time_t now = time(nullptr);
    struct tm lt;
    localtime_r(&now, &lt);
    char buf[24];
    strftime(buf, sizeof(buf), "%d.%m.%Y %H:%M", &lt);
    d["time"] = buf;
  }
  playerFlushOdometer(false);
  d["odoToday"] = round(cfg.odoToday);
  d["odoTotal"] = round(cfg.odoTotal);
  d["backlightPin"] = TFT_BL;
  d["chip"] = ESP.getChipModel();
  d["flash"] = ESP.getFlashChipSize();
  d["sketch"] = ESP.getSketchSize();
  d["sketchFree"] = ESP.getFreeSketchSpace();
  sendJson(d);
}

static void hFiles() {
  JsonDocument d;
  JsonArray a = d["files"].to<JsonArray>();
  for (auto& f : listGifs()) {
    JsonObject o = a.add<JsonObject>();
    o["name"] = f.name;
    o["size"] = f.size;
    o["playlist"] = cfg.inPlaylist(f.name);
  }
  d["fsTotal"] = LittleFS.totalBytes();
  d["fsUsed"] = LittleFS.usedBytes();
  d["current"] = playerCurrent();
  sendJson(d);
}

static void hGetSettings() {
  JsonDocument d;
  cfg.toJson(d.to<JsonObject>());
  d["backlightPin"] = TFT_BL;
  sendJson(d);
}

static void hPostSettings() {
  JsonDocument body;
  if (!readBody(body)) return sendErr(400, "Ungueltiges JSON");
  playerLock();  // die Animation liest cfg in ihrem eigenen Task
  Settings before = cfg;
  if (cfg.fromJson(body.as<JsonVariantConst>())) settingsSave();
  playerUnlock();
  if (before.txPower != cfg.txPower) WiFi.setTxPower(txPower());
  bool display = before.rotation != cfg.rotation || before.brightness != cfg.brightness;
  bool night = before.nightEnabled != cfg.nightEnabled || before.nightStart != cfg.nightStart ||
               before.nightEnd != cfg.nightEnd || before.nightAction != cfg.nightAction ||
               before.nightDim != cfg.nightDim || before.nightGif != cfg.nightGif;
  if (before.tz != cfg.tz) {
    setenv("TZ", cfg.tz.c_str(), 1);
    tzset();
    night = true;
  }
  if (before.hostname != cfg.hostname && WiFi.status() == WL_CONNECTED) {
    WiFi.setHostname(cfg.hostname.c_str());
    startMdns();
  }
  if (night) {
    playerSetNight(false);
    netEvaluateNight();
  }
  if (display) {
    playerApplyDisplay();
    // kompletten Frame neu zeichnen (sonst bleiben unveraenderte Bereiche schwarz)
    playerRestart();
  }
  hGetSettings();
}

static void hPlay() {
  String n = server.arg("name");
  if (!validName(n) || !gifExists(n)) return sendErr(404, "Datei nicht gefunden");
  if (!playerPlay(n, true)) return sendErr(422, "GIF kann nicht abgespielt werden (max. 240x240?)");
  sendOk();
}

static void hNext() {
  playerNext();
  sendOk();
}

static void hDelete() {
  String n = server.arg("name");
  if (!validName(n) || !gifExists(n)) return sendErr(404, "Datei nicht gefunden");
  bool wasCurrent = playerCurrent() == n;
  if (wasCurrent) playerSuspend();
  LittleFS.remove(String(GIF_DIR) + "/" + n);
  if (wasCurrent) {
    playerNext();
    playerResume();
  }
  sendOk("geloescht");
}

static void hIdentify() {
  playerShowMessage("Hallo!", "Ich bin " + cfg.name, netIp(), 5000);
  sendOk();
}

static void hReboot() {
  sendOk("Neustart");
  scheduleRestart(800);
}

static void hFactory() {
  settingsFactoryReset();
  sendOk("Werkseinstellungen - Neustart");
  scheduleRestart(800);
}

static void hScan() {
  int n = WiFi.scanComplete();
  JsonDocument d;
  if (n == WIFI_SCAN_FAILED) {
    WiFi.scanNetworks(true, false);
    d["scanning"] = true;
  } else if (n == WIFI_SCAN_RUNNING) {
    d["scanning"] = true;
  } else {
    d["scanning"] = false;
    JsonArray a = d["networks"].to<JsonArray>();
    for (int i = 0; i < n && i < 30; i++) {
      String ssid = WiFi.SSID(i);
      if (!ssid.length()) continue;
      bool dup = false;
      for (JsonObject o : a)
        if (ssid == o["ssid"].as<const char*>()) { dup = true; break; }
      if (dup) continue;
      JsonObject o = a.add<JsonObject>();
      o["ssid"] = ssid;
      o["rssi"] = WiFi.RSSI(i);
      o["open"] = WiFi.encryptionType(i) == WIFI_AUTH_OPEN;
    }
    WiFi.scanDelete();
  }
  sendJson(d);
}

static void hWifi() {
  JsonDocument body;
  if (!readBody(body)) return sendErr(400, "Ungueltiges JSON");
  String ssid = body["ssid"] | "";
  ssid.trim();
  if (!ssid.length() || ssid.length() > 32) return sendErr(400, "SSID fehlt");
  if (!body["pass"].isNull()) cfg.wifiPass = body["pass"].as<String>();
  else if (ssid != cfg.wifiSsid) cfg.wifiPass = "";
  cfg.wifiSsid = ssid;
  settingsSaveWifi();
  sendOk("Gespeichert - Neustart");
  playerShowMessage("Neustart", "verbinde mit", ssid, 5000);
  scheduleRestart(1200);
}

// --- GIF-Upload -------------------------------------------------------------
static void hUploadChunk() {
  HTTPUpload& up = server.upload();
  if (up.status == UPLOAD_FILE_START) {
    upError = "";
    upBytes = 0;
    upName = server.hasArg("name") ? cleanName(server.arg("name")) : cleanName(up.filename);
    size_t freeB = LittleFS.totalBytes() - LittleFS.usedBytes();
    size_t len = server.clientContentLength();
    // vorhandene Datei gleichen Namens zaehlt als frei
    String final = String(GIF_DIR) + "/" + upName;
    if (LittleFS.exists(final)) {
      File f = LittleFS.open(final, "r");
      freeB += f.size();
      f.close();
    }
    if (len > 0 && (int64_t)len + 8192 > (int64_t)freeB) {
      upError = "Nicht genug Speicher frei (" + String(freeB / 1024) + " KB frei)";
      return;
    }
    playerSuspend();
    LittleFS.remove(TMP_UPLOAD);
    upFile = LittleFS.open(TMP_UPLOAD, "w");
    if (!upFile) upError = "Datei kann nicht angelegt werden";
    Serial.printf("[Upload] %s (%u Bytes)\n", upName.c_str(), (unsigned)len);
  } else if (up.status == UPLOAD_FILE_WRITE) {
    if (upError.length() || !upFile) return;
    if (upFile.write(up.buf, up.currentSize) != up.currentSize) {
      upError = "Schreibfehler - Speicher voll?";
      upFile.close();
      LittleFS.remove(TMP_UPLOAD);
    }
    upBytes += up.currentSize;
  } else if (up.status == UPLOAD_FILE_END) {
    if (upFile) upFile.close();
    if (upError.length()) {
      LittleFS.remove(TMP_UPLOAD);
      return;
    }
    // GIF pruefen: Signatur + Groesse
    File f = LittleFS.open(TMP_UPLOAD, "r");
    uint8_t h[10] = {0};
    size_t n = f ? f.read(h, 10) : 0;
    if (f) f.close();
    int w = h[6] | (h[7] << 8), hh = h[8] | (h[9] << 8);
    if (n < 10 || memcmp(h, "GIF8", 4) != 0) {
      upError = "Keine GIF-Datei";
    } else if (w > DISPLAY_W || hh > DISPLAY_H) {
      upError = "GIF ist " + String(w) + "x" + String(hh) + " - maximal 240x240";
    }
    if (upError.length()) {
      LittleFS.remove(TMP_UPLOAD);
      return;
    }
    String final = String(GIF_DIR) + "/" + upName;
    LittleFS.remove(final);
    LittleFS.rename(TMP_UPLOAD, final);
    Serial.printf("[Upload] fertig: %s (%u Bytes, %dx%d)\n", upName.c_str(), (unsigned)upBytes, w, hh);
  } else if (up.status == UPLOAD_FILE_ABORTED) {
    if (upFile) upFile.close();
    LittleFS.remove(TMP_UPLOAD);
    upError = "Upload abgebrochen";
  }
}

static void hUploadDone() {
  bool ok = upError.isEmpty();
  if (ok && server.hasArg("play") && server.arg("play") == "1") {
    playerPlay(upName, true);
  }
  playerResume();
  if (!ok) return sendErr(400, upError);
  JsonDocument d;
  d["ok"] = true;
  d["name"] = upName;
  d["size"] = upBytes;
  sendJson(d);
}

// --- Firmware-Update (OTA) --------------------------------------------------
static void hOtaChunk() {
  HTTPUpload& up = server.upload();
  if (up.status == UPLOAD_FILE_START) {
    otaOk = false;
    otaError = "";
    playerSuspend();
    playerShowMessage("Update", "Firmware wird", "installiert ...", 120000);
    if (!Update.begin(UPDATE_SIZE_UNKNOWN, U_FLASH)) otaError = Update.errorString();
    Serial.printf("[OTA] Start: %s\n", up.filename.c_str());
  } else if (up.status == UPLOAD_FILE_WRITE) {
    if (otaError.length()) return;
    if (Update.write(up.buf, up.currentSize) != up.currentSize) otaError = Update.errorString();
  } else if (up.status == UPLOAD_FILE_END) {
    if (otaError.isEmpty()) {
      if (Update.end(true)) otaOk = true;
      else otaError = Update.errorString();
    } else {
      Update.abort();
    }
  } else if (up.status == UPLOAD_FILE_ABORTED) {
    Update.abort();
    otaError = "abgebrochen";
  }
}

static void hOtaDone() {
  if (!otaOk) {
    playerShowMessage("Update", "fehlgeschlagen", otaError, 5000);
    playerResume();
    return sendErr(400, "Update fehlgeschlagen: " + otaError);
  }
  playerFlushOdometer(true);
  playerShowMessage("Update ok", "Neustart ...", "", 5000);
  sendOk("Update erfolgreich - Neustart");
  scheduleRestart(1200);
}

// --- Captive Portal ---------------------------------------------------------
static bool captiveRedirect() {
  if (!apActive) return false;
  String host = server.hostHeader();
  String apIp = WiFi.softAPIP().toString();
  if (host == apIp || host == cfg.hostname + ".local" ||
      (WiFi.status() == WL_CONNECTED && host == WiFi.localIP().toString()))
    return false;
  server.sendHeader("Location", "http://" + apIp + "/", true);
  server.send(302, "text/plain", "");
  return true;
}

static void hNotFound() {
  if (captiveRedirect()) return;
  server.send(404, "text/plain", "Nicht gefunden");
}

static void setupRoutes() {
  server.on("/", HTTP_GET, [] {
    if (captiveRedirect()) return;
    hIndex();
  });
  // Captive-Portal-Erkennung von Android / iOS / Windows
  for (const char* p : {"/generate_204", "/gen_204", "/hotspot-detect.html", "/connecttest.txt", "/ncsi.txt",
                        "/fwlink", "/redirect"}) {
    server.on(p, HTTP_GET, [] {
      if (!captiveRedirect()) hIndex();
    });
  }
  server.on("/api/status", HTTP_GET, hStatus);
  server.on("/api/files", HTTP_GET, hFiles);
  server.on("/api/settings", HTTP_GET, hGetSettings);
  server.on("/api/settings", HTTP_POST, hPostSettings);
  server.on("/api/play", HTTP_POST, hPlay);
  server.on("/api/next", HTTP_POST, hNext);
  server.on("/api/delete", HTTP_POST, hDelete);
  server.on("/api/identify", HTTP_POST, hIdentify);
  server.on("/api/reboot", HTTP_POST, hReboot);
  server.on("/api/factory", HTTP_POST, hFactory);
  server.on("/api/scan", HTTP_GET, hScan);
  server.on("/api/wifi", HTTP_POST, hWifi);
  server.on("/api/upload", HTTP_POST, hUploadDone, hUploadChunk);
  server.on("/api/update", HTTP_POST, hOtaDone, hOtaChunk);
  // GIF-URLs tragen ?v=<Groesse> -> der Browser darf sie dauerhaft cachen
  server.serveStatic("/gifs/", LittleFS, "/gifs/", "public, max-age=31536000, immutable");
  server.onNotFound(hNotFound);
  const char* hdrs[] = {"Host"};
  server.collectHeaders(hdrs, 1);
  server.begin();
}

// ---------------------------------------------------------------------------
//  Start / Loop
// ---------------------------------------------------------------------------
static void onConnected() {
  state = NET_STA;
  Serial.printf("[Net] Verbunden mit %s, IP %s, RSSI %d\n", cfg.wifiSsid.c_str(),
                WiFi.localIP().toString().c_str(), WiFi.RSSI());
  startMdns();
  startTime();
  netShowInfo();
}

void netBegin() {
  uint8_t mac[6];
  WiFi.macAddress(mac);
  char suf[8];
  snprintf(suf, sizeof(suf), "%02X%02X", mac[4], mac[5]);
  apName = String(AP_PREFIX) + suf;

  WiFi.persistent(false);
  WiFi.setAutoReconnect(true);
  WiFi.setHostname(cfg.hostname.c_str());
  setenv("TZ", cfg.tz.c_str(), 1);
  tzset();

  if (cfg.wifiSsid.length()) {
    WiFi.mode(WIFI_STA);
    WiFi.begin(cfg.wifiSsid.c_str(), cfg.wifiPass.c_str());
    WiFi.setTxPower(txPower());  // C3 Super Mini: volle Leistung stoert die Antenne
    state = NET_CONNECTING;
    connectStart = millis();
    Serial.printf("[Net] Verbinde mit \"%s\" ...\n", cfg.wifiSsid.c_str());
    // Begruessungs-Animation waehrend des Verbindens
    if (gifExists("hami_hallo.gif")) playerPlay("hami_hallo.gif", false);
  } else {
    state = NET_AP;
    startAp();
    netShowInfo();
  }
  setupRoutes();
}

void netLoop() {
  if (apActive) dns.processNextRequest();
  server.handleClient();

  uint32_t now = millis();
  if (restartAt && (int32_t)(now - restartAt) >= 0) {
    playerFlushOdometer(true);
    ESP.restart();
  }

  switch (state) {
    case NET_CONNECTING:
      if (WiFi.status() == WL_CONNECTED) {
        onConnected();
      } else if (now - connectStart > WIFI_CONNECT_TIMEOUT_MS) {
        Serial.println("[Net] Verbindung fehlgeschlagen -> Access Point");
        state = NET_AP;
        startAp();
        netShowInfo();
        lastStaRetry = now;
      }
      break;
    case NET_AP:
      // gespeichertes WLAN im Hintergrund weiter versuchen
      if (cfg.wifiSsid.length()) {
        if (WiFi.status() == WL_CONNECTED) {
          onConnected();
        } else if (now - lastStaRetry > 60000 && WiFi.softAPgetStationNum() == 0) {
          lastStaRetry = now;
          WiFi.begin(cfg.wifiSsid.c_str(), cfg.wifiPass.c_str());
        }
      }
      break;
    case NET_STA:
      // AP nach erfolgreicher Verbindung schliessen, sobald niemand mehr dran ist
      if (apActive && WiFi.softAPgetStationNum() == 0 && now - apSince > 120000) stopAp();
      break;
  }
}
