// ============================================================================
//  Uhr-Ansicht "Digital"
//
//  Aufbau (wie Entwurf B):
//   * Radrand mit 60 Sprossen - die Sekunden fuellen die Sprossen im
//     Uhrzeigersinn von oben auf
//   * grosse Uhrzeit (Doppelpunkt blinkt), Wochentag und Datum
//   * unten laeuft der Hamster (kleine eingebettete Animation)
//
//  Gezeichnet wird direkt auf das Display; Text und Hamster ueber zwei
//  Sprites, deren Speicher sich die Uhr vom GIF-Framepuffer leiht.
//  Pixel ausserhalb der Innenflaeche sind im Sprite "transparent" (KEY),
//  damit die Sprossen am Rand nicht ueberdeckt werden.
// ============================================================================
#include "clockface.h"
#include <time.h>
#include "clock_assets.h"
#include "display.h"

namespace {

constexpr int CX = 120, CY = 120;
constexpr int R_EDGE = 119, R_RUNG = 116, R_RUNG_S = 112, R_TRACK = 103, R_INNER = 101;
constexpr uint16_t KEY = 0xF81F;  // Magenta = transparent in den Sprites

// Textbereich (Uhrzeit, Wochentag, Datum)
constexpr int TX = 24, TY = 38, TW = 192, TH = 100;

// Farben (RGB888) - identisch mit den gezeichneten Animationen
constexpr uint32_t C_CREAM = 0xFCEBCB, C_BAND = 0xCF7F1F, C_RUNG = 0xFFD47E, C_RUNG_L = 0x8A4F12;
constexpr uint32_t C_RIM = 0xE8952A, C_FILLED = 0xFFF6D8, C_INK = 0x4A2C1A, C_SOFT = 0x8A5A2B;

const char* const TAGE[] = {"Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"};
const char* const MONATE[] = {"Januar", "Februar", "M\xC3\xA4rz", "April",  "Mai",      "Juni",
                              "Juli",   "August",  "September", "Oktober", "November", "Dezember"};

LGFX_Sprite txt(&tft);
LGFX_Sprite ham(&tft);
uint16_t dimS = 256;
int lastSec = -1, lastMin = -1, lastYday = -1;
bool lastColon = false, lastValid = false;
uint32_t nextHam = 0;
bool running = false;

uint16_t col(uint32_t rgb) {
  uint32_t r = ((rgb >> 16) & 255) * dimS >> 8, g = ((rgb >> 8) & 255) * dimS >> 8, b = (rgb & 255) * dimS >> 8;
  return lgfx::color565(r, g, b);
}

inline uint16_t dimBE(uint16_t be) {
  if (dimS >= 256) return be;
  uint16_t v = (uint16_t)((be >> 8) | (be << 8));
  uint32_t r = ((v >> 11) & 31) * dimS >> 8, g = ((v >> 5) & 63) * dimS >> 8, b = (v & 31) * dimS >> 8;
  v = (uint16_t)((r << 11) | (g << 5) | b);
  return (uint16_t)((v >> 8) | (v << 8));
}

// Winkel: 0 = 12 Uhr, im Uhrzeigersinn  ->  LovyanGFX: 0 = 3 Uhr
inline float lg(float deg) {
  float a = deg - 90.0f;
  while (a < 0) a += 360.0f;
  while (a >= 360.0f) a -= 360.0f;
  return a;
}

void arc(int rOut, int rIn, float deg0, float deg1, uint16_t c) {
  float a0 = lg(deg0), a1 = lg(deg1);
  if (a1 < a0) {  // ueber 3 Uhr hinweg -> in zwei Teile
    tft.fillArc(CX, CY, rOut, rIn, a0, 360.0f, c);
    tft.fillArc(CX, CY, rOut, rIn, 0.0f, a1, c);
  } else {
    tft.fillArc(CX, CY, rOut, rIn, a0, a1, c);
  }
}

void drawRung(int i, bool filled) {
  bool big = (i % 5) == 0;
  float deg = i * 6.0f;
  float half = big ? 2.1f : 1.2f;
  int r1 = big ? R_RUNG : R_RUNG_S;
  // Band hinter der Sprosse auffrischen, dann Umriss + Fuellung
  arc(R_RUNG - 2, R_TRACK + 1, deg - 2.9f, deg + 2.9f, col(C_BAND));
  arc(r1, R_TRACK + 1, deg - half - 0.6f, deg + half + 0.6f, col(C_RUNG_L));
  arc(r1 - 1, R_TRACK + 2, deg - half, deg + half, col(filled ? C_FILLED : C_RUNG));
}

void drawStaticFace() {
  tft.fillScreen(TFT_BLACK);
  tft.fillCircle(CX, CY, R_EDGE, col(C_RIM));
  tft.fillArc(CX, CY, R_RUNG, R_TRACK, 0, 360, col(C_BAND));
  tft.fillArc(CX, CY, R_RUNG + 1, R_RUNG - 1, 0, 360, col(C_RUNG_L));
  for (int i = 0; i < 60; i++) drawRung(i, false);
  tft.fillArc(CX, CY, R_TRACK + 1, R_INNER, 0, 360, col(C_RUNG_L));
  tft.fillCircle(CX, CY, R_INNER, col(C_CREAM));
}

// Sprite-Hintergrund: Innenflaeche Creme, Rest transparent
void spriteBase(LGFX_Sprite& s, int x0, int y0) {
  s.fillScreen(KEY);
  s.fillCircle(CX - x0, CY - y0, R_INNER, col(C_CREAM));
}

void drawText(const struct tm* t, bool valid, bool colon) {
  spriteBase(txt, TX, TY);
  int cx = CX - TX;
  if (valid) {
    char hh[3], mm[3];
    snprintf(hh, sizeof(hh), "%02d", t->tm_hour);
    snprintf(mm, sizeof(mm), "%02d", t->tm_min);
    txt.loadFont(CLOCK_FONT_TIME);
    txt.setTextColor(col(C_INK), col(C_CREAM));
    int gap = txt.textWidth(":") / 2 + 2;
    txt.setTextDatum(textdatum_t::middle_right);
    txt.drawString(hh, cx - gap, 36);
    txt.setTextDatum(textdatum_t::middle_left);
    txt.drawString(mm, cx + gap, 36);
    if (colon) {
      txt.setTextDatum(textdatum_t::middle_center);
      txt.drawString(":", cx, 33);
    }
    txt.unloadFont();

    char date[32];
    snprintf(date, sizeof(date), "%d. %s %d", t->tm_mday, MONATE[t->tm_mon % 12], t->tm_year + 1900);
    txt.loadFont(CLOCK_FONT_DAY);
    txt.setTextColor(col(C_SOFT), col(C_CREAM));
    txt.setTextDatum(textdatum_t::middle_center);
    txt.drawString(TAGE[t->tm_wday % 7], cx, 70);
    txt.unloadFont();
    txt.loadFont(CLOCK_FONT_DATE);
    txt.setTextColor(col(C_SOFT), col(C_CREAM));
    txt.setTextDatum(textdatum_t::middle_center);
    txt.drawString(date, cx, 88);
    txt.unloadFont();
  } else {
    txt.loadFont(CLOCK_FONT_TIME);
    txt.setTextColor(col(C_INK), col(C_CREAM));
    txt.setTextDatum(textdatum_t::middle_center);
    txt.drawString("--:--", cx, 36);
    txt.unloadFont();
    txt.loadFont(CLOCK_FONT_DATE);
    txt.setTextColor(col(C_SOFT), col(C_CREAM));
    txt.drawString("Uhrzeit fehlt", cx, 70);
    txt.drawString("WLAN verbinden", cx, 88);
    txt.unloadFont();
  }
  txt.pushSprite(&tft, TX, TY, KEY);
}

// GIF-Callback: nur deckende Pixel in den Hamster-Sprite schreiben
void hamDraw(GIFDRAW* d) {
  int y = d->iY + d->y;
  if (y < 0 || y >= CLOCK_HAM_H) return;
  uint16_t* buf = (uint16_t*)ham.getBuffer();
  const uint8_t* s = d->pPixels;
  const uint16_t* pal = d->pPalette;
  // nur innerhalb der Innenflaeche zeichnen - ausserhalb ist der Sprite
  // transparent und wuerde Reste alter Bilder stehen lassen
  int dy = CLOCK_HAM_Y + y - CY;
  for (int i = 0; i < d->iWidth; i++) {
    int x = d->iX + i;
    if (x >= CLOCK_HAM_W) break;
    uint8_t c = s[i];
    if (d->ucHasTransparency && c == d->ucTransparent) continue;
    int dx = CLOCK_HAM_X + x - CX;
    if (dx * dx + dy * dy > R_INNER * R_INNER) continue;
    buf[y * CLOCK_HAM_W + x] = dimBE(pal[c]);
  }
}

uint32_t hamFrame(AnimatedGIF& gif) {
  spriteBase(ham, CLOCK_HAM_X, CLOCK_HAM_Y);
  int delayMs = 70;
  if (gif.playFrame(false, &delayMs) < 0) gif.reset();
  ham.pushSprite(&tft, CLOCK_HAM_X, CLOCK_HAM_Y, KEY);
  return delayMs < 20 ? 70 : (uint32_t)delayMs;
}

}  // namespace

bool clockFaceStart(AnimatedGIF& gif, uint8_t* work, size_t workLen, uint16_t dimScale) {
  size_t need = (size_t)TW * TH * 2 + (size_t)CLOCK_HAM_W * CLOCK_HAM_H * 2;
  if (workLen < need) return false;
  dimS = dimScale;
  txt.setColorDepth(16);
  ham.setColorDepth(16);
  txt.setBuffer(work, TW, TH, 16);
  ham.setBuffer(work + TW * TH * 2, CLOCK_HAM_W, CLOCK_HAM_H, 16);
  if (!gif.open((uint8_t*)CLOCK_HAMSTER_GIF, (int)CLOCK_HAMSTER_GIF_LEN, hamDraw)) return false;
  gif.setFrameBuf(nullptr);
  gif.setTurboBuf(nullptr);
  gif.setDrawType(GIF_DRAW_RAW);
  tft.startWrite();
  drawStaticFace();
  tft.endWrite();
  lastSec = lastMin = lastYday = -1;
  lastValid = false;
  nextHam = 0;
  running = true;
  return true;
}

void clockFaceStop(AnimatedGIF& gif) {
  if (!running) return;
  gif.close();
  running = false;  // Sprite-Speicher gehoert dem GIF-Framepuffer, nichts freigeben
}

uint32_t clockFaceStep(AnimatedGIF& gif) {
  if (!running) return 50;
  time_t now = time(nullptr);
  struct tm t;
  localtime_r(&now, &t);
  bool valid = now > 1700000000;
  uint32_t ms = millis();

  tft.startWrite();
  if (!valid || t.tm_sec != lastSec || valid != lastValid) {
    int sec = valid ? t.tm_sec : -1;
    // neue Minute (oder Start): alle Sprossen leeren, sonst nur die neue fuellen
    if (!valid || lastSec < 0 || t.tm_min != lastMin || sec < lastSec) {
      for (int i = 0; i < 60; i++) drawRung(i, valid && i <= sec);
    } else {
      for (int i = lastSec + 1; i <= sec; i++) drawRung(i, true);
    }
    bool colon = (t.tm_sec % 2) == 0;
    if (!valid || valid != lastValid || t.tm_min != lastMin || t.tm_yday != lastYday || colon != lastColon) {
      drawText(&t, valid, colon);
      lastColon = colon;
    }
    lastSec = sec;
    lastMin = t.tm_min;
    lastYday = t.tm_yday;
    lastValid = valid;
  }
  uint32_t wait = 50;
  if ((int32_t)(ms - nextHam) >= 0) {
    uint32_t d = hamFrame(gif);
    nextHam = ms + d;
  }
  int32_t toHam = (int32_t)(nextHam - millis());
  if (toHam < (int32_t)wait) wait = toHam < 2 ? 2 : (uint32_t)toHam;
  tft.endWrite();
  return wait;
}
