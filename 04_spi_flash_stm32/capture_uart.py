"""Capture the binary UART stream from spi_flash_reader.c (not hardware tested).

Usage: python capture_uart.py COM7 flash_spi.bin
Start this process before resetting STM32. Requires pyserial.
"""
import hashlib
import sys
from pathlib import Path
import serial

SIZE = 0x200000

def read_exact(port, count):
    data = bytearray()
    while len(data) < count:
        chunk = port.read(min(4096, count - len(data)))
        if not chunk:
            raise TimeoutError(f"Received {len(data)}/{count} bytes")
        data.extend(chunk)
    return bytes(data)

def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python capture_uart.py COM7 flash_spi.bin")
    with serial.Serial(sys.argv[1], baudrate=115200, timeout=10) as link:
        jedec = read_exact(link, 3)
        data = read_exact(link, SIZE)
    Path(sys.argv[2]).write_bytes(data)
    print("JEDEC ID:", jedec.hex(" ").upper())
    print("Bytes:", len(data))
    print("SHA256:", hashlib.sha256(data).hexdigest())

if __name__ == "__main__":
    main()
