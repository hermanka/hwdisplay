// Pengaturan hardware. Sesuaikan nomor pin (GPIO) dengan kabel Anda.
#pragma once

// Bus SPI yang dipakai: SPI (SPI0) atau SPI1. Pin SCK/MOSI harus cocok dengan busnya:
//   SPI0 -> SCK: GP2, GP6, GP18    MOSI: GP3, GP7, GP19    MISO: GP0, GP4, GP16, GP20
//   SPI1 -> SCK: GP10, GP14, GP26  MOSI: GP11, GP15, GP27  MISO: GP8, GP12, GP28
#define TFT_SPI SPI

// Bawaan untuk Waveshare RP2040-Zero dengan modul ST7789V 9 pin
// (OUT, CS-TF, CS, DC, RST, SDA, SCL, VCC, GND). CS-TF dan OUT tidak disambung.
#define PIN_TFT_SCK 2    // SCL / CLK
#define PIN_TFT_MOSI 3   // SDA / DIN
#define PIN_TFT_CS 7     // CS  (-1 bila pin CS modul ditanam ke GND)
#define PIN_TFT_DC 6     // DC / RS
#define PIN_TFT_RST 5    // RES / RST
#define PIN_TFT_BL -1    // BLK / BL (-1 bila modul tanpa pin backlight atau disambung ke 3V3)

// Display tidak mengirim data balik, jadi MISO tidak perlu disambung. Namun bus SPI
// tetap mengambil alih satu pin MISO: pilih pin yang kosong, jangan sama dengan CS/DC.
// Di RP2040-Zero jangan pakai GP16: itu LED RGB di papan.
#define PIN_TFT_MISO 4

#define TFT_SPI_HZ 40000000
#define TFT_SPI_MODE SPI_MODE0   // SPI_MODE3 untuk modul tanpa pin CS
#define TFT_INVERT_COLORS 0      // ubah ke 1 bila warna tampil terbalik (negatif)
#define TFT_BL_ACTIVE_HIGH 1     // 0 bila backlight menyala saat pin LOW

// Tombol opsional untuk ganti halaman (ke GND, pakai pull-up internal). -1 = tidak ada.
#define PIN_BUTTON -1

// Splash saat dinyalakan. Lama dan judulnya diatur dari editor di PC lalu disimpan di
// flash; nilai di bawah hanya dipakai selama belum pernah diatur dari editor.
#define SPLASH_DEFAULT_MS 1500           // 0 = tanpa splash
#define SPLASH_DEFAULT_TITLE "HWDisplay"

#define PANEL_W 240
#define PANEL_H 320
