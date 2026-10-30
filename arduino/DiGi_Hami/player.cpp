#include "player.h"
#include <AnimatedGIF.h>
#include <LittleFS.h>
#include <algorithm>
#include "config.h"
#include "display.h"
#include "settings.h"

// ---------------------------------------------------------------------------
//  Eigener FreeRTOS-Task fuer die Animation
//  Der C3 hat nur einen Kern. Laeuft die Animation in einem Task mit hoeherer
//  Prioritaet als loop() (Webserver), unterbricht sie laufende Uebertragungen
//  statt auf sie zu warten -> kein Ruckeln, wenn der Browser Daten laedt.
//  Alle oeffentlichen player*-Funktionen sind ueber einen rekursiven Mutex
//  abgesichert.
// ---------------------------------------------------------------------------
static SemaphoreHandle_t pmtx = nullptr;
struct PlayerGuard {
  PlayerGuard() { if (pmtx) xSemaphoreTakeRecursive(pmtx, portMAX_DELAY); }
  ~PlayerGuard() { if (pmtx) xSemaphoreGiveRecursive(pmtx); }
};
#define PLOCK PlayerGuard _pg
void playerLock() { if (pmtx) xSemaphoreTakeRecursive(pmtx, portMAX_DELAY); }
void playerUnlock() { if (pmtx) xSemaphoreGiveRecursive(pmtx); }

// ---------------------------------------------------------------------------
//  Puffer
// ---------------------------------------------------------------------------
static AnimatedGIF gif;
// Frame-Puffer fuer den "cooked"-Modus (8 bit Index pro Pixel + 3 Zeilen
// Arbeitsbereich). Statisch -> keine Heap-Fragmentierung.
static uint8_t frameBuf[DISPLAY_W * (DISPLAY_H + 3)];
static uint8_t* turboBuf = nullptr;

// Doppelter Streifenpuffer fuer DMA (16 Zeilen a 240 Pixel)
static constexpr int STRIP_PX = DISPLAY_W * 16;
static uint16_t strip[2][STRIP_PX];
static int stripCur = 0, stripX = 0, stripY = 0, stripW = 0, stripLines = 0;
static int offX = 0, offY = 0;      // Zentrierung kleinerer GIFs
static uint16_t dimScale = 256;     // Software-Helligkeit (256 = 100 %)

// ---------------------------------------------------------------------------
//  Zustand
// ---------------------------------------------------------------------------
static File gifFile;
static bool isOpen = false;
static bool suspended = false;
static String curName;
static uint32_t nextFrameAt = 0;
static uint32_t shownSince = 0;     // seit wann laeuft die aktuelle Animation
static bool nightActive = false;
static bool nightOverride = false;  // Nutzer hat nachts manuell etwas gestartet
static bool displayAsleep = false;
static uint32_t holdUntil = 0;      // Meldung auf dem Display bis ...
static bool holding = false;
static uint32_t lastErrorShown = 0;

// Statistik
static uint32_t fpsFrames = 0, fpsT0 = 0, lastDecode = 0;
static float fps = 0;
static double odoPending = 0;
static uint32_t odoLastSave = 0;

// ---------------------------------------------------------------------------
//  Datei-Callbacks fuer AnimatedGIF
// ---------------------------------------------------------------------------
static void* cbOpen(const char* fname, int32_t* pSize) {
  gifFile = LittleFS.open(fname, "r");
  if (!gifFile) return nullptr;
  *pSize = gifFile.size();
  return (void*)&gifFile;
}
static void cbClose(void* h) {
  File* f = static_cast<File*>(h);
  if (f) f->close();
}
static int32_t cbRead(GIFFILE* pFile, uint8_t* pBuf, int32_t iLen) {
  File* f = static_cast<File*>(pFile->fHandle);
  int32_t n = iLen;
  if ((pFile->iSize - pFile->iPos) < iLen) n = pFile->iSize - pFile->iPos - 1;  // s. AnimatedGIF-Doku
  if (n <= 0) return 0;
  n = (int32_t)f->read(pBuf, n);
  pFile->iPos = f->position();
  return n;
}
static int32_t cbSeek(GIFFILE* pFile, int32_t pos) {
  File* f = static_cast<File*>(pFile->fHandle);
  f->seek(pos);
  pFile->iPos = (int32_t)f->position();
  return pFile->iPos;
}

// ---------------------------------------------------------------------------
//  Zeichnen: fertige RGB565-Zeilen sammeln und per DMA rausschieben
// ---------------------------------------------------------------------------
static void flushStrip() {
  if (!stripLines) return;
  tft.pushImageDMA(offX + stripX, offY + stripY, stripW, stripLines, (const lgfx::swap565_t*)strip[stripCur]);
  stripCur ^= 1;
  stripLines = 0;
}

static inline uint16_t dimPixel(uint16_t be) {
  uint16_t v = (uint16_t)((be >> 8) | (be << 8));
  uint32_t r = ((v >> 11) & 31) * dimScale >> 8;
  uint32_t g = ((v >> 5) & 63) * dimScale >> 8;
  uint32_t b = (v & 31) * dimScale >> 8;
  v = (uint16_t)((r << 11) | (g << 5) | b);
  return (uint16_t)((v >> 8) | (v << 8));
}

static void cbDraw(GIFDRAW* d) {
  int x = d->iX;
  int y = d->iY + d->y;
  int w = d->iWidth;
  if (x >= DISPLAY_W || y >= DISPLAY_H) return;
  if (x + w > DISPLAY_W) w = DISPLAY_W - x;
  if (w <= 0) return;
  int maxLines = STRIP_PX / w;
  if (stripLines && (x != stripX || w != stripW || y != stripY + stripLines || stripLines >= maxLines))
    flushStrip();
  if (!stripLines) {
    stripX = x;
    stripY = y;
    stripW = w;
  }
  // Hinweis: d->pPixels (die "cooked"-Zeile) ist in AnimatedGIF 2.2.0 an
  // transparenten Stellen fehlerhaft (wird nicht beschrieben). Darum lesen wir
  // die bereits korrekt zusammengefuehrte Zeile direkt aus dem 8-Bit-Framepuffer
  // und wandeln sie selbst ueber die Palette (RGB565, Big Endian) um.
  const uint8_t* idx = frameBuf + y * d->iCanvasWidth + x;
  const uint16_t* pal = d->pPalette;
  uint16_t* dst = strip[stripCur] + stripLines * w;
  if (dimScale >= 256) {
    for (int i = 0; i < w; i++) dst[i] = pal[idx[i]];
  } else {
    for (int i = 0; i < w; i++) dst[i] = dimPixel(pal[idx[i]]);
  }
  stripLines++;
}

// Zweiter Pfad fuer GIFs mit lokalen Farbpaletten pro Frame: Diese lassen sich
// nicht im 8-Bit-Framepuffer zusammenfuehren. Hier werden nur die deckenden
// Pixel direkt aufs Display geschrieben - das Display selbst haelt das
// vorherige Bild (wie in v1.0).
static uint16_t rawLine[DISPLAY_W];

static void cbDrawRaw(GIFDRAW* d) {
  int y = d->iY + d->y;
  if (y >= DISPLAY_H) return;
  int w = d->iWidth;
  if (d->iX + w > DISPLAY_W) w = DISPLAY_W - d->iX;
  if (w <= 0) return;
  const uint8_t* s = d->pPixels;
  const uint16_t* pal = d->pPalette;
  auto px = [&](uint8_t c) -> uint16_t { return dimScale >= 256 ? pal[c] : dimPixel(pal[c]); };
  if (!d->ucHasTransparency) {
    for (int i = 0; i < w; i++) rawLine[i] = px(s[i]);
    tft.pushImage(offX + d->iX, offY + y, w, 1, (const lgfx::swap565_t*)rawLine);
    return;
  }
  uint8_t tr = d->ucTransparent;
  bool restoreBg = d->ucDisposalMethod == 2;
  int x = 0;
  while (x < w) {
    int n = 0;
    while (x + n < w && (s[x + n] != tr || restoreBg)) {
      uint8_t c = s[x + n];
      rawLine[n] = (c == tr) ? px(d->ucBackground) : px(c);
      n++;
    }
    if (n) {
      tft.pushImage(offX + d->iX + x, offY + y, n, 1, (const lgfx::swap565_t*)rawLine);
      x += n;
    }
    while (x < w && s[x] == tr && !restoreBg) x++;
  }
}

// Prueft, ob irgendein Frame eine lokale Farbpalette hat.
static bool gifHasLocalPalette(const String& path) {
  File f = LittleFS.open(path, "r");
  if (!f) return false;
  uint8_t h[13];
  bool local = false;
  if (f.read(h, 13) != 13) return false;
  if (h[10] & 0x80) f.seek(f.position() + 3 * (1 << ((h[10] & 7) + 1)));
  auto skipBlocks = [&]() {
    for (int guard = 0; guard < 100000; guard++) {
      int len = f.read();
      if (len <= 0) return;
      f.seek(f.position() + len);
    }
  };
  for (int guard = 0; guard < 5000 && !local; guard++) {
    int b = f.read();
    if (b == 0x21) {
      f.read();
      skipBlocks();
    } else if (b == 0x2C) {
      uint8_t desc[9];
      if (f.read(desc, 9) != 9) break;
      if (desc[8] & 0x80) local = true;
      f.read();  // LZW-Mindestcodegroesse
      skipBlocks();
    } else {
      break;  // 0x3B (Ende) oder kaputt
    }
  }
  f.close();
  return local;
}

// ---------------------------------------------------------------------------
//  Hilfsfunktionen
// ---------------------------------------------------------------------------
static String pathOf(const String& name) { return String(GIF_DIR) + "/" + name; }

bool gifExists(const String& name) { return name.length() && LittleFS.exists(pathOf(name)); }

std::vector<GifFile> listGifs() {
  std::vector<GifFile> out;
  File dir = LittleFS.open(GIF_DIR);
  if (!dir || !dir.isDirectory()) return out;
  File f = dir.openNextFile();
  while (f) {
    if (!f.isDirectory()) {
      String n = f.name();
      int slash = n.lastIndexOf('/');
      if (slash >= 0) n = n.substring(slash + 1);
      String lower = n;
      lower.toLowerCase();
      if (lower.endsWith(".gif")) out.push_back({n, (size_t)f.size()});
    }
    f = dir.openNextFile();
  }
  std::sort(out.begin(), out.end(), [](const GifFile& a, const GifFile& b) { return a.name < b.name; });
  return out;
}

bool isRunningAnimation(const String& name) {
  String n = name;
  n.toLowerCase();
  static const char* still[] = {"schlaf", "sleep", "snack", "hallo", "hello", "idle", "putz", "gaehn",
                               "kaffee", "hantel", "halloween", "weihnacht"};
  for (auto s : still)
    if (n.indexOf(s) >= 0) return false;
  return true;
}

static void applyBrightness() {
  uint8_t pct = cfg.brightness;
  if (nightActive && cfg.nightAction == NIGHT_DIM) pct = cfg.nightDim;
#if TFT_BL >= 0
  tft.setBrightness((uint8_t)(pct * 255 / 100));
  dimScale = 256;
#else
  // quadratische Kurve -> gleichmaessiger wahrgenommene Abstufung
  uint32_t s = (uint32_t)pct * pct * 256 / 10000;
  dimScale = s < 8 ? 8 : (s > 256 ? 256 : s);
#endif
}

void playerApplyDisplay() {
  PLOCK;
  tft.setRotation(cfg.rotation & 3);
  applyBrightness();
  tft.fillScreen(TFT_BLACK);
}

static void closeGif() {
  if (isOpen) {
    gif.close();
    isOpen = false;
  }
}

static void drawCentered(const String& s, int y, const lgfx::IFont* f, uint16_t col) {
  tft.setFont(f);
  tft.setTextColor(col);
  tft.setTextDatum(textdatum_t::middle_center);
  tft.drawString(s, DISPLAY_W / 2, y);
}

static void showNoGifs() {
  tft.fillScreen(TFT_BLACK);
  tft.fillCircle(120, 120, 119, 0x18C3);
  drawCentered("Keine Animation", 92, &fonts::FreeSansBold9pt7b, TFT_WHITE);
  drawCentered("GIFs ueber die", 124, &fonts::FreeSans9pt7b, 0xC618);
  drawCentered("Web-Oberflaeche", 146, &fonts::FreeSans9pt7b, 0xC618);
  drawCentered("hochladen", 168, &fonts::FreeSans9pt7b, 0xC618);
}

static bool openGif(const String& name) {
  closeGif();
  if (!gifExists(name)) return false;
  String p = pathOf(name);
  bool raw = gifHasLocalPalette(p);
  if (!gif.open(p.c_str(), cbOpen, cbClose, cbRead, cbSeek, raw ? cbDrawRaw : cbDraw)) {
    Serial.printf("[GIF] Kann %s nicht oeffnen (Fehler %d)\n", name.c_str(), gif.getLastError());
    return false;
  }
  int cw = gif.getCanvasWidth(), ch = gif.getCanvasHeight();
  if (cw > DISPLAY_W || ch > DISPLAY_H || cw <= 0 || ch <= 0) {
    Serial.printf("[GIF] %s ist %dx%d - maximal %dx%d erlaubt\n", name.c_str(), cw, ch, DISPLAY_W, DISPLAY_H);
    gif.close();
    return false;
  }
  if (raw) {
    gif.setFrameBuf(nullptr);
    gif.setTurboBuf(nullptr);
    gif.setDrawType(GIF_DRAW_RAW);
  } else {
    memset(frameBuf, 0, sizeof(frameBuf));
    gif.setFrameBuf(frameBuf);
    gif.setTurboBuf(turboBuf);
    gif.setDrawType(GIF_DRAW_COOKED);
  }
  offX = (DISPLAY_W - cw) / 2;
  offY = (DISPLAY_H - ch) / 2;
  if (cw < DISPLAY_W || ch < DISPLAY_H) tft.fillScreen(TFT_BLACK);
  isOpen = true;
  curName = name;
  nextFrameAt = millis();
  Serial.printf("[GIF] Spiele %s (%dx%d%s)\n", name.c_str(), cw, ch, raw ? ", lokale Paletten" : "");
  return true;
}

// naechste spielbare Datei nach Playlist-Regeln
static String pickNext(const String& after, bool random) {
  auto files = listGifs();
  std::vector<String> pl;
  for (auto& f : files)
    if (cfg.inPlaylist(f.name)) pl.push_back(f.name);
  if (pl.empty())
    for (auto& f : files) pl.push_back(f.name);  // Notfall: alles
  if (pl.empty()) return "";
  if (pl.size() == 1) return pl[0];
  if (random) {
    String n;
    for (int i = 0; i < 6; i++) {
      n = pl[esp_random() % pl.size()];
      if (n != after) break;
    }
    return n;
  }
  for (size_t i = 0; i < pl.size(); i++)
    if (pl[i] == after) return pl[(i + 1) % pl.size()];
  return pl[0];
}

static void wakeDisplay() {
  if (displayAsleep) {
    tft.wakeup();
    displayAsleep = false;
    playerApplyDisplay();
  }
}

static void startSomething() {
  if (nightActive) {
    if (cfg.nightAction == NIGHT_OFF) return;
    if (cfg.nightAction == NIGHT_GIF && openGif(cfg.nightGif)) return;
  }
  // gewuenschte Datei, sonst Playlist
  if (openGif(cfg.current)) return;
  String n = pickNext(cfg.current, false);
  for (int tries = 0; tries < 8 && n.length(); tries++) {
    if (openGif(n)) return;
    n = pickNext(n, false);
  }
  if (millis() - lastErrorShown > 10000 || lastErrorShown == 0) {
    showNoGifs();
    lastErrorShown = millis();
  }
}

// ---------------------------------------------------------------------------
//  API
// ---------------------------------------------------------------------------
void playerBegin() {
  if (!pmtx) pmtx = xSemaphoreCreateRecursiveMutex();
  PLOCK;
  gif.begin(GIF_PALETTE_RGB565_BE);
  playerApplyDisplay();
  shownSince = millis();
  startSomething();
}

void playerEnableTurbo() {
  PLOCK;
#ifndef HAMI_NO_TURBO
  // Turbo-Puffer (~82 KB) nur, wenn nach dem WLAN-Start genug RAM frei bleibt
  size_t need = 0x6100 + DISPLAY_W * DISPLAY_H;
  if (!turboBuf && ESP.getMaxAllocHeap() > need + 50000) turboBuf = (uint8_t*)malloc(need);
#endif
  Serial.printf("[GIF] Turbo-Modus: %s (freier Heap %u)\n", turboBuf ? "an" : "aus", ESP.getFreeHeap());
}

bool playerPlay(const String& name, bool remember) {
  PLOCK;
  if (!gifExists(name)) return false;
  holding = false;
  wakeDisplay();
  if (remember && cfg.current != name) {
    cfg.current = name;
    settingsSave();
  }
  shownSince = millis();
  if (nightActive && remember) {
    // manuelle Auswahl hat Vorrang - bis zum naechsten Ende der Nachtruhe
    nightOverride = true;
    nightActive = false;
    applyBrightness();
  }
  return openGif(name);
}

void playerRestart() {
  PLOCK;
  if (isOpen && curName.length()) openGif(curName);
}

void playerNext() {
  PLOCK;
  String n = pickNext(curName.length() ? curName : cfg.current, cfg.mode == MODE_SHUFFLE);
  if (n.length()) playerPlay(n, true);
}

void playerSuspend() {
  PLOCK;
  closeGif();
  suspended = true;
}

void playerResume() {
  PLOCK;
  suspended = false;
  if (!holding) startSomething();
}

void playerSetNight(bool active) {
  PLOCK;
  if (!active) nightOverride = false;
  if (active && nightOverride) return;
  if (active == nightActive) return;
  nightActive = active;
  Serial.printf("[Nacht] %s\n", active ? "Beginn" : "Ende");
  if (active && cfg.nightAction == NIGHT_OFF) {
    closeGif();
    tft.fillScreen(TFT_BLACK);
#if TFT_BL >= 0
    tft.setBrightness(0);
#endif
    tft.sleep();
    displayAsleep = true;
    return;
  }
  wakeDisplay();
  applyBrightness();
  if (!holding && !suspended) {
    closeGif();
    startSomething();
  }
}

bool playerNightActive() { return nightActive; }

void playerShowMessage(const String& title, const String& l1, const String& l2, uint32_t ms, const String& qr) {
  PLOCK;
  wakeDisplay();
  closeGif();
  tft.setRotation(cfg.rotation & 3);
  tft.fillScreen(TFT_BLACK);
  tft.fillCircle(120, 120, 119, 0x2104);
  tft.drawCircle(120, 120, 118, 0xFD20);
  tft.drawCircle(120, 120, 117, 0xFD20);
  if (qr.length()) {
    drawCentered(title, 38, &fonts::FreeSansBold9pt7b, 0xFE60);
    tft.fillRoundRect(72, 54, 96, 96, 6, TFT_WHITE);
    tft.qrcode(qr.c_str(), 76, 58, 88, 3);
    drawCentered(l1, 168, &fonts::FreeSans9pt7b, TFT_WHITE);
    drawCentered(l2, 192, &fonts::Font2, 0xC618);
  } else {
    drawCentered(title, 84, &fonts::FreeSansBold12pt7b, 0xFE60);
    drawCentered(l1, 124, &fonts::FreeSans9pt7b, TFT_WHITE);
    drawCentered(l2, 154, &fonts::FreeSans9pt7b, 0xC618);
  }
  holding = true;
  holdUntil = millis() + ms;
}

String playerCurrent() {
  PLOCK;
  return isOpen ? curName : String("");
}
float playerFps() { return fps; }
bool playerTurbo() { return turboBuf != nullptr; }
uint32_t playerLastDecodeMs() { return lastDecode; }

static void addOdometer(int frameDelayMs) {
  if (!isRunningAnimation(curName)) return;
  // ein Hamster rennt im Rad etwa 0,8 m/s; beim Sprint doppelt so schnell
  double v = 0.8 * cfg.speed / 100.0;
  if (curName.indexOf("sprint") >= 0) v *= 2;
  odoPending += v * frameDelayMs / 1000.0 * 100.0 / cfg.speed;  // v * reale Abspielzeit
}

void playerFlushOdometer(bool force) {
  PLOCK;
  if (odoPending <= 0) return;
  time_t now = time(nullptr);
  struct tm lt;
  localtime_r(&now, &lt);
  if (now > 1700000000 && lt.tm_yday != cfg.odoDay) {
    cfg.odoDay = lt.tm_yday;
    cfg.odoToday = 0;
  }
  cfg.odoTotal += odoPending;
  cfg.odoToday += odoPending;
  odoPending = 0;
  if (force || millis() - odoLastSave > 10UL * 60 * 1000) {
    settingsSaveOdo();
    odoLastSave = millis();
  }
}

void playerLoop() {
  PLOCK;
  uint32_t now = millis();

  if (holding) {
    if ((int32_t)(now - holdUntil) < 0) return;
    holding = false;
    tft.fillScreen(TFT_BLACK);
    if (!suspended) startSomething();
  }
  if (suspended || displayAsleep) return;

  if (!isOpen) {
    static uint32_t lastTry = 0;
    if (now - lastTry > 3000) {
      lastTry = now;
      startSomething();
    }
    return;
  }

  if ((int32_t)(now - nextFrameAt) < 0) return;

  int delayMs = 0;
  uint32_t t0 = millis();
  tft.startWrite();
  int rc = gif.playFrame(false, &delayMs);
  flushStrip();
  tft.waitDMA();
  tft.endWrite();
  lastDecode = millis() - t0;

  if (rc < 0) {
    Serial.printf("[GIF] Dekodierfehler in %s (%d)\n", curName.c_str(), gif.getLastError());
    closeGif();
    nextFrameAt = millis() + 500;
    return;
  }
  if (delayMs < 20) delayMs = 100;  // wie Browser: 0/10 ms -> 100 ms
  addOdometer(delayMs);
  uint32_t d = (uint32_t)delayMs * 100 / cfg.speed;
  nextFrameAt = t0 + d;
  if ((int32_t)(millis() - nextFrameAt) > 0) nextFrameAt = millis();

  // FPS
  fpsFrames++;
  if (now - fpsT0 >= 2000) {
    fps = fpsFrames * 1000.0f / (now - fpsT0);
    fpsFrames = 0;
    fpsT0 = now;
    playerFlushOdometer(false);
  }

  // Ende eines Durchlaufs -> ggf. zur naechsten Animation wechseln
  if (rc == 0 && !nightActive && cfg.mode != MODE_SINGLE) {
    if (now - shownSince >= (uint32_t)cfg.interval * 60000UL) {
      String n = pickNext(curName, cfg.mode == MODE_SHUFFLE);
      shownSince = now;
      if (n.length() && n != curName) {
        cfg.current = n;  // nicht speichern (Flash schonen)
        openGif(n);
      }
    }
  }
}

// Wie lange darf der Task schlafen, bis wieder etwas zu tun ist?
static uint32_t playerIdleMs() {
  PLOCK;
  uint32_t now = millis();
  int32_t w;
  if (holding) w = (int32_t)(holdUntil - now);
  else if (suspended || displayAsleep || !isOpen) w = 50;
  else w = (int32_t)(nextFrameAt - now);
  if (w < 2) w = 2;  // immer kurz abgeben, damit WLAN/Webserver drankommen
  if (w > 50) w = 50;
  return (uint32_t)w;
}

static void playerTask(void*) {
  for (;;) {
    playerLoop();
    vTaskDelay(pdMS_TO_TICKS(playerIdleMs()));
  }
}

void playerStartTask() {
  // Prioritaet 3 > loop() (1): die Animation hat Vorrang vor dem Webserver
  xTaskCreate(playerTask, "hami_gif", 8192, nullptr, 3, nullptr);
}
