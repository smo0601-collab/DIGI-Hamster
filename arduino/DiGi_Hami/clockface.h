// Uhr-Ansicht "Digital": Hamsterrad als Uhr mit Datum
#pragma once
#include <AnimatedGIF.h>
#include <Arduino.h>

// Zeichnet das Zifferblatt neu und richtet die Zeichenflaechen ein.
// work: Arbeitsspeicher (der GIF-Framepuffer wird mitbenutzt, >= 53 KB)
bool clockFaceStart(AnimatedGIF& gif, uint8_t* work, size_t workLen, uint16_t dimScale);
// Aktualisiert Sekunden, Uhrzeit, Datum und den laufenden Hamster.
// Gibt zurueck, in wie vielen ms der naechste Aufruf faellig ist.
uint32_t clockFaceStep(AnimatedGIF& gif);
void clockFaceStop(AnimatedGIF& gif);
