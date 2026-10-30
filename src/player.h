// GIF-Wiedergabe auf dem GC9A01
#pragma once
#include <Arduino.h>
#include <vector>

struct GifFile {
  String name;
  size_t size;
};

void playerBegin();
void playerLoop();
void playerStartTask();                // Animation in eigenem Task (empfohlen)
void playerLock();                     // fuer Zugriffe auf cfg aus anderen Tasks
void playerUnlock();
void playerEnableTurbo();              // nach dem WLAN-Start aufrufen
bool playerPlay(const String& name, bool remember = true);  // sofort abspielen
void playerNext();
void playerRestart();                  // aktuelle Animation neu zeichnen
void playerSuspend();                  // Datei schliessen (z. B. fuer Upload)
void playerResume();                   // nach Suspend weiter
void playerApplyDisplay();             // Rotation/Helligkeit neu setzen
void playerSetNight(bool active);      // Nachtruhe an/aus
bool playerNightActive();
void playerShowMessage(const String& title, const String& l1, const String& l2,
                       uint32_t ms, const String& qr = "");
String playerCurrent();
float playerFps();
bool playerTurbo();
uint32_t playerLastDecodeMs();
void playerFlushOdometer(bool force);  // km-Zaehler sichern
std::vector<GifFile> listGifs();
bool gifExists(const String& name);
bool isRunningAnimation(const String& name);
