#include "render.h"

#include <math.h>
#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include <Fonts/FreeSans9pt7b.h>
#include <Fonts/FreeSansBold12pt7b.h>
#include <Fonts/FreeSansBold18pt7b.h>
#include <Fonts/FreeSansBold24pt7b.h>

#include "config.h"
#include "layout.h"

// Widget digambar dulu ke kanvas di RAM lalu disalin sekaligus supaya tidak berkedip.
// Widget yang lebih besar dari batas ini digambar langsung ke layar.
#define CANVAS_MAX_PIXELS 32000L

#define ARC_START_DEG 135.0f
#define ARC_SWEEP_DEG 270.0f
#define ARC_STEP_DEG 4.0f
#define GRAPH_STEP 2
#define SPLASH_BAR_H 6

static Adafruit_ST7789 tft(&TFT_SPI, PIN_TFT_CS, PIN_TFT_DC, PIN_TFT_RST);
static uint8_t currentPage = 0;

// --- teks ---------------------------------------------------------------

static const GFXfont* fontFor(uint8_t id) {
  switch (id) {
    case 2: return &FreeSans9pt7b;
    case 3: return &FreeSansBold12pt7b;
    case 4: return &FreeSansBold18pt7b;
    case 5: return &FreeSansBold24pt7b;
    default: return nullptr;  // font bawaan 6x8
  }
}

static int16_t capHeight(const GFXfont* f) {
  return f ? f->glyph['0' - f->first].height : 7;
}

static int16_t degreeSize(const GFXfont* f) {
  int16_t d = capHeight(f) / 3;
  return d < 3 ? 3 : d;
}

// Font GFX hanya berisi ASCII, jadi tanda derajat (UTF-8: C2 B0) digambar sendiri.
static bool isDegree(const uint8_t* p) {
  return p[0] == 0xC2 && p[1] == 0xB0;
}

static int16_t textWidth(const GFXfont* f, const char* s) {
  int16_t width = 0;
  for (const uint8_t* p = (const uint8_t*)s; *p; p++) {
    if (isDegree(p)) {
      width += degreeSize(f) + 2;
      p++;
    } else if (!f) {
      width += 6;
    } else if (*p >= f->first && *p <= f->last) {
      width += f->glyph[*p - f->first].xAdvance;
    }
  }
  return width;
}

static void drawText(Adafruit_GFX& g, const GFXfont* f, int16_t x, int16_t baseline,
                     const char* s, uint16_t color) {
  int16_t cap = capHeight(f);
  // Font bawaan memakai kursor di sudut kiri-atas, font GFX di garis dasar.
  int16_t cursorY = f ? baseline : baseline - cap;
  g.setFont(f);
  g.setTextSize(1);
  g.setTextWrap(false);
  g.setTextColor(color);
  g.setCursor(x, cursorY);
  for (const uint8_t* p = (const uint8_t*)s; *p; p++) {
    if (isDegree(p)) {
      int16_t d = degreeSize(f);
      int16_t cx = g.getCursorX() + d / 2;
      int16_t cy = baseline - cap + d / 2;
      g.drawCircle(cx, cy, d / 2, color);
      if (d >= 5) g.drawCircle(cx, cy, d / 2 - 1, color);
      g.setCursor(g.getCursorX() + d + 2, cursorY);
      p++;
    } else {
      g.write(*p);
    }
  }
}

static void drawTextBox(Adafruit_GFX& g, uint8_t fontId, int16_t x, int16_t y, int16_t w,
                        int16_t h, const char* s, uint16_t color, uint8_t align) {
  const GFXfont* f = fontFor(fontId);
  int16_t width = textWidth(f, s);
  if (align == ALIGN_CENTER) x += (w - width) / 2;
  else if (align == ALIGN_RIGHT) x += w - width;
  drawText(g, f, x, y + (h + capHeight(f)) / 2, s, color);
}

// --- nilai --------------------------------------------------------------

static uint16_t stateColor(const Widget& w, float v) {
  if (!isnan(v)) {
    if (!isnan(w.crit) && v >= w.crit) return layout.critColor;
    if (!isnan(w.warn) && v >= w.warn) return layout.warnColor;
  }
  return w.color;
}

static float fraction(const Widget& w, float v) {
  if (isnan(v) || w.vmax <= w.vmin) return 0;
  float f = (v - w.vmin) / (w.vmax - w.vmin);
  return f < 0 ? 0 : (f > 1 ? 1 : f);
}

static void formatValue(const Widget& w, float v, char* out, size_t size) {
  if (isnan(v)) strlcpy(out, "--", size);
  else snprintf(out, size, "%.*f%s", w.dec, (double)v, w.unit);
}

// Warna yang sama dengan kecerahan seperempatnya (RGB565).
static uint16_t dimColor(uint16_t c) {
  return (c >> 2) & 0x39E7;
}

// --- widget -------------------------------------------------------------

static void fillArc(Adafruit_GFX& g, int16_t cx, int16_t cy, int16_t outer, int16_t inner,
                    float fromDeg, float toDeg, uint16_t color) {
  float a = fromDeg;
  float c = cosf(a * DEG_TO_RAD), s = sinf(a * DEG_TO_RAD);
  int16_t ox0 = cx + lroundf(c * outer), oy0 = cy + lroundf(s * outer);
  int16_t ix0 = cx + lroundf(c * inner), iy0 = cy + lroundf(s * inner);
  while (a < toDeg) {
    a = min(a + ARC_STEP_DEG, toDeg);
    c = cosf(a * DEG_TO_RAD);
    s = sinf(a * DEG_TO_RAD);
    int16_t ox1 = cx + lroundf(c * outer), oy1 = cy + lroundf(s * outer);
    int16_t ix1 = cx + lroundf(c * inner), iy1 = cy + lroundf(s * inner);
    g.fillTriangle(ox0, oy0, ox1, oy1, ix0, iy0, color);
    g.fillTriangle(ix0, iy0, ox1, oy1, ix1, iy1, color);
    ox0 = ox1; oy0 = oy1; ix0 = ix1; iy0 = iy1;
  }
}

static void paintBar(Adafruit_GFX& g, const Widget& w, int16_t x, int16_t y, float v) {
  int16_t radius = min(3, min(w.w, w.h) / 2);
  g.fillRoundRect(x, y, w.w, w.h, radius, layout.track);
  float f = fraction(w, v);
  if (f <= 0) return;
  uint16_t color = stateColor(w, v);
  if (w.h > w.w) {  // vertikal: terisi dari bawah
    int16_t len = max((int16_t)lroundf(f * w.h), (int16_t)(2 * radius));
    g.fillRoundRect(x, y + w.h - len, w.w, len, radius, color);
  } else {
    int16_t len = max((int16_t)lroundf(f * w.w), (int16_t)(2 * radius));
    g.fillRoundRect(x, y, len, w.h, radius, color);
  }
}

static void paintArc(Adafruit_GFX& g, const Widget& w, int16_t x, int16_t y, float v) {
  int16_t cx = x + w.w / 2, cy = y + w.h / 2;
  int16_t outer = min(w.w, w.h) / 2 - 1;
  int16_t inner = max(outer - w.thick, 2);
  fillArc(g, cx, cy, outer, inner, ARC_START_DEG, ARC_START_DEG + ARC_SWEEP_DEG, layout.track);
  float f = fraction(w, v);
  if (f > 0) {
    fillArc(g, cx, cy, outer, inner, ARC_START_DEG, ARC_START_DEG + ARC_SWEEP_DEG * f,
            stateColor(w, v));
  }
  char buf[24];
  formatValue(w, v, buf, sizeof(buf));
  drawTextBox(g, w.font, x, y, w.w, w.h, buf, layout.fg, ALIGN_CENTER);
  // Keterangan ditaruh di celah bawah busur.
  if (w.text[0]) drawTextBox(g, 2, x, y + w.h - 16, w.w, 16, w.text, layout.fg, ALIGN_CENTER);
}

static void paintGraph(Adafruit_GFX& g, const Widget& w, int16_t x, int16_t y) {
  g.fillRect(x, y, w.w, w.h, layout.track);
  if (w.graph < 0) return;
  const GraphHistory& h = layout.history[w.graph];
  uint16_t fill = dimColor(w.color);
  int16_t count = min(w.w / GRAPH_STEP, GRAPH_SAMPLES);
  int16_t bottom = y + w.h - 1;
  int16_t prevX = 0, prevY = -1;
  for (int16_t age = 0; age < count; age++) {  // age 0 = sampel terbaru, di tepi kanan
    uint8_t sample = h.samples[(h.head + GRAPH_SAMPLES - 1 - age) % GRAPH_SAMPLES];
    if (sample == GRAPH_EMPTY) {
      prevY = -1;
      continue;
    }
    int16_t px = x + w.w - 1 - age * GRAPH_STEP;
    int16_t py = bottom - (int32_t)sample * (w.h - 1) / 254;
    g.fillRect(px - GRAPH_STEP + 1, py, GRAPH_STEP, bottom - py + 1, fill);
    if (prevY >= 0) g.drawLine(prevX, prevY, px, py, w.color);
    else g.drawPixel(px, py, w.color);
    prevX = px;
    prevY = py;
  }
}

static void paintWidget(Adafruit_GFX& g, const Widget& w, int16_t x, int16_t y) {
  float v = (w.metric >= 0) ? layout.metrics[w.metric].value : NAN;
  char buf[24];
  switch (w.type) {
    case W_LABEL:
      drawTextBox(g, w.font, x, y, w.w, w.h, w.text, w.color, w.align);
      break;
    case W_VALUE:
      formatValue(w, v, buf, sizeof(buf));
      drawTextBox(g, w.font, x, y, w.w, w.h, buf, stateColor(w, v), w.align);
      break;
    case W_BAR:
      paintBar(g, w, x, y, v);
      break;
    case W_ARC:
      paintArc(g, w, x, y, v);
      break;
    case W_GRAPH:
      paintGraph(g, w, x, y);
      break;
  }
}

static void drawWidget(Widget& w) {
  w.dirty = false;
  if ((int32_t)w.w * w.h <= CANVAS_MAX_PIXELS) {
    GFXcanvas16 canvas(w.w, w.h);
    if (canvas.getBuffer()) {
      canvas.fillScreen(layout.bg);
      paintWidget(canvas, w, 0, 0);
      tft.drawRGBBitmap(w.x, w.y, canvas.getBuffer(), w.w, w.h);
      return;
    }
  }
  tft.fillRect(w.x, w.y, w.w, w.h, layout.bg);
  paintWidget(tft, w, w.x, w.y);
}

// --- antarmuka ----------------------------------------------------------

void renderBegin() {
  TFT_SPI.setSCK(PIN_TFT_SCK);
  TFT_SPI.setTX(PIN_TFT_MOSI);
  TFT_SPI.setRX(PIN_TFT_MISO);
  tft.init(PANEL_W, PANEL_H, TFT_SPI_MODE);
  tft.setSPISpeed(TFT_SPI_HZ);
#if TFT_INVERT_COLORS
  tft.sendCommand(ST77XX_INVOFF);
#endif
  tft.fillScreen(0);
#if PIN_TFT_BL >= 0
  pinMode(PIN_TFT_BL, OUTPUT);
#endif
}

void renderSetBacklight(uint8_t percent) {
#if PIN_TFT_BL >= 0
  int duty = min((int)percent, 100) * 255 / 100;
  analogWrite(PIN_TFT_BL, TFT_BL_ACTIVE_HIGH ? duty : 255 - duty);
#else
  (void)percent;
#endif
}

static int16_t splashBarX, splashBarY, splashBarW, splashBarFill;

void renderSplash(const char* title, const char* subtitle) {
  tft.setRotation(layout.rotation);
  tft.fillScreen(layout.bg);
  int16_t w = tft.width();
  int16_t mid = tft.height() / 2;

  // Font terbesar yang masih muat selebar layar.
  uint8_t font = 5;
  while (font > 1 && textWidth(fontFor(font), title) > w - 16) font--;
  drawTextBox(tft, font, 0, mid - 50, w, 40, title, layout.fg, ALIGN_CENTER);
  drawTextBox(tft, 2, 0, mid, w, 20, subtitle, layout.fg, ALIGN_CENTER);

  splashBarW = w * 3 / 5;
  splashBarX = (w - splashBarW) / 2;
  splashBarY = mid + 40;
  splashBarFill = 0;
  tft.fillRect(splashBarX, splashBarY, splashBarW, SPLASH_BAR_H, layout.track);
}

void renderSplashProgress(uint8_t percent) {
  int16_t fill = (int32_t)splashBarW * min((int)percent, 100) / 100;
  if (fill <= splashBarFill) return;
  // Hanya bagian yang baru terisi yang digambar.
  tft.fillRect(splashBarX + splashBarFill, splashBarY, fill - splashBarFill,
               SPLASH_BAR_H, layout.fg);
  splashBarFill = fill;
}

void renderShowPage(uint8_t page) {
  currentPage = (page < layout.pageCount) ? page : 0;
  tft.setRotation(layout.rotation);
  tft.fillScreen(layout.bg);
  for (uint8_t i = 0; i < layout.widgetCount; i++) {
    if (layout.widgets[i].page == currentPage) drawWidget(layout.widgets[i]);
  }
}

uint8_t renderCurrentPage() {
  return currentPage;
}

void renderUpdate() {
  for (uint8_t i = 0; i < layout.widgetCount; i++) {
    Widget& w = layout.widgets[i];
    if (w.dirty && w.page == currentPage) drawWidget(w);
  }
}
