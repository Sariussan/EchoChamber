#include <Wire.h>
#include "rgb_lcd.h"

rgb_lcd lcd;

int state = 0; // 0 = Standby, 1 = Aufnahme
unsigned long lastSwitch = 0;
const unsigned long switchInterval = 5000; // 5 Sekunden

// Für ASCII-Animation
int animFrame = 0;
const char *frames[] = {
    "................",
    "\\\\\\\\\\\\\\\\",
    "||||||||||||||||",
    "████████████████",
    "////////////////"};
const int frameCount = sizeof(frames) / sizeof(frames[0]);

// Für pulsierende Farbe
int brightness = 100;
int dir = 5;

void setup()
{
  Serial.begin(9600);
  lcd.begin(16, 2);
  setState(0);
}

void loop()
{
  unsigned long now = millis();

  // Zustandswechsel alle 5 Sekunden
  if (now - lastSwitch > switchInterval)
  {
    state = (state + 1) % 2;
    setState(state);
    lastSwitch = now;
  }

  if (state == 1)
  {
    // 1. Animation anzeigen
    animateAscii();

    // 2. Pulsierendes Rot (zwischen 100 und 255)
    brightness += dir;
    if (brightness >= 255 || brightness <= 100)
      dir *= -1;
    lcd.setRGB(brightness, 0, 0);

    delay(150); // Animationsgeschwindigkeit
  }

  // Serial control
  if (Serial.available())
  {
    char c = Serial.read();
    if (c == '0')
      setState(0);
    if (c == '1')
      setState(1);
  }
}

void setState(int newState)
{
  state = newState;
  lcd.clear();

  if (state == 0)
  {
    lcd.setRGB(255, 255, 255); // Weiß – Standby
  }
  else if (state == 1)
  {
    // Startwert für Aufnahme-Modus
    animFrame = 0;
    brightness = 100;
    dir = 5;
  }
}

void animateAscii()
{
  lcd.setCursor(0, 0);
  lcd.print(frames[animFrame % frameCount]);

  lcd.setCursor(0, 1);
  lcd.print(frames[(animFrame + 1) % frameCount]);

  animFrame++;
}
