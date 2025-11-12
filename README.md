# 📚 PDDIKTI Search Bot - Dokumentasi

## 🤖 Deskripsi Bot
Bot Telegram untuk mencari data PDDIKTI (Pangkalan Data Pendidikan Tinggi) yang dapat mencari informasi mahasiswa, dosen, dan perguruan tinggi secara real-time.

## ✨ Fitur Utama

### 🔍 Pencarian Data
- **Pencarian Mahasiswa** (berdasarkan NIM atau nama)
- **Pencarian Dosen** (berdasarkan NIDN/NIDK atau nama)  
- **Pencarian Perguruan Tinggi** (berdasarkan nama PT)
- **Pencarian Semua** (kombinasi semua jenis data)

### 📊 Export Data
- Export hasil pencarian ke file Excel
- Multiple sheets (Mahasiswa, Dosen, Perguruan Tinggi)
- Format terstruktur dan rapi

### 🔔 Monitoring Perubahan
- Monitoring otomatis perubahan data
- Notifikasi ketika ada perubahan
- Management monitoring aktif
- Manual check perubahan

## 🚀 Cara Menggunakan

### 1. Memulai Bot
```
/start
```

### 2. Pilih Jenis Pencarian
- 🔍 Cari Semua
- 📚 Cari Mahasiswa  
- 👨‍🏫 Cari Dosen
- 🏛️ Cari Perguruan Tinggi

### 3. Kirim Keyword
Minimal 3 karakter, contoh:
- `23.83.1000` (NIM)
- `Ahmad` (Nama)
- `Universitas Indonesia` (PT)

### 4. Navigasi Hasil
Gunakan tombol:
- `⬅️ Prev` - Halaman sebelumnya
- `Next ➡️` - Halaman berikutnya
- `📊 Export Excel` - Download data
- `🔔 Monitoring` - Setup monitoring

## 📋 Daftar Perintah

| Perintah | Deskripsi |
|----------|-----------|
| `/start` | Memulai bot dan menu utama |
| `/help` | Panduan penggunaan bot |
| `/export` | Export data terakhir ke Excel |
| `/monitor` | Monitoring data terakhir |
| `/mylist` | Lihat list monitoring aktif |
| `/checknow` | Cek perubahan data manual |

## 🗃️ Fitur Monitoring

### Cara Setup Monitoring:
1. Lakukan pencarian terlebih dahulu
2. Klik tombol `🔔 Monitoring` 
3. Pilih `✅ Aktifkan Monitoring`
4. Bot akan mengecek perubahan setiap periode

### Management Monitoring:
- `📋 List Monitoring` - Lihat semua monitoring aktif
- `🚫 Stop Monitoring` - Hentikan monitoring
- `🔄 Cek Perubahan Sekarang` - Manual check

## 📁 Struktur Database

### Tabel `monitoring`
| Column | Type | Deskripsi |
|--------|------|-----------|
| id | INTEGER | Primary key |
| user_id | INTEGER | ID user Telegram |
| keyword | TEXT | Keyword pencarian |
| search_type | TEXT | Jenis pencarian |
| last_data_hash | TEXT | Hash data terakhir |
| last_check | TIMESTAMP | Waktu cek terakhir |
| is_active | BOOLEAN | Status aktif |
| created_at | TIMESTAMP | Waktu dibuat |

### Tabel `change_log`
| Column | Type | Deskripsi |
|--------|------|-----------|
| id | INTEGER | Primary key |
| monitoring_id | INTEGER | Foreign key ke monitoring |
| user_id | INTEGER | ID user Telegram |
| change_type | TEXT | Jenis perubahan |
| change_details | TEXT | Detail perubahan (JSON) |
| detected_at | TIMESTAMP | Waktu deteksi |

## 🔧 Teknologi yang Digunakan

- **Python 3.8+**
- **python-telegram-bot** - Framework Telegram Bot
- **Playwright** - Web scraping
- **Pandas** - Export Excel
- **SQLite** - Database monitoring
- **XlsxWriter** - Writer Excel files

## 📦 Instalasi Dependencies

```bash
pip3 install playwright pandas xlsxwriter
pip3 install "python-telegram-bot[job-queue]"
playwright install chromium
```

## 🎯 Contoh Penggunaan

### Pencarian Mahasiswa
```
User: /start
Bot: Tampilkan menu pencarian
User: Pilih "📚 Cari Mahasiswa"  
User: Kirim "23.83.1040"
Bot: Menampilkan data mahasiswa dengan NIM tersebut
```

### Export Data
```
User: Setelah pencarian, klik "📊 Export Excel"
Bot: Mengirim file Excel dengan data lengkap
```

### Monitoring Data  
```
User: Setelah pencarian, klik "🔔 Monitoring"
User: Pilih "✅ Aktifkan Monitoring"
Bot: Monitoring aktif, akan beri notifikasi jika data berubah
```

## ⚠️ Catatan Penting

1. **Data bersifat real-time** dari PDDIKTI
2. **Minimal keyword 3 karakter**
3. **Monitoring cek manual** dengan `/checknow`
4. **Data terisolasi per user** - aman dan privat
5. **Export data maksimal** 5 menit setelah pencarian

## 🔄 Flow Monitoring

```
Pencarian → Aktifkan Monitoring → Periodic Check → 
    ↓
  Data Berubah? → Ya → Simpan Log → Kirim Notifikasi
    ↓
  Tidak → Lanjutkan Monitoring
```

## 📞 Support

Jika mengalami masalah:
1. Pastikan koneksi internet stabil
2. Cek keyword minimal 3 karakter  
3. Gunakan perintah `/help` untuk panduan
4. Restart bot dengan `/start`

---

**🎓 PDDIKTI Search Bot** - Membantu pencarian data pendidikan tinggi Indonesia dengan mudah dan cepat!
