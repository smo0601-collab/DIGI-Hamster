// WLAN, Captive Portal, Web-Server und REST-API
#pragma once
#include <Arduino.h>

enum NetState : uint8_t { NET_CONNECTING, NET_STA, NET_AP };

void netBegin();
void netLoop();
NetState netState();
String netIp();
String netApName();
bool netTimeValid();
void netShowInfo();   // IP/QR auf dem Display anzeigen
void netEvaluateNight();
