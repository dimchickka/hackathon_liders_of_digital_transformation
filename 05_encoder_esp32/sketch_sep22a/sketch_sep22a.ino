/*
  ESP32-C3 encoder emulator with a serial START/STOP protocol.

  GPIO4 -> encoder A / RP2040 GPIO27
  GPIO5 -> encoder B / RP2040 GPIO29
  GPIO6 -> encoder button / RP2040 GPIO28
  GND   -> target GND

  Lines are only pulled LOW or released. HIGH comes from target pull-ups.
  Reconstructed from the colleague's description; hardware not verified here.
*/

#include <Arduino.h>
#include <string.h>

constexpr uint8_t PIN_ENCODER_A = 4;
constexpr uint8_t PIN_ENCODER_B = 5;
constexpr uint8_t PIN_ENCODER_SW = 6;

constexpr uint16_t FIRST_ATTEMPT = 3912;
constexpr uint16_t LAST_ATTEMPT = 3920;

constexpr uint32_t PHASE_DELAY_MS = 8;
constexpr uint32_t BETWEEN_DETENTS_MS = 82;
constexpr uint32_t BEFORE_BUTTON_MS = 15;
constexpr uint32_t BUTTON_DOWN_MS = 15;
constexpr uint32_t BUTTON_RELEASE_MS = 35;
constexpr uint32_t AFTER_ATTEMPT_MS = 1360;

bool encoderAt11 = true;
bool stopRequested = false;
bool startRequested = false;
bool started = false;
bool finished = false;
bool stopAnnounced = false;
char commandBuffer[16] = {};
uint8_t commandLength = 0;

void pullLow(uint8_t pin) {
  digitalWrite(pin, LOW);
  pinMode(pin, OUTPUT);
}

void releaseLine(uint8_t pin) {
  pinMode(pin, INPUT);
}

void releaseAllLines() {
  releaseLine(PIN_ENCODER_A);
  releaseLine(PIN_ENCODER_B);
  releaseLine(PIN_ENCODER_SW);
}

void processCommandLine() {
  commandBuffer[commandLength] = '\0';
  if (strcmp(commandBuffer, "START") == 0 && !started && !finished && !stopRequested) {
    startRequested = true;
  } else if (strcmp(commandBuffer, "STOP") == 0) {
    stopRequested = true;
  }
  commandLength = 0;
}

void pollCommands() {
  while (Serial.available() > 0) {
    const char c = static_cast<char>(Serial.read());
    if (c == 'X' || c == 'x') {
      stopRequested = true;
      commandLength = 0;
    } else if (c == '\n' || c == '\r') {
      if (commandLength > 0) processCommandLine();
    } else if (commandLength < sizeof(commandBuffer) - 1) {
      commandBuffer[commandLength++] = c;
    } else {
      commandLength = 0;
    }
  }
}

bool controlledDelay(uint32_t durationMs) {
  for (uint32_t i = 0; i < durationMs; ++i) {
    pollCommands();
    if (stopRequested) return false;
    delay(1);
  }
  pollCommands();
  return !stopRequested;
}

bool rotateOneStepUp() {
  if (encoderAt11) {
    pullLow(PIN_ENCODER_B);       // 11 -> 01
    if (!controlledDelay(PHASE_DELAY_MS)) return false;
    pullLow(PIN_ENCODER_A);       // 01 -> 00
    encoderAt11 = false;
  } else {
    releaseLine(PIN_ENCODER_B);   // 00 -> 10
    if (!controlledDelay(PHASE_DELAY_MS)) return false;
    releaseLine(PIN_ENCODER_A);   // 10 -> 11
    encoderAt11 = true;
  }
  return controlledDelay(BETWEEN_DETENTS_MS);
}

bool rotateOneStepDown() {
  if (encoderAt11) {
    pullLow(PIN_ENCODER_A);       // 11 -> 10
    if (!controlledDelay(PHASE_DELAY_MS)) return false;
    pullLow(PIN_ENCODER_B);       // 10 -> 00
    encoderAt11 = false;
  } else {
    releaseLine(PIN_ENCODER_A);   // 00 -> 01
    if (!controlledDelay(PHASE_DELAY_MS)) return false;
    releaseLine(PIN_ENCODER_B);   // 01 -> 11
    encoderAt11 = true;
  }
  return controlledDelay(BETWEEN_DETENTS_MS);
}

bool clickEncoder() {
  pullLow(PIN_ENCODER_SW);
  if (!controlledDelay(BUTTON_DOWN_MS)) return false;
  releaseLine(PIN_ENCODER_SW);
  return controlledDelay(BUTTON_RELEASE_MS);
}

bool enterDigitFromZero(uint8_t digit) {
  if (digit <= 5) {
    for (uint8_t step = 0; step < digit; ++step) {
      if (!rotateOneStepUp()) return false;
    }
  } else {
    for (uint8_t step = 0; step < 10 - digit; ++step) {
      if (!rotateOneStepDown()) return false;
    }
  }
  if (!controlledDelay(BEFORE_BUTTON_MS)) return false;
  return clickEncoder();
}

bool enterAttempt(uint16_t value) {
  const uint8_t digits[4] = {
    static_cast<uint8_t>((value / 1000) % 10),
    static_cast<uint8_t>((value / 100) % 10),
    static_cast<uint8_t>((value / 10) % 10),
    static_cast<uint8_t>(value % 10)
  };

  Serial.printf("TRY %04u %lu\n", value, static_cast<unsigned long>(millis()));
  for (const uint8_t digit : digits) {
    if (!enterDigitFromZero(digit)) return false;
  }
  Serial.printf("SUBMITTED %04u %lu\n", value, static_cast<unsigned long>(millis()));
  return true;
}

void runSearch() {
  started = true;
  Serial.printf("STARTED %04u %04u\n", FIRST_ATTEMPT, LAST_ATTEMPT);
  for (uint16_t attempt = FIRST_ATTEMPT; attempt <= LAST_ATTEMPT; ++attempt) {
    if (!enterAttempt(attempt) || !controlledDelay(AFTER_ATTEMPT_MS)) break;
  }
  releaseAllLines();
  finished = true;
  if (stopRequested) {
    Serial.printf("STOPPED %lu\n", static_cast<unsigned long>(millis()));
    stopAnnounced = true;
  } else {
    Serial.printf("FINISHED %lu\n", static_cast<unsigned long>(millis()));
  }
}

void setup() {
  Serial.begin(115200);
  releaseAllLines();
  Serial.println("READY");
}

void loop() {
  pollCommands();
  if (stopRequested && !stopAnnounced) {
    releaseAllLines();
    finished = true;
    Serial.printf("STOPPED %lu\n", static_cast<unsigned long>(millis()));
    stopAnnounced = true;
  } else if (startRequested && !started && !finished) {
    runSearch();
  }
  delay(1);
}
