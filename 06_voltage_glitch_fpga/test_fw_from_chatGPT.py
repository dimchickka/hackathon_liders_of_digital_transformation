"""
MAX II glitcher + монитор RP2040-Zero в одном терминале.

Порт 1:
    USB-UART -> EPM240
    Отправляем:
        AA D_H D_L W_H W_L 01

    FPGA сейчас отвечает:
        55 AA

Порт 2:
    встроенный USB Type-C RP2040-Zero
    Читаем USB CDC сообщения тестовой прошивки:
        [BOOT]
        [BEGIN]
        [OK]
        ANOMALY

Если появляется ANOMALY, перебор останавливается и выводятся
delay/width, на которых это произошло.
"""

import time
import threading
import serial
from serial.tools import list_ports


# ============================================================
# FPGA / GLITCHER
# ============================================================

CLK_FREQ_HZ = 50_000_000
NS_PER_TICK = 1e9 / CLK_FREQ_HZ

MAX_DELAY_TICKS = 0xFFFF
MAX_WIDTH_TICKS = 0xFF

EXPECTED_RESPONSE = b"\x55\xAA"

FPGA_BAUDRATE = 115200


# ============================================================
# RP2040 USB CDC
# ============================================================

# Для USB CDC эта скорость фактически не задаёт
# физическую скорость USB, но pyserial требует значение.
RP2040_BAUDRATE = 115200


# ============================================================
# ДИАПАЗОН ПЕРЕБОРА
# ============================================================

DELAY_START_US = 800.0
DELAY_STOP_US  = 1310.0
DELAY_STEP_US  = 2.0

WIDTH_START_NS = 20.0
WIDTH_STOP_NS  = 300.0
WIDTH_STEP_NS  = 20.0


# ============================================================
# ТАЙМИНГИ
# ============================================================

RESPONSE_TIMEOUT_MS = 100

# Сколько ждём после каждой попытки.
# В это время отдельный поток продолжает читать RP2040.
POST_GLITCH_WAIT_MS = 1000

INTER_ATTEMPT_MS = 0

COOLDOWN_EVERY = 0
COOLDOWN_MS = 1000


# ============================================================
# ГЛОБАЛЬНЫЕ СОБЫТИЯ
# ============================================================

stop_event = threading.Event()
anomaly_event = threading.Event()

print_lock = threading.Lock()


def log(text=""):
    """Печать из нескольких потоков без каши."""
    with print_lock:
        print(text, flush=True)


# ============================================================
# ПРЕОБРАЗОВАНИЯ
# ============================================================

def us_to_ticks(us):
    return int(round(us * 1000.0 / NS_PER_TICK))


def ticks_to_us(t):
    return t * NS_PER_TICK / 1000.0


def ns_to_ticks(ns):
    return max(1, int(round(ns / NS_PER_TICK)))


def frange(a, b, s):
    n = int(round((b - a) / s)) + 1
    return [a + i * s for i in range(n)]


# ============================================================
# COM-ПОРТЫ
# ============================================================

def get_ports():
    return sorted(
        list(list_ports.comports()),
        key=lambda p: p.device
    )


def print_ports(ports):
    log("\nДоступные COM-порты:")

    for i, p in enumerate(ports, 1):
        log(
            f"  {i}. {p.device:8s} "
            f"{p.description or ''} "
            f"[VID={p.vid} PID={p.pid} "
            f"SER={p.serial_number}]"
        )


def choose_ports():
    ports = get_ports()

    if len(ports) < 2:
        raise RuntimeError(
            "Нужно минимум два COM-порта:\n"
            "1) USB-UART адаптер MAX II\n"
            "2) USB CDC RP2040-Zero"
        )

    print_ports(ports)

    # --------------------------------------------------------
    # FPGA
    # --------------------------------------------------------

    while True:
        s = input(
            "\nНомер COM-порта USB-UART адаптера FPGA: "
        ).strip()

        if s.isdecimal():
            index = int(s) - 1

            if 0 <= index < len(ports):
                fpga = ports[index]
                break

    # --------------------------------------------------------
    # RP2040
    # --------------------------------------------------------

    while True:
        s = input(
            "Номер COM-порта RP2040-Zero (Type-C): "
        ).strip()

        if s.isdecimal():
            index = int(s) - 1

            if 0 <= index < len(ports):
                rp = ports[index]

                if rp.device == fpga.device:
                    log("Нельзя выбрать один порт дважды.")
                    continue

                break

    return fpga, rp


# ============================================================
# ИДЕНТИФИКАЦИЯ RP2040 ПОСЛЕ ПЕРЕЗАГРУЗКИ
# ============================================================

def make_port_identity(port):
    """
    Запоминаем характеристики устройства.

    После reset COM-порт может исчезнуть и появиться снова.
    Иногда Windows даже может поменять номер COM.
    """
    return {
        "device": port.device,
        "vid": port.vid,
        "pid": port.pid,
        "serial_number": port.serial_number,
        "description": port.description,
    }


def find_same_device(identity):
    ports = get_ports()

    # --------------------------------------------------------
    # 1. Лучший вариант — уникальный serial number
    # --------------------------------------------------------

    serial_number = identity["serial_number"]

    if serial_number:
        for p in ports:
            if p.serial_number == serial_number:
                return p

    # --------------------------------------------------------
    # 2. Тот же COM
    # --------------------------------------------------------

    for p in ports:
        if p.device == identity["device"]:
            return p

    # --------------------------------------------------------
    # 3. VID/PID
    # --------------------------------------------------------

    vid = identity["vid"]
    pid = identity["pid"]

    if vid is not None and pid is not None:

        candidates = [
            p for p in ports
            if p.vid == vid and p.pid == pid
        ]

        if len(candidates) == 1:
            return candidates[0]

    return None


# ============================================================
# FPGA ПРОТОКОЛ
# ============================================================

def build_packet(delay_ticks: int, width_ticks: int) -> bytes:

    if not (0 <= delay_ticks <= MAX_DELAY_TICKS):
        raise ValueError(
            f"delay_ticks={delay_ticks} вне 16 бит"
        )

    if not (0 <= width_ticks <= MAX_WIDTH_TICKS):
        raise ValueError(
            f"width_ticks={width_ticks} вне 8 бит"
        )

    return bytes([
        0xAA,

        (delay_ticks >> 8) & 0xFF,
        delay_ticks & 0xFF,

        0x00,
        width_ticks & 0xFF,

        0x01
    ])


def transact(link, packet, resp_timeout_s):

    link.reset_input_buffer()

    link.write(packet)
    link.flush()

    data = bytearray()

    deadline = time.monotonic() + resp_timeout_s

    while (
        len(data) < 2
        and time.monotonic() < deadline
    ):
        chunk = link.read(2 - len(data))

        if chunk:
            data.extend(chunk)

    return bytes(data)


# ============================================================
# МОНИТОР RP2040
# ============================================================

def rp2040_monitor(identity):
    """
    Работает в отдельном потоке.

    Постоянно читает встроенный USB RP2040.

    Если RP2040 перезагрузился:
        COM исчезнет
        -> ждём
        -> подключаемся снова.

    Если пришло ANOMALY:
        выставляем anomaly_event.
    """

    ser = None
    connected_port = None

    boot_count = 0

    while not stop_event.is_set():

        # ----------------------------------------------------
        # Нужно подключиться / переподключиться
        # ----------------------------------------------------

        if ser is None:

            p = find_same_device(identity)

            if p is None:
                time.sleep(0.1)
                continue

            try:
                ser = serial.Serial(
                    port=p.device,
                    baudrate=RP2040_BAUDRATE,
                    timeout=0.1,
                    write_timeout=1
                )

                connected_port = p.device

                log(
                    f"\n[RP2040] USB подключён: "
                    f"{connected_port}"
                )

            except (serial.SerialException, OSError):
                ser = None
                time.sleep(0.1)
                continue

        # ----------------------------------------------------
        # Читаем USB CDC
        # ----------------------------------------------------

        try:
            raw = ser.readline()

            if not raw:
                continue

            text = raw.decode(
                "utf-8",
                errors="replace"
            ).strip()

            if not text:
                continue

            log(f"[RP2040] {text}")

            # ------------------------------------------------
            # Reset / boot
            # ------------------------------------------------

            if "[BOOT] RP2040 started" in text:

                boot_count += 1

                log(
                    f"[RP2040] >>> BOOT #{boot_count} "
                    f"(произошёл запуск/перезапуск)"
                )

            # ------------------------------------------------
            # Аномалия
            # ------------------------------------------------

            if "ANOMALY" in text:

                if not anomaly_event.is_set():

                    log("")
                    log("#" * 64)
                    log(
                        "### RP2040 СООБЩИЛ ОБ АНОМАЛИИ "
                        "ВЫПОЛНЕНИЯ"
                    )
                    log("#" * 64)
                    log("")

                anomaly_event.set()

        except (
            serial.SerialException,
            OSError
        ):

            log(
                f"\n[RP2040] USB {connected_port} исчез."
            )

            log(
                "[RP2040] Возможно, произошёл reset. "
                "Жду повторного подключения..."
            )

            try:
                ser.close()
            except Exception:
                pass

            ser = None
            connected_port = None

            time.sleep(0.1)

    # --------------------------------------------------------
    # Завершение
    # --------------------------------------------------------

    if ser is not None:
        try:
            ser.close()
        except Exception:
            pass


# ============================================================
# ОЖИДАНИЕ ПОСЛЕ ПОПЫТКИ
# ============================================================

def wait_after_attempt(seconds):
    """
    Ждём, но выходим раньше, если RP2040 сообщил ANOMALY.
    """

    deadline = time.monotonic() + seconds

    while time.monotonic() < deadline:

        if anomaly_event.is_set():
            return True

        if stop_event.is_set():
            return False

        time.sleep(0.01)

    return anomaly_event.is_set()


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # Выбираем оба устройства
    # --------------------------------------------------------

    fpga_port_info, rp_port_info = choose_ports()

    fpga_port = fpga_port_info.device

    rp_identity = make_port_identity(rp_port_info)

    log("")
    log("=" * 64)
    log("ВЫБРАННЫЕ УСТРОЙСТВА")
    log("=" * 64)

    log(
        f"FPGA USB-UART : {fpga_port} "
        f"({fpga_port_info.description})"
    )

    log(
        f"RP2040 Type-C  : {rp_port_info.device} "
        f"({rp_port_info.description})"
    )

    log("=" * 64)

    # --------------------------------------------------------
    # Запускаем отдельный поток чтения RP2040
    # --------------------------------------------------------

    monitor_thread = threading.Thread(
        target=rp2040_monitor,
        args=(rp_identity,),
        daemon=True
    )

    monitor_thread.start()

    # Даём монитору время открыть порт
    time.sleep(0.5)

    # --------------------------------------------------------
    # Формируем диапазоны
    # --------------------------------------------------------

    delays_us = [
        d
        for d in frange(
            DELAY_START_US,
            DELAY_STOP_US,
            DELAY_STEP_US
        )
        if 0 < us_to_ticks(d) <= MAX_DELAY_TICKS
    ]

    width_ticks_list = sorted(
        set(
            w
            for w in (
                ns_to_ticks(n)
                for n in frange(
                    WIDTH_START_NS,
                    WIDTH_STOP_NS,
                    WIDTH_STEP_NS
                )
            )
            if 0 < w <= MAX_WIDTH_TICKS
        )
    )

    total = (
        len(delays_us)
        * len(width_ticks_list)
    )

    per_attempt_ms = (
        POST_GLITCH_WAIT_MS
        + INTER_ATTEMPT_MS
    )

    eta_min = (
        total
        * per_attempt_ms
        / 1000.0
        / 60.0
    )

    log("")
    log("=" * 64)
    log("ПАРАМЕТРЫ ПЕРЕБОРА")
    log("=" * 64)

    log(
        f"CLK FPGA = {CLK_FREQ_HZ / 1e6:.0f} МГц"
    )

    log(
        f"1 такт = {NS_PER_TICK:.1f} нс"
    )

    log(
        f"delay = "
        f"{DELAY_START_US}..{DELAY_STOP_US} мкс, "
        f"шаг {DELAY_STEP_US} мкс"
    )

    log(
        f"width = "
        f"{WIDTH_START_NS}..{WIDTH_STOP_NS} нс, "
        f"шаг {WIDTH_STEP_NS} нс"
    )

    log(
        f"width ticks = {width_ticks_list}"
    )

    log(
        f"Комбинаций = {total}"
    )

    log(
        f"Оценка времени = ~{eta_min:.1f} мин"
    )

    log("=" * 64)
    log("")

    resp_timeout_s = RESPONSE_TIMEOUT_MS / 1000.0
    post_wait_s = POST_GLITCH_WAIT_MS / 1000.0
    inter_att_s = INTER_ATTEMPT_MS / 1000.0
    cooldown_s = COOLDOWN_MS / 1000.0

    # --------------------------------------------------------
    # FPGA
    # --------------------------------------------------------

    with serial.Serial(
        fpga_port,
        baudrate=FPGA_BAUDRATE,
        timeout=resp_timeout_s,
        write_timeout=1
    ) as fpga:

        time.sleep(0.2)

        fpga.reset_input_buffer()

        # ====================================================
        # ДИАГНОСТИКА FPGA
        # ====================================================

        log("[FPGA] Диагностика связи.")

        probe = build_packet(
            us_to_ticks(100),
            1
        )

        log(
            f"[FPGA] TX: "
            f"{probe.hex(' ').upper()}"
        )

        resp = transact(
            fpga,
            probe,
            resp_timeout_s
        )

        log(
            f"[FPGA] RX: "
            f"{resp.hex(' ').upper() or '(пусто)'}"
        )

        if resp != EXPECTED_RESPONSE:

            log("")
            log(
                f"!!! FPGA не ответила "
                f"{EXPECTED_RESPONSE.hex(' ').upper()}"
            )

            log(
                "Проверь COM-порт FPGA, "
                "115200 8N1, GND, TX<->RX."
            )

            return

        log("[FPGA] Связь работает.")
        log("")
        log("=" * 64)
        log("НАЧИНАЮ ПЕРЕБОР")
        log("=" * 64)
        log("")

        # ====================================================
        # ПЕРЕБОР
        # ====================================================

        attempt = 0
        t0 = time.monotonic()

        found = False

        found_delay_us = None
        found_delay_ticks = None
        found_width_ticks = None

        for d_us in delays_us:

            d_t = us_to_ticks(d_us)

            for w_t in width_ticks_list:

                if anomaly_event.is_set():
                    found = True
                    break

                attempt += 1

                packet = build_packet(
                    d_t,
                    w_t
                )

                # ------------------------------------------------
                # Показываем текущую попытку
                # ------------------------------------------------

                log(
                    f"\n[TRY {attempt:5d}/{total}] "
                    f"delay={d_us:7.2f} us "
                    f"({d_t:5d} ticks), "
                    f"width={w_t:3d} ticks "
                    f"({ticks_to_us(w_t) * 1000:.0f} ns)"
                )

                # ------------------------------------------------
                # FPGA
                # ------------------------------------------------

                resp = transact(
                    fpga,
                    packet,
                    resp_timeout_s
                )

                status = (
                    resp.hex(" ").upper()
                    if resp
                    else "---"
                )

                if resp == EXPECTED_RESPONSE:

                    log(
                        f"[FPGA] RX={status}  OK"
                    )

                else:

                    log(
                        f"[FPGA] RX={status}  "
                        f"!!! неожиданный ответ"
                    )

                # ------------------------------------------------
                # RP2040 продолжает читаться параллельно
                # ------------------------------------------------

                anomaly = wait_after_attempt(
                    post_wait_s
                )

                if anomaly:

                    found = True

                    found_delay_us = d_us
                    found_delay_ticks = d_t
                    found_width_ticks = w_t

                    break

                # ------------------------------------------------
                # Дополнительная пауза
                # ------------------------------------------------

                if inter_att_s > 0:
                    time.sleep(inter_att_s)

                # ------------------------------------------------
                # Cooldown
                # ------------------------------------------------

                if (
                    COOLDOWN_EVERY > 0
                    and attempt % COOLDOWN_EVERY == 0
                ):

                    log(
                        f"[SYSTEM] cooldown "
                        f"{COOLDOWN_MS} ms"
                    )

                    time.sleep(cooldown_s)

            if found:
                break

        # ====================================================
        # РЕЗУЛЬТАТ
        # ====================================================

        elapsed = time.monotonic() - t0

        log("")
        log("=" * 64)

        if anomaly_event.is_set():

            log("ОБНАРУЖЕНА ANOMALY")

            if found_delay_us is not None:

                log(
                    f"delay = "
                    f"{found_delay_us:.2f} мкс"
                )

                log(
                    f"delay ticks = "
                    f"{found_delay_ticks}"
                )

                log(
                    f"width = "
                    f"{found_width_ticks} тактов"
                )

                log(
                    f"width = "
                    f"{ticks_to_us(found_width_ticks) * 1000:.0f} нс"
                )

            log(
                f"Попытка: {attempt}/{total}"
            )

            log(
                f"Время: {elapsed:.1f} с"
            )

        else:

            log("Перебор завершён.")

            log(
                "Сообщение ANOMALY от RP2040 "
                "не получено."
            )

            log(
                f"Попыток: {attempt}"
            )

            log(
                f"Время: {elapsed:.1f} с"
            )

        log("=" * 64)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    try:
        main()

    except KeyboardInterrupt:
        log("\n[SYSTEM] Остановлено пользователем.")

    except (
        serial.SerialException,
        OSError,
        RuntimeError,
        ValueError
    ) as e:
        log(f"\nОшибка: {e}")

    finally:
        stop_event.set()

        # Немного времени потоку RP2040 на завершение
        time.sleep(0.2)