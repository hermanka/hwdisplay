// Pengaturan hardware. Sesuaikan nomor pin (GPIO) dengan kabel Anda.
#pragma once

// Bus SPI yang dipakai: SPI (SPI0) atau SPI1. Pin SCK/MOSI harus cocok dengan busnya:
//   SPI0 -> SCK: GP2, GP6, GP18    MOSI: GP3, GP7, GP19    MISO: GP0, GP4, GP16, GP20
//   SPI1 -> SCK: GP10, GP14, GP26  MOSI: GP11, GP15, GP27  MISO: GP8, GP12, GP28
#define TFT_SPI SPI

#define PIN_TFT_SCK 18   // SCL / CLK
#define PIN_TFT_MOSI 19  // SDA / DIN
#define PIN_TFT_CS 17    // CS  (-1 bila pin CS modul ditanam ke GND)
#define PIN_TFT_DC 20    // DC / RS
#define PIN_TFT_RST 21   // RES / RST
#define PIN_TFT_BL 22    // BLK / BL (-1 bila backlight disambung langsung ke 3V3)

// Display tidak mengirim data balik, jadi MISO tidak perlu disambung. Namun bus SPI
// tetap mengambil alih satu pin MISO: pilih pin yang kosong, jangan sama dengan CS/DC.
#define PIN_TFT_MISO 16

#define TFT_SPI_HZ 40000000
#define TFT_SPI_MODE SPI_MODE0   // SPI_MODE3 untuk modul tanpa pin CS
#define TFT_INVERT_COLORS 0      // ubah ke 1 bila warna tampil terbalik (negatif)
#define TFT_BL_ACTIVE_HIGH 1     // 0 bila backlight menyala saat pin LOW

// Tombol opsional untuk ganti halaman (ke GND, pakai pull-up internal). -1 = tidak ada.
#define PIN_BUTTON -1

#define PANEL_W 240
#define PANEL_H 320
