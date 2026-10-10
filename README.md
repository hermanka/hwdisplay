# HWDisplay

Monitor hardware PC (CPU, RAM, GPU NVIDIA) di layar TFT 2 inci ST7789V 240×320 yang
terpasang pada Raspberry Pi Pico (RP2040). Tampilan diatur dari PC lewat editor layout.

```
host/                       program PC (Python, Windows dan Linux)
firmware/hwdisplay/   sketch Arduino untuk Pico
```

PC mengirim layout sekali dan nilai sensor tiap detik lewat USB serial. Pico yang
menggambar, dan menyimpan layout di flash sehingga langsung tampil saat dinyalakan.

## 1. Kabel display

Nomor pin diatur di [firmware/hwdisplay/config.h](firmware/hwdisplay/config.h).
Bawaan:

| Pin display | Pico |
|---|---|
| VCC | 3V3(OUT) |
| GND | GND |
| SCL / CLK | GP18 |
| SDA / DIN | GP19 |
| CS | GP17 |
| DC | GP20 |
| RES / RST | GP21 |
| BLK / BL | GP22 |
| SDO / MISO (pin ke-9) | tidak disambung |

Bila kabel Anda berbeda, ubah `config.h`, bukan kabelnya. SCK dan MOSI harus memakai
pin yang sah untuk bus SPI yang dipilih; daftarnya ada di komentar `config.h`.

## 2. Firmware (Arduino IDE)

1. **File → Preferences → Additional boards manager URLs**, tambahkan
   `https://github.com/earlephilhower/arduino-pico/releases/download/global/package_rp2040_index.json`
2. **Boards Manager**: pasang **Raspberry Pi Pico/RP2040** oleh Earle F. Philhower.
   Jangan pakai "Arduino Mbed OS RP2040 Boards".
3. **Library Manager**: pasang **Adafruit ST7735 and ST7789 Library**,
   **Adafruit GFX Library**, dan **ArduinoJson** (versi 7).
4. Buka `firmware/hwdisplay/hwdisplay.ino`.
5. **Tools → Board**: Raspberry Pi Pico. **Tools → Flash Size**: `2MB (Sketch: 1MB, FS: 1MB)`.
   Tanpa bagian FS, layout tidak bisa disimpan di Pico.
6. Tahan tombol BOOTSEL saat mencolok Pico untuk upload pertama, lalu **Upload**.

Setelah upload, layar menampilkan layout bawaan dengan nilai `--` sampai program PC berjalan.

| Gejala | Perbaikan di `config.h` |
|---|---|
| Layar putih atau kosong | Periksa pin; untuk modul tanpa CS pakai `PIN_TFT_CS -1` dan `SPI_MODE3` |
| Warna negatif | `TFT_INVERT_COLORS 1` |
| Layar gelap | Periksa `PIN_TFT_BL` dan `TFT_BL_ACTIVE_HIGH` |

## 3. Program PC

Butuh Python 3.8 atau lebih baru. Pemasangan, sekali saja, dari folder proyek:

```
py -3 -m venv .venv             # Linux: python3 -m venv .venv
.venv\Scripts\activate          # Linux: source .venv/bin/activate
pip install -r host/requirements.txt
```

Di Windows pakai `py -3`, bukan `python`, bila `python` masih menunjuk ke Python 2.

Menjalankan, setiap kali:

```
.venv\Scripts\activate          # Linux: source .venv/bin/activate
cd host
python -m hwdisplay
```

Di Linux tambahkan `sudo apt install python3-tk` dan izin port serial:
`sudo usermod -aG dialout $USER`, lalu login ulang.

| Perintah | Fungsi |
|---|---|
| `python -m hwdisplay` | Editor layout dengan pratinjau |
| `python -m hwdisplay --headless` | Hanya mengirim data, tanpa jendela |
| `python -m hwdisplay --sensors` | Cetak pembacaan sensor |
| `python -m hwdisplay --ports` | Daftar port serial |
| `python -m hwdisplay --port COM5` | Pakai port tertentu |

Pico dicari otomatis dan disambung ulang bila dicabut-pasang.

### Pemakaian sehari-hari

Program PC harus berjalan setiap kali Pico dipakai. Pico hanya menyimpan layout;
nilai sensor dibaca program PC dan dikirim tiap detik.

Bila Pico dicolok tanpa program PC berjalan:

- Layout terakhir yang disimpan tampil, tetapi semua nilainya `--`.
- Setelah 60 detik tanpa data, lampu layar padam (atur di **Padam bila tanpa data**).
- Begitu program PC dijalankan, Pico ditemukan sendiri dan angka mulai muncul.
  Urutan mencolok dan menjalankan bebas.

### Menjalankan otomatis saat login

Supaya tidak perlu dijalankan manual, pasang mode `--headless` sebagai program startup.
Ganti path di bawah dengan lokasi folder proyek Anda.

**Windows**

1. Tekan `Win+R`, ketik `shell:startup`, Enter.
2. Buat shortcut baru di folder itu dengan target:
   ```
   D:\GitProject\maximus-display\.venv\Scripts\pythonw.exe -m hwdisplay --headless
   ```
3. Buka Properties shortcut tersebut, isi **Start in** dengan
   `D:\GitProject\maximus-display\host`.

`pythonw.exe` menjalankan program tanpa jendela terminal.

**Linux**

Tambahkan entri di "Startup Applications", atau file `.desktop` di
`~/.config/autostart`, dengan perintah:

```
sh -c 'cd /path/ke/hwdisplay/host && ../.venv/bin/python -m hwdisplay --headless'
```

Hanya satu program yang bisa memakai port serial Pico pada satu waktu. Tutup program
headless sebelum membuka editor, lalu jalankan lagi setelah selesai mengedit.

### Editor

- Klik widget pada pratinjau untuk memilih, seret untuk memindah, seret kotak di sudut
  kanan-bawah untuk mengubah ukuran. Tombol panah menggeser 1 piksel, Delete menghapus.
- Setiap perubahan langsung tampil di Pico. **Simpan ke Pico** menuliskannya ke flash
  supaya tetap dipakai saat program PC tidak berjalan.
- **Simpan sebagai…** dan **Buka…** mengekspor dan mengimpor layout sebagai file JSON.
- Widget sebaiknya tidak saling menimpa: tiap widget menggambar ulang seluruh kotaknya.

| Widget | Isi |
|---|---|
| Teks | Tulisan tetap |
| Nilai | Angka satu metrik beserta satuan |
| Bar | Batang horizontal, atau vertikal bila tinggi > lebar |
| Gauge | Busur 270° dengan angka di tengah dan keterangan di bawah |
| Grafik | Riwayat nilai, satu sampel per pengiriman data |

Ambang peringatan dan kritis mengganti warna widget saat nilai melewatinya.

### Halaman

Satu layout bisa berisi beberapa halaman; tombolnya ada di bawah pratinjau.

| Kontrol | Fungsi |
|---|---|
| ◀ ▶ | Pindah halaman di editor; Pico ikut menampilkan halaman itu |
| **+ Halaman** | Menambah halaman kosong di akhir |
| **Hapus halaman** | Menghapus halaman yang sedang dibuka beserta widgetnya |
| **Templat GPU** | Menambah halaman siap pakai untuk GPU (lihat [Menambah GPU](#menambah-gpu)) |
| **Ganti halaman tiap (dtk)**, di panel Tampilan | Jeda pergantian otomatis di Pico; `0` = tidak berganti |

Untuk tampilan satu halaman saja, hapus halaman lainnya, atau isi **Ganti halaman
tiap** dengan `0`. Saat dinyalakan Pico selalu mulai dari halaman 1, dan urutan halaman
tidak bisa diubah di editor.

Bila `PIN_BUTTON` di `config.h` diisi, tombol di pin itu memindah ke halaman berikutnya.

### Lokasi penyimpanan

| Tempat | File | Isi |
|---|---|---|
| PC | `layout.json` | Layout yang sedang diedit; disimpan otomatis tiap ada perubahan |
| PC | `settings.json` | Port, interval kirim, kecerahan, waktu padam, `gpu_index` |
| Pico (flash) | `/layout.json`, `/config.json` | Salinan yang dipakai saat program PC tidak berjalan; ditulis oleh **Simpan ke Pico** |

Folder di PC: `%APPDATA%\hwdisplay` (Windows) atau `~/.config/hwdisplay`
(Linux). Menghapus `layout.json` mengembalikan editor ke layout bawaan.

### Metrik

Daftar metrik mengikuti hardware yang terdeteksi saat program dimulai;
`python -m hwdisplay --sensors` menampilkan semuanya.

| Metrik | Isi |
|---|---|
| `cpu.load`, `cpu.temp` | Beban CPU; suhu CPU hanya di Linux |
| `ram.pct`, `ram.used`, `ram.total` | Pemakaian RAM |
| `gpuN.load`, `.temp`, `.vram_pct`, `.vram_used`, `.vram_total`, `.fan`, `.power` | Satu set per GPU NVIDIA: `gpu0`, `gpu1`, … |
| `gpu.*` | Alias GPU utama (`gpu_index` di `settings.json`, bawaan GPU 0) |
| `gpus.max_load`, `.max_temp`, `.vram_pct`, `.vram_used`, `.vram_total`, `.power` | Gabungan semua GPU, hanya bila ada lebih dari satu |

GPU dinomori menurut slot PCI, sehingga nomornya tetap sama antar-boot dan dua kartu
bertipe sama tetap bisa dibedakan. Kipas dan daya tidak tersedia di sebagian GPU.

### Menambah GPU

Setelah GPU baru terpasang, jalankan ulang program: metriknya langsung muncul di
dropdown **Metrik**. Menu **Templat GPU** di bawah pratinjau membuat halamannya:

- **Ringkasan semua GPU**: satu baris per GPU (suhu, beban, VRAM).
- **Detail GPU**: satu halaman penuh per GPU (tiga gauge dan grafik beban).

Layout tidak berubah sendiri saat hardware berganti. Widget milik GPU yang dicabut
menampilkan `--` sampai dihapus.

Satu layout menampung 8 halaman, 64 widget, 12 grafik, dan 48 metrik berbeda. Batas ini
ada di `firmware/hwdisplay/layout.h` dan `host/hwdisplay/layout.py`, dan
keduanya harus sama.

## Protokol

USB CDC serial, satu objek JSON per baris.

| Pesan dari PC | Jawaban Pico |
|---|---|
| `{"t":"hello"}` | `{"t":"hello","name":"hwdisplay","fw":…}` |
| `{"t":"layout","layout":{…},"page":0,"save":true}` | `{"t":"ok","for":"layout","saved":true}` |
| `{"t":"data","v":{"cpu.load":12.5,…}}` | tidak ada |
| `{"t":"config","brightness":80,"sleep_s":60}` | `{"t":"ok","for":"config",…}` |
| `{"t":"page","n":1}` | `{"t":"ok","for":"page",…}` |

Kegagalan dijawab `{"t":"err","for":…,"msg":…}`. Tanpa data selama 5 detik semua nilai
menjadi `--`; tanpa pesan selama `sleep_s` detik backlight dipadamkan.
