// Penggambaran layout ke layar ST7789.
#pragma once

#include <Arduino.h>

void renderBegin();

// Kecerahan backlight 0..100 persen.
void renderSetBacklight(uint8_t percent);

// Layar pembuka: judul, subjudul, dan batang progres yang masih kosong.
void renderSplash(const char* title, const char* subtitle);

// Mengisi batang progres layar pembuka sampai 0..100 persen.
void renderSplashProgress(uint8_t percent);

// Menerapkan rotasi layout aktif lalu menggambar ulang satu halaman penuh.
void renderShowPage(uint8_t page);

uint8_t renderCurrentPage();

// Menggambar ulang hanya widget yang nilainya berubah.
void renderUpdate();
