"""Pembacaan sensor PC: CPU dan RAM lewat psutil, GPU NVIDIA lewat NVML."""

from __future__ import annotations

import collections
import math
import time
from dataclasses import dataclass

import psutil

try:
    import pynvml
except ImportError:  # paket nvidia-ml-py belum dipasang
    pynvml = None

GIB = 1024 ** 3


@dataclass(frozen=True)
class MetricInfo:
    label: str
    unit: str
    min: float
    max: float
    dec: int
    hidden: bool = False  # tetap dikirim, tetapi tidak ditawarkan di editor


@dataclass(frozen=True)
class GpuInfo:
    index: int
    prefix: str     # awalan nama metrik, mis. "gpu1"
    name: str
    vram_gb: float


# akhiran metrik -> (label, satuan, min, max, desimal); max None = kapasitas VRAM kartu
_GPU_FIELDS = {
    "load": ("Beban", "%", 0, 100, 0),
    "temp": ("Suhu", "°C", 30, 95, 0),
    "vram_pct": ("Pemakaian VRAM", "%", 0, 100, 0),
    "vram_used": ("VRAM terpakai", " GB", 0, None, 1),
    "vram_total": ("VRAM total", " GB", 0, None, 1),
    "fan": ("Kipas", "%", 0, 100, 0),
    "power": ("Daya", " W", 0, 300, 0),
}

_CPU_TEMP_CHIPS = ("coretemp", "k10temp", "zenpower", "cpu_thermal")


def _text(value):
    return value.decode() if isinstance(value, bytes) else value


def _short_name(name):
    for word in ("NVIDIA ", "GeForce "):
        name = name.replace(word, "")
    return name.strip()


class _Nvidia:
    RETRY_S = 10

    def __init__(self):
        self.gpus = []      # tetap diingat saat driver hilang, supaya metriknya jadi "--"
        self._handles = []
        self._retry_at = 0.0

    def open(self):
        if pynvml is None or time.monotonic() < self._retry_at:
            return
        try:
            pynvml.nvmlInit()
            found = []
            for i in range(pynvml.nvmlDeviceGetCount()):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                found.append((
                    _text(pynvml.nvmlDeviceGetPciInfo(handle).busId),
                    handle,
                    _short_name(_text(pynvml.nvmlDeviceGetName(handle))),
                    pynvml.nvmlDeviceGetMemoryInfo(handle).total,
                ))
        except pynvml.NVMLError:
            self._retry_at = time.monotonic() + self.RETRY_S
            return
        # Diurutkan menurut slot PCI: nomor GPU tetap sama antar-boot, dan dua
        # kartu bertipe sama tetap bisa dibedakan dari posisi fisiknya.
        found.sort(key=lambda gpu: gpu[0])
        self._handles = [gpu[1] for gpu in found]
        self.gpus = [GpuInfo(i, f"gpu{i}", name, round(total / GIB, 1))
                     for i, (_bus, _handle, name, total) in enumerate(found)]

    @staticmethod
    def _query(fn, handle, *args):
        try:
            return fn(handle, *args)
        except pynvml.NVMLError:
            # Kipas dan daya memang tidak tersedia di sebagian GPU (mis. laptop).
            return None

    def _read_one(self, handle) -> dict:
        util = self._query(pynvml.nvmlDeviceGetUtilizationRates, handle)
        temp = self._query(pynvml.nvmlDeviceGetTemperature, handle,
                           pynvml.NVML_TEMPERATURE_GPU)
        mem = self._query(pynvml.nvmlDeviceGetMemoryInfo, handle)
        fan = self._query(pynvml.nvmlDeviceGetFanSpeed, handle)
        power = self._query(pynvml.nvmlDeviceGetPowerUsage, handle)
        out = dict.fromkeys(_GPU_FIELDS)
        if util is not None:
            out["load"] = float(util.gpu)
        if temp is not None:
            out["temp"] = float(temp)
        if mem is not None and mem.total:
            out["vram_used"] = round(mem.used / GIB, 1)
            out["vram_total"] = round(mem.total / GIB, 1)
            out["vram_pct"] = round(100.0 * mem.used / mem.total, 1)
        if fan is not None:
            out["fan"] = float(fan)
        if power is not None:
            out["power"] = round(power / 1000.0, 1)
        return out

    def read(self) -> list:
        """Satu dict per GPU, urutannya sama dengan self.gpus."""
        if not self._handles:
            self.open()
        readings = [self._read_one(handle) for handle in self._handles]
        if readings and all(r["load"] is None and r["temp"] is None
                            and r["vram_used"] is None for r in readings):
            # Driver sedang diperbarui atau GPU hilang: coba buka ulang nanti.
            self._handles = []
            self._retry_at = time.monotonic() + self.RETRY_S
        if not self._handles:
            return [dict.fromkeys(_GPU_FIELDS) for _ in self.gpus]
        return readings

    def close(self):
        if self._handles:
            try:
                pynvml.nvmlShutdown()
            except pynvml.NVMLError:
                pass
            self._handles = []


def _cpu_temp():
    read = getattr(psutil, "sensors_temperatures", None)  # tidak ada di Windows
    if read is None:
        return None
    try:
        temps = read()
    except OSError:
        return None
    for chip in _CPU_TEMP_CHIPS:
        if temps.get(chip):
            return round(temps[chip][0].current, 1)
    return None


def _known(values):
    return [v for v in values if v is not None]


class Sensors:
    """Metrik yang tersedia mengikuti hardware yang terdeteksi.

    Tiap GPU mendapat metrik `gpuN.*`. `gpu.*` adalah alias untuk GPU utama
    (`primary_gpu`), dan `gpus.*` adalah gabungan semua GPU bila ada lebih dari satu.
    """

    def __init__(self, primary_gpu: int = 0):
        self._primary = primary_gpu
        self._nvidia = _Nvidia()
        self._nvidia.open()
        psutil.cpu_percent(interval=None)  # panggilan pertama selalu 0.0

    @property
    def gpus(self) -> list:
        return list(self._nvidia.gpus)

    @property
    def gpu_summary(self):
        """Mis. "2× RTX 3060, RTX 2060"; None bila tidak ada GPU NVIDIA."""
        counts = collections.Counter(gpu.name for gpu in self._nvidia.gpus)
        return ", ".join(name if n == 1 else f"{n}× {name}"
                         for name, n in counts.items()) or None

    def _primary_gpu(self):
        gpus = self._nvidia.gpus
        if not gpus:
            return None
        return gpus[self._primary] if self._primary < len(gpus) else gpus[0]

    def metrics(self) -> dict:
        """Katalog metrik: nama -> MetricInfo."""
        ram_gb = math.ceil(psutil.virtual_memory().total / GIB)
        catalog = {
            "cpu.load": MetricInfo("Beban CPU", "%", 0, 100, 0),
            "cpu.temp": MetricInfo("Suhu CPU (hanya Linux)", "°C", 30, 100, 0),
            "ram.pct": MetricInfo("Pemakaian RAM", "%", 0, 100, 0),
            "ram.used": MetricInfo("RAM terpakai", " GB", 0, ram_gb, 1),
            "ram.total": MetricInfo("RAM total", " GB", 0, ram_gb, 1),
        }

        def add(prefix, who, vram_gb, hidden=False):
            for field, (label, unit, low, high, dec) in _GPU_FIELDS.items():
                catalog[f"{prefix}.{field}"] = MetricInfo(
                    f"{label} {who}", unit, low,
                    math.ceil(vram_gb) if high is None else high, dec, hidden)

        gpus = self._nvidia.gpus
        for gpu in gpus:
            add(gpu.prefix, f"GPU {gpu.index} ({gpu.name})", gpu.vram_gb)
        primary = self._primary_gpu()
        if primary is not None:
            add("gpu", f"GPU {primary.index}", primary.vram_gb, hidden=True)
        if len(gpus) > 1:
            total_gb = math.ceil(sum(gpu.vram_gb for gpu in gpus))
            catalog.update({
                "gpus.max_load": MetricInfo("Beban tertinggi semua GPU", "%", 0, 100, 0),
                "gpus.max_temp": MetricInfo("Suhu tertinggi semua GPU", "°C", 30, 95, 0),
                "gpus.vram_pct": MetricInfo("Pemakaian VRAM semua GPU", "%", 0, 100, 0),
                "gpus.vram_used": MetricInfo("VRAM terpakai semua GPU", " GB", 0, total_gb, 1),
                "gpus.vram_total": MetricInfo("VRAM total semua GPU", " GB", 0, total_gb, 1),
                "gpus.power": MetricInfo("Daya semua GPU", " W", 0, 300 * len(gpus), 0),
            })
        return catalog

    def read(self) -> dict:
        """Nilai terbaru semua metrik; None berarti tidak tersedia."""
        mem = psutil.virtual_memory()
        values = {
            "cpu.load": round(psutil.cpu_percent(interval=None), 1),
            "cpu.temp": _cpu_temp(),
            "ram.pct": round(mem.percent, 1),
            "ram.used": round((mem.total - mem.available) / GIB, 1),
            "ram.total": round(mem.total / GIB, 1),
        }

        readings = self._nvidia.read()
        gpus = self._nvidia.gpus
        for gpu, reading in zip(gpus, readings):
            values.update({f"{gpu.prefix}.{k}": v for k, v in reading.items()})
        primary = self._primary_gpu()
        if primary is not None:
            values.update({f"gpu.{k}": values[f"{primary.prefix}.{k}"]
                           for k in _GPU_FIELDS})

        if len(gpus) > 1:
            def column(field):
                return _known(r[field] for r in readings)
            used, total = column("vram_used"), column("vram_total")
            values.update({
                "gpus.max_load": max(column("load"), default=None),
                "gpus.max_temp": max(column("temp"), default=None),
                "gpus.vram_used": round(sum(used), 1) if used else None,
                "gpus.vram_total": round(sum(total), 1) if total else None,
                "gpus.vram_pct": (round(100.0 * sum(used) / sum(total), 1)
                                  if used and sum(total) else None),
                "gpus.power": round(sum(column("power")), 1) if column("power") else None,
            })
        return values

    def close(self):
        self._nvidia.close()
