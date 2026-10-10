#include "layout.h"

#include <math.h>

Layout layout;

static uint16_t parseColor(JsonVariantConst v, uint16_t fallback) {
  const char* s = v.as<const char*>();
  if (!s || s[0] != '#' || strlen(s) != 7) return fallback;
  char* end;
  unsigned long rgb = strtoul(s + 1, &end, 16);
  if (*end) return fallback;
  return ((rgb >> 8) & 0xF800) | ((rgb >> 5) & 0x07E0) | ((rgb >> 3) & 0x001F);
}

static int16_t clampInt(long v, long low, long high) {
  return v < low ? low : (v > high ? high : v);
}

static int8_t metricIndex(const char* name, bool create) {
  if (!name || !name[0]) return -1;
  for (uint8_t i = 0; i < layout.metricCount; i++) {
    if (!strcmp(layout.metrics[i].name, name)) return i;
  }
  if (!create || layout.metricCount >= MAX_METRICS) return -1;
  Metric& m = layout.metrics[layout.metricCount];
  strlcpy(m.name, name, sizeof(m.name));
  m.value = NAN;
  return layout.metricCount++;
}

static bool parseWidget(JsonObjectConst j, Widget& w) {
  const char* type = j["type"] | "";
  if (!strcmp(type, "label")) w.type = W_LABEL;
  else if (!strcmp(type, "value")) w.type = W_VALUE;
  else if (!strcmp(type, "bar")) w.type = W_BAR;
  else if (!strcmp(type, "arc")) w.type = W_ARC;
  else if (!strcmp(type, "graph")) w.type = W_GRAPH;
  else return false;

  w.x = clampInt(j["x"] | 0, -320, 320);
  w.y = clampInt(j["y"] | 0, -320, 320);
  w.w = clampInt(j["w"] | 100, 4, 320);
  w.h = clampInt(j["h"] | 24, 4, 320);
  w.font = clampInt(j["font"] | 2, 1, 5);
  w.dec = clampInt(j["dec"] | 0, 0, 3);
  w.thick = clampInt(j["thick"] | 9, 2, 40);
  w.color = parseColor(j["color"], 0xFFFF);
  w.vmin = j["min"] | 0.0f;
  w.vmax = j["max"] | 100.0f;
  w.warn = j["warn"].is<float>() ? j["warn"].as<float>() : NAN;
  w.crit = j["crit"].is<float>() ? j["crit"].as<float>() : NAN;
  strlcpy(w.text, j["text"] | "", sizeof(w.text));
  strlcpy(w.unit, j["unit"] | "", sizeof(w.unit));

  const char* align = j["align"] | "left";
  w.align = !strcmp(align, "center") ? ALIGN_CENTER
            : !strcmp(align, "right") ? ALIGN_RIGHT : ALIGN_LEFT;

  w.metric = (w.type == W_LABEL) ? -1 : metricIndex(j["metric"] | "", true);
  w.graph = -1;
  if (w.type == W_GRAPH && layout.graphCount < MAX_GRAPHS) w.graph = layout.graphCount++;
  w.dirty = true;
  return true;
}

bool layoutLoad(JsonVariantConst root, const char** error) {
  JsonArrayConst pages = root["pages"].as<JsonArrayConst>();
  if (pages.isNull() || pages.size() == 0) {
    *error = "layout tidak punya halaman";
    return false;
  }

  // Nilai metrik dibawa ke layout baru supaya angka tidak sempat menjadi "--"
  // setiap kali layout dikirim ulang dari editor.
  static Metric previous[MAX_METRICS];
  uint8_t previousCount = layout.metricCount;
  memcpy(previous, layout.metrics, sizeof(previous));

  memset(&layout, 0, sizeof(layout));
  for (uint8_t i = 0; i < MAX_GRAPHS; i++) {
    memset(layout.history[i].samples, GRAPH_EMPTY, GRAPH_SAMPLES);
  }

  layout.rotation = (root["rot"] | 1) & 3;
  layout.bg = parseColor(root["bg"], 0x0000);
  layout.fg = parseColor(root["fg"], 0xE75E);
  layout.track = parseColor(root["track"], 0x1926);
  layout.warnColor = parseColor(root["warn_color"], 0xFD84);
  layout.critColor = parseColor(root["crit_color"], 0xFA69);
  layout.pageTime = clampInt(root["page_time"] | 0, 0, 3600);

  for (JsonVariantConst pageVar : pages) {
    if (layout.pageCount >= MAX_PAGES) break;
    JsonArrayConst widgets = pageVar["widgets"].as<JsonArrayConst>();
    for (JsonVariantConst widgetVar : widgets) {
      if (layout.widgetCount >= MAX_WIDGETS) break;
      Widget& w = layout.widgets[layout.widgetCount];
      if (!parseWidget(widgetVar.as<JsonObjectConst>(), w)) continue;
      w.page = layout.pageCount;
      layout.widgetCount++;
    }
    layout.pageCount++;
  }

  for (uint8_t i = 0; i < layout.metricCount; i++) {
    for (uint8_t k = 0; k < previousCount; k++) {
      if (!strcmp(layout.metrics[i].name, previous[k].name)) {
        layout.metrics[i].value = previous[k].value;
      }
    }
  }
  return true;
}

static bool sameValue(float a, float b) {
  return (isnan(a) && isnan(b)) || a == b;
}

static void pushSample(const Widget& w, float value) {
  if (w.graph < 0) return;
  GraphHistory& h = layout.history[w.graph];
  uint8_t sample = GRAPH_EMPTY;
  if (!isnan(value) && w.vmax > w.vmin) {
    float f = (value - w.vmin) / (w.vmax - w.vmin);
    f = f < 0 ? 0 : (f > 1 ? 1 : f);
    sample = (uint8_t)lroundf(f * 254.0f);
  }
  h.samples[h.head] = sample;
  h.head = (h.head + 1) % GRAPH_SAMPLES;
}

void layoutSetMetric(const char* name, float value) {
  int8_t index = metricIndex(name, false);
  if (index < 0) return;
  bool changed = !sameValue(layout.metrics[index].value, value);
  layout.metrics[index].value = value;
  for (uint8_t i = 0; i < layout.widgetCount; i++) {
    Widget& w = layout.widgets[i];
    if (w.metric != index) continue;
    if (w.type == W_GRAPH) {
      pushSample(w, value);
      w.dirty = true;
    } else if (changed) {
      w.dirty = true;
    }
  }
}

void layoutClearMetrics() {
  for (uint8_t i = 0; i < layout.metricCount; i++) layout.metrics[i].value = NAN;
  for (uint8_t i = 0; i < layout.widgetCount; i++) {
    if (layout.widgets[i].type != W_LABEL) layout.widgets[i].dirty = true;
  }
}
