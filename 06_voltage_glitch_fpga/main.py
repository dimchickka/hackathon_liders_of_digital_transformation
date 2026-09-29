"""Check UART, reset_gate, and glitch_out on a MAX II glitcher board.

Requires pyserial: python -m pip install pyserial
UART: 115200 8N1, raw packet AA 27 10 00 64 01.
"""

import time

import serial
from serial.tools import list_ports


PACKET = bytes.fromhex("AA 27 10 00 64 01")


def choose_port():
    ports = sorted(list_ports.comports(), key=lambda port: port.device)
    if not ports:
        raise RuntimeError("COM-порты не найдены. Подключите USB–UART адаптер.")

    print("Доступные COM-порты:")
    for number, port in enumerate(ports, start=1):
        print(f"  {number}. {port.device}: {port.description}")

    if len(ports) == 1:
        print(f"Выбран единственный порт: {ports[0].device}")
        return ports[0].device

    while True:
        selection = input("Введите номер USB–UART адаптера из списка: ").strip()
        if selection.isdecimal() and 1 <= int(selection) <= len(ports):
            return ports[int(selection) - 1].device
        print("Введите номер строки из списка выше.")


def main():
    port = choose_port()
    print(f"Открываю {port} на 115200 бод, 8N1.")
    with serial.Serial(port, baudrate=115200, timeout=2, write_timeout=2) as link:
        time.sleep(0.2)
        while True:
            answer = input("Нажмите Enter, чтобы отправить импульс, или q + Enter для выхода: ")
            if answer.strip().lower() == "q":
                break
            link.reset_input_buffer()
            link.write(PACKET)
            link.flush()
            response = link.read(2)
            print("Отправлено:", PACKET.hex(" ").upper())
            print("Получено:  ", response.hex(" ").upper() or "нет ответа")
            if response == b"\xAA\x55":
                print("OK: контроллер завершил последовательность.")
                print("Ожидается: reset_gate 100 мкс; пауза 200 мкс; glitch_out 2 мкс.\n")
            else:
                print("Нет ожидаемого ответа AA 55; проверьте распиновку и тактирование.\n")


if __name__ == "__main__":
    try:
        main()
    except (serial.SerialException, OSError, RuntimeError) as error:
        print(f"Ошибка: {error}")
