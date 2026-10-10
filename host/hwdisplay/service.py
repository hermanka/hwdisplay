"""Thread latar: baca sensor, jaga sambungan ke Pico, kirim data dan perintah."""

from __future__ import annotations

import json
import os
import threading
import time

import psutil

from . import device as dev_mod
from .layout import to_device, used_metrics
from .sensors import Sensors

RECONNECT_S = 2.0
_ORDER = ("config", "layout", "page")


def _headless_running() -> bool:
    """Ada proses `hwdisplay --headless` lain yang sedang berjalan."""
    own = {os.getpid(), os.getppid()}  # induk: peluncur virtualenv di Windows
    for proc in psutil.process_iter(["pid", "name"]):
        if proc.info["pid"] in own or "python" not in (proc.info["name"] or "").lower():
            continue
        try:
            cmdline = proc.cmdline()
        except psutil.Error:
            continue
        if "hwdisplay" in cmdline and "--headless" in cmdline:
            return True
    return False


class Service(threading.Thread):
    def __init__(self, settings: dict, layout: dict, watch_headless: bool = False):
        super().__init__(daemon=True, name="hwdisplay-service")
        self.settings = settings
        self._watch_headless = watch_headless  # hanya editor yang perlu memeriksa
        self._headless = False
        self._busy = None  # port Pico yang sedang dipakai program lain
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stopping = threading.Event()
        self._pending = {}
        self._resend = {}  # perintah yang diulang setiap kali Pico tersambung lagi
        self._values = {}
        self._seq = 0  # naik setiap pembacaan sensor baru
        self._info = None
        self._port = None
        self._error = None
        self._used = set()  # metrik yang dipakai layout; hanya ini yang dikirim ke Pico
        # Dibuat di sini, bukan di thread, supaya katalog metrik langsung tersedia.
        self._sensors = Sensors(settings.get("gpu_index", 0))
        self.set_config(settings["brightness"], settings["sleep_s"])
        self.set_layout(layout)

    # --- dipanggil dari thread GUI -------------------------------------

    def set_layout(self, layout: dict, page: int = 0, save: bool = False):
        msg = {"t": "layout", "layout": to_device(layout), "page": page, "save": save}
        with self._lock:
            self._used = used_metrics(msg["layout"])
        self._submit(msg, resend={**msg, "save": False})

    def set_config(self, brightness: int, sleep_s: int):
        msg = {"t": "config", "brightness": int(brightness), "sleep_s": int(sleep_s)}
        self._submit(msg, resend=msg)

    def set_page(self, page: int):
        self._submit({"t": "page", "n": page})

    def metrics(self) -> dict:
        return self._sensors.metrics()

    def gpus(self) -> list:
        return self._sensors.gpus

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "connected": self._info is not None,
                "port": self._port,
                "info": self._info,
                "values": dict(self._values),
                "seq": self._seq,
                "error": self._error,
                "busy": self._busy,
                "headless": self._headless,
                "gpu_name": self._sensors.gpu_summary,
            }

    def stop(self):
        self._stopping.set()
        self._wake.set()

    # --- thread latar ---------------------------------------------------

    def _submit(self, msg: dict, resend=None):
        with self._lock:
            self._pending[msg["t"]] = msg
            if resend is not None:
                self._resend[msg["t"]] = resend
        self._wake.set()

    def _flush(self, dev):
        with self._lock:
            pending, self._pending = self._pending, {}
        for kind in _ORDER:
            msg = pending.get(kind)
            if msg is None:
                continue
            size = len(json.dumps(msg, ensure_ascii=False).encode("utf-8"))
            limit = dev.info.get("max_line", 16384) - 2
            error = None
            if size > limit:
                error = f"Layout terlalu besar ({size} byte, batas {limit})"
            else:
                try:
                    reply = dev.request(msg)
                    if msg.get("save") and not reply.get("saved", True):
                        error = ("Pico tidak punya filesystem; pilih Flash Size "
                                 "dengan FS di Arduino IDE lalu upload ulang")
                except dev_mod.DeviceError as exc:
                    error = str(exc)
            if error is not None or kind == "layout":
                with self._lock:
                    self._error = error

    def _disconnect(self, dev):
        dev.close()
        with self._lock:
            self._info = None
            self._port = None

    def run(self):
        sensors = self._sensors
        dev = None
        next_try = 0.0
        next_tick = 0.0
        next_watch = 0.0
        while not self._stopping.is_set():
            now = time.monotonic()
            if self._watch_headless and now >= next_watch:
                headless = _headless_running()
                next_watch = time.monotonic() + RECONNECT_S
                with self._lock:
                    self._headless = headless

            if dev is None and now >= next_try:
                busy = []
                dev = dev_mod.connect(self.settings.get("port"), busy)
                next_try = time.monotonic() + RECONNECT_S
                with self._lock:
                    self._busy = busy[0] if busy and dev is None else None
                if dev is not None:
                    with self._lock:
                        self._info = dev.info
                        self._port = dev.port
                        self._pending = {**self._resend, **self._pending}

            try:
                if dev is not None:
                    self._flush(dev)
                if time.monotonic() >= next_tick:
                    values = sensors.read()
                    with self._lock:
                        self._values = values
                        self._seq += 1
                        # Metrik yang hilang dikirim sebagai null supaya Pico
                        # menampilkan "--", bukan nilai terakhir yang sudah basi.
                        outgoing = {key: values.get(key) for key in sorted(self._used)}
                    next_tick = time.monotonic() + max(0.2, float(self.settings["interval"]))
                    if dev is not None:
                        dev.send({"t": "data", "v": outgoing})
                        dev.drain()
            except dev_mod.LinkError:
                self._disconnect(dev)
                dev = None
                next_try = time.monotonic() + RECONNECT_S

            wake_at = next_tick if dev is not None else min(next_tick, next_try)
            self._wake.wait(max(0.02, wake_at - time.monotonic()))
            self._wake.clear()

        if dev is not None:
            self._disconnect(dev)
        sensors.close()
