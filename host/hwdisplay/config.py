"""Lokasi dan isi file pengaturan pengguna."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from . import layout as layout_model

DEFAULT_SETTINGS = {
    "port": None,       # None = cari Pico otomatis
    "interval": 1.0,    # detik antar pengiriman data
    "brightness": 80,   # persen
    "sleep_s": 60,      # layar padam setelah sekian detik tanpa data; 0 = tidak pernah
    "gpu_index": 0,
}


def config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = base / "hwdisplay"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_settings() -> dict:
    settings = dict(DEFAULT_SETTINGS)
    try:
        with open(config_dir() / "settings.json", encoding="utf-8") as handle:
            stored = json.load(handle)
        settings.update({k: v for k, v in stored.items() if k in settings})
    except (OSError, ValueError):
        pass
    return settings


def save_settings(settings: dict):
    with open(config_dir() / "settings.json", "w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=2)


def load_layout() -> dict:
    try:
        return layout_model.load(config_dir() / "layout.json")
    except (OSError, ValueError):
        return layout_model.default_layout()


def save_layout(layout: dict):
    layout_model.save(config_dir() / "layout.json", layout)
