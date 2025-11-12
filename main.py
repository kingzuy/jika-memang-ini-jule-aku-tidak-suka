from playwright.sync_api import sync_playwright
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from datetime import datetime, timedelta
import asyncio
import pandas as pd
import io
import sqlite3
import hashlib
import json
from telegram import InputFile

# =================================
# KONFIGURASI BOT
# =================================
TELEGRAM_BOT_TOKEN = "8406243492:sebagainya"  # Ganti dengan token bot Anda

# =================================
# DATABASE SETUP
# =================================
def setup_database():
    """Setup database SQLite untuk monitoring"""
    conn = sqlite3.connect('pddikti_monitor.db', check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS monitoring (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            keyword TEXT,
            search_type TEXT,
            last_data_hash TEXT,
            last_check TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS change_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            monitoring_id INTEGER,
            change_type TEXT,
            change_details TEXT,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (monitoring_id) REFERENCES monitoring (id)
        )
    ''')

    conn.commit()
    return conn

# Inisialisasi database
db_connection = setup_database()

# =================================
# FUNGSI SCRAPING PDDIKTI
# =================================
def search_pddikti(keyword, tipe_pencarian="semua"):
    """Mencari data di PDDIKTI berdasarkan keyword dan tipe"""
    with sync_playwright() as playwright:
        with playwright.chromium.launch(headless=True) as browser:
            page = browser.new_page()

            # Set user agent agar tidak diblock
            page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })

            try:
                url = f"https://pddikti.kemdiktisaintek.go.id/search/{keyword}"
                print(f"🔍 Mencari: {keyword}")

                # Tunggu halaman load dan JavaScript selesai
                page.goto(url, wait_until='domcontentloaded', timeout=60000)

                # Tunggu lebih lama untuk JavaScript render
                print("⏳ Menunggu JavaScript render...")
                page.wait_for_timeout(5000)

                # Coba tunggu selector yang lebih spesifik
                try:
                    # Tunggu sampai ada tabel tbody dengan data
                    page.wait_for_selector("tbody tr", timeout=15000)
                    print("✅ Tabel ditemukan")
                except:
                    # Jika tidak ada, cek apakah ada pesan "tidak ada hasil"
                    print("⚠️ Tidak ditemukan tabel dengan data")
                    body_text = page.inner_text("body")
                    if "tidak ditemukan" in body_text.lower() or "tidak ada" in body_text.lower():
                        print("ℹ️ Tidak ada hasil pencarian")
                        return {
                            "keyword": keyword,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "mahasiswa": [],
                            "dosen": [],
                            "perguruan_tinggi": []
                        }

                # Tunggu tambahan untuk memastikan semua data ter-render
                page.wait_for_timeout(2000)

                hasil = {
                    "keyword": keyword,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "mahasiswa": [],
                    "dosen": [],
                    "perguruan_tinggi": []
                }

                # Ambil semua tabel yang ada
                tables = page.query_selector_all("table.table")  # Class spesifik PDDIKTI

                if not tables:
                    # Fallback ke selector umum
                    tables = page.query_selector_all("table")

                if not tables:
                    print("❌ Tidak ditemukan tabel")
                    return hasil

                print(f"✅ Ditemukan {len(tables)} tabel")

                # Identifikasi tabel berdasarkan header
                for idx, table in enumerate(tables):
                    print(f"📊 Memproses tabel {idx+1}...")

                    rows = table.query_selector_all("tr")
                    if not rows:
                        print(f"   ⚠️ Tabel {idx+1} tidak ada rows")
                        continue

                    # Ambil header dari thead atau tr pertama
                    thead = table.query_selector("thead")
                    if thead:
                        header_row = thead.query_selector("tr")
                        header_cells = header_row.query_selector_all("th") if header_row else []
                    else:
                        header_cells = rows[0].query_selector_all("th")

                    if not header_cells:
                        print(f"   ⚠️ Tabel {idx+1} tidak ada header")
                        continue

                    headers = [cell.inner_text().strip() for cell in header_cells]
                    print(f"   Headers: {headers}")

                    # Tentukan starting row untuk data
                    data_start_idx = 1 if not thead else 0

                    # TABEL MAHASISWA
                    if "NIM" in headers or "nim" in [h.lower() for h in headers]:
                        if tipe_pencarian in ["semua", "mahasiswa"]:
                            print(f"   ✅ Tabel Mahasiswa")
                            tbody = table.query_selector("tbody")
                            data_rows = tbody.query_selector_all("tr") if tbody else rows[data_start_idx:]

                            for row in data_rows:
                                cells = row.query_selector_all("td")
                                if len(cells) >= 4:
                                    data_mhs = {
                                        "nama": cells[0].inner_text().strip(),
                                        "nim": cells[1].inner_text().strip(),
                                        "perguruan_tinggi": cells[2].inner_text().strip(),
                                        "program_studi": cells[3].inner_text().strip()
                                    }
                                    hasil["mahasiswa"].append(data_mhs)
                                    print(f"      ✓ {data_mhs['nama']}")

                    # TABEL DOSEN
                    elif "NIDN" in headers or "NIDK" in headers or any("nidn" in h.lower() or "nidk" in h.lower() for h in headers):
                        if tipe_pencarian in ["semua", "dosen"]:
                            print(f"   ✅ Tabel Dosen")
                            tbody = table.query_selector("tbody")
                            data_rows = tbody.query_selector_all("tr") if tbody else rows[data_start_idx:]

                            for row in data_rows:
                                cells = row.query_selector_all("td")
                                if len(cells) >= 3:
                                    nidn_nidk = cells[1].inner_text().strip() if len(cells) > 1 else ""
                                    data_dosen = {
                                        "nama": cells[0].inner_text().strip(),
                                        "nidn_nidk": nidn_nidk,
                                        "perguruan_tinggi": cells[2].inner_text().strip() if len(cells) > 2 else ""
                                    }
                                    hasil["dosen"].append(data_dosen)
                                    print(f"      ✓ {data_dosen['nama']}")

                    # TABEL PERGURUAN TINGGI
                    elif any("pt" in h.lower() or "perguruan tinggi" in h.lower() or "nama pt" in h.lower() for h in headers):
                        if tipe_pencarian in ["semua", "perguruan_tinggi", "pt"]:
                            print(f"   ✅ Tabel Perguruan Tinggi")
                            tbody = table.query_selector("tbody")
                            data_rows = tbody.query_selector_all("tr") if tbody else rows[data_start_idx:]

                            for row in data_rows:
                                cells = row.query_selector_all("td")
                                if len(cells) >= 1:
                                    data_pt = {
                                        "nama": cells[0].inner_text().strip(),
                                        "npsn": cells[1].inner_text().strip() if len(cells) > 1 else "",
                                        "akreditasi": cells[2].inner_text().strip() if len(cells) > 2 else ""
                                    }
                                    hasil["perguruan_tinggi"].append(data_pt)
                                    print(f"      ✓ {data_pt['nama']}")

                return hasil

            except Exception as e:
                print(f"❌ Error: {str(e)}")
                return None

# =================================
# FITUR 1: EKSPOR DATA KE EXCEL
# =================================
def export_to_excel(hasil):
    """Ekspor hasil pencarian ke file Excel"""
    if not hasil:
        return None

    # Buat Excel writer
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Sheet Mahasiswa
        if hasil["mahasiswa"]:
            df_mhs = pd.DataFrame(hasil["mahasiswa"])
            df_mhs.to_excel(writer, sheet_name='Mahasiswa', index=False)

        # Sheet Dosen
        if hasil["dosen"]:
            df_dosen = pd.DataFrame(hasil["dosen"])
            df_dosen.to_excel(writer, sheet_name='Dosen', index=False)

        # Sheet Perguruan Tinggi
        if hasil["perguruan_tinggi"]:
            df_pt = pd.DataFrame(hasil["perguruan_tinggi"])
            df_pt.to_excel(writer, sheet_name='Perguruan_Tinggi', index=False)

    output.seek(0)
    return output

async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk export data ke Excel"""
    if 'last_result' not in context.user_data:
        await update.message.reply_text(
            "⚠️ Tidak ada data untuk di-export. Silakan lakukan pencarian terlebih dahulu."
        )
        return

    hasil = context.user_data['last_result']

    # Kirim pesan processing
    processing_msg = await update.message.reply_text("📊 Membuat file Excel...")

    try:
        # Ekspor ke Excel
        excel_file = export_to_excel(hasil)

        if excel_file:
            # Kirim file
            await update.message.reply_document(
                document=InputFile(
                    excel_file,
                    filename=f"pddikti_{hasil['keyword']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                ),
                caption=f"📄 Hasil pencarian: {hasil['keyword']}\n"
                       f"⏰ {hasil['timestamp']}\n"
                       f"📊 Total: {len(hasil['mahasiswa'])} mahasiswa, "
                       f"{len(hasil['dosen'])} dosen, "
                       f"{len(hasil['perguruan_tinggi'])} PT"
            )
            await processing_msg.delete()
        else:
            await processing_msg.edit_text("❌ Gagal membuat file Excel.")

    except Exception as e:
        await processing_msg.edit_text(f"❌ Error: {str(e)}")

# =================================
# FITUR 2: MONITORING PERUBAHAN DATA
# =================================
def create_data_hash(hasil):
    """Buat hash dari data untuk deteksi perubahan"""
    if not hasil:
        return None
    data_str = json.dumps(hasil, sort_keys=True, default=str)
    return hashlib.md5(data_str.encode()).hexdigest()

def add_monitoring(user_id, keyword, search_type, initial_data):
    """Tambahkan keyword ke monitoring"""
    data_hash = create_data_hash(initial_data)

    cursor = db_connection.cursor()
    cursor.execute('''
        INSERT INTO monitoring (user_id, keyword, search_type, last_data_hash, last_check)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, keyword, search_type, data_hash, datetime.now()))

    db_connection.commit()
    return cursor.lastrowid

def stop_monitoring(monitor_id, user_id):
    """Stop monitoring berdasarkan ID"""
    cursor = db_connection.cursor()
    cursor.execute('''
        UPDATE monitoring
        SET is_active = 0
        WHERE id = ? AND user_id = ?
    ''', (monitor_id, user_id))

    db_connection.commit()
    return cursor.rowcount > 0

def get_user_monitoring(user_id):
    """Ambil semua monitoring aktif user"""
    cursor = db_connection.cursor()
    cursor.execute('''
        SELECT id, keyword, search_type, last_check, created_at
        FROM monitoring
        WHERE user_id = ? AND is_active = 1
        ORDER BY last_check DESC
    ''', (user_id,))

    return cursor.fetchall()

async def check_monitoring_changes(context: ContextTypes.DEFAULT_TYPE):
    """Background task untuk cek perubahan data"""
    try:
        cursor = db_connection.cursor()
        cursor.execute('''
            SELECT m.id, m.user_id, m.keyword, m.search_type, m.last_data_hash
            FROM monitoring m
            WHERE m.is_active = 1
            AND m.last_check <= ?
        ''', (datetime.now() - timedelta(hours=1),))

        monitors = cursor.fetchall()

        for monitor in monitors:
            monitor_id, user_id, keyword, search_type, last_hash = monitor

            # Scrape data terbaru
            current_data = search_pddikti(keyword, search_type)
            if current_data:
                current_hash = create_data_hash(current_data)

                if current_hash != last_hash:
                    # Deteksi perubahan - simpan ke change_log
                    change_details = {
                        'type': 'data_updated',
                        'timestamp': datetime.now().isoformat(),
                        'total_mahasiswa': len(current_data['mahasiswa']),
                        'total_dosen': len(current_data['dosen']),
                        'total_pt': len(current_data['perguruan_tinggi'])
                    }

                    cursor.execute('''
                        INSERT INTO change_log (monitoring_id, change_type, change_details)
                        VALUES (?, ?, ?)
                    ''', (monitor_id, 'data_updated', json.dumps(change_details)))

                    # Update hash terbaru
                    cursor.execute('''
                        UPDATE monitoring
                        SET last_data_hash = ?, last_check = ?
                        WHERE id = ?
                    ''', (current_hash, datetime.now(), monitor_id))

                    db_connection.commit()

                    # Kirim notifikasi ke user
                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=f"🔔 *PERUBAHAN DATA DETECTED!*\n\n"
                                 f"Keyword: `{keyword}`\n"
                                 f"Tipe: {search_type}\n"
                                 f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                                 f"📊 Data terbaru:\n"
                                 f"• {len(current_data['mahasiswa'])} Mahasiswa\n"
                                 f"• {len(current_data['dosen'])} Dosen\n"
                                 f"• {len(current_data['perguruan_tinggi'])} PT\n\n"
                                 f"Gunakan /search untuk melihat detail data terbaru.",
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        print(f"Gagal kirim notifikasi ke user {user_id}: {e}")
    except Exception as e:
        print(f"Error dalam monitoring background task: {e}")

# =================================
# HANDLER UNTUK FITUR MONITORING
# =================================
async def monitor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk memonitoring perubahan data"""
    if 'last_result' not in context.user_data:
        await update.message.reply_text(
            "⚠️ Silakan lakukan pencarian terlebih dahulu sebelum setup monitoring."
        )
        return

    keyword = context.user_data['last_result']['keyword']
    user_id = update.effective_user.id
    search_type = context.user_data.get('tipe_pencarian', 'semua')

    # Cek apakah sudah ada monitoring aktif untuk keyword yang sama
    existing_monitors = get_user_monitoring(user_id)
    for monitor in existing_monitors:
        if monitor[1] == keyword and monitor[2] == search_type:
            await update.message.reply_text(
                f"⚠️ Monitoring untuk `{keyword}` ({search_type}) sudah aktif!\n"
                f"Gunakan /mylist untuk melihat semua monitoring aktif.",
                parse_mode='Markdown'
            )
            return

    # Tambah ke monitoring
    monitor_id = add_monitoring(
        user_id, keyword, search_type, context.user_data['last_result']
    )

    keyboard = [
        [InlineKeyboardButton("📋 List Monitoring", callback_data='list_monitor')],
        [InlineKeyboardButton("🚫 Stop Monitoring", callback_data=f'stop_monitor_{monitor_id}')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🔔 *MONITORING DIAKTIFKAN*\n\n"
        f"Keyword: `{keyword}`\n"
        f"Tipe: {search_type}\n"
        f"ID Monitoring: `{monitor_id}`\n\n"
        f"Sistem akan mengecek perubahan data setiap 1 jam dan mengirim notifikasi jika ada perubahan.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def mylist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk melihat list monitoring aktif"""
    user_id = update.effective_user.id

    monitors = get_user_monitoring(user_id)

    if not monitors:
        await update.message.reply_text("📭 Tidak ada monitoring aktif.")
        return

    message = "🔔 *MONITORING AKTIF*\n\n"
    keyboard = []

    for monitor in monitors:
        monitor_id, keyword, search_type, last_check, created_at = monitor
        message += f"• ID: `{monitor_id}`\n"
        message += f"  Keyword: `{keyword}`\n"
        message += f"  Tipe: {search_type}\n"
        message += f"  Dibuat: {created_at[:16]}\n"
        message += f"  Cek terakhir: {last_check[:16]}\n\n"

        keyboard.append([InlineKeyboardButton(
            f"🚫 Stop {monitor_id}: {keyword[:15]}...",
            callback_data=f'stop_monitor_{monitor_id}'
        )])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)

# =================================
# FUNGSI FORMAT HASIL DENGAN PAGINATION
# =================================
def format_hasil_paginated(hasil, page=1, per_page=5):
    """Format hasil pencarian dengan pagination untuk Telegram"""
    if not hasil:
        return "❌ Tidak ada hasil ditemukan", 1, False, False

    total = (len(hasil["mahasiswa"]) + len(hasil["dosen"]) +
             len(hasil["perguruan_tinggi"]))

    if total == 0:
        return "❌ Tidak ada data ditemukan untuk keyword: " + hasil['keyword'], 1, False, False

    pesan = f"🔍 *HASIL PENCARIAN*\n"
    pesan += f"Keyword: `{hasil['keyword']}`\n"
    pesan += f"Total: {total} data\n"
    pesan += f"{'='*40}\n\n"

    # Gabungkan semua data dengan tipe
    all_data = []

    for mhs in hasil["mahasiswa"]:
        all_data.append(("mahasiswa", mhs))

    for dsn in hasil["dosen"]:
        all_data.append(("dosen", dsn))

    for pt in hasil["perguruan_tinggi"]:
        all_data.append(("pt", pt))

    # Hitung pagination
    total_items = len(all_data)
    total_pages = (total_items + per_page - 1) // per_page

    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, total_items)

    # Ambil data untuk halaman ini
    page_data = all_data[start_idx:end_idx]

    for idx, (tipe, data) in enumerate(page_data, start=start_idx + 1):
        if tipe == "mahasiswa":
            pesan += f"📚 *{idx}. MAHASISWA*\n"
            pesan += f"Nama: *{data['nama']}*\n"
            pesan += f"NIM: `{data['nim']}`\n"
            pesan += f"PT: {data['perguruan_tinggi']}\n"
            pesan += f"Prodi: {data['program_studi']}\n\n"

        elif tipe == "dosen":
            pesan += f"👨‍🏫 *{idx}. DOSEN*\n"
            pesan += f"Nama: *{data['nama']}*\n"
            pesan += f"NIDN/NIDK: `{data['nidn_nidk']}`\n"
            pesan += f"PT: {data['perguruan_tinggi']}\n\n"

        elif tipe == "pt":
            pesan += f"🏛️ *{idx}. PERGURUAN TINGGI*\n"
            pesan += f"Nama: *{data['nama']}*\n"
            if data['npsn']:
                pesan += f"NPSN: `{data['npsn']}`\n"
            if data['akreditasi']:
                pesan += f"Akreditasi: {data['akreditasi']}\n"
            pesan += "\n"

    pesan += f"{'─'*40}\n"
    pesan += f"Halaman {page}/{total_pages} • Data {start_idx+1}-{end_idx} dari {total_items}"

    has_prev = page > 1
    has_next = page < total_pages

    return pesan, total_pages, has_prev, has_next

# =================================
# HANDLER TELEGRAM BOT (UTAMA)
# =================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /start"""
    keyboard = [
        [InlineKeyboardButton("🔍 Cari Semua", callback_data='type_semua')],
        [InlineKeyboardButton("📚 Cari Mahasiswa", callback_data='type_mahasiswa')],
        [InlineKeyboardButton("👨‍🏫 Cari Dosen", callback_data='type_dosen')],
        [InlineKeyboardButton("🏛️ Cari Perguruan Tinggi", callback_data='type_pt')],
        [InlineKeyboardButton("📊 Export Data", callback_data='export_data')],
        [InlineKeyboardButton("🔔 Monitoring", callback_data='monitor_info')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        "🎓 *Selamat Datang di PDDIKTI Search Bot!*\n\n"
        "Bot ini dapat membantu Anda mencari data:\n"
        "• Mahasiswa (NIM, Nama)\n"
        "• Dosen (NIDN/NIDK, Nama)\n"
        "• Perguruan Tinggi\n\n"
        "*Fitur Baru:*\n"
        "• 📊 Export data ke Excel\n"
        "• 🔔 Monitoring perubahan data\n\n"
        "Pilih jenis pencarian di bawah ini:"
    )

    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk button callback"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    # Handle pagination
    if query.data == 'page_prev':
        if 'last_result' in context.user_data and 'current_page' in context.user_data:
            context.user_data['current_page'] -= 1
            page = context.user_data['current_page']
            hasil = context.user_data['last_result']

            pesan, total_pages, has_prev, has_next = format_hasil_paginated(hasil, page=page)

            # Update keyboard
            keyboard = []
            nav_buttons = []

            if has_prev:
                nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data='page_prev'))

            if has_next:
                nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data='page_next'))

            if nav_buttons:
                keyboard.append(nav_buttons)

            keyboard.append([InlineKeyboardButton("🔄 Cari Lagi", callback_data='type_semua')])
            keyboard.append([InlineKeyboardButton("📊 Export Excel", callback_data='export_data')])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(pesan, parse_mode='Markdown', reply_markup=reply_markup)
        return

    elif query.data == 'page_next':
        if 'last_result' in context.user_data and 'current_page' in context.user_data:
            context.user_data['current_page'] += 1
            page = context.user_data['current_page']
            hasil = context.user_data['last_result']

            pesan, total_pages, has_prev, has_next = format_hasil_paginated(hasil, page=page)

            # Update keyboard
            keyboard = []
            nav_buttons = []

            if has_prev:
                nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data='page_prev'))

            if has_next:
                nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data='page_next'))

            if nav_buttons:
                keyboard.append(nav_buttons)

            keyboard.append([InlineKeyboardButton("🔄 Cari Lagi", callback_data='type_semua')])
            keyboard.append([InlineKeyboardButton("📊 Export Excel", callback_data='export_data')])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(pesan, parse_mode='Markdown', reply_markup=reply_markup)
        return

    # Handle stop monitoring
    elif query.data.startswith('stop_monitor_'):
        monitor_id = query.data.replace('stop_monitor_', '')

        if stop_monitoring(monitor_id, user_id):
            await query.edit_message_text(
                f"✅ Monitoring ID `{monitor_id}` berhasil dihentikan.",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                "❌ Gagal menghentikan monitoring. Pastikan ID benar."
            )
        return

    # Handle list monitor
    elif query.data == 'list_monitor':
        monitors = get_user_monitoring(user_id)

        if not monitors:
            await query.edit_message_text("📭 Tidak ada monitoring aktif.")
            return

        message = "🔔 *MONITORING AKTIF*\n\n"
        keyboard = []

        for monitor in monitors:
            monitor_id, keyword, search_type, last_check, created_at = monitor
            message += f"• ID: `{monitor_id}`\n"
            message += f"  Keyword: `{keyword}`\n"
            message += f"  Tipe: {search_type}\n"
            message += f"  Cek terakhir: {last_check[:16]}\n\n"

            keyboard.append([InlineKeyboardButton(
                f"🚫 Stop {monitor_id}: {keyword[:15]}...",
                callback_data=f'stop_monitor_{monitor_id}'
            )])

        keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data='back_to_main')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
        return

    # Handle export data
    elif query.data == 'export_data':
        if 'last_result' not in context.user_data:
            await query.edit_message_text(
                "⚠️ Tidak ada data untuk di-export. Silakan lakukan pencarian terlebih dahulu."
            )
            return

        await query.edit_message_text("📊 Membuat file Excel...")

        try:
            hasil = context.user_data['last_result']
            excel_file = export_to_excel(hasil)

            if excel_file:
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=InputFile(
                        excel_file,
                        filename=f"pddikti_{hasil['keyword']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                    ),
                    caption=f"📄 Hasil pencarian: {hasil['keyword']}\n"
                           f"⏰ {hasil['timestamp']}\n"
                           f"📊 Total: {len(hasil['mahasiswa'])} mahasiswa, "
                           f"{len(hasil['dosen'])} dosen, "
                           f"{len(hasil['perguruan_tinggi'])} PT"
                )
            else:
                await query.edit_message_text("❌ Gagal membuat file Excel.")

        except Exception as e:
            await query.edit_message_text(f"❌ Error: {str(e)}")
        return

    # Handle monitor info
    elif query.data == 'monitor_info':
        if 'last_result' not in context.user_data:
            await query.edit_message_text(
                "⚠️ Silakan lakukan pencarian terlebih dahulu sebelum setup monitoring."
            )
            return

        keyword = context.user_data['last_result']['keyword']
        search_type = context.user_data.get('tipe_pencarian', 'semua')

        keyboard = [
            [InlineKeyboardButton("✅ Aktifkan Monitoring", callback_data='activate_monitor')],
            [InlineKeyboardButton("📋 List Monitoring Saya", callback_data='list_monitor')],
            [InlineKeyboardButton("🔙 Kembali", callback_data='back_to_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"🔔 *FITUR MONITORING*\n\n"
            f"Dengan fitur ini, bot akan:\n"
            f"• Mengecek data setiap 1 jam\n"
            f"• Mengirim notifikasi otomatis\n"
            f"• Memberitahu jika ada perubahan\n\n"
            f"Data yang akan dimonitor:\n"
            f"Keyword: `{keyword}`\n"
            f"Tipe: {search_type}",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return

    # Handle activate monitor
    elif query.data == 'activate_monitor':
        if 'last_result' not in context.user_data:
            await query.edit_message_text("⚠️ Data tidak ditemukan.")
            return

        keyword = context.user_data['last_result']['keyword']
        user_id = query.from_user.id
        search_type = context.user_data.get('tipe_pencarian', 'semua')

        # Cek duplikat
        existing_monitors = get_user_monitoring(user_id)
        for monitor in existing_monitors:
            if monitor[1] == keyword and monitor[2] == search_type:
                await query.edit_message_text(
                    f"⚠️ Monitoring untuk `{keyword}` ({search_type}) sudah aktif!",
                    parse_mode='Markdown'
                )
                return

        # Tambah ke monitoring
        monitor_id = add_monitoring(
            user_id, keyword, search_type, context.user_data['last_result']
        )

        keyboard = [
            [InlineKeyboardButton("📋 List Monitoring", callback_data='list_monitor')],
            [InlineKeyboardButton("🚫 Stop Monitoring", callback_data=f'stop_monitor_{monitor_id}')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"🔔 *MONITORING DIAKTIFKAN*\n\n"
            f"Keyword: `{keyword}`\n"
            f"Tipe: {search_type}\n"
            f"ID Monitoring: `{monitor_id}`\n\n"
            f"Sistem akan mengecek perubahan data setiap 1 jam.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return

    # Handle back to main
    elif query.data == 'back_to_main':
        keyboard = [
            [InlineKeyboardButton("🔍 Cari Semua", callback_data='type_semua')],
            [InlineKeyboardButton("📚 Cari Mahasiswa", callback_data='type_mahasiswa')],
            [InlineKeyboardButton("👨‍🏫 Cari Dosen", callback_data='type_dosen')],
            [InlineKeyboardButton("🏛️ Cari Perguruan Tinggi", callback_data='type_pt')],
            [InlineKeyboardButton("📊 Export Data", callback_data='export_data')],
            [InlineKeyboardButton("🔔 Monitoring", callback_data='monitor_info')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        welcome_text = (
            "🎓 *Selamat Datang di PDDIKTI Search Bot!*\n\n"
            "Pilih jenis pencarian di bawah ini:"
        )

        await query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
        return

    # Handle tipe pencarian
    tipe_map = {
        'type_semua': 'semua',
        'type_mahasiswa': 'mahasiswa',
        'type_dosen': 'dosen',
        'type_pt': 'perguruan_tinggi'
    }

    tipe_pencarian = tipe_map.get(query.data)

    if tipe_pencarian:
        # Reset context
        context.user_data.clear()
        context.user_data['tipe_pencarian'] = tipe_pencarian

        tipe_text = {
            'semua': 'Semua (Mahasiswa, Dosen, PT)',
            'mahasiswa': 'Mahasiswa',
            'dosen': 'Dosen',
            'perguruan_tinggi': 'Perguruan Tinggi'
        }

        await query.edit_message_text(
            f"✅ Tipe pencarian: *{tipe_text[tipe_pencarian]}*\n\n"
            f"Silakan kirim keyword pencarian (min. 3 karakter)\n"
            f"Contoh: `1123111.11`, `Admin`, atau nama PT",
            parse_mode='Markdown'
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk pesan teks (keyword pencarian)"""
    if 'tipe_pencarian' not in context.user_data:
        await update.message.reply_text(
            "⚠️ Silakan pilih jenis pencarian terlebih dahulu dengan command /start"
        )
        return

    keyword = update.message.text.strip()

    # Validasi minimal 3 karakter
    if len(keyword) < 3:
        await update.message.reply_text(
            "⚠️ Keyword minimal 3 karakter!"
        )
        return

    tipe_pencarian = context.user_data['tipe_pencarian']

    # Kirim pesan loading
    loading_msg = await update.message.reply_text("🔍 Mencari data... Mohon tunggu...")

    try:
        # Jalankan scraping dalam thread executor untuk async
        loop = asyncio.get_event_loop()
        hasil = await loop.run_in_executor(None, search_pddikti, keyword, tipe_pencarian)

        if hasil:
            # Simpan hasil ke context untuk pagination
            context.user_data['last_result'] = hasil
            context.user_data['current_page'] = 1

            # Format hasil halaman pertama
            pesan, total_pages, has_prev, has_next = format_hasil_paginated(hasil, page=1)

            # Hapus pesan loading
            await loading_msg.delete()

            # Buat keyboard pagination
            keyboard = []
            nav_buttons = []

            if has_prev:
                nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data='page_prev'))

            if has_next:
                nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data='page_next'))

            if nav_buttons:
                keyboard.append(nav_buttons)

            keyboard.append([InlineKeyboardButton("🔄 Cari Lagi", callback_data='type_semua')])
            keyboard.append([InlineKeyboardButton("📊 Export Excel", callback_data='export_data')])
            keyboard.append([InlineKeyboardButton("🔔 Monitoring", callback_data='monitor_info')])

            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(pesan, parse_mode='Markdown', reply_markup=reply_markup)
        else:
            await loading_msg.edit_text("❌ Terjadi kesalahan saat scraping. Coba lagi nanti.")

    except Exception as e:
        await loading_msg.edit_text(f"❌ Error: {str(e)}")
        print(f"Error: {str(e)}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /help"""
    help_text = (
        "📖 *PANDUAN PENGGUNAAN BOT*\n\n"
        "*Command:*\n"
        "/start - Mulai pencarian\n"
        "/help - Bantuan\n"
        "/export - Export data terakhir ke Excel\n"
        "/monitor - Monitoring data terakhir\n"
        "/mylist - List monitoring aktif\n\n"
        "*Cara Penggunaan:*\n"
        "1. Ketik /start\n"
        "2. Pilih jenis pencarian\n"
        "3. Kirim keyword (min. 3 karakter)\n"
        "4. Gunakan tombol untuk navigasi\n\n"
        "*Fitur Baru:*\n"
        "• 📊 Export data ke Excel\n"
        "• 🔔 Monitoring perubahan data (otomatis)\n"
        "• 📋 Management monitoring\n\n"
        "*Contoh Keyword:*\n"
        "• `2001.299.11` (NIM)\n"
        "• `Admin` (Nama)\n"
        "• `Universitas Indonesia` (PT)\n"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

# =================================
# MAIN FUNCTION
# =================================
def main():
    """Jalankan bot"""
    print("🤖 Bot PDDIKTI dimulai...")

    # Buat aplikasi bot
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Tambahkan handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("export", export_command))
    application.add_handler(CommandHandler("monitor", monitor_command))
    application.add_handler(CommandHandler("mylist", mylist_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Setup background task untuk monitoring
    job_queue = application.job_queue
    job_queue.run_repeating(check_monitoring_changes, interval=3600, first=10)  # Cek setiap 1 jam

    # Jalankan bot
    print("✅ Bot berjalan... Tekan Ctrl+C untuk berhenti")
    print("📊 Fitur Export Excel: Aktif")
    print("🔔 Fitur Monitoring: Aktif (Cek setiap 1 jam)")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
