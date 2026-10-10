"""Sambungan USB serial ke Pico. Protokol: satu pesan JSON per baris."""

from __future__ import annotations

import errno
import json
import time

import serial
from serial.tools import list_ports

PICO_VID = 0x2E8A
DEVICE_NAME = "hwdisplay"
BAUD = 115200  # jangan pernah 1200: itu perintah reset ke bootloader di arduino-pico

LinkError = (serial.SerialException, OSError)


class DeviceError(Exception):
    """Perangkat menolak perintah atau tidak menjawab."""


def available_ports() -> list:
    return sorted(list_ports.comports(), key=lambda p: p.device)


def candidate_ports(port=None) -> list:
    if port:
        return [port]
    # Tanpa port eksplisit hanya perangkat ber-VID Raspberry Pi yang dicoba,
    # supaya perangkat serial lain tidak ikut dikirimi data.
    return [p.device for p in available_ports() if p.vid == PICO_VID]


class Device:
    def __init__(self, port: str):
        self.port = port
        self._buf = b""
        self._ser = serial.Serial(port, BAUD, timeout=0.1, write_timeout=2)
        try:
            self.info = self._handshake()
        except Exception:
            self._ser.close()
            raise

    def _handshake(self) -> dict:
        self._ser.reset_input_buffer()
        self.send({"t": "hello"})
        reply = self._wait(lambda m: m.get("t") == "hello", 2.0)
        if reply is None or reply.get("name") != DEVICE_NAME:
            raise DeviceError(f"{self.port} bukan {DEVICE_NAME}")
        return reply

    def send(self, msg: dict):
        line = json.dumps(msg, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        self._ser.write(line.encode("utf-8") + b"\n")

    def _read(self, block: bool) -> list:
        waiting = self._ser.in_waiting
        if not waiting and not block:
            return []
        self._buf += self._ser.read(waiting or 1)
        *lines, self._buf = self._buf.split(b"\n")
        messages = []
        for line in lines:
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if isinstance(msg, dict):
                messages.append(msg)
        return messages

    def _wait(self, wanted, timeout: float):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for msg in self._read(block=True):
                if wanted(msg):
                    return msg
        return None

    def request(self, msg: dict, timeout: float = 3.0) -> dict:
        """Kirim perintah dan tunggu jawaban ok/err dari Pico."""
        kind = msg["t"]
        self.send(msg)
        reply = self._wait(
            lambda m: m.get("t") in ("ok", "err") and m.get("for") == kind, timeout)
        if reply is None:
            raise DeviceError(f"Pico tidak menjawab perintah '{kind}'")
        if reply["t"] == "err":
            raise DeviceError(reply.get("msg", "perintah ditolak"))
        return reply

    def drain(self):
        self._read(block=False)

    def close(self):
        try:
            self._ser.close()
        except LinkError:
            pass


def _is_busy(exc) -> bool:
    """Port ada, tetapi sedang dibuka program lain."""
    if getattr(exc, "errno", None) == errno.EBUSY:
        return True
    # pyserial di Windows membungkus galatnya tanpa errno, hanya sebagai teks.
    return "PermissionError" in str(exc)


def connect(port=None, busy=None):
    """Device pertama yang menjawab handshake, atau None.

    Port yang sedang dipakai program lain ditambahkan ke list `busy` bila diberikan.
    """
    for name in candidate_ports(port):
        try:
            return Device(name)
        except DeviceError:
            continue
        except LinkError as exc:
            if busy is not None and _is_busy(exc):
                busy.append(name)
            continue
    return None
