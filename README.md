# YouTube Auto-Clipper & Karaoke Subtitle Renderer Bot

Bot otomatis untuk mendownload video YouTube, menganalisis bagian paling menarik/viral (berdasarkan energi audio, dinamika suara, dan densitas obrolan), memotong klip (durasi 1-1.5 menit), mengubah layout menjadi vertikal (9:16) kualitas HD, dan menambahkan subtitle karaoke dengan highlight per kata secara otomatis menggunakan AI **faster-whisper large-v3**.

Bot ini dilengkapi dengan fitur **Resume Download** (jika koneksi terputus tidak akan mengulang download dari awal) dan **Clip Blacklist History** (tidak akan pernah memotong bagian video yang sama pada video yang sudah pernah dipotong sebelumnya).

---

## 📋 Persyaratan Sistem
Sebelum menjalankan bot, pastikan sistem Anda memenuhi persyaratan berikut:
1. **Python 3.10 atau versi di atasnya** (Pastikan centang opsi "Add Python to PATH" saat instalasi).
2. **Koneksi Internet** (Untuk download video & download model Whisper pertama kali).

---

## 🛠️ Cara Instalasi (Sangat Mudah)

Kami telah menyediakan script installer otomatis untuk Windows. Ikuti langkah mudah berikut:

### Langkah 1: Jalankan Installer Dependensi
Buka terminal/PowerShell di folder project ini, lalu jalankan perintah berikut:
```powershell
python install_deps.py
```
*Script ini akan otomatis menginstal seluruh package Python yang dibutuhkan seperti `faster-whisper`, `yt-dlp`, `opencv-python`, dan FFmpeg.*

### Langkah 2: Daftarkan Perintah Global 'clipyt'
Jalankan script berikut agar bot dapat dipanggil dari mana saja (directori mana saja) di komputer Anda:
```powershell
python register_cmd.py
```
*Setelah selesai, silakan close dan **buka kembali** terminal/CMD/PowerShell Anda.*

---

## 🚀 Cara Menjalankan Bot dari Mana Saja

Sekarang Anda bisa menjalankan bot dari folder mana saja hanya dengan mengetik perintah berikut di CMD/PowerShell baru:
```bash
clipyt
```

### 📁 Pemilihan Folder Penyimpanan (File Explorer GUI)
Setelah Anda memasukkan link YouTube, pilihan layout, durasi, dan jumlah clip, **File Explorer Windows** akan otomatis terbuka.
* Anda bisa memilih folder mana saja di komputer Anda (misalnya Desktop, Documents, Harddisk eksternal, dll) sebagai tempat penyimpanan hasil video clip final.

---

## 📁 Struktur Folder Output
* **`output/clip_history.json`**: Menyimpan riwayat detik video yang sudah pernah diclip untuk masing-masing URL agar tidak terjadi duplikasi klip di masa mendatang.
* **`temp/`**: Folder penyimpanan file download mentah (`full_merged.mp4`) untuk mendukung fitur resume. Jangan hapus folder ini jika proses download Anda sempat terputus dan ingin dilanjutkan.

---

## 🔧 Troubleshooting & Tips
* **Masalah Akurasi Subtitle**: Bot ini menggunakan AI tercanggih saat ini (`large-v3`) untuk transkripsi bahasa Indonesia dengan akurasi di atas 95%. Pertama kali dijalankan, komputer akan mendownload model AI tersebut (~3 GB). Proses ini membutuhkan waktu beberapa menit tergantung kecepatan internet Anda. Proses selanjutnya akan berjalan instan.
* **FP16 Warning**: Muncul peringatan `FP16 is not supported on CPU; using FP32 instead`? Peringatan ini normal bagi komputer yang menjalankan AI menggunakan CPU (tanpa NVIDIA GPU) dan tidak mempengaruhi jalannya program maupun kualitas video.
* **Audio Hilang/Mute**: Pastikan saat memutar video di PC Anda, volume player tidak dalam keadaan mute. File output diproduksi dengan format audio standar AAC stereo 192kbps.
