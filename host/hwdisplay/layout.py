"""Model layout: halaman berisi widget. Format yang sama dikirim ke Pico."""

from __future__ import annotations

import json
import re

PANEL_W, PANEL_H = 240, 320  # ukuran asli panel (rotasi 0)
# Batas di bawah ini harus sama dengan firmware/hwdisplay/layout.h.
MAX_WIDGETS = 64
MAX_PAGES = 8
MAX_METRICS = 48             # metrik berbeda yang dipakai satu layout
MAX_GRAPHS = 12
TEXT_BYTES = 27
UNIT_BYTES = 7

WIDGET_TYPES = ("label", "value", "bar", "arc", "graph")
ALIGNS = ("left", "center", "right")

ROOT_DEFAULTS = {
    "rot": 1,
    "bg": "#000000",
    "fg": "#E6EAF0",
    "track": "#1E2530",
    "warn_color": "#FFB020",
    "crit_color": "#FF4D4D",
    "page_time": 8,
}

WIDGET_DEFAULTS = {
    "label": {"w": 100, "h": 24, "text": "Label", "font": 2,
              "color": "#8B95A5", "align": "left"},
    "value": {"w": 100, "h": 28, "metric": "cpu.load", "dec": 0, "unit": "%",
              "font": 3, "color": "#E6EAF0", "align": "right",
              "warn": None, "crit": None},
    "bar": {"w": 200, "h": 16, "metric": "cpu.load", "min": 0, "max": 100,
            "color": "#3DA9FC", "warn": None, "crit": None},
    "arc": {"w": 100, "h": 100, "metric": "cpu.load", "min": 0, "max": 100,
            "thick": 9, "dec": 0, "unit": "%", "font": 3, "text": "CPU",
            "color": "#3DA9FC", "warn": None, "crit": None},
    "graph": {"w": 200, "h": 70, "metric": "cpu.load", "min": 0, "max": 100,
              "color": "#3DA9FC"},
}

_INT_LIMITS = {
    "x": (-320, 320), "y": (-320, 320), "w": (4, 320), "h": (4, 320),
    "font": (1, 5), "dec": (0, 3), "thick": (2, 40),
}
_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def screen_size(rot: int) -> tuple:
    return (PANEL_H, PANEL_W) if rot % 2 else (PANEL_W, PANEL_H)


def _color(value, default):
    return value.upper() if isinstance(value, str) and _COLOR_RE.match(value) else default


def _number(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clip_bytes(text, limit):
    text = str(text)
    while len(text.encode("utf-8")) > limit:
        text = text[:-1]
    return text


def clean_widget(raw):
    kind = raw.get("type") if isinstance(raw, dict) else None
    if kind not in WIDGET_DEFAULTS:
        return None
    out = {"type": kind}
    for key, default in {"x": 0, "y": 0, **WIDGET_DEFAULTS[kind]}.items():
        value = raw.get(key, default)
        if key in _INT_LIMITS:
            low, high = _INT_LIMITS[key]
            value = int(min(high, max(low, _number(value, default))))
        elif key in ("min", "max"):
            value = _number(value, default)
        elif key in ("warn", "crit"):
            value = None if value in (None, "") else _number(value, None)
        elif key == "color":
            value = _color(value, default)
        elif key == "align":
            value = value if value in ALIGNS else default
        elif key == "text":
            value = _clip_bytes(value, TEXT_BYTES)
        elif key == "unit":
            value = _clip_bytes(value, UNIT_BYTES)
        else:  # metric
            value = str(value)
        out[key] = value
    return out


def normalize(raw) -> dict:
    """Rapikan layout dari sumber mana pun (file, GUI) menjadi bentuk yang valid."""
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    for key, default in ROOT_DEFAULTS.items():
        value = raw.get(key, default)
        if key == "rot":
            out[key] = int(_number(value, default)) % 4
        elif key == "page_time":
            out[key] = int(min(3600, max(0, _number(value, default))))
        else:
            out[key] = _color(value, default)

    pages = raw.get("pages")
    out["pages"] = []
    for page in (pages if isinstance(pages, list) else [])[:MAX_PAGES]:
        widgets = page.get("widgets", []) if isinstance(page, dict) else []
        cleaned = [w for w in map(clean_widget, widgets) if w]
        out["pages"].append({"widgets": cleaned})
    if not out["pages"]:
        out["pages"].append({"widgets": []})
    return out


def new_widget(kind: str) -> dict:
    return clean_widget({"type": kind})


def used_metrics(layout: dict) -> set:
    return {widget["metric"] for page in layout["pages"]
            for widget in page["widgets"] if widget.get("metric")}


def limit_error(layout: dict):
    """Pesan bila layout melebihi kapasitas firmware, atau None bila muat."""
    widgets = [w for page in layout["pages"] for w in page["widgets"]]
    graphs = sum(1 for w in widgets if w["type"] == "graph")
    for count, limit, what in (
            (len(layout["pages"]), MAX_PAGES, "halaman"),
            (len(widgets), MAX_WIDGETS, "widget"),
            (graphs, MAX_GRAPHS, "grafik"),
            (len(used_metrics(layout)), MAX_METRICS, "metrik berbeda")):
        if count > limit:
            return f"Pico hanya menampung {limit} {what}; layout ini butuh {count}."
    return None


def to_device(layout: dict) -> dict:
    """Bentuk yang dikirim ke Pico: tanpa ambang yang kosong."""
    out = normalize(layout)
    for page in out["pages"]:
        page["widgets"] = [
            {k: v for k, v in widget.items() if v is not None}
            for widget in page["widgets"]
        ]
    return out


def load(path) -> dict:
    with open(path, encoding="utf-8") as handle:
        return normalize(json.load(handle))


def save(path, layout: dict):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(normalize(layout), handle, indent=2, ensure_ascii=False)


GPU_GREEN, TEMP_ORANGE, VRAM_TEAL = "#76B900", "#FF8A3D", "#2DD4BF"


def _arc(x, metric, text, color, unit="%", low=0, high=100, warn=None, crit=None,
         y=8, size=100):
    return {"type": "arc", "x": x, "y": y, "w": size, "h": size, "metric": metric,
            "min": low, "max": high, "unit": unit, "text": text, "color": color,
            "warn": warn, "crit": crit, "font": 3 if size >= 90 else 2}


def _meter(y, text, value_metric, bar_metric, color):
    return [
        {"type": "label", "x": 8, "y": y, "w": 120, "h": 24, "text": text},
        {"type": "value", "x": 172, "y": y, "w": 140, "h": 24, "metric": value_metric,
         "dec": 1, "unit": " GB"},
        {"type": "bar", "x": 8, "y": y + 28, "w": 304, "h": 16, "metric": bar_metric,
         "color": color, "warn": 80, "crit": 92},
    ]


def _history(y, text, metric, color):
    return [
        {"type": "label", "x": 8, "y": y, "w": 150, "h": 24, "text": text,
         "font": 3, "color": color},
        {"type": "value", "x": 212, "y": y, "w": 100, "h": 24, "metric": metric},
        {"type": "graph", "x": 8, "y": y + 28, "w": 304, "h": 78, "metric": metric,
         "color": color},
    ]


def default_layout() -> dict:
    return normalize({
        "pages": [
            {"widgets": [
                _arc(6, "cpu.load", "CPU", "#3DA9FC", warn=75, crit=90),
                _arc(110, "gpu.load", "GPU", GPU_GREEN),
                _arc(214, "gpu.temp", "TEMP", TEMP_ORANGE, unit="°C", low=30, high=95,
                     warn=75, crit=85),
                *_meter(122, "RAM", "ram.used", "ram.pct", "#B78CFF"),
                *_meter(180, "VRAM", "gpu.vram_used", "gpu.vram_pct", VRAM_TEAL),
            ]},
            {"widgets": [
                *_history(6, "GPU", "gpu.load", GPU_GREEN),
                *_history(124, "CPU", "cpu.load", "#3DA9FC"),
            ]},
        ],
    })


# --- templat halaman GPU -------------------------------------------------
# `gpu` adalah sensors.GpuInfo (dipakai: index, prefix, name).

_SUMMARY_ROW_H = 78


def gpu_summary_pages(gpus, rot: int) -> list:
    """Satu baris per GPU: nama, suhu, beban, VRAM. Dipecah bila tidak muat sehalaman."""
    width, height = screen_size(rot)
    per_page = max(1, height // _SUMMARY_ROW_H)
    bar_w, value_x = width - 104, width - 88
    pages = []
    for start in range(0, len(gpus), per_page):
        widgets = []
        for row, gpu in enumerate(gpus[start:start + per_page]):
            y, p = row * _SUMMARY_ROW_H + 4, gpu.prefix
            widgets += [
                {"type": "label", "x": 8, "y": y, "w": bar_w, "h": 22,
                 "text": f"GPU {gpu.index} {gpu.name}"},
                {"type": "value", "x": value_x, "y": y, "w": 80, "h": 22,
                 "metric": f"{p}.temp", "unit": "°C", "warn": 75, "crit": 85},
                {"type": "bar", "x": 8, "y": y + 28, "w": bar_w, "h": 14,
                 "metric": f"{p}.load", "color": GPU_GREEN},
                {"type": "value", "x": value_x, "y": y + 24, "w": 80, "h": 22,
                 "metric": f"{p}.load", "font": 2},
                {"type": "bar", "x": 8, "y": y + 50, "w": bar_w, "h": 14,
                 "metric": f"{p}.vram_pct", "color": VRAM_TEAL, "warn": 80, "crit": 92},
                {"type": "value", "x": value_x, "y": y + 46, "w": 80, "h": 22,
                 "metric": f"{p}.vram_used", "dec": 1, "unit": " GB", "font": 2},
            ]
        pages.append({"widgets": [clean_widget(w) for w in widgets]})
    return pages


def gpu_detail_page(gpu, rot: int) -> dict:
    """Satu halaman penuh untuk satu GPU: tiga gauge, VRAM terpakai, grafik beban."""
    width, height = screen_size(rot)
    p = gpu.prefix
    size = min(100, (width - 20) // 3)
    gap = (width - 3 * size) // 4
    below = 32 + size + 6

    def arc(slot, field, text, color, **extra):
        return _arc(gap + slot * (size + gap), f"{p}.{field}", text, color,
                    y=32, size=size, **extra)

    widgets = [
        {"type": "label", "x": 8, "y": 4, "w": width - 16, "h": 24,
         "text": f"GPU {gpu.index} {gpu.name}", "font": 3, "color": GPU_GREEN},
        arc(0, "load", "LOAD", GPU_GREEN),
        arc(1, "temp", "TEMP", TEMP_ORANGE, unit="°C", low=30, high=95, warn=75, crit=85),
        arc(2, "vram_pct", "VRAM", VRAM_TEAL, warn=80, crit=92),
        {"type": "label", "x": 8, "y": below, "w": 90, "h": 22, "text": "VRAM"},
        {"type": "value", "x": width - 148, "y": below, "w": 140, "h": 22,
         "metric": f"{p}.vram_used", "dec": 1, "unit": " GB"},
        {"type": "graph", "x": 8, "y": below + 28, "w": width - 16,
         "h": max(20, height - below - 34), "metric": f"{p}.load", "color": GPU_GREEN},
    ]
    return {"widgets": [clean_widget(w) for w in widgets]}
