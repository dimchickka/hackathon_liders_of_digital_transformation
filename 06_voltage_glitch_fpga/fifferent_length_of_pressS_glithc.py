"""
Только глитчи с растущей длительностью, без reset.
Остановка — Ctrl+C. В конце показывает последнее значение.

1 тик = 20 нс. width_ticks: 1..255 → 20 нс .. 5.1 мкс.
"""

import time
import serial
from serial.tools import list_ports


# --- Настройки ---
DEVICE_HINT  = "CH340"
BAUD         = 115200
TIMEOUT      = 0.2

# Длительность глитча в тиках (1 тик = 20 нс)
WIDTH_START_TICKS = 1        # 20 нс
WIDTH_STEP_TICKS  = 1        # +20 нс за цикл
WIDTH_MAX_TICKS   = 255      # 5.1 мкс — предел 8-битного поля

# delay=0 — глитч сразу, без паузы после reset-фазы
DELAY_TICKS = 0

# Пауза между глитчами
INTER_CYCLE_DELAY = 0.05     # 50 мс

TICK_NS = 20                 # 1 тик @ 50 МГц


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
                print(f"Автовыбор: {p.device}")
                return p.device
    while True:
        sel = input("Номер USB-UART адаптера: ").strip()
        if sel.isdecimal() and 1 <= int(sel) <= len(ports):
            return ports[int(sel) - 1].device


def pkt(delay_ticks, width_ticks):
    """AA D_H D_L 00 W_L 01 — reset_gate 100 мкс + пауза + глитч.

    Примечание: FPGA всегда сначала даёт reset_gate 100 мкс (это в HDL
    зашито в ST_RESET). Убрать его совсем без перепрошивки нельзя.
    Здесь убран только явный reset-ПАКЕТ, который ты слал отдельно.
    """
    return bytes([
        0xAA,
        (delay_ticks >> 8) & 0xFF,
        delay_ticks & 0xFF,
        0x00,
        width_ticks & 0xFF,
        0x01,
    ])


def fmt_ns(ticks):
    ns = ticks * TICK_NS
    if ns < 1000:
        return f"{ns:5d} нс"
    if ns < 1_000_000:
        return f"{ns/1000:7.3f} мкс"
    return f"{ns/1_000_000:7.3f} мс"


def main():
    port = pick_port()
    print(f"Открываю {port} @ {BAUD}\n")

    with serial.Serial(port, BAUD, timeout=TIMEOUT, write_timeout=1) as s:
        time.sleep(0.2)
        s.reset_input_buffer(); time.sleep(0.3); s.reset_input_buffer()

        input("Enter — начать перебор длительности глитча (Ctrl+C для стопа)...\n")

        width_ticks = WIDTH_START_TICKS
        cycle = 0
        last_ticks = 0
        t_start = time.monotonic()

        try:
            while width_ticks <= WIDTH_MAX_TICKS:
                cycle += 1

                glitch_pkt = pkt(DELAY_TICKS, width_ticks)
                s.write(glitch_pkt); s.flush()
                s.read(2)   # AA 55

                last_ticks = width_ticks
                print(f"[цикл {cycle:4d}] глитч "
                      f"{width_ticks:3d}t = {fmt_ns(width_ticks)}")

                time.sleep(INTER_CYCLE_DELAY)

                width_ticks += WIDTH_STEP_TICKS

        except KeyboardInterrupt:
            pass
        finally:
            total = time.monotonic() - t_start
            print("\n" + "=" * 60)
            print("ОСТАНОВЛЕНО.")
            print(f"Циклов сделано         : {cycle}")
            print(f"Последняя длит. глитча : {last_ticks} тиков = "
                  f"{fmt_ns(last_ticks)}")
            print(f"Общее время работы     : {total:.1f} с")
            print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except (serial.SerialException, OSError, RuntimeError) as e:
        print(f"Ошибка: {e}")