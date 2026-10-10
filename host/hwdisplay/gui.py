"""Editor layout dengan pratinjau langsung (tkinter)."""

from __future__ import annotations

import collections
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

from . import config
from . import layout as lm

SCALE = 2          # pratinjau digambar 2x ukuran layar asli
HANDLE = 5         # ukuran pegangan resize, dalam piksel layar Pico
HISTORY = 160      # sama dengan GRAPH_SAMPLES di firmware
GRAPH_STEP = 2

# Tinggi font pratinjau yang mendekati font firmware (bawaan 6x8, FreeSans 9/12/18/24pt).
FONT_PX = {1: 8, 2: 18, 3: 24, 4: 36, 5: 48}
FONT_CHOICES = ["1 – mungil", "2 – kecil", "3 – sedang", "4 – besar", "5 – sangat besar"]
ROT_CHOICES = ["0 – potret", "1 – lanskap", "2 – potret terbalik", "3 – lanskap terbalik"]
TYPE_NAMES = {"label": "Teks", "value": "Nilai", "bar": "Bar",
              "arc": "Gauge", "graph": "Grafik"}

# kunci -> (label, jenis editor)
FIELDS = {
    "x": ("X", "int"), "y": ("Y", "int"), "w": ("Lebar", "int"), "h": ("Tinggi", "int"),
    "text": ("Teks", "str"), "metric": ("Metrik", "metric"),
    "min": ("Minimum", "float"), "max": ("Maksimum", "float"),
    "dec": ("Desimal", "int"), "unit": ("Satuan", "str"),
    "thick": ("Tebal", "int"), "font": ("Font", "font"),
    "color": ("Warna", "color"), "align": ("Rata", "align"),
    "warn": ("Ambang peringatan", "optfloat"), "crit": ("Ambang kritis", "optfloat"),
}


def format_value(value, dec, unit):
    return "--" if value is None else f"{value:.{dec}f}{unit}"


def state_color(widget, value, layout):
    if value is not None:
        if widget.get("crit") is not None and value >= widget["crit"]:
            return layout["crit_color"]
        if widget.get("warn") is not None and value >= widget["warn"]:
            return layout["warn_color"]
    return widget["color"]


def fraction(widget, value):
    span = widget["max"] - widget["min"]
    if value is None or span <= 0:
        return 0.0
    return min(1.0, max(0.0, (value - widget["min"]) / span))


def dim(color):
    r, g, b = (int(color[i:i + 2], 16) // 4 for i in (1, 3, 5))
    return f"#{r:02X}{g:02X}{b:02X}"


def text_on(color):
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return "#000000" if (r * 299 + g * 587 + b * 114) > 140000 else "#FFFFFF"


class App(tk.Tk):
    def __init__(self, service, settings, layout):
        super().__init__()
        self.title("HWDisplay")
        self.service = service
        self.settings = settings
        self.layout = layout
        self.page = 0
        self.sel = None
        self.values = {}
        self.history = collections.defaultdict(
            lambda: collections.deque(maxlen=HISTORY))
        self._drag = None
        self._geom_vars = {}
        self._jobs = {}
        self._seq = None

        self._build_ui()
        self._build_display_panel()
        self._refresh_page()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(200, self._tick)

    # --- susunan jendela ------------------------------------------------

    def _build_ui(self):
        top = ttk.Frame(self, padding=6)
        top.pack(fill="x")
        self.status = ttk.Label(top, text="Mencari Pico…")
        self.status.pack(side="left")
        for text, command in (("Reset default", self._reset),
                              ("Simpan sebagai…", self._export),
                              ("Buka…", self._import),
                              ("Simpan ke Pico", self._save_to_pico)):
            ttk.Button(top, text=text, command=command).pack(side="right", padx=2)

        body = ttk.Frame(self, padding=(6, 0, 6, 6))
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body)
        left.pack(side="left", anchor="n")
        self.canvas = tk.Canvas(left, highlightthickness=1,
                                highlightbackground="#555555", takefocus=True)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Delete>", lambda e: self._delete_widget())
        for key, delta in (("Left", (-1, 0)), ("Right", (1, 0)),
                           ("Up", (0, -1)), ("Down", (0, 1))):
            self.canvas.bind(f"<{key}>", lambda e, d=delta: self._nudge(*d))

        pages = ttk.Frame(left, padding=(0, 6))
        pages.pack(fill="x")
        ttk.Button(pages, text="◀", width=3,
                   command=lambda: self._go_page(self.page - 1)).pack(side="left")
        self.page_label = ttk.Label(pages, width=14, anchor="center")
        self.page_label.pack(side="left")
        ttk.Button(pages, text="▶", width=3,
                   command=lambda: self._go_page(self.page + 1)).pack(side="left")
        ttk.Button(pages, text="Hapus halaman",
                   command=self._delete_page).pack(side="right")
        ttk.Button(pages, text="+ Halaman", command=self._add_page).pack(side="right", padx=2)
        templates = ttk.Menubutton(pages, text="Templat GPU")
        # Menu diisi saat dibuka: daftar GPU mengikuti hardware yang terdeteksi.
        self.template_menu = tk.Menu(templates, tearoff=False,
                                     postcommand=self._fill_template_menu)
        templates["menu"] = self.template_menu
        templates.pack(side="right")

        right = ttk.Frame(body, padding=(8, 0, 0, 0))
        right.pack(side="left", fill="y", anchor="n")

        self.display_box = ttk.LabelFrame(right, text="Tampilan", padding=4)
        self.display_box.pack(fill="x")

        widget_box = ttk.LabelFrame(right, text="Widget di halaman ini", padding=4)
        widget_box.pack(fill="x", pady=6)
        self.listbox = tk.Listbox(widget_box, height=8, exportselection=False)
        self.listbox.pack(fill="x")
        self.listbox.bind("<<ListboxSelect>>", self._on_list_select)
        buttons = ttk.Frame(widget_box)
        buttons.pack(fill="x", pady=(4, 0))
        add = ttk.Menubutton(buttons, text="Tambah")
        menu = tk.Menu(add, tearoff=False)
        for kind in lm.WIDGET_TYPES:
            menu.add_command(label=TYPE_NAMES[kind],
                             command=lambda k=kind: self._add_widget(k))
        add["menu"] = menu
        add.pack(side="left")
        ttk.Button(buttons, text="Duplikat",
                   command=self._duplicate_widget).pack(side="left", padx=2)
        ttk.Button(buttons, text="Hapus", command=self._delete_widget).pack(side="left")

        self.prop_box = ttk.LabelFrame(right, text="Properti", padding=4)
        self.prop_box.pack(fill="x")

    def _editor(self, parent, row, label, kind, get, set_):
        """Satu baris label + editor. Mengembalikan StringVar bila editornya teks."""
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 6), pady=1)

        if kind == "color":
            def pick():
                chosen = colorchooser.askcolor(get(), parent=self)[1]
                if chosen:
                    set_(chosen.upper())
                    button.config(text=get(), bg=get(), fg=text_on(get()))
            button = tk.Button(parent, text=get(), bg=get(), fg=text_on(get()),
                               width=10, relief="groove", command=pick)
            button.grid(row=row, column=1, sticky="ew", pady=1)
            return None

        choices = {"font": FONT_CHOICES, "rot": ROT_CHOICES,
                   "align": list(lm.ALIGNS)}.get(kind)
        if kind == "metric":
            # Disusun tiap kali: daftar metrik mengikuti hardware yang terdeteksi.
            choices = [f"{key} – {info.label}"
                       for key, info in self.service.metrics().items() if not info.hidden]
        if choices:
            current = get()
            shown = next((c for c in choices
                          if c.split(" – ")[0] == str(current)), str(current))
            var = tk.StringVar(value=shown)
            box = ttk.Combobox(parent, textvariable=var, values=choices,
                               state="readonly", width=34)
            box.grid(row=row, column=1, sticky="ew", pady=1)

            def chosen(_event):
                key = var.get().split(" – ")[0]
                set_(int(key) if kind in ("font", "rot") else key)
            box.bind("<<ComboboxSelected>>", chosen)
            return None

        def show(value):
            if value is None:
                return ""
            if isinstance(value, float) and value.is_integer():
                return str(int(value))
            return str(value)

        var = tk.StringVar(value=show(get()))
        entry = ttk.Entry(parent, textvariable=var, width=26)
        entry.grid(row=row, column=1, sticky="ew", pady=1)

        def commit(_event=None):
            text = var.get()
            try:
                if kind == "int":
                    value = int(float(text))
                elif kind == "float":
                    value = float(text)
                elif kind == "optfloat":
                    value = float(text) if text.strip() else None
                else:
                    value = text
            except ValueError:
                var.set(show(get()))
                return
            if value != get():
                set_(value)
            if entry.winfo_exists():
                var.set(show(get()))
        entry.bind("<Return>", commit)
        entry.bind("<FocusOut>", commit)
        entry.commit = commit
        return var

    def _commit_focused(self):
        # Panel properti dibangun ulang saat pilihan berganti; tanpa ini, isian yang
        # masih diketik hilang karena FocusOut tidak sampai ke entry yang dihapus.
        try:
            commit = getattr(self.focus_get(), "commit", None)
        except KeyError:
            commit = None
        if commit:
            commit()

    def _build_display_panel(self):
        for child in self.display_box.winfo_children():
            child.destroy()

        def root_field(key):
            def set_(value):
                clean = lm.normalize({**self.layout, key: value, "pages": []})
                self.layout[key] = clean[key]
                if key == "rot":
                    self._resize_canvas()
                self._changed()
            return (lambda: self.layout[key]), set_

        def setting_field(key):
            def set_(value):
                self.settings[key] = max(0.2, value) if key == "interval" else max(0, value)
                self._push_config()
            return (lambda: self.settings[key]), set_

        rows = [
            ("Rotasi", "rot", root_field("rot")),
            ("Ganti halaman tiap (dtk)", "int", root_field("page_time")),
            ("Latar", "color", root_field("bg")),
            ("Teks gauge", "color", root_field("fg")),
            ("Trek bar/gauge", "color", root_field("track")),
            ("Warna peringatan", "color", root_field("warn_color")),
            ("Warna kritis", "color", root_field("crit_color")),
            ("Padam bila tanpa data (dtk)", "int", setting_field("sleep_s")),
            ("Interval kirim (dtk)", "float", setting_field("interval")),
        ]
        for row, (label, kind, (get, set_)) in enumerate(rows):
            self._editor(self.display_box, row, label, kind, get, set_)

        row = len(rows)
        ttk.Label(self.display_box, text="Kecerahan").grid(row=row, column=0, sticky="w")
        scale = ttk.Scale(self.display_box, from_=5, to=100,
                          command=self._on_brightness)
        scale.set(self.settings["brightness"])
        scale.grid(row=row, column=1, sticky="ew")
        self.display_box.columnconfigure(1, weight=1)
        self._resize_canvas()

    def _build_props(self):
        for child in self.prop_box.winfo_children():
            child.destroy()
        self._geom_vars = {}
        widget = self._selected()
        if widget is None:
            ttk.Label(self.prop_box, text="Klik widget pada pratinjau untuk mengedit.\n"
                      "Seret untuk memindah, seret sudut kanan-bawah\n"
                      "untuk mengubah ukuran.").grid()
            return

        def field(key):
            def set_(value):
                widget[key] = value
                info = self.service.metrics().get(value) if key == "metric" else None
                if info is not None:
                    for name in ("min", "max", "dec", "unit"):
                        if name in widget:
                            widget[name] = getattr(info, name)
                widget.update(lm.clean_widget(widget))
                self._changed()
                if key == "metric":
                    self._build_props()
            return (lambda: widget[key]), set_

        keys = ["x", "y", "w", "h"] + [k for k in lm.WIDGET_DEFAULTS[widget["type"]]
                                       if k not in ("w", "h")]
        for row, key in enumerate(keys):
            label, kind = FIELDS[key]
            var = self._editor(self.prop_box, row, label, kind, *field(key))
            if key in ("x", "y", "w", "h"):
                self._geom_vars[key] = var
        self.prop_box.columnconfigure(1, weight=1)

    # --- keadaan --------------------------------------------------------

    def _widgets(self):
        return self.layout["pages"][self.page]["widgets"]

    def _selected(self):
        widgets = self._widgets()
        if self.sel is None or self.sel >= len(widgets):
            return None
        return widgets[self.sel]

    def _debounce(self, name, delay_ms, func):
        if name in self._jobs:
            self.after_cancel(self._jobs[name])

        def run():
            self._jobs.pop(name, None)
            func()
        self._jobs[name] = self.after(delay_ms, run)

    def _changed(self):
        """Layout berubah: gambar ulang, kirim pratinjau ke Pico, simpan otomatis."""
        self._refresh_list()
        self._redraw()
        self._debounce("send", 300, self._push_layout)
        self._debounce("save", 1000, lambda: config.save_layout(self.layout))

    def _push_layout(self, save=False):
        self.service.set_layout(self.layout, page=self.page, save=save)

    def _push_config(self):
        self.service.set_config(self.settings["brightness"], self.settings["sleep_s"])
        self._debounce("settings", 1000, lambda: config.save_settings(self.settings))

    def _on_brightness(self, value):
        self.settings["brightness"] = int(float(value))
        self._debounce("config", 150, self._push_config)

    def _save_to_pico(self):
        if not self.service.snapshot()["connected"]:
            messagebox.showwarning("HWDisplay", "Pico belum terhubung.", parent=self)
            return
        self._push_layout(save=True)

    def _select(self, index):
        self.sel = index
        self.listbox.selection_clear(0, "end")
        if index is not None:
            self.listbox.selection_set(index)
            self.listbox.see(index)
        self._build_props()
        self._redraw()

    def _refresh_list(self):
        self.listbox.delete(0, "end")
        for widget in self._widgets():
            detail = widget.get("metric") or widget.get("text", "")
            self.listbox.insert("end", f"{TYPE_NAMES[widget['type']]}: {detail}")
        if self._selected() is not None:
            self.listbox.selection_set(self.sel)

    def _refresh_page(self):
        self.page = min(self.page, len(self.layout["pages"]) - 1)
        self.page_label.config(
            text=f"Halaman {self.page + 1} / {len(self.layout['pages'])}")
        self.sel = None
        self._refresh_list()
        self._build_props()
        self._redraw()

    def _resize_canvas(self):
        width, height = lm.screen_size(self.layout["rot"])
        self.canvas.config(width=width * SCALE, height=height * SCALE)

    # --- halaman dan widget ---------------------------------------------

    def _go_page(self, page):
        if 0 <= page < len(self.layout["pages"]):
            self.page = page
            self._refresh_page()
            self.service.set_page(page)

    def _add_pages(self, pages):
        """Tambahkan halaman di akhir layout, kecuali bila melebihi kapasitas Pico."""
        first = len(self.layout["pages"])
        self.layout["pages"].extend(pages)
        error = lm.limit_error(self.layout)
        if error:
            del self.layout["pages"][first:]
            messagebox.showinfo("HWDisplay", error, parent=self)
            return
        self.page = first
        self._refresh_page()
        self.service.set_page(first)
        self._changed()

    def _add_page(self):
        self._add_pages([{"widgets": []}])

    def _fill_template_menu(self):
        menu = self.template_menu
        menu.delete(0, "end")
        gpus = self.service.gpus()
        rot = self.layout["rot"]
        if not gpus:
            menu.add_command(label="GPU NVIDIA tidak terdeteksi", state="disabled")
            return
        menu.add_command(
            label="Ringkasan semua GPU",
            command=lambda: self._add_pages(lm.gpu_summary_pages(gpus, rot)))
        menu.add_command(
            label="Detail semua GPU (satu halaman per GPU)",
            command=lambda: self._add_pages([lm.gpu_detail_page(g, rot) for g in gpus]))
        menu.add_separator()
        for gpu in gpus:
            menu.add_command(
                label=f"Detail GPU {gpu.index} – {gpu.name} ({gpu.vram_gb:g} GB)",
                command=lambda g=gpu: self._add_pages([lm.gpu_detail_page(g, rot)]))

    def _delete_page(self):
        if len(self.layout["pages"]) <= 1:
            return
        if self._widgets() and not messagebox.askyesno(
                "HWDisplay", "Hapus halaman ini beserta widgetnya?", parent=self):
            return
        del self.layout["pages"][self.page]
        self._refresh_page()
        self._changed()

    def _insert_widget(self, widget):
        self._widgets().append(widget)
        error = lm.limit_error(self.layout)
        if error:
            self._widgets().pop()
            messagebox.showinfo("HWDisplay", error, parent=self)
            return
        self._changed()
        self._select(len(self._widgets()) - 1)

    def _add_widget(self, kind):
        widget = lm.new_widget(kind)
        width, height = lm.screen_size(self.layout["rot"])
        widget["x"] = max(0, (width - widget["w"]) // 2)
        widget["y"] = max(0, (height - widget["h"]) // 2)
        self._insert_widget(widget)

    def _duplicate_widget(self):
        widget = self._selected()
        if widget is not None:
            self._insert_widget({**widget, "x": widget["x"] + 8, "y": widget["y"] + 8})

    def _delete_widget(self):
        if self._selected() is not None:
            del self._widgets()[self.sel]
            self._select(None)
            self._changed()

    def _reset(self):
        if messagebox.askyesno("HWDisplay",
                               "Ganti layout sekarang dengan layout default?", parent=self):
            self._replace_layout(lm.default_layout())

    def _import(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("Layout JSON", "*.json")])
        if not path:
            return
        try:
            self._replace_layout(lm.load(path))
        except (OSError, ValueError) as exc:
            messagebox.showerror("HWDisplay", f"Gagal membuka layout:\n{exc}",
                                 parent=self)

    def _export(self):
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".json",
                                            filetypes=[("Layout JSON", "*.json")])
        if path:
            lm.save(path, self.layout)

    def _replace_layout(self, layout):
        self.layout.clear()
        self.layout.update(layout)
        self.page = 0
        self._build_display_panel()
        self._refresh_page()
        self._changed()

    # --- mouse dan keyboard ---------------------------------------------

    def _on_list_select(self, _event):
        picked = self.listbox.curselection()
        index = picked[0] if picked else None
        self._commit_focused()
        self._select(index)

    def _on_press(self, event):
        self._commit_focused()
        self.canvas.focus_set()
        px, py = event.x / SCALE, event.y / SCALE
        widget = self._selected()
        if widget is not None:
            right, bottom = widget["x"] + widget["w"], widget["y"] + widget["h"]
            if abs(px - right) <= HANDLE and abs(py - bottom) <= HANDLE:
                self._drag = ("size", px, py, widget["w"], widget["h"])
                return
        widgets = self._widgets()
        for index in range(len(widgets) - 1, -1, -1):
            w = widgets[index]
            if w["x"] <= px < w["x"] + w["w"] and w["y"] <= py < w["y"] + w["h"]:
                self._select(index)
                self._drag = ("move", px, py, w["x"], w["y"])
                return
        self._drag = None
        self._select(None)

    def _on_motion(self, event):
        widget = self._selected()
        if self._drag is None or widget is None:
            return
        mode, start_x, start_y, a, b = self._drag
        dx = round(event.x / SCALE - start_x)
        dy = round(event.y / SCALE - start_y)
        if mode == "move":
            self._set_geometry(widget, x=a + dx, y=b + dy)
        else:
            self._set_geometry(widget, w=max(4, a + dx), h=max(4, b + dy))

    def _on_release(self, _event):
        self._drag = None

    def _nudge(self, dx, dy):
        widget = self._selected()
        if widget is not None:
            self._set_geometry(widget, x=widget["x"] + dx, y=widget["y"] + dy)

    def _set_geometry(self, widget, **changes):
        if all(widget[key] == value for key, value in changes.items()):
            return
        widget.update(changes)
        for key, var in self._geom_vars.items():
            var.set(str(widget[key]))
        self._redraw()
        self._debounce("send", 300, self._push_layout)
        self._debounce("save", 1000, lambda: config.save_layout(self.layout))

    # --- pratinjau ------------------------------------------------------

    def _redraw(self):
        canvas = self.canvas
        canvas.delete("all")
        width, height = lm.screen_size(self.layout["rot"])
        canvas.create_rectangle(0, 0, width * SCALE, height * SCALE,
                                fill=self.layout["bg"], outline="")
        for widget in self._widgets():
            self._draw_widget(widget)
        widget = self._selected()
        if widget is not None:
            x0, y0 = widget["x"] * SCALE, widget["y"] * SCALE
            x1, y1 = x0 + widget["w"] * SCALE, y0 + widget["h"] * SCALE
            canvas.create_rectangle(x0, y0, x1, y1, outline="#FFFFFF", dash=(4, 3))
            canvas.create_rectangle(x1 - 5, y1 - 5, x1 + 5, y1 + 5,
                                    fill="#FFFFFF", outline="#000000")

    def _text(self, x, y, w, h, text, font_id, color, align):
        anchor, tx = {"left": ("w", x), "center": ("center", x + w / 2),
                      "right": ("e", x + w)}[align]
        family = "Courier" if font_id == 1 else "Helvetica"
        weight = "bold" if font_id >= 3 else "normal"
        self.canvas.create_text(tx, y + h / 2, text=text, fill=color, anchor=anchor,
                                font=(family, -FONT_PX[font_id] * SCALE, weight))

    def _draw_widget(self, widget):
        canvas = self.canvas
        x, y = widget["x"] * SCALE, widget["y"] * SCALE
        w, h = widget["w"] * SCALE, widget["h"] * SCALE
        kind = widget["type"]
        value = self.values.get(widget.get("metric"))
        color = state_color(widget, value, self.layout)
        track = self.layout["track"]

        if kind == "label":
            self._text(x, y, w, h, widget["text"], widget["font"], widget["color"],
                       widget["align"])
        elif kind == "value":
            self._text(x, y, w, h, format_value(value, widget["dec"], widget["unit"]),
                       widget["font"], color, widget["align"])
        elif kind == "bar":
            canvas.create_rectangle(x, y, x + w, y + h, fill=track, outline="")
            part = fraction(widget, value)
            if part > 0:
                if widget["h"] > widget["w"]:
                    canvas.create_rectangle(x, y + h * (1 - part), x + w, y + h,
                                            fill=color, outline="")
                else:
                    canvas.create_rectangle(x, y, x + w * part, y + h,
                                            fill=color, outline="")
        elif kind == "arc":
            thick = widget["thick"] * SCALE
            radius = min(w, h) / 2 - SCALE - thick / 2
            cx, cy = x + w / 2, y + h / 2
            box = (cx - radius, cy - radius, cx + radius, cy + radius)
            canvas.create_arc(box, start=225, extent=-270, style="arc",
                              width=thick, outline=track)
            part = fraction(widget, value)
            if part > 0:
                canvas.create_arc(box, start=225, extent=-270 * part, style="arc",
                                  width=thick, outline=color)
            self._text(x, y, w, h, format_value(value, widget["dec"], widget["unit"]),
                       widget["font"], self.layout["fg"], "center")
            if widget["text"]:
                self._text(x, y + h - 16 * SCALE, w, 16 * SCALE, widget["text"], 2,
                           self.layout["fg"], "center")
        elif kind == "graph":
            canvas.create_rectangle(x, y, x + w, y + h, fill=track, outline="")
            samples = list(self.history[widget["metric"]])[-(widget["w"] // GRAPH_STEP):]
            points = []
            for age, sample in enumerate(reversed(samples)):
                if sample is None:
                    continue
                px = x + w - SCALE - age * GRAPH_STEP * SCALE
                py = y + h - SCALE - fraction(widget, sample) * (h - SCALE)
                points.append((px, py))
            if len(points) >= 2:
                area = [(points[0][0], y + h)] + points + [(points[-1][0], y + h)]
                canvas.create_polygon(area, fill=dim(widget["color"]), outline="")
                canvas.create_line(points, fill=widget["color"], width=SCALE)

    # --- pembaruan berkala ----------------------------------------------

    def _tick(self):
        snap = self.service.snapshot()
        if snap["seq"] != self._seq:
            self._seq = snap["seq"]
            self.values = snap["values"]
            for key, value in self.values.items():
                self.history[key].append(value)
            self._redraw()

        if snap["connected"]:
            text = f"Terhubung: {snap['port']} (firmware {snap['info'].get('fw', '?')})"
        elif snap["busy"]:
            text = f"Port {snap['busy']} sedang dipakai program lain"
        else:
            text = "Mencari Pico…"
        if snap["headless"]:
            text += "   |   Mode headless masih berjalan, hentikan dulu"
        if snap["gpu_name"]:
            text += f"   |   GPU: {snap['gpu_name']}"
        if snap["error"]:
            text += f"   |   Galat: {snap['error']}"
        warn = snap["error"] or snap["busy"] or snap["headless"]
        self.status.config(text=text, foreground="#C0392B" if warn else "")
        self.after(200, self._tick)

    def _on_close(self):
        config.save_layout(self.layout)
        config.save_settings(self.settings)
        self.service.stop()
        self.destroy()


def run(service, settings, layout):
    App(service, settings, layout).mainloop()
