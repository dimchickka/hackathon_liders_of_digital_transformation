"""Receive one complete bare-metal W25Q16JV dump over a 3.3 V USB-UART adapter.

Usage: python capture_uart.py COM7 flash_spi_1.bin
Requires pyserial. Start while the STM32 firmware is running; it waits for 'D'.
"""

import hashlib
import sys
import zlib
from pathlib import Path

FLASH_BYTES = 0x200000


def read_exact(port, count):
    result = bytearray()
    while len(result) < count:
        chunk = port.read(min(4096, count - len(result)))
        if not chunk:
            raise TimeoutError(f"UART stopped after {len(result)} of {count} bytes")
        result.extend(chunk)
    return bytes(result)


def capture(port):
    port.reset_input_buffer()
    port.write(b"D")
    port.flush()

    marker = read_exact(port, 4)
    if marker == b"ERR1":
        ident = read_exact(port, 3)
        raise RuntimeError(f"Flash JEDEC check failed; received {ident.hex(' ').upper()}")
    if marker != b"RPF1":
        raise RuntimeError(f"Unexpected frame marker {marker!r}")

    ident = read_exact(port, 3)
    length = int.from_bytes(read_exact(port, 4), "little")
    if ident != bytes.fromhex("EF 40 15") or length != FLASH_BYTES:
        raise RuntimeError(f"Unexpected JEDEC {ident.hex(' ').upper()} or length {length}")

    image = bytearray()
    while len(image) < length:
        image.extend(read_exact(port, min(4096, length - len(image))))
        if len(image) % (256 * 1024) == 0:
            print(f"Received {len(image):,}/{length:,} bytes", flush=True)

    received_crc = int.from_bytes(read_exact(port, 4), "little")
    actual_crc = zlib.crc32(image) & 0xFFFFFFFF
    if actual_crc != received_crc:
        raise RuntimeError(
            f"CRC32 mismatch: STM32={received_crc:08X}, PC={actual_crc:08X}"
        )
    return ident, bytes(image), actual_crc


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python capture_uart.py COM7 flash_spi_1.bin")
    import serial  # Install with: python -m pip install pyserial

    output = Path(sys.argv[2])
    with serial.Serial(sys.argv[1], 115200, timeout=15, write_timeout=2) as port:
        ident, image, crc = capture(port)
    output.write_bytes(image)
    print("JEDEC ID:", ident.hex(" ").upper())
    print("CRC32:", f"{crc:08X}")
    print("SHA256:", hashlib.sha256(image).hexdigest())
    print("Saved:", output.resolve())


if __name__ == "__main__":
    main()
