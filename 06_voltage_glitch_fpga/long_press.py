"""
10 секунд держим glitch_out активным. Потом выходим.

Работает с прошивкой, где FLAG=0x02 = удержание glitch_out.
Один пакет = максимум ~1.31 мс, поэтому шлём их в цикле 10 секунд.
"""

import time
import serial
from serial.tools import list_ports


# --- Настройки ---
DEVICE_HINT  = "CH340"        # подстрока в описании; None = спросить вручную
DURATION_SEC = 10.0
HOLD_TICKS   = 0xFFFF         # макс. длительность одного пакета (~1.31 мс)
BAUD         = 115200
TIMEOUT      = 0.2


def pick_port():
    ports = sorted(list_ports.comports(), key=lambda p: p.device)
    if not ports:
        raise RuntimeError("COM-порты не найдены.")

    print("Доступные COM-порты:")
    for i, p in enumerate(ports, 1):
        vidpid = f"{p.vid:04X}:{p.pid:04X}" if p.vid else "-"
        print(f"  {i}. {p.device}  [{vidpid}]  {p.description}")

    if DEVICE_HINT:
        for p in ports:
            if DEVICE_HINT.lower() in (p.description or "").lower():
                print(f"Автовыбор: {p.device} (совпало с '{DEVICE_HINT}')")
                return p.device

    while True:
        sel = input("Номер USB-UART адаптера: ").strip()
        if sel.isdecimal() and 1 <= int(sel) <= len(ports):
            return ports[int(sel) - 1].device


def hold_packet(ticks):
    """AA D_H D_L 00 00 02 — FLAG=0x02 = удержание glitch_out на ticks тиков."""
    return bytes([
        0xAA,
        (ticks >> 8) & 0xFF,
        ticks & 0xFF,
        0x00,
        0x00,
        0x02,
    ])


def main():
    port = pick_port()
    print(f"Открываю {port} @ {BAUD}\n")

    pkt = hold_packet(HOLD_TICKS)
    print(f"Пакет удержания: {pkt.hex(' ').upper()}")
    print(f"(один пакет держит ~{HOLD_TICKS * 20 / 1e6:.2f} мс)\n")

    with serial.Serial(port, BAUD, timeout=TIMEOUT, write_timeout=1) as s:
        time.sleep(0.2)
        s.reset_input_buffer(); time.sleep(0.3); s.reset_input_buffer()

        input("Enter — начать 10 секунд удержания...")
        print(f"Держу glitch_out {DURATION_SEC:.0f} секунд...")

        t0 = time.monotonic()
        t_end = t0 + DURATION_SEC
        n = 0

        while time.monotonic() < t_end:
            s.write(pkt)
            s.flush()
            n += 1
            # не ждём ответа, чтобы паузы между пакетами были минимальны

        dt = time.monotonic() - t0
        print(f"\nГотово. Отправлено пакетов: {n}, время: {dt:.2f} с")


if __name__ == "__main__":
    try:
        main()
    except (serial.SerialException, OSError, RuntimeError) as e:
        print(f"Ошибка: {e}")
    except KeyboardInterrupt:
        print("\nПрервано.")