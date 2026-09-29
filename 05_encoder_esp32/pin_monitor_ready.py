"""Windows monitor for sketch_sep22a.ino on an ESP32-C3.

Example:
    py pin_monitor_ready.py --port COM7
    py pin_monitor_ready.py --port COM7 --volume-label "Flash Disk"

Requires pyserial. The script waits for a NEW Windows drive letter; an existing
drive that merely changes its contents will not be detected. A detected PIN is
a candidate until separately verified.
"""

import argparse
import ctypes
import json
import os
import re
import shutil
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path


BAUD = 115200
DRIVE_POLL_S = 0.05
START_RETRY_S = 0.5
START_TIMEOUT_S = 12.0
STOP_TIMEOUT_S = 2.0
FINAL_DRIVE_WAIT_S = 8.0
DRIVE_READY_WAIT_S = 15.0

TRY_RE = re.compile(r"^TRY (\d{4}) (\d+)$")
SUBMITTED_RE = re.compile(r"^SUBMITTED (\d{4}) (\d+)$")


def timestamp():
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def filename_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def logical_drives():
    """Return drive roots such as E:\\ from the Windows drive bitmap."""
    bits = ctypes.windll.kernel32.GetLogicalDrives()
    if bits == 0:
        raise ctypes.WinError()
    return {"{}:\\".format(chr(ord("A") + index))
            for index in range(26) if bits & (1 << index)}


def volume_label(root):
    name = ctypes.create_unicode_buffer(261)
    ok = ctypes.windll.kernel32.GetVolumeInformationW(
        ctypes.c_wchar_p(root), name, len(name),
        None, None, None, None, 0,
    )
    return name.value if ok else None


def matching_new_drive(baseline, expected_label):
    for root in sorted(logical_drives() - baseline):
        label = volume_label(root)
        if expected_label is None or (label and label.casefold() == expected_label.casefold()):
            return root, label
    return None


class SerialHistory:
    def __init__(self):
        self.lines = []
        self.last_started = None
        self.recent_submitted = deque(maxlen=8)

    def add(self, line):
        received_at = timestamp()
        self.lines.append({"received_at": received_at, "line": line})
        match = TRY_RE.fullmatch(line)
        if match:
            self.last_started = {
                "pin": match.group(1),
                "esp_millis": int(match.group(2)),
                "received_at": received_at,
            }
        match = SUBMITTED_RE.fullmatch(line)
        if match:
            self.recent_submitted.append({
                "pin": match.group(1),
                "esp_millis": int(match.group(2)),
                "received_at": received_at,
            })
        print(line, flush=True)

    def snapshot(self):
        recent = list(self.recent_submitted)
        return {
            "last_started": self.last_started,
            "last_submitted_pin": recent[-1]["pin"] if recent else None,
            "recent_submitted_attempts": recent,
            "pin_verified": False,
            "serial_log": self.lines,
        }


class SerialLines:
    def __init__(self, port):
        self.port = port
        self.buffer = bytearray()

    def read_available(self):
        count = self.port.in_waiting
        if count:
            self.buffer.extend(self.port.read(count))
        if len(self.buffer) > 65536:
            self.buffer.clear()
            raise RuntimeError("Serial line exceeds 64 KiB")
        lines = []
        while True:
            newline = self.buffer.find(b"\n")
            if newline < 0:
                break
            raw = bytes(self.buffer[:newline]).rstrip(b"\r")
            del self.buffer[:newline + 1]
            lines.append(raw.decode("utf-8", errors="replace"))
        return lines


def consume(lines, history):
    result = []
    for line in lines.read_available():
        history.add(line)
        result.append(line)
    return result


def send(port, command):
    port.write((command + "\n").encode("ascii"))
    port.flush()


def stop_esp(port, lines, history):
    send(port, "X")
    deadline = time.monotonic() + STOP_TIMEOUT_S
    stopped = False
    while time.monotonic() < deadline:
        for line in consume(lines, history):
            if line.startswith("STOPPED "):
                stopped = True
        if stopped:
            break
        time.sleep(DRIVE_POLL_S)
    # Drain messages that were already queued behind the stop response.
    drain_deadline = time.monotonic() + 0.2
    while time.monotonic() < drain_deadline:
        consume(lines, history)
        time.sleep(DRIVE_POLL_S)
    return stopped


def is_link_or_junction(path):
    if path.is_symlink():
        return True
    return hasattr(path, "is_junction") and path.is_junction()


def copy_drive(root, destination):
    source = Path(root)
    destination.mkdir(parents=True, exist_ok=False)
    deadline = time.monotonic() + DRIVE_READY_WAIT_S
    while True:
        try:
            if source.is_dir():
                list(source.iterdir())  # Force an actual directory read.
                break
        except OSError:
            pass
        if time.monotonic() >= deadline:
            return {"files": 0, "bytes": 0, "errors": ["Drive did not become readable"]}
        time.sleep(0.1)

    result = {"files": 0, "bytes": 0, "errors": []}
    def record_walk_error(exc):
        result["errors"].append(str(exc))

    for current, directories, files in os.walk(
            source, topdown=True, followlinks=False, onerror=record_walk_error):
        current_path = Path(current)
        relative = current_path.relative_to(source)
        output_dir = destination / relative
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_directories = []
        for directory in directories:
            candidate = current_path / directory
            if is_link_or_junction(candidate):
                result["errors"].append("Skipped link: {}".format(candidate))
            else:
                safe_directories.append(directory)
        directories[:] = safe_directories
        for filename in files:
            item = current_path / filename
            if is_link_or_junction(item):
                result["errors"].append("Skipped link: {}".format(item))
                continue
            try:
                shutil.copy2(item, output_dir / filename)
                result["files"] += 1
                result["bytes"] += item.stat().st_size
            except OSError as exc:
                result["errors"].append("{}: {}".format(item, exc))
    return result


def write_json_atomic(directory, record):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "pin_result_{}.json".format(filename_timestamp())
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    return path


def event_record(event, history, baseline, **extra):
    record = {
        "event": event,
        "recorded_at": timestamp(),
        "baseline_drives": sorted(baseline),
    }
    record.update(history.snapshot())
    record.update(extra)
    return record


def run(args):
    import serial  # py -m pip install pyserial

    output_root = args.output_dir.resolve()
    copies_dir = output_root / "flash_copies"
    results_dir = output_root / "pin_results"
    baseline = logical_drives()  # Before opening COM / starting the ESP32.
    print("Baseline drives:", ", ".join(sorted(baseline)))
    history = SerialHistory()

    with serial.Serial(args.port, BAUD, timeout=0, write_timeout=1) as port:
        lines = SerialLines(port)
        try:
            start_deadline = time.monotonic() + START_TIMEOUT_S
            next_start = 0.0
            started = False
            while time.monotonic() < start_deadline:
                now = time.monotonic()
                if now >= next_start:
                    send(port, "START")
                    next_start = now + START_RETRY_S
                for line in consume(lines, history):
                    if line.startswith("STARTED "):
                        started = True
                if started:
                    break
                time.sleep(DRIVE_POLL_S)
            if not started:
                raise TimeoutError("No STARTED response from ESP32-C3 within 12 seconds")

            finished_deadline = None
            while True:
                # Check drives BEFORE parsing accumulated serial lines.
                found = matching_new_drive(baseline, args.volume_label)
                if found is not None:
                    drive, label = found
                    detected_at = timestamp()
                    stopped = stop_esp(port, lines, history)
                    copy_path = copies_dir / "flash_{}_{}".format(
                        drive[0], filename_timestamp())
                    try:
                        copy_result = copy_drive(drive, copy_path)
                    except OSError as exc:
                        copy_result = {"files": 0, "bytes": 0, "errors": [str(exc)]}
                    record = event_record(
                        "NEW_DRIVE_DETECTED", history, baseline,
                        detected_at=detected_at,
                        drive=drive,
                        volume_label=label,
                        stop_confirmed=stopped,
                        copy_path=str(copy_path),
                        copy_result=copy_result,
                    )
                    path = write_json_atomic(results_dir, record)
                    print("Result:", path)
                    return 0

                for line in consume(lines, history):
                    if line.startswith("FINISHED ") and finished_deadline is None:
                        finished_deadline = time.monotonic() + FINAL_DRIVE_WAIT_S
                if finished_deadline is not None and time.monotonic() >= finished_deadline:
                    path = write_json_atomic(results_dir, event_record(
                        "SEARCH_FINISHED_NO_DRIVE", history, baseline))
                    print("No new drive. Result:", path)
                    return 0
                time.sleep(DRIVE_POLL_S)
        except KeyboardInterrupt:
            stopped = stop_esp(port, lines, history)
            path = write_json_atomic(results_dir, event_record(
                "MANUAL_STOP", history, baseline, stop_confirmed=stopped))
            print("Manual stop. Result:", path)
            return 130
        except Exception:
            # Do not leave the encoder running after a host-side failure.
            try:
                stop_esp(port, lines, history)
            except Exception:
                pass
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="ESP32-C3 COM port, e.g. COM7")
    parser.add_argument("--volume-label", help="Expected new drive label")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent,
                        help="Directory for flash_copies and pin_results")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("This monitor requires Windows GetLogicalDrives")
    try:
        return run(args)
    except ImportError as exc:
        parser.error("Install pyserial: py -m pip install pyserial ({})".format(exc))
    except (OSError, TimeoutError, RuntimeError) as exc:
        print("Error:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
