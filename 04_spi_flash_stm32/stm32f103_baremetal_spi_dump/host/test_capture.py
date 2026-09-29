"""Small host protocol checks; no target hardware required."""

import unittest
import zlib
from unittest.mock import patch

import capture_uart


class FakePort:
    def __init__(self, response):
        self.response = response
        self.offset = 0
        self.command = b""

    def reset_input_buffer(self):
        pass

    def write(self, value):
        self.command += value

    def flush(self):
        pass

    def read(self, count):
        chunk = self.response[self.offset:self.offset + count]
        self.offset += len(chunk)
        return chunk


class CaptureTests(unittest.TestCase):
    def test_valid_image_and_crc(self):
        image = bytes(range(256))
        response = (b"RPF1" + bytes.fromhex("EF 40 15") +
                    len(image).to_bytes(4, "little") + image +
                    zlib.crc32(image).to_bytes(4, "little"))
        port = FakePort(response)
        with patch.object(capture_uart, "FLASH_BYTES", len(image)):
            ident, data, crc = capture_uart.capture(port)
        self.assertEqual(port.command, b"D")
        self.assertEqual(ident, bytes.fromhex("EF 40 15"))
        self.assertEqual(data, image)
        self.assertEqual(crc, zlib.crc32(image))

    def test_corrupted_image_rejected(self):
        image = bytes(range(256))
        response = (b"RPF1" + bytes.fromhex("EF 40 15") +
                    len(image).to_bytes(4, "little") + image + b"\x00" * 4)
        with patch.object(capture_uart, "FLASH_BYTES", len(image)):
            with self.assertRaisesRegex(RuntimeError, "CRC32 mismatch"):
                capture_uart.capture(FakePort(response))


if __name__ == "__main__":
    unittest.main()
