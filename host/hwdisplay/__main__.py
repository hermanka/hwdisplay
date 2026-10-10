"""Titik masuk: `python -m hwdisplay`."""

from __future__ import annotations

import argparse
import time

from . import __version__, config
from .device import PICO_VID, available_ports
from .sensors import Sensors
from .service import Service


def print_ports():
    ports = available_ports()
    if not ports:
        print("Tidak ada port serial.")
    for port in ports:
        mark = "  <- Raspberry Pi" if port.vid == PICO_VID else ""
        print(f"{port.device}\t{port.description}{mark}")


def print_sensors(gpu_index):
    sensors = Sensors(gpu_index)
    time.sleep(0.5)  # beban CPU butuh dua pembacaan
    values = sensors.read()
    if not sensors.gpus:
        print("GPU NVIDIA tidak terdeteksi.")
    for gpu in sensors.gpus:
        print(f"{gpu.prefix}: {gpu.name} ({gpu.vram_gb:g} GB)")
    for key, info in sensors.metrics().items():
        if info.hidden:
            continue
        value = values.get(key)
        shown = "tidak tersedia" if value is None else f"{value:.{info.dec}f}{info.unit}"
        print(f"{key:18} {shown:>16}   {info.label}")
    sensors.close()


def run_headless(service):
    service.start()
    print("Berjalan tanpa jendela. Tekan Ctrl+C untuk berhenti.")
    last = None
    try:
        while True:
            snap = service.snapshot()
            state = (snap["port"], snap["error"])
            if state != last:
                last = state
                print(f"Terhubung ke {snap['port']}" if snap["connected"]
                      else "Mencari Pico…")
                if snap["error"]:
                    print(f"Galat: {snap['error']}")
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()
        service.join(timeout=3)


def main():
    parser = argparse.ArgumentParser(
        prog="hwdisplay",
        description="Menampilkan informasi hardware PC di layar Raspberry Pi Pico.")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--port", help="port serial Pico (default: cari otomatis)")
    parser.add_argument("--headless", action="store_true",
                        help="jalankan tanpa jendela editor")
    parser.add_argument("--ports", action="store_true", help="tampilkan port serial")
    parser.add_argument("--sensors", action="store_true",
                        help="tampilkan pembacaan sensor sekali lalu keluar")
    args = parser.parse_args()

    settings = config.load_settings()
    if args.port:
        settings["port"] = args.port

    if args.ports:
        print_ports()
        return
    if args.sensors:
        print_sensors(settings["gpu_index"])
        return

    layout = config.load_layout()
    service = Service(settings, layout)
    if args.headless:
        run_headless(service)
        return

    from . import gui  # tkinter hanya dibutuhkan untuk mode jendela
    service.start()
    gui.run(service, settings, layout)
    service.join(timeout=3)


if __name__ == "__main__":
    main()
