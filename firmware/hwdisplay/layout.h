// Model layout: daftar widget per halaman dan tabel nilai metrik.
#pragma once

#include <Arduino.h>
#include <ArduinoJson.h>

// Batas di bawah ini harus sama dengan host/hwdisplay/layout.py.
#define MAX_WIDGETS 64
#define MAX_PAGES 8
#define MAX_METRICS 48
#define MAX_GRAPHS 12
#define GRAPH_SAMPLES 160
#define GRAPH_EMPTY 255
#define METRIC_NAME_LEN 20
#define TEXT_LEN 28
#define UNIT_LEN 8

enum WidgetType : uint8_t { W_LABEL, W_VALUE, W_BAR, W_ARC, W_GRAPH };
enum Align : uint8_t { ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT };

struct Widget {
  WidgetType type;
  uint8_t page;
  int16_t x, y, w, h;
  uint8_t font;   // 1..5
  uint8_t align;
  uint8_t dec;
  uint8_t thick;
  int8_t metric;  // indeks ke Layout::metrics, -1 bila tidak ada
  int8_t graph;   // indeks ke Layout::history, -1 bila bukan grafik
  uint16_t color;
  float vmin, vmax;
  float warn, crit;  // NAN = ambang tidak dipakai
  char text[TEXT_LEN];
  char unit[UNIT_LEN];
  bool dirty;
};

struct Metric {
  char name[METRIC_NAME_LEN];
  float value;  // NAN = belum ada data
};

struct GraphHistory {
  uint8_t head;  // posisi tulis berikutnya
  uint8_t samples[GRAPH_SAMPLES];  // 0..254, GRAPH_EMPTY = kosong
};

struct Layout {
  uint8_t rotation;
  uint16_t bg, fg, track, warnColor, critColor;
  uint16_t pageTime;  // detik, 0 = tidak berganti otomatis
  uint8_t pageCount;
  uint8_t widgetCount;
  uint8_t metricCount;
  uint8_t graphCount;
  Widget widgets[MAX_WIDGETS];
  Metric metrics[MAX_METRICS];
  GraphHistory history[MAX_GRAPHS];
};

extern Layout layout;

// Mengganti layout aktif dari JSON. Bila gagal, layout lama tidak disentuh.
bool layoutLoad(JsonVariantConst root, const char** error);

// Memperbarui satu metrik dan menandai widget yang perlu digambar ulang.
void layoutSetMetric(const char* name, float value);

// Mengosongkan semua nilai (dipakai saat data dari PC berhenti datang).
void layoutClearMetrics();
