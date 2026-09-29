"""
Перебор delay и width для compact-прошивки glitcher (EPM240).
ВНИМАНИЕ: из-за бага в текущей прошивке FPGA отвечает 55 AA (байты
перепутаны местами). Поэтому ожидаем именно 55 AA. Если когда-нибудь
пересоберёте Verilog с фиксом — поменяйте на AA 55.

Протокол: AA D_H D_L W_H W_L 01
  delay : 16 бит, такты 50 МГц (20 нс), макс 65535 = 1310 мкс
  width : младший байт W_L, 8 бит, 0..255; W_H игнорируется
"""

import os, sys, time
import serial
from serial.tools import list_ports

CLK_FREQ_HZ  = 50_000_000
NS_PER_TICK  = 1e9 / CLK_FREQ_HZ
MAX_DELAY_TICKS = 0xFFFF
MAX_WIDTH_TICKS = 0xFF

def us_to_ticks(us): return int(round(us * 1000.0 / NS_PER_TICK))
def ticks_to_us(t):  return t * NS_PER_TICK / 1000.0
def ns_to_ticks(ns): return max(1, int(round(ns / NS_PER_TICK)))

# ---------------------------------------------------------------------------
# Диапазон
# ---------------------------------------------------------------------------
DELAY_START_US = 800.0
DELAY_STOP_US  = 1310.0
DELAY_STEP_US  = 2.0

WIDTH_START_NS = 20.0
WIDTH_STOP_NS  = 300.0
WIDTH_STEP_NS  = 20.0

# ---------------------------------------------------------------------------
# Тайминги (миллисекунды)
# ---------------------------------------------------------------------------
RESPONSE_TIMEOUT_MS  = 100
POST_GLITCH_WAIT_MS  = 1000    # пауза после КАЖДОЙ попытки
POST_GLITCH_POLL_MS  = 5
INTER_ATTEMPT_MS     = 0

COOLDOWN_EVERY       = 0
COOLDOWN_MS          = 1000

# ---------------------------------------------------------------------------
# !!! ГЛАВНАЯ ПРАВКА !!!
# FPGA сейчас отвечает 55 AA из-за бага в прошивке.
# ---------------------------------------------------------------------------
EXPECTED_RESPONSE = b"\x55\xAA"

_IS_WINDOWS = (os.name == "nt")


def list_ports_fast():
    if not _IS_WINDOWS:
        try:
            entries = os.listdir("/dev")
        except OSError:
            return set()
        if sys.platform == "darwin":
            return {e for e in entries if e.startswith(("cu.", "tty."))}
        return {e for e in entries if e.startswith(("ttyACM", "ttyUSB"))}
    return {p.device for p in list_ports.comports()}


def choose_port():
    ports = sorted(list_ports.comports(), key=lambda p: p.device)
    if not ports:
        raise RuntimeError("COM-порты не найдены.")
    print("Доступные порты:")
    for i, p in enumerate(ports, 1):
        print(f"  {i}. {p.device}: {p.description}")
    if len(ports) == 1:
        print(f"Выбран: {ports[0].device}")
        return ports[0].device
    while True:
        s = input("Номер USB–UART адаптера: ").strip()
        if s.isdecimal() and 1 <= int(s) <= len(ports):
            return ports[int(s) - 1].device


def build_packet(delay_ticks: int, width_ticks: int) -> bytes:
    if not (0 <= delay_ticks <= MAX_DELAY_TICKS):
        raise ValueError(f"delay_ticks={delay_ticks} вне 16 бит")
    if not (0 <= width_ticks <= MAX_WIDTH_TICKS):
        raise ValueError(f"width_ticks={width_ticks} вне 8 бит")
    return bytes([0xAA,
                  (delay_ticks >> 8) & 0xFF, delay_ticks & 0xFF,
                  0x00, width_ticks & 0xFF,
                  0x01])


def frange(a, b, s):
    n = int(round((b - a) / s)) + 1
    return [a + i * s for i in range(n)]


def wait_for_new_port(known, max_wait_s, poll_s):
    t0 = time.monotonic()
    deadline = t0 + max_wait_s
    while True:
        new = list_ports_fast() - known
        if new:
            return new, time.monotonic() - t0
        if time.monotonic() >= deadline:
            return set(), time.monotonic() - t0
        time.sleep(poll_s)


def transact(link, packet, resp_timeout_s):
    link.reset_input_buffer()
    link.write(packet)
    link.flush()
    data = bytearray()
    deadline = time.monotonic() + resp_timeout_s
    while len(data) < 2 and time.monotonic() < deadline:
        chunk = link.read(2 - len(data))
        if chunk:
            data.extend(chunk)
    return bytes(data)


def main():
    port = choose_port()
    print(f"\nОткрываю {port}, 115200 8N1")
    print(f"CLK = {CLK_FREQ_HZ/1e6:.0f} МГц, 1 такт = {NS_PER_TICK:.1f} нс")
    print(f"Ожидаемый ответ FPGA: {EXPECTED_RESPONSE.hex(' ').upper()}")

    known = list_ports_fast()
    print(f"Портов до старта: {sorted(known) or '(нет)'}")

    delays_us = [d for d in frange(DELAY_START_US, DELAY_STOP_US, DELAY_STEP_US)
                 if 0 < us_to_ticks(d) <= MAX_DELAY_TICKS]
    width_ticks_list = sorted(set(
        w for w in (ns_to_ticks(n) for n in
                    frange(WIDTH_START_NS, WIDTH_STOP_NS, WIDTH_STEP_NS))
        if 0 < w <= MAX_WIDTH_TICKS))

    total = len(delays_us) * len(width_ticks_list)
    per_attempt_ms = POST_GLITCH_WAIT_MS + INTER_ATTEMPT_MS
    eta_min = total * per_attempt_ms / 1000.0 / 60.0

    print(f"delay : {DELAY_START_US}..{DELAY_STOP_US} мкс, шаг {DELAY_STEP_US} "
          f"-> {len(delays_us)}")
    print(f"width : {WIDTH_START_NS}..{WIDTH_STOP_NS} нс, шаг {WIDTH_STEP_NS} "
          f"-> {len(width_ticks_list)} ({width_ticks_list} тактов)")
    print(f"Комбинаций: {total}")
    print(f"Одна итерация: {per_attempt_ms} мс")
    print(f"Оценка: ~{eta_min:.1f} мин\n")

    resp_timeout_s = RESPONSE_TIMEOUT_MS / 1000.0
    post_wait_s    = POST_GLITCH_WAIT_MS / 1000.0
    post_poll_s    = POST_GLITCH_POLL_MS / 1000.0
    inter_att_s    = INTER_ATTEMPT_MS / 1000.0
    cooldown_s     = COOLDOWN_MS / 1000.0

    with serial.Serial(port, baudrate=115200,
                       timeout=resp_timeout_s, write_timeout=1) as link:
        time.sleep(0.2)
        link.reset_input_buffer()

        # --- Диагностика ---
        print("Диагностика: пробный пакет delay=100 мкс, width=1 такт")
        probe = build_packet(us_to_ticks(100), 1)
        resp = transact(link, probe, resp_timeout_s)
        print(f"  отправлено: {probe.hex(' ').upper()}")
        print(f"  получено:   {resp.hex(' ').upper() or '(пусто)'}")
        if resp != EXPECTED_RESPONSE:
            print()
            print(f"!!! FPGA не ответила {EXPECTED_RESPONSE.hex(' ').upper()}.")
            print("Проверьте COM-порт, 115200 8N1, GND, TX<->RX.")
            print("Скрипт остановлен.")
            return
        print("ОК, FPGA отвечает. Начинаю перебор.\n")

        attempt = 0
        t0 = time.monotonic()
        success = False

        for d_us in delays_us:
            d_t = us_to_ticks(d_us)
            for w_t in width_ticks_list:
                attempt += 1

                resp = transact(link, build_packet(d_t, w_t), resp_timeout_s)

                # Пауза после КАЖДОЙ попытки + поиск нового USB
                new, waited = wait_for_new_port(known, post_wait_s, post_poll_s)

                if new:
                    el = time.monotonic() - t0
                    print(f"\n{'='*60}")
                    print(f"УСПЕХ! Новое устройство: {sorted(new)}")
                    print(f"delay = {d_us:.2f} мкс ({d_t} тактов)")
                    print(f"width = {w_t} тактов ({ticks_to_us(w_t)*1000:.0f} нс)")
                    print(f"Попыток: {attempt}, время: {el:.1f} с")
                    print(f"USB появилось за {waited*1000:.0f} мс после ответа")
                    print(f"{'='*60}")
                    success = True
                    break

                status = resp.hex(' ').upper() if resp else '---'
                mark = "OK " if resp == EXPECTED_RESPONSE else "!! "
                print(f"[{attempt:5d}] d={d_us:7.2f}us w={w_t:3d}t "
                      f"resp={status:6s} waited={waited*1000:4.0f}ms  {mark}")

                if inter_att_s > 0:
                    time.sleep(inter_att_s)

                if COOLDOWN_EVERY > 0 and attempt % COOLDOWN_EVERY == 0:
                    print(f"  ... cooldown {COOLDOWN_MS} мс ...")
                    time.sleep(cooldown_s)

            if success:
                break

        if not success:
            print("\nПеребор завершён, USB не появилось.")


if __name__ == "__main__":
    try:
        main()
    except (serial.SerialException, OSError, RuntimeError) as e:
        print(f"Ошибка: {e}")
    except KeyboardInterrupt:
        print("\nПрервано.")