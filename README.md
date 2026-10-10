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
Bawaan untuk Waveshare RP2040-Zero dengan modul ST7789V 9 pin:

| Pin display | RP2040-Zero |
|---|---|
| VCC | 3V3(OUT) |
| GND | GND |
| SCL | GP2 |
| SDA | GP3 |
| RST | GP5 |
| DC | GP6 |
| CS | GP7 |
| CS-TF | tidak disambung |
| OUT | tidak disambung |

GP4 dipakai bus SPI sebagai MISO walau tidak disambung, jadi jangan dipakai untuk
keperluan lain.

Modul ini tidak punya pin backlight, sehingga `PIN_TFT_BL` diisi `-1` dan backlight
selalu menyala penuh. Akibatnya pengaturan **Kecerahan** dan **Padam bila tanpa data**
di editor tidak berpengaruh pada layar.

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
5. **Tools → Board**: Waveshare RP2040 Zero (atau Raspberry Pi Pico bila memakai Pico
   biasa). **Tools → Flash Size**: `2MB (Sketch: 1MB, FS: 1MB)`.
   Tanpa bagian FS, layout tidak bisa disimpan di Pico.
6. Tahan tombol BOOT saat mencolok papan untuk upload pertama, lalu **Upload**.

Setelah upload, layar menampilkan layout bawaan dengan nilai `--` sampai program PC berjalan.

| Gejala | Perbaikan di `config.h` |
|---|---|
| Layar putih atau kosong | Periksa pin; untuk modul tanpa CS pakai `PIN_TFT_CS -1` dan `SPI_MODE3` |
| Warna negatif | `TFT_INVERT_COLORS 1` |
| Layar gelap | Periksa `PIN_TFT_BL` dan `TFT_BL_ACTIVE_HIGH` (hanya modul dengan pin backlight) |

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
Program mulai saat Anda login, bukan saat komputer menyala. Ganti path di bawah dengan
lokasi folder proyek Anda.

**Windows**

1. Tekan `Win+R`, ketik `shell:startup`, Enter. Folder Startup terbuka.
2. Klik kanan di folder itu, pilih **New → Shortcut**, isi lokasinya dengan:
   ```
   D:\GitProject\hwdisplay\.venv\Scripts\pythonw.exe -m hwdisplay --headless
   ```
3. Beri nama, misalnya `HWDisplay`, lalu **Finish**.
4. Klik kanan shortcut itu, pilih **Properties**, isi **Start in** dengan
   `D:\GitProject\hwdisplay\host`.

`pythonw.exe` menjalankan program tanpa jendela terminal. **Start in** wajib diisi:
tanpa itu Python tidak menemukan modul `hwdisplay` dan program keluar tanpa pesan.

**Linux**

Buat file `~/.config/autostart/hwdisplay.desktop`:

```ini
[Desktop Entry]
Type=Application
Name=HWDisplay
Path=/home/NAMA/hwdisplay/host
Exec=/home/NAMA/hwdisplay/.venv/bin/python -m hwdisplay --headless
```

Baris `Path` berfungsi seperti **Start in** di Windows. Akun Anda harus sudah masuk
grup `dialout` (lihat di atas); tanpa itu program berjalan tetapi tidak bisa membuka
port Pico.

**Memeriksa**

- Logout, login lagi, lalu lihat apakah angka muncul di Pico dalam beberapa detik.
- Bila tidak muncul, jalankan perintah yang sama di terminal dengan `python` sebagai
  ganti `pythonw` supaya pesan galatnya terlihat.
- Untuk menonaktifkan autostart, hapus shortcut atau file `.desktop` tersebut.

### Menghentikan program headless

Program headless tidak punya jendela maupun ikon tray, jadi ia dihentikan dari luar.

| Cara menjalankan | Windows | Linux |
|---|---|---|
| Dari terminal | `Ctrl+C` | `Ctrl+C` |
| Di belakang layar | Task Manager → tab **Details** → `pythonw.exe` → **End task** | `pkill -f "hwdisplay --headless"` |

Di Windows biasanya ada dua proses `pythonw.exe` untuk satu program, karena virtualenv
memakai peluncur; akhiri keduanya. Bila ada program Python lain yang tidak boleh ikut
mati, pakai PowerShell:

```powershell
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" |
  Where-Object CommandLine -like '*hwdisplay*' |
  ForEach-Object { Stop-Process -Id $_.ProcessId }
```

Di Linux, tanpa terminal: buka **System Monitor**, cari proses `python` yang baris
perintahnya memuat `hwdisplay`, lalu **End**.

Menghentikan paksa aman: tidak ada file yang sedang ditulis dan port serial dilepas
sendiri. Di Pico nilai menjadi `--`, lalu layar padam setelah 60 detik.

### Mengubah layout saat headless berjalan

Hanya satu program yang boleh memakai port serial Pico pada satu waktu, jadi hentikan
program headless sebelum membuka editor:

1. Hentikan program headless (lihat di atas).
2. Buka editor, ubah layout, lalu klik **Simpan ke Pico**. Selama editor terbuka,
   editor yang mengirim data ke Pico.
3. Tutup editor, lalu jalankan headless lagi atau biarkan sampai login berikutnya.

Bila editor dibuka saat headless masih berjalan, baris status di kiri atas editor
berubah merah dan menampilkan salah satu atau kedua pesan berikut:

| Pesan | Artinya |
|---|---|
| `Mode headless masih berjalan, hentikan dulu` | Ada proses `hwdisplay --headless` lain |
| `Port COM3 sedang dipakai program lain` | Port Pico sedang dibuka program lain, headless atau bukan |

Pesan hilang sendiri sekitar 2 detik setelah penyebabnya dihentikan. Selama pesan itu
tampil:

- **Windows:** editor tidak tersambung dan perubahan layout tidak sampai ke Pico.
  Tidak ada yang rusak; editor tersambung sendiri setelah headless dihentikan.
- **Linux:** kedua program bisa membuka port bersamaan dan saling mengganggu: tampilan
  berganti-ganti dan muncul galat "Pico tidak menjawab". Pesan port tidak muncul di
  sini, hanya pesan mode headless.

Program headless membaca `layout.json` hanya saat mulai, jadi layout baru dipakai
setelah ia dijalankan ulang.

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

### Splash saat menyala

Saat Pico mendapat daya, layar menampilkan judul, versi firmware, dan batang progres
sebelum halaman 1 muncul. Pengaturannya ada di panel **Tampilan** (butuh firmware 0.2.0
atau lebih baru):

| Kontrol | Fungsi |
|---|---|
| **Splash saat menyala (dtk)** | Lama splash, 0–10 detik; `0` = tanpa splash |
| **Judul splash** | Tulisan besar di splash, paling banyak 24 huruf ASCII |
| **Tes splash** | Menampilkan splash sekarang juga, lalu kembali ke halaman semula |

Kedua nilai tersimpan otomatis di flash Pico begitu diubah, karena splash tampil
sebelum PC tersambung. Perubahannya terlihat saat Pico dinyalakan berikutnya, atau
langsung lewat **Tes splash**. Bila lamanya `0`, **Tes splash** tetap menampilkannya
selama 1,5 detik.

Splash memakai rotasi, warna latar, dan warna teks dari layout tersimpan. Selama
splash tampil Pico tetap menerima pesan dari PC.

### Lokasi penyimpanan

| Tempat | File | Isi |
|---|---|---|
| PC | `layout.json` | Layout yang sedang diedit; disimpan otomatis tiap ada perubahan |
| PC | `settings.json` | Port, interval kirim, kecerahan, waktu padam, `gpu_index`, lama dan judul splash |
| Pico (flash) | `/layout.json` | Salinan layout yang dipakai saat program PC tidak berjalan; ditulis oleh **Simpan ke Pico** |
| Pico (flash) | `/config.json` | Kecerahan, waktu padam, lama dan judul splash; ditulis otomatis saat diubah |

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

Pembanding tiap angka di alat bawaan sistem:

| Metrik | Windows | Linux |
|---|---|---|
| `cpu.load` | Sama dengan Task Manager (ikut menghitung kecepatan turbo) | Sama dengan `top` |
| `vram_used` | Sama dengan "Dedicated GPU memory" di Task Manager | Sama dengan `nvidia-smi` |
| `load` GPU | Sama dengan `nvidia-smi`; bisa sedikit lebih tinggi dari Task Manager, yang hanya menampilkan mesin GPU tersibuk | Sama dengan `nvidia-smi` |

Task Manager menampilkan GPU Intel bawaan dan GPU NVIDIA sebagai panel terpisah;
bandingkan dengan panel NVIDIA.

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
| `{"t":"config","brightness":80,"sleep_s":60,"splash_ms":1500,"splash_title":"HWDisplay"}` | `{"t":"ok","for":"config",…}` |
| `{"t":"page","n":1}` | `{"t":"ok","for":"page",…}` |
| `{"t":"splash"}` | `{"t":"ok","for":"splash",…}`, lalu splash tampil |

Kegagalan dijawab `{"t":"err","for":…,"msg":…}`. Tanpa data selama 5 detik semua nilai
menjadi `--`; tanpa pesan selama `sleep_s` detik backlight dipadamkan.
