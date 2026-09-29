"""
Один reset + один глитч 20 нс.
Пакет: AA 00 00 00 01 01 → reset_gate 100 мкс, глитч 20 нс.
Ответ FPGA: AA 55.
"""

import time
import serial
from serial.tools import list_ports


DEVICE_HINT = "CH340"
BAUD        = 115200
TIMEOUT     = 0.2

# delay=0 тиков, width=1 тик (= 20 нс @ 50 МГц)
PACKET = bytes([0xAA, 0x00, 0x00, 0x00, 0x01, 0x01])


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


def main():
    port = pick_port()
    print(f"Открываю {port} @ {BAUD}\n")

    with serial.Serial(port, BAUD, timeout=TIMEOUT, write_timeout=1) as s:
        time.sleep(0.2)
        s.reset_input_buffer()
        time.sleep(0.3)
        s.reset_input_buffer()

        print(f"Отправляю пакет: {PACKET.hex(' ').upper()}")
        print("reset_gate 100 мкс → глитч 20 нс")

        t0 = time.monotonic()
        s.write(PACKET)
        s.flush()
        resp = s.read(2)
        dt = time.monotonic() - t0

        print(f"Ответ FPGA : {resp.hex(' ').upper() or '(нет)'} "
              f"за {dt*1000:.1f} мс")

        if resp in (b"\xAA\x55", b"\x55\xAA"):
            print("OK.")
        else:
            print("Не получил AA 55. Проверь связь.")


if __name__ == "__main__":
    try:
        main()
    except (serial.SerialException, OSError, RuntimeError) as e:
        print(f"Ошибка: {e}")