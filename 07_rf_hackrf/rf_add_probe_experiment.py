#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""RP2040-Zero / HackRF checked A/B/A experiment.
Default is hardware-free dry-run. Host API times are not RF envelope edges.
255-2^k is compatible with an ADD skip, not proof. Gain is not chip power.
Original user source is preserved under backups/*_host_original/.
"""
from __future__ import annotations
import argparse
import binascii
from collections import Counter
import ctypes as c
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import threading
import time

WORKDIR = Path(r"C:\Users\mkkr\Documents\Codex\hackathon")
RESULTS_DIR = WORKDIR / "fault_experiment_2026-09-25"
PYTHON_EXE = Path(r"C:\Users\mkkr\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
HACKRF_DLL = Path(r"C:\Users\mkkr\AppData\Local\Programs\SDRPlusPlus\sdrpp_windows_x64\hackrf.dll")
BOARD_VID, BOARD_PID = 0x2E8A, 0x101F
BOARD_SERIAL = "5303284740FF6F9C"
HACKRF_SERIAL = "000000000000000066a062dc2a4f2e9f"
HACKRF_VID, HACKRF_PID = 0x1D50, 0x6089
NOTE = ("API timestamps do not measure RF envelope or synchronize with an RP2040 instruction; "
        "255-2^k is compatible with skipped ADD, not proof; gain is not power at the chip.")
CLASSES = ("OK", "COMPUTATIONAL_ERROR", "SUSPECTED_SKIPPED_ADD_SIGNATURE",
           "INTEGRITY_VIOLATION", "TIMEOUT_UNCONFIRMED", "COMM_LOSS", "OBSERVED_RESET")
SKIP_SIGNATURE_SET = {255 - (1 << k) for k in range(8)}
DEFAULT_PLAN = {
    "common": dict(center_freq_hz=125000000, tone_offset_hz=0, sample_rate_hz=2000000,
                   waveform="sine", txvga_gain=0, rf_amp=0, digital_amplitude=0.0),
    "rf_series": [
        dict(name="txvga_gain_sweep", parameter="txvga_gain", values=[0,1,2,4,8,12,16,20,24,28,32,36,40,47]),
        dict(name="rf_amp_sweep", parameter="rf_amp", values=[0,1]),
        dict(name="digital_amplitude_sweep", parameter="digital_amplitude", values=[0,.01,.02,.05,.1,.2,.5,1.0]),
    ],
}
sys.path.insert(0, str(WORKDIR / "vendor"))

def stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")

def sha(data):
    return hashlib.sha256(data).hexdigest()

class StopExperiment(RuntimeError):
    pass

class Logger:
    def __init__(self):
        self.path = RESULTS_DIR / ("rf_experiment_" + stamp() + ".jsonl")
        self.file = self.path.open("x", encoding="utf-8")
        self.lock = threading.Lock()
    def log(self, event, **values):
        row = dict(ts=datetime.now(timezone.utc).isoformat(),
                   monotonic_ns=time.perf_counter_ns(), event=event, **values)
        with self.lock:
            self.file.write(json.dumps(row, ensure_ascii=False) + "\n")
            self.file.flush()
            if event not in ("serial_rx", "serial_tx", "api"):
                print(json.dumps(row, ensure_ascii=False), flush=True)
        return row
    def close(self):
        self.file.close()

def find_port(requested=None):
    from serial.tools import list_ports
    ports = [p for p in list_ports.comports()
             if (p.vid, p.pid, p.serial_number) == (BOARD_VID, BOARD_PID, BOARD_SERIAL)]
    if len(ports) != 1 or (requested and ports[0].device != requested):
        raise RuntimeError("Expected RP2040 not found by VID/PID/serial")
    return ports[0].device

def parse_frame(line):
    prefix, rest = line.split(",", 1)
    if prefix in ("INFO", "DENSE", "DIAG"):
        body, checksum = rest.rsplit(":", 1)
        if len(checksum) != 8 or (binascii.crc32(body.encode("ascii")) & 0xffffffff) != int(checksum, 16):
            raise ValueError("CRC32 mismatch")
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("Expected JSON object")
        return prefix, data
    if prefix in ("PONG", "READY"):
        parts = rest.split(",")
        if len(parts) != 3 or parts[:2] != ["RP2040-ZERO", "PROBE2"]:
            raise ValueError("Unexpected service identity")
        return prefix, dict(session=parts[2], program_version="PROBE2")
    if prefix == "RESULT":
        sequence, iterations, bad, total, elapsed = map(int, rest.split(","))
        return prefix, dict(sequence=sequence, iterations=iterations, bad=bad,
                            total=total, elapsed_us=elapsed)
    raise ValueError("Unexpected frame " + prefix)

def classify(cmd, data, session=None):
    if data.get("_transport_class"):
        return data["_transport_class"]
    if session is not None and data.get("session", session) != session:
        return "OBSERVED_RESET"
    if data.get("_error"):
        return "INTEGRITY_VIOLATION"
    if cmd in ("PING", "INFO"):
        return "OK" if data.get("session") else "INTEGRITY_VIOLATION"
    try:
        bad = data["bad"]
        if type(bad) is not int or bad < 0 or bad > data["iterations"]:
            return "INTEGRITY_VIOLATION"
        if cmd == "RUN":
            return "COMPUTATIONAL_ERROR" if bad else "OK"
        if data["integrity"] != 0 or data["completed"] != data["iterations"]:
            return "INTEGRITY_VIOLATION"
        if cmd == "DENSE":
            value, inverse = data["first_value"], data["inverse"]
            if not (0 <= value <= 0xffffffff and 0 <= inverse <= 0xffffffff) or value ^ inverse != 0xffffffff:
                return "INTEGRITY_VIOLATION"
            if bad and not 0 <= data["first_index"] < data["iterations"]:
                return "INTEGRITY_VIOLATION"
            if bad:
                return ("SUSPECTED_SKIPPED_ADD_SIGNATURE" if value in SKIP_SIGNATURE_SET
                        else "COMPUTATIONAL_ERROR")
            if value != 0 or inverse != 0xffffffff or data.get("signature") is not None:
                return "INTEGRITY_VIOLATION"
            return "OK"
        if cmd == "TRACE":
            signatures, examples = data["signatures"], data["examples"]
            if len(signatures) != 8 or any(type(v) is not int or v < 0 for v in signatures):
                return "INTEGRITY_VIOLATION"
            if sum(signatures) > bad:
                return "INTEGRITY_VIOLATION"
            for index, value, inverse, stored_index in examples:
                if value ^ inverse != 0xffffffff or stored_index != index % 1024:
                    return "INTEGRITY_VIOLATION"
            if not bad and (any(signatures) or examples):
                return "INTEGRITY_VIOLATION"
            if bad:
                compatible = any(value in SKIP_SIGNATURE_SET for _,value,_,_ in examples)
                return ("SUSPECTED_SKIPPED_ADD_SIGNATURE" if compatible or any(signatures)
                        else "COMPUTATIONAL_ERROR")
            return "OK"
    except (KeyError, ValueError, TypeError):
        return "INTEGRITY_VIOLATION"
    return "INTEGRITY_VIOLATION"

class Board:
    def __init__(self, logger, port):
        import serial
        self.log = logger
        self.ser = serial.Serial(port, 115200, timeout=.05, write_timeout=2)
        self.session = None
        self.sequence = None
        self.log.log("board_connected", port=port, serial=BOARD_SERIAL)
    def close(self):
        self.ser.close()
    def command(self, cmd_line, timeout=10):
        import serial
        cmd = cmd_line.split()[0]
        wanted = dict(PING="PONG", INFO="INFO", RUN="RESULT", DENSE="DENSE", TRACE="DIAG")[cmd]
        raw, pending, begin = [], b"", None
        try:
            self.log.log("serial_tx", command=cmd_line)
            self.ser.write((cmd_line + "\n").encode("ascii"))
            self.ser.flush()
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                chunk = self.ser.read_until(b"\n")
                if not chunk:
                    continue
                self.log.log("serial_rx", raw_hex=chunk.hex())
                pending += chunk
                if len(pending) > 65536:
                    return raw, dict(_error="Overlong frame")
                if not pending.endswith(b"\n"):
                    continue
                line = pending.decode("ascii").strip()
                pending = b""
                raw.append(line)
                if not line:
                    continue
                if line.startswith("READY,"):
                    _, boot = parse_frame(line)
                    if self.session is not None:
                        return raw, dict(**boot, _transport_class="OBSERVED_RESET")
                    continue
                if line.startswith("BEGIN,"):
                    _, sid, seq, n = line.split(",")
                    begin = dict(session=sid, sequence=int(seq), iterations=int(n))
                    if self.session is not None and sid != self.session:
                        return raw, dict(**begin, _transport_class="OBSERVED_RESET")
                    continue
                prefix, data = parse_frame(line)
                if prefix != wanted:
                    return raw, dict(_error="Unexpected response", received=prefix, expected=wanted)
                if cmd in ("RUN", "DENSE", "TRACE"):
                    if data["iterations"] != int(cmd_line.split()[1]):
                        data["_error"] = "Wrong iteration count"
                    seq = data["sequence"]
                    if self.sequence is not None and seq != self.sequence + 1:
                        data["_error"] = "Sequence discontinuity"
                    if cmd in ("DENSE", "TRACE") and (begin is None or any(data.get(k) != v for k,v in begin.items())):
                        data["_error"] = "BEGIN/result mismatch"
                    self.sequence = seq
                return raw, data
            return raw, dict(_transport_class="TIMEOUT_UNCONFIRMED", partial_hex=pending.hex(), begin=begin)
        except (serial.SerialException, OSError) as exc:
            return raw, dict(_transport_class="COMM_LOSS", error=repr(exc))
        except (ValueError, KeyError, TypeError, UnicodeError) as exc:
            return raw, dict(_error=repr(exc))

def verify_firmware(port, log, upload=False):
    from mpremote.transport_serial import SerialTransport
    backup = RESULTS_DIR / "backups" / (stamp() + "_board_readback")
    backup.mkdir(parents=True, exist_ok=False)
    transport = SerialTransport(port, timeout=3)
    entered = False
    try:
        transport.enter_raw_repl(soft_reset=False)
        entered = True
        out, err = transport.exec_raw(
            "import sys, machine, os; print(sys.implementation); print('FREQ', machine.freq()); print('FILES', os.listdir())")
        if err:
            raise RuntimeError(err.decode(errors="replace"))
        identity = out.decode()
        log.log("firmware_identity", identity=identity)
        if "1, 29, 0" not in identity or "Waveshare RP2040-Zero" not in identity or "FREQ 125000000" not in identity:
            raise RuntimeError("MicroPython version/board/frequency differs from expected")
        remote = {}
        for name in ("fault_probe.py", "main.py"):
            remote[name] = bytes(transport.fs_readfile(name))
            (backup / name).write_bytes(remote[name])
            log.log("board_backup", name=name, path=str(backup/name), sha256=sha(remote[name]))
        expected = {
            "fault_probe.py": (WORKDIR / "fault_probe.py").read_bytes(),
            "main.py": b"import fault_probe\nfault_probe.serve()\n",
        }
        if upload:
            # All originals have been backed up successfully before the first write.
            expected["main.py"] = (WORKDIR / "main.py").read_bytes()
            for name, data in expected.items():
                transport.fs_writefile(name, data)
                remote[name] = bytes(transport.fs_readfile(name))
        for name, data in expected.items():
            exact = remote[name] == data
            # main.py is compared as text as its reference comes from user instructions.
            matches = exact or (name == "main.py" and remote[name].replace(b"\r\n", b"\n").strip() == data.strip())
            log.log("firmware_file_check", name=name, remote_sha256=sha(remote[name]),
                    expected_sha256=sha(data), exact_bytes=exact, matches=matches)
            if not matches or (upload and not exact):
                raise RuntimeError("Readback mismatch: " + name)
    finally:
        if entered:
            transport.exit_raw_repl()
            transport.serial.write(b"\x04")
            transport.serial.flush()
            log.log("intentional_soft_reset", reason="Restart verified service after file readback; not an RF reset")
            time.sleep(1)
        transport.close()

class Transfer(c.Structure):
    _fields_ = [("device", c.c_void_p), ("buffer", c.POINTER(c.c_uint8)),
                ("buffer_length", c.c_int), ("valid_length", c.c_int),
                ("rx_ctx", c.c_void_p), ("tx_ctx", c.c_void_p)]
CB = c.CFUNCTYPE(c.c_int, c.POINTER(Transfer))

class HackRF:
    def __init__(self, log):
        self.log, self.dev = log, c.c_void_p()
        self.cookie = os.add_dll_directory(str(HACKRF_DLL.parent))
        self.lib = c.CDLL(str(HACKRF_DLL))
        prototypes = {
            "hackrf_init": [], "hackrf_exit": [],
            "hackrf_open_by_serial": [c.c_char_p, c.POINTER(c.c_void_p)],
            "hackrf_close": [c.c_void_p], "hackrf_stop_tx": [c.c_void_p],
            "hackrf_is_streaming": [c.c_void_p],
            "hackrf_start_tx": [c.c_void_p, CB, c.c_void_p],
            "hackrf_set_freq": [c.c_void_p, c.c_uint64],
            "hackrf_set_sample_rate": [c.c_void_p, c.c_double],
            "hackrf_set_baseband_filter_bandwidth": [c.c_void_p, c.c_uint32],
            "hackrf_set_txvga_gain": [c.c_void_p, c.c_uint32],
            "hackrf_set_amp_enable": [c.c_void_p, c.c_uint8],
            "hackrf_set_antenna_enable": [c.c_void_p, c.c_uint8],
            "hackrf_version_string_read": [c.c_void_p, c.c_char_p, c.c_uint8],
        }
        for name, types in prototypes.items():
            getattr(self.lib, name).argtypes = types
            getattr(self.lib, name).restype = c.c_int
        self.call("hackrf_init")
        try:
            self.call("hackrf_open_by_serial", HACKRF_SERIAL.encode(), c.byref(self.dev))
            self.off()
            version = c.create_string_buffer(255)
            self.call("hackrf_version_string_read", self.dev, version, 255)
            firmware = version.value.decode()
            self.log.log("hackrf_identity", serial=HACKRF_SERIAL, firmware=firmware, streaming=self.streaming())
            if firmware != "2023.01.1":
                raise RuntimeError("Unexpected HackRF firmware " + firmware)
        except BaseException:
            self.close()
            raise
    def call(self, name, *args):
        rc = getattr(self.lib, name)(*args)
        self.log.log("api", name=name, rc=rc)
        if rc:
            raise RuntimeError(f"{name} failed: {rc}")
        return rc
    def streaming(self):
        return self.lib.hackrf_is_streaming(self.dev)
    def off(self):
        errors = []
        if not self.dev.value:
            return
        # Try every shutdown operation even when an earlier one fails.
        for name, values in [
            ("hackrf_stop_tx", (self.dev,)),
            ("hackrf_set_amp_enable", (self.dev, 0)),
            ("hackrf_set_antenna_enable", (self.dev, 0)),
            ("hackrf_set_txvga_gain", (self.dev, 0)),
        ]:
            rc = getattr(self.lib, name)(*values)
            self.log.log("api", name=name, rc=rc)
            if rc != 0:
                errors.append((name, rc))
        streaming = self.streaming()
        self.log.log("rf_off", streaming=streaming, gain_db=0, amp=False, antenna_power=False, errors=errors)
        if streaming == 1 or errors:
            raise RuntimeError("RF shutdown check failed: " + repr(errors))
    def close(self):
        try:
            if self.dev.value:
                try:
                    self.off()
                finally:
                    self.call("hackrf_close", self.dev)
                    self.dev = c.c_void_p()
        finally:
            self.call("hackrf_exit")
            self.cookie.close()
    def configure(self, cfg):
        if self.streaming() == 1:
            raise RuntimeError("Unexpected streaming before configuration")
        for name, value in [
            ("hackrf_set_sample_rate", cfg["sample_rate_hz"]),
            ("hackrf_set_baseband_filter_bandwidth", cfg["filter_hz"]),
            ("hackrf_set_freq", cfg["center_freq_hz"]),
            ("hackrf_set_txvga_gain", cfg["txvga_gain"]),
            ("hackrf_set_amp_enable", int(cfg["rf_amp"])),
            ("hackrf_set_antenna_enable", 0),
        ]:
            self.call(name, self.dev, value)

class Burst:
    def __init__(self, radio, cfg, log, label):
        self.radio, self.cfg, self.log, self.label = radio, cfg, log, label
        self.timer = None
        self.started = False
        self.stop_lock = threading.Lock()
        self.stopped = False
        self.stop_error = None
        self.stats = dict(callback_count=0, samples_offered=0, signal_samples_offered=0, callback_error=None)
        sr, tone = cfg["sample_rate_hz"], cfg["tone_offset_hz"]
        tone_period = sr // math.gcd(sr, abs(tone)) if tone else 1
        pulse_rate = cfg.get("pulse_rate_hz")
        pulse_period = sr // pulse_rate if pulse_rate else 1
        self.period = math.lcm(tone_period, pulse_period)
        if self.period > 1000000:
            raise ValueError("Waveform period too long")
        amp = round(127 * cfg["digital_amplitude"])
        self.wave = bytes(component & 255 for n in range(self.period) for component in (
            round(amp * math.cos(2*math.pi*tone*n/sr)) if not pulse_rate or n % pulse_period < pulse_period*cfg["duty_percent"]/100 else 0,
            round(amp * math.sin(2*math.pi*tone*n/sr)) if not pulse_rate or n % pulse_period < pulse_period*cfg["duty_percent"]/100 else 0))
        self.sample_limit = int(sr * cfg["max_tx_seconds"])
        self.callback = CB(self.fill)
    def fill(self, ptr):
        try:
            block = ptr.contents
            count = block.buffer_length // 2
            offered = self.stats["samples_offered"]
            remaining = max(0, min(count, self.sample_limit - offered))
            offset = offered % self.period
            pattern = self.wave[2*offset:] + self.wave[:2*offset]
            payload = (pattern * (remaining*2//len(pattern)+1))[:remaining*2] + bytes((count-remaining)*2)
            c.memmove(block.buffer, payload, len(payload))
            block.valid_length = len(payload)
            self.stats["callback_count"] += 1
            self.stats["samples_offered"] += count
            self.stats["signal_samples_offered"] += remaining
            return 0
        except BaseException as exc:
            self.stats["callback_error"] = repr(exc)
            return -1
    def stop(self):
        with self.stop_lock:
            if self.stopped:
                return
            self.stopped = True
            try:
                self.radio.off()
            except BaseException as exc:
                self.stop_error = repr(exc)
            self.log.log("tx_stop", label=self.label, api_duration_s=time.monotonic()-self.start_time,
                         stats=dict(self.stats), error=self.stop_error, note=NOTE)
    def __enter__(self):
        try:
            self.radio.configure(self.cfg)
            self.start_time = time.monotonic()
            self.radio.call("hackrf_start_tx", self.radio.dev, self.callback, None)
            self.started = True
            streaming = self.radio.streaming()
            self.timer = threading.Timer(max(0, self.cfg["max_tx_seconds"]-(time.monotonic()-self.start_time)), self.stop)
            self.timer.daemon = True
            self.timer.start()
            self.log.log("tx_start", label=self.label, rf_cfg=self.cfg, streaming=streaming, note=NOTE)
            if streaming != 1:
                raise RuntimeError("HackRF did not enter streaming state")
            return self
        except BaseException:
            if self.started:
                self.stop()
            else:
                self.radio.off()
            raise
    def __exit__(self, typ, value, tb):
        if self.timer:
            if typ is not None:
                self.timer.cancel()
                self.stop()
            self.timer.join(timeout=3)
            if self.timer.is_alive():
                raise RuntimeError("TX stop watchdog did not finish")
        if not self.stopped:
            self.stop()
        if self.stop_error or self.stats["callback_error"] or not self.stats["callback_count"]:
            raise RuntimeError("TX failed: " + repr(self.stats) + " " + str(self.stop_error))

def load_configs(args):
    path = Path(args.rf_plan) if args.rf_plan else RESULTS_DIR / "rf_plan.json"
    plan = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else DEFAULT_PLAN
    configs = []
    if "settings" in plan:
        for i, setting in enumerate(plan["settings"]):
            cfg = dict(
                label=f"setting_{i}_{setting['carrier_hz']}_{setting['waveform']}",
                carrier_hz=setting["carrier_hz"], center_freq_hz=setting["center_hz"],
                tone_offset_hz=setting["iq_tone_hz"], sample_rate_hz=setting["sample_rate"],
                filter_hz=setting["filter_hz"], txvga_gain=setting["tx_gain_db"],
                rf_amp=bool(setting["rf_amp"]), digital_amplitude=setting["amplitude"]/127,
                waveform=setting["waveform"], pulse_rate_hz=setting.get("pulse_rate_hz"),
                duty_percent=setting["duty_percent"], max_tx_seconds=args.max_tx_seconds)
            if args.max_output:
                cfg.update(txvga_gain=47, rf_amp=True, digital_amplitude=1.0)
            configs.append(cfg)
    elif "rf_series" in plan:
        for series in plan["rf_series"]:
            for value in series["values"]:
                cfg = dict(DEFAULT_PLAN["common"])
                cfg.update(plan.get("common", {}))
                if args.max_output:
                    cfg.update(txvga_gain=47, rf_amp=True, digital_amplitude=1.0)
                cfg[series["parameter"]] = value
                cfg.update(label=f"{series['name']}_{value}", filter_hz=1750000,
                           max_tx_seconds=args.max_tx_seconds, pulse_rate_hz=None, duty_percent=100)
                cfg["carrier_hz"] = cfg["center_freq_hz"] + cfg["tone_offset_hz"]
                configs.append(cfg)
    else:
        raise ValueError("Unrecognized RF plan schema")
    if not configs:
        raise ValueError("Empty RF plan")
    for cfg in configs:
        if not (0 <= cfg["txvga_gain"] <= 47 and 0 <= cfg["digital_amplitude"] <= 1
                and 1000000 <= cfg["center_freq_hz"] <= 6000000000
                and .01 <= cfg["max_tx_seconds"] <= .5
                and cfg["sample_rate_hz"] >= 2000000):
            raise ValueError("Invalid RF configuration")
        if cfg["waveform"] not in ("cw", "sine", "pulsed_1khz_10percent"):
            raise ValueError("Unsupported waveform")
    return dict(source=str(path), original=plan, configurations=configs)

class Experiment:
    def __init__(self, args, plan):
        self.args, self.plan = args, plan
        self.log = Logger()
        self.board, self.radio = None, None
        self.results, self.suspicious = [], []
        self.completed = False
    def save_suspicious(self, row):
        folder = RESULTS_DIR / "suspicious"
        folder.mkdir(exist_ok=True)
        path = folder / (stamp() + "_" + row["classification"] + ".json")
        path.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
        self.suspicious.append(str(path))
        self.log.log("suspicious_saved", path=str(path))
    def one(self, cmd_line, label, rep=0, cfg=None):
        cmd = cmd_line.split()[0]
        start = time.time()
        raw, data = self.board.command(cmd_line, timeout=60 if cmd=="TRACE" else 10)
        cls = classify(cmd, data, self.board.session)
        row = self.log.log("probe_result", label=label, rep=rep, cmd=cmd, cmd_line=cmd_line,
                           rf=cfg, raw_lines=raw, parsed=data, classification=cls,
                           api_cmd_start=start, api_cmd_end=time.time(), note=NOTE)
        self.results.append(row)
        if cls != "OK":
            self.save_suspicious(row)
            raise StopExperiment("Non-OK result; stopped: " + cls)
        if self.board.session is None and "session" in data:
            self.board.session = data["session"]
        return data
    def controls(self, label, repetitions=1):
        for rep in range(repetitions):
            self.one("PING", label, rep)
            self.one("INFO", label, rep)
            self.one(f"DENSE {self.args.dense_n}", label, rep)
            self.one(f"TRACE {self.args.trace_n}", label, rep)
    def rf_trial(self, label, cfg, rep, commands=None):
        self.controls(label+"_pre")
        for cmd in commands or (f"DENSE {self.args.dense_n}", f"TRACE {self.args.trace_n}"):
            with Burst(self.radio, cfg, self.log, label+"_"+cmd.split()[0]):
                self.one(cmd, label+"_rf", rep, cfg)
            self.one("PING", label+"_after_burst", rep)
        self.controls(label+"_post")
    def run(self):
        try:
            setup = json.loads((RESULTS_DIR/"setup.json").read_text(encoding="utf-8"))
            if not (setup["shielded_box_confirmed"] and setup["anechoic_chamber_confirmed"]
                    and setup["near_field_probe_over_chip_confirmed"]):
                raise RuntimeError("Shielded setup not confirmed")
            self.log.log("experiment_start", args=vars(self.args), setup=setup, plan=self.plan,
                         source_sha256=sha(Path(__file__).read_bytes()), note=NOTE)
            port = find_port(self.args.port)
            self.radio = HackRF(self.log)
            verify_firmware(port, self.log, self.args.upload)
            self.board = Board(self.log, port)
            self.one("PING", "identity")
            info = self.one("INFO", "identity")
            if info.get("freq") != 125000000:
                raise RuntimeError("Unexpected MCU clock")
            for n in (1,10,1000,100000,1000000):
                self.one(f"RUN {n}", "functional")
            self.controls("baseline_no_rf", self.args.repetitions)
            self.log.log("baseline_complete")
            if not self.args.baseline_only:
                if self.args.repeat_event:
                    event = json.loads(Path(self.args.repeat_event).read_text(encoding="utf-8"))
                    cfg = event.get("rf")
                    if cfg:
                        self.rf_trial("repeat_"+event["label"], cfg, 0, [event["cmd_line"]])
                    else:
                        self.one(event["cmd_line"], "repeat_no_rf")
                else:
                    for cfg in self.plan["configurations"]:
                        for rep in range(self.args.repetitions):
                            self.rf_trial(f"{cfg['label']}_rep{rep}", cfg, rep)
                self.controls("final_no_rf", self.args.repetitions)
            self.completed = True
            self.log.log("experiment_complete")
        except BaseException as exc:
            self.log.log("experiment_aborted", error=repr(exc))
            raise
        finally:
            try:
                if self.radio:
                    self.radio.close()
            except BaseException:
                self.completed = False
                raise
            finally:
                if self.board:
                    self.board.close()
                counts = Counter(row["classification"] for row in self.results)
                summary = dict(completed=self.completed, log=str(self.log.path),
                               classification={name:counts[name] for name in CLASSES},
                               diagnostic_iterations=sum(row["parsed"].get("iterations",0) for row in self.results if row["cmd"] in ("DENSE","TRACE")),
                               suspicious=self.suspicious, note=NOTE)
                self.log.log("summary", **summary)
                self.log.path.with_suffix(".summary.json").write_text(
                    json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
                self.log.close()

def build_argparser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--execute", action="store_true")
    p.add_argument("--upload", action="store_true")
    p.add_argument("--baseline-only", action="store_true")
    p.add_argument("--max-output", action="store_true", help="Legacy settings plan: 47 dB, RF amp on, IQ 127/127")
    p.add_argument("--port")
    p.add_argument("--dense-n", type=int, default=1000000)
    p.add_argument("--trace-n", type=int, default=10000)
    p.add_argument("--repetitions", type=int, default=3)
    p.add_argument("--max-tx-seconds", type=float, default=.5)
    p.add_argument("--rf-plan")
    p.add_argument("--repeat-event")
    return p

def main():
    args = build_argparser().parse_args()
    if not (1 <= args.dense_n <= 1000000 and 1 <= args.trace_n <= 1000000
            and 1 <= args.repetitions <= 10 and .01 <= args.max_tx_seconds <= .5):
        raise ValueError("Invalid iteration, repetition or TX bound")
    plan = load_configs(args)
    if not args.execute:
        print("DRY-RUN. Hardware is not opened; TX is not enabled.")
        print(json.dumps(dict(WORKDIR=str(WORKDIR), RESULTS_DIR=str(RESULTS_DIR),
                              PYTHON_EXE=str(PYTHON_EXE), HACKRF_DLL=str(HACKRF_DLL),
                              args=vars(args), plan=plan, note=NOTE), ensure_ascii=False, indent=2))
        return 0
    Experiment(args, plan).run()
    return 0

if __name__ == "__main__":
    sys.exit(main())
