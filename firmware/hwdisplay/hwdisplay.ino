// HWDisplay - firmware Raspberry Pi Pico (RP2040) + TFT ST7789V 240x320.
//
// Menerima layout dan data sensor dari PC lewat USB serial (satu pesan JSON per
// baris) lalu menggambarnya. Layout tersimpan di flash sehingga langsung tampil
// saat Pico dinyalakan.
//
// Board  : "Raspberry Pi Pico/RP2040" oleh Earle F. Philhower (arduino-pico)
// Tools  : Flash Size -> "2MB (Sketch: 1MB, FS: 1MB)"
// Library: Adafruit ST7735 and ST7789 Library, Adafruit GFX Library, ArduinoJson 7

#include <Arduino.h>
#include <ArduinoJson.h>
#include <LittleFS.h>

#include "config.h"
#include "default_layout.h"
#include "layout.h"
#include "render.h"

#ifdef ARDUINO_ARCH_MBED
#error "Pakai core 'Raspberry Pi Pico/RP2040' (Earle Philhower), bukan 'Arduino Mbed OS RP2040 Boards'."
#endif

#define FW_VERSION "0.2.0"
#define DEVICE_NAME "hwdisplay"
#define RX_LINE_MAX 16384
#define STALE_MS 5000  // tanpa data selama ini, semua nilai ditampilkan "--"
#define LAYOUT_PATH "/layout.json"
#define CONFIG_PATH "/config.json"

// Batas splash harus sama dengan host/hwdisplay/config.py.
#define SPLASH_MAX_MS 10000
#define SPLASH_TITLE_LEN 25  // 24 huruf + penutup
#define SPLASH_TEST_MS 1500  // lama uji splash bila splash dimatikan (0)

struct Settings {
  uint8_t brightness;  // persen
  uint16_t sleepS;     // layar padam setelah sekian detik tanpa pesan; 0 = tidak pernah
  uint16_t splashMs;   // lama splash saat dinyalakan; 0 = tanpa splash
  char splashTitle[SPLASH_TITLE_LEN];
};

static Settings settings = {80, 60, SPLASH_DEFAULT_MS, SPLASH_DEFAULT_TITLE};
static bool fsReady = false;

static bool splashActive = false;
static uint8_t splashPage = 0;  // halaman yang digambar setelah splash selesai
static uint32_t splashStartMs = 0;
static uint16_t splashDurationMs = 0;

static char lineBuf[RX_LINE_MAX];
static size_t lineLen = 0;
static bool lineOverflow = false;

static bool dataFresh = false;
static bool sleeping = false;
static uint32_t lastDataMs = 0;
static uint32_t lastActivityMs = 0;
static uint32_t pageSinceMs = 0;

// --- penyimpanan ---------------------------------------------------------

static bool loadJsonFile(const char* path, JsonDocument& doc) {
  if (!fsReady) return false;
  File f = LittleFS.open(path, "r");
  if (!f) return false;
  DeserializationError err = deserializeJson(doc, f);
  f.close();
  return !err;
}

static bool saveJsonFile(const char* path, JsonVariantConst value) {
  if (!fsReady) return false;
  String out;
  serializeJson(value, out);
  File f = LittleFS.open(path, "r");
  if (f) {
    // Isi yang sama tidak ditulis ulang supaya flash tidak cepat aus.
    String current = f.readString();
    f.close();
    if (current == out) return true;
  }
  f = LittleFS.open(path, "w");
  if (!f) return false;
  bool ok = f.print(out) == out.length();
  f.close();
  return ok;
}

static void saveSettings() {
  JsonDocument doc;
  doc["brightness"] = settings.brightness;
  doc["sleep_s"] = settings.sleepS;
  doc["splash_ms"] = settings.splashMs;
  doc["splash_title"] = settings.splashTitle;
  saveJsonFile(CONFIG_PATH, doc.as<JsonVariantConst>());
}

static void applySettings(JsonVariantConst v) {
  settings.brightness = constrain(v["brightness"] | (int)settings.brightness, 0, 100);
  settings.sleepS = constrain(v["sleep_s"] | (int)settings.sleepS, 0, 65535);
  settings.splashMs = constrain(v["splash_ms"] | (int)settings.splashMs, 0, SPLASH_MAX_MS);
  if (v["splash_title"].is<const char*>()) {
    strlcpy(settings.splashTitle, v["splash_title"].as<const char*>(),
            sizeof(settings.splashTitle));
  }
}

// --- halaman -------------------------------------------------------------

static void showPage(uint8_t page) {
  pageSinceMs = millis();
  if (splashActive) {
    splashPage = page;  // digambar setelah splash selesai
    return;
  }
  renderShowPage(page);
}

static void nextPage() {
  if (layout.pageCount > 1) showPage((renderCurrentPage() + 1) % layout.pageCount);
}

// --- splash --------------------------------------------------------------

// Splash tidak menahan program: pesan dari PC tetap dibaca selama ia tampil.
static void startSplash(uint8_t returnPage, uint16_t durationMs) {
  splashActive = true;
  splashPage = returnPage;
  splashStartMs = millis();
  splashDurationMs = durationMs;
  renderSplash(settings.splashTitle, "v" FW_VERSION);
}

static void updateSplash() {
  uint32_t elapsed = millis() - splashStartMs;
  if (elapsed < splashDurationMs) {
    renderSplashProgress(elapsed * 100 / splashDurationMs);
    return;
  }
  splashActive = false;
  showPage(splashPage);
}

// --- protokol ------------------------------------------------------------

static void sendJson(JsonDocument& doc) {
  serializeJson(doc, Serial);
  Serial.println();
}

static void replyOk(const char* kind, bool saved) {
  JsonDocument doc;
  doc["t"] = "ok";
  doc["for"] = kind;
  doc["saved"] = saved;
  sendJson(doc);
}

static void replyErr(const char* kind, const char* message) {
  JsonDocument doc;
  doc["t"] = "err";
  doc["for"] = kind;
  doc["msg"] = message;
  sendJson(doc);
}

static void handleHello() {
  JsonDocument doc;
  doc["t"] = "hello";
  doc["name"] = DEVICE_NAME;
  doc["fw"] = FW_VERSION;
  doc["panel_w"] = PANEL_W;
  doc["panel_h"] = PANEL_H;
  doc["rot"] = layout.rotation;
  doc["max_widgets"] = MAX_WIDGETS;
  doc["max_pages"] = MAX_PAGES;
  doc["max_line"] = RX_LINE_MAX;
  doc["fs"] = fsReady;
  doc["brightness"] = settings.brightness;
  doc["sleep_s"] = settings.sleepS;
  doc["splash_ms"] = settings.splashMs;
  doc["splash_title"] = settings.splashTitle;
  sendJson(doc);
}

static void handleLayout(JsonDocument& doc) {
  JsonVariantConst value = doc["layout"];
  const char* error = "";
  if (!layoutLoad(value, &error)) {
    replyErr("layout", error);
    return;
  }
  bool saved = false;
  if (doc["save"] | true) saved = saveJsonFile(LAYOUT_PATH, value);
  showPage(doc["page"] | (int)renderCurrentPage());
  replyOk("layout", saved);
}

static void handleData(JsonDocument& doc) {
  JsonObjectConst values = doc["v"].as<JsonObjectConst>();
  for (JsonPairConst kv : values) {
    float value = kv.value().is<float>() ? kv.value().as<float>() : NAN;
    layoutSetMetric(kv.key().c_str(), value);
  }
  dataFresh = true;
  lastDataMs = millis();
}

static void handleLine(const char* line) {
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, line);
  if (err) {
    replyErr("", err.c_str());
    return;
  }
  lastActivityMs = millis();
  const char* type = doc["t"] | "";

  if (!strcmp(type, "data")) {
    handleData(doc);
  } else if (!strcmp(type, "hello")) {
    handleHello();
  } else if (!strcmp(type, "layout")) {
    handleLayout(doc);
  } else if (!strcmp(type, "config")) {
    applySettings(doc.as<JsonVariantConst>());
    saveSettings();
    if (!sleeping) renderSetBacklight(settings.brightness);
    replyOk("config", fsReady);
  } else if (!strcmp(type, "page")) {
    int page = doc["n"] | 0;
    if (page >= 0 && page < layout.pageCount) showPage(page);
    replyOk("page", false);
  } else if (!strcmp(type, "splash")) {
    // Uji dari editor: tampilkan splash sekarang, lalu kembali ke halaman semula.
    replyOk("splash", false);
    startSplash(splashActive ? splashPage : renderCurrentPage(),
                settings.splashMs ? settings.splashMs : SPLASH_TEST_MS);
  } else {
    replyErr(type, "perintah tidak dikenal");
  }
}

static void readSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      if (lineOverflow) {
        replyErr("", "pesan terlalu panjang");
      } else if (lineLen > 0) {
        lineBuf[lineLen] = '\0';
        handleLine(lineBuf);
      }
      lineLen = 0;
      lineOverflow = false;
    } else if (c != '\r') {
      if (lineLen < RX_LINE_MAX - 1) lineBuf[lineLen++] = c;
      else lineOverflow = true;
    }
  }
}

// --- program utama -------------------------------------------------------

static void loadStartupLayout() {
  const char* error = "";
  {
    JsonDocument doc;
    if (loadJsonFile(LAYOUT_PATH, doc) && layoutLoad(doc.as<JsonVariantConst>(), &error)) {
      return;
    }
  }
  JsonDocument doc;
  deserializeJson(doc, DEFAULT_LAYOUT_JSON);
  layoutLoad(doc.as<JsonVariantConst>(), &error);
}

#if PIN_BUTTON >= 0
static void pollButton() {
  static bool wasDown = false;
  static uint32_t changedMs = 0;
  bool down = digitalRead(PIN_BUTTON) == LOW;
  if (down != wasDown && millis() - changedMs > 50) {
    wasDown = down;
    changedMs = millis();
    if (down) {
      lastActivityMs = millis();
      nextPage();
    }
  }
}
#endif

void setup() {
  Serial.begin(115200);
#if PIN_BUTTON >= 0
  pinMode(PIN_BUTTON, INPUT_PULLUP);
#endif

  fsReady = LittleFS.begin();
  {
    JsonDocument doc;
    if (loadJsonFile(CONFIG_PATH, doc)) applySettings(doc.as<JsonVariantConst>());
  }

  renderBegin();
  loadStartupLayout();  // sebelum splash, supaya rotasi dan warnanya ikut layout
  if (settings.splashMs > 0) startSplash(0, settings.splashMs);
  else showPage(0);
  renderSetBacklight(settings.brightness);
  lastActivityMs = millis();
}

void loop() {
  readSerial();
#if PIN_BUTTON >= 0
  pollButton();
#endif

  if (splashActive) {
    updateSplash();
    return;
  }

  uint32_t now = millis();

  if (dataFresh && now - lastDataMs > STALE_MS) {
    dataFresh = false;
    layoutClearMetrics();
  }

  bool shouldSleep = settings.sleepS > 0 && now - lastActivityMs > settings.sleepS * 1000UL;
  if (shouldSleep != sleeping) {
    sleeping = shouldSleep;
    renderSetBacklight(sleeping ? 0 : settings.brightness);
  }

  if (layout.pageCount > 1 && layout.pageTime > 0 &&
      now - pageSinceMs > layout.pageTime * 1000UL) {
    nextPage();
  }

  renderUpdate();
}
