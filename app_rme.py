import streamlit as st
import streamlit.components.v1 as components
from streamlit_drawable_canvas import st_canvas
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Inches
import sqlite3, os, json, pandas as pd
from datetime import datetime, timedelta
from PIL import Image
from streamlit_autorefresh import st_autorefresh
from supabase import create_client
import pdfplumber
import time
import pytz 
import subprocess
import urllib.parse
import calendar
from datetime import date
import shutil
import zipfile
from PyPDF2 import PdfMerger

# =========================================================
# 0. FUNGSI UCAPAN HARI BESAR
# =========================================================
def get_ramadhan_dates(tahun_masehi=2026):
    ramadhan_start = date(tahun_masehi, 3, 11)
    ramadhan_end = date(tahun_masehi, 4, 9)
    idul_fitri = date(tahun_masehi, 4, 10)
    
    return {
        'start': ramadhan_start,
        'end': ramadhan_end,
        'idul_fitri': idul_fitri
    }

def is_ramadhan(tanggal):
    ramadhan = get_ramadhan_dates(tanggal.year)
    return ramadhan['start'] <= tanggal <= ramadhan['end']

def get_ucapan_spesial():
    now = get_now_jakarta()
    tanggal = now.date()
    jam = now.hour
    menit = now.minute
    
    if is_ramadhan(tanggal):
        if (jam == 18 and menit >= 15) or (jam == 18 and menit <= 30):
            return {
                'judul': "🌙 Waktu Berbuka Puasa",
                'deskripsi': "Selamat berbuka puasa untuk rekan-rekan yang menjalankan.",
                'emoji': "🥘",
                'bg_color': "linear-gradient(90deg, #FF8C00 0%, #FF4500 100%)"
            }
        elif 3 <= jam < 5:
            return {
                'judul': "🌙 Sahur Telah Tiba",
                'deskripsi': "Jangan lupa sahur, biar kuat puasanya!",
                'emoji': "🍽️",
                'bg_color': "linear-gradient(90deg, #483D8B 0%, #6A5ACD 100%)"
            }
        elif 5 <= jam < 12:
            return {
                'judul': "🌙 Selamat Menjalankan Ibadah Puasa",
                'deskripsi': "Semoga puasa dan pekerjaan diberi kelancaran.",
                'emoji': "💪",
                'bg_color': "linear-gradient(90deg, #2E8B57 0%, #228B22 100%)"
            }
        elif 15 <= jam < 18:
            return {
                'judul': "🌙 Menjelang Berbuka Puasa",
                'deskripsi': "Sebentar lagi berbuka, tetap semangat!",
                'emoji': "⏳",
                'bg_color': "linear-gradient(90deg, #CD853F 0%, #D2691E 100%)"
            }
    
    ramadhan = get_ramadhan_dates(tanggal.year)
    if tanggal == ramadhan['idul_fitri']:
        return {
            'judul': "🕌 Selamat Hari Raya Idul Fitri 1447 H",
            'deskripsi': "Minal aidin wal faizin, mohon maaf lahir dan batin.",
            'emoji': "✨",
            'bg_color': "linear-gradient(90deg, #FFD700 0%, #FFA500 100%)"
        }
    
    if now.weekday() == 4:
        if 11 <= jam < 13:
            return {
                'judul': "🕌 Jumat Berkah",
                'deskripsi': "Jangan lupa shalat Jumat. Semoga ibadah diterima.",
                'emoji': "🤲",
                'bg_color': "linear-gradient(90deg, #4B0082 0%, #800080 100%)"
            }
        else:
            return {
                'judul': "🤲 Jumat Berkah",
                'deskripsi': "Semoga hari Jumat penuh keberkahan.",
                'emoji': "🕌",
                'bg_color': "linear-gradient(90deg, #9370DB 0%, #8A2BE2 100%)"
            }
    
    hari_besar = {
        (1, 1): ("🎉 Selamat Tahun Baru Masehi 2026", "Tahun baru, semangat baru!"),
        (5, 1): ("💪 Selamat Hari Buruh", "Apresiasi untuk pekerja kesehatan"),
        (5, 2): ("☸️ Selamat Hari Raya Waisak", "Semoga kedamaian menyertai"),
        (6, 1): ("🇮🇩 Selamat Hari Lahir Pancasila", "Bersama Pancasila kita maju"),
        (8, 17): ("🇮🇩 Dirgahayu RI ke-81", "Indonesia maju, kesehatan prima"),
        (10, 5): ("🇮🇩 HUT TNI", "TNI dan Rakyat Bersatu Sehat"),
        (10, 28): ("🇮🇩 Selamat Hari Sumpah Pemuda", "Pemuda kesehatan, inspirasi bangsa"),
        (11, 10): ("🇮🇩 Selamat Hari Pahlawan", "Teladani semangat pahlawan"),
        (12, 25): ("🎄 Selamat Hari Raya Natal", "Damai Natal menyertai")
    }
    
    if (tanggal.month, tanggal.day) in hari_besar:
        judul, desk = hari_besar[(tanggal.month, tanggal.day)]
        return {
            'judul': judul,
            'deskripsi': desk,
            'emoji': "🎉",
            'bg_color': "linear-gradient(90deg, #FF69B4 0%, #FF1493 100%)"
        }
    
    if 0 <= jam < 5:
        return {
            'judul': "🌃 Selamat Bertugas Malam",
            'deskripsi': "Terima kasih untuk dedikasi rekan-rekan yang bertugas malam.",
            'emoji': "⭐",
            'bg_color': "linear-gradient(90deg, #2C3E50 0%, #34495E 100%)"
        }
    elif 5 <= jam < 7:
        return {
            'judul': "🌅 Selamat Pagi, Semangat Bertugas!",
            'deskripsi': "Awali pagi dengan senyuman, layani pasien dengan sepenuh hati.",
            'emoji': "🌤️",
            'bg_color': "linear-gradient(90deg, #F39C12 0%, #F1C40F 100%)"
        }
    elif 7 <= jam < 12:
        return {
            'judul': "☀️ Semangat Pagi, Rekan Hebat!",
            'deskripsi': "Bersama kita wujudkan pelayanan kesehatan terbaik.",
            'emoji': "💪",
            'bg_color': "linear-gradient(90deg, #3498DB 0%, #2980B9 100%)"
        }
    elif 12 <= jam < 14:
        return {
            'judul': "🍽️ Waktu Istirahat",
            'deskripsi': "Jangan lupa istirahat dan makan siang.",
            'emoji': "😊",
            'bg_color': "linear-gradient(90deg, #27AE60 0%, #229954 100%)"
        }
    elif 14 <= jam < 17:
        return {
            'judul': "🌆 Selamat Sore, Tetap Produktif!",
            'deskripsi': "Ayo kita selesaikan tugas dengan baik.",
            'emoji': "📋",
            'bg_color': "linear-gradient(90deg, #E67E22 0%, #D35400 100%)"
        }
    elif 17 <= jam < 19:
        return {
            'judul': "🌇 Selamat Sore Menjelang Malam",
            'deskripsi': "Terima kasih atas pelayanan hari ini.",
            'emoji': "🌃",
            'bg_color': "linear-gradient(90deg, #8E44AD 0%, #9B59B6 100%)"
        }
    else:
        return {
            'judul': "🌃 Selamat Malam, Terima Kasih",
            'deskripsi': "Terima kasih atas dedikasi hari ini. Istirahat yang cukup.",
            'emoji': "🌙",
            'bg_color': "linear-gradient(90deg, #2C3E50 0%, #34495E 100%)"
        }

def tampilkan_banner_ucapan():
    ucapan = get_ucapan_spesial()
    
    banner_html = f"""
    <div style="
        background: {ucapan['bg_color']};
        padding: 15px 25px;
        border-radius: 15px;
        margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        border-left: 8px solid white;
        animation: pulse 2s infinite;
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
            <div style="display: flex; align-items: center; gap: 15px;">
                <span style="font-size: 48px;">{ucapan['emoji']}</span>
                <div>
                    <h2 style="color: white; margin: 0; font-size: 28px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);">
                        {ucapan['judul']}
                    </h2>
                    <p style="color: white; margin: 5px 0 0 0; font-size: 18px; opacity: 0.95;">
                        {ucapan['deskripsi']}
                    </p>
                </div>
            </div>
            <div style="
                background: rgba(255,255,255,0.3);
                padding: 8px 20px;
                border-radius: 50px;
                color: white;
                font-weight: bold;
                font-size: 16px;
                backdrop-filter: blur(5px);
            ">
                {get_now_jakarta().strftime("%d %B %Y")} | {get_now_jakarta().strftime("%H:%M")} WIB
            </div>
        </div>
    </div>
    
    <style>
    @keyframes pulse {{
        0% {{ transform: scale(1); }}
        50% {{ transform: scale(1.01); }}
        100% {{ transform: scale(1); }}
    }}
    </style>
    """
    
    st.markdown(banner_html, unsafe_allow_html=True)

# =========================================================
# 1. CORE CONFIG & FUNCTIONS
# =========================================================
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="SIRS RME Pro 2026", layout="wide", page_icon="🏥")

# MAPPING DATA PETUGAS IT
MAPPING_IT_DETAIL = {
    "Rey":    {"nip": "NIP. .....................", "wa": "628991112223"},
    "Isfan":  {"nip": "199709302025211069", "wa": "6282298180077"},
    "Jaka":   {"nip": "199605282025211138", "wa": "628121212121"},
    "Teguh":  {"nip": "199901162025211080", "wa": "628991234567"},
    "Hisyam": {"nip": "199308302025211114", "wa": "628131313131"},
    "Udin":   {"nip": "NIP. .....................", "wa": "628571234567"},
    "Ferdi":  {"nip": "NIP. .....................", "wa": "628112223334"}
}

LIST_IT = ["Rey", "Isfan", "Jaka", "Teguh", "Hisyam", "Udin", "Ferdi"]

def convert_to_pdf(docx_path, output_dir):
    try:
        subprocess.run(['libreoffice', '--headless', '--convert-to', 'pdf', docx_path, '--outdir', output_dir], check=True)
        return docx_path.replace(".docx", ".pdf")
    except Exception as e:
        st.error(f"Gagal konversi PDF: {e}")
        return None

def get_now_jakarta():
    tz = pytz.timezone('Asia/Jakarta')
    return datetime.now(tz)

for folder in ["temp", "arsip_rme", "arsip_bulanan"]:
    if not os.path.exists(folder): os.makedirs(folder)

def play_notification():
    audio_url = "https://www.soundjay.com/buttons/sounds/button-3.mp3"
    html_code = f'<audio autoplay><source src="{audio_url}" type="audio/mpeg"></audio>'
    components.html(html_code, height=0)

# =========================================================
# 2. DATABASE & LOGIKA JADWAL
# =========================================================
def init_db():
    conn = sqlite3.connect('rme_system.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS rme_tasks 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, unit TEXT, data_pasien TEXT, 
                  status TEXT, file_name TEXT, waktu_input TEXT, waktu_selesai TEXT,
                  pemohon TEXT, nip_user TEXT, it_executor TEXT, nip_it TEXT, 
                  ttd_user_path TEXT, ip_address TEXT, rm_utama TEXT, pasien_display TEXT,
                  notif_user TEXT DEFAULT 'NO', notif_dibaca TEXT DEFAULT 'NO',
                  bulan TEXT, tahun TEXT)''')
    c.execute("CREATE TABLE IF NOT EXISTS jadwal_it (nama TEXT, tanggal INTEGER, shift TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS notifikasi_user (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER, nip_user TEXT, pesan TEXT, status TEXT, created_at TEXT)")
    conn.commit()
    return conn

# =========================================================
# 3. FUNGSI HAPUS OTOMATIS PER BULAN
# =========================================================
def cek_dan_hapus_data_lama():
    """
    Cek apakah sudah ganti bulan, jika ya backup dulu lalu hapus data
    """
    now = get_now_jakarta()
    bulan_ini = now.strftime("%Y-%m")
    
    # Cek file marker bulan terakhir
    marker_file = "last_month.txt"
    bulan_lalu = None
    if os.path.exists(marker_file):
        with open(marker_file, 'r') as f:
            bulan_lalu = f.read().strip()
    
    # Jika bulan berbeda, lakukan backup dan hapus
    if bulan_lalu != bulan_ini:
        st.warning(f"🔄 Ganti bulan terdeteksi: {bulan_lalu} -> {bulan_ini}")
        
        # Backup data bulan lalu ke folder arsip_bulanan
        if bulan_lalu:
            db = init_db()
            data_bulan_lalu = db.execute("""
                SELECT * FROM rme_tasks 
                WHERE strftime('%Y-%m', waktu_selesai) = ? 
                OR (status='Selesai' AND bulan=?)
            """, (bulan_lalu, bulan_lalu)).fetchall()
            
            if data_bulan_lalu:
                # Buat folder arsip untuk bulan lalu
                arsip_folder = f"arsip_bulanan/{bulan_lalu}"
                if not os.path.exists(arsip_folder):
                    os.makedirs(arsip_folder)
                
                # Copy file-file PDF ke folder arsip
                for task in data_bulan_lalu:
                    pdf_name = f"{task[14]}_{task[13]}.pdf"
                    pdf_path = f"arsip_rme/{pdf_name}"
                    if os.path.exists(pdf_path):
                        shutil.copy(pdf_path, f"{arsip_folder}/{pdf_name}")
                
                # Buat file laporan
                with open(f"{arsip_folder}/laporan_{bulan_lalu}.txt", 'w') as f:
                    f.write(f"Laporan Bulan: {bulan_lalu}\n")
                    f.write(f"Total Tiket: {len(data_bulan_lalu)}\n")
                    for task in data_bulan_lalu:
                        f.write(f"- {task[14]} ({task[13]}) selesai {task[6]} oleh {task[9]}\n")
            
            db.close()
            
            # Hapus data dari database
            db = init_db()
            db.execute("DELETE FROM rme_tasks WHERE strftime('%Y-%m', waktu_selesai) = ? OR (status='Selesai' AND bulan=?)", (bulan_lalu, bulan_lalu))
            db.execute("DELETE FROM notifikasi_user WHERE strftime('%Y-%m', created_at) = ?", (bulan_lalu,))
            db.commit()
            db.close()
            
            # Hapus file-file di arsip_rme untuk bulan lalu
            for f in os.listdir("arsip_rme"):
                if bulan_lalu in f:
                    os.remove(f"arsip_rme/{f}")
        
        # Update marker bulan
        with open(marker_file, 'w') as f:
            f.write(bulan_ini)
        
        return True
    return False

# =========================================================
# 4. FUNGSI NOTIFIKASI USER
# =========================================================
def buat_notifikasi_user(task_id, nip_user, pesan):
    db = init_db()
    db.execute("""
        INSERT INTO notifikasi_user (task_id, nip_user, pesan, status, created_at)
        VALUES (?, ?, ?, 'BARU', ?)
    """, (task_id, nip_user, pesan, get_now_jakarta().strftime("%Y-%m-%d %H:%M:%S")))
    db.commit()
    db.close()

def get_notifikasi_user(nip_user):
    db = init_db()
    notif = db.execute("""
        SELECT * FROM notifikasi_user 
        WHERE nip_user = ? 
        ORDER BY created_at DESC 
        LIMIT 10
    """, (nip_user,)).fetchall()
    db.close()
    return notif

def get_jumlah_notif_belum_dibaca(nip_user):
    db = init_db()
    jml = db.execute("""
        SELECT COUNT(*) FROM notifikasi_user 
        WHERE nip_user = ? AND status = 'BARU'
    """, (nip_user,)).fetchone()[0]
    db.close()
    return jml

def tandai_notif_dibaca(nip_user):
    db = init_db()
    db.execute("""
        UPDATE notifikasi_user 
        SET status = 'DIBACA' 
        WHERE nip_user = ? AND status = 'BARU'
    """, (nip_user,))
    db.commit()
    db.close()

# =========================================================
# 5. FUNGSI ARSIP BULANAN (MERGE PDF)
# =========================================================
def buat_arsip_bulanan(bulan_tahun):
    """
    Membuat arsip bulanan: ZIP semua PDF dan merge jadi 1 file
    """
    arsip_folder = f"arsip_bulanan/{bulan_tahun}"
    if not os.path.exists(arsip_folder):
        os.makedirs(arsip_folder)
    
    # Kumpulkan semua PDF bulan ini
    pdf_files = []
    for f in os.listdir("arsip_rme"):
        if bulan_tahun in f and f.endswith('.pdf'):
            pdf_files.append(f"arsip_rme/{f}")
    
    if not pdf_files:
        return None
    
    # 1. Buat file ZIP
    zip_path = f"{arsip_folder}/arsip_{bulan_tahun}.zip"
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for pdf in pdf_files:
            zipf.write(pdf, os.path.basename(pdf))
    
    # 2. Merge semua PDF jadi 1 file (opsional)
    merger = PdfMerger()
    for pdf in sorted(pdf_files):
        merger.append(pdf)
    merged_path = f"{arsip_folder}/gabungan_{bulan_tahun}.pdf"
    merger.write(merged_path)
    merger.close()
    
    return {
        'zip': zip_path,
        'merged': merged_path,
        'total': len(pdf_files)
    }

def get_status_petugas():
    """
    Mendapatkan status petugas IT hari ini
    """
    try:
        now = get_now_jakarta()
        tgl_ini, tgl_kmrn, jam_ini = now.day, (now - timedelta(days=1)).day, now.hour
        db = init_db()
        
        cek = db.execute("SELECT COUNT(*) FROM jadwal_it").fetchone()
        if cek[0] == 0:
            db.close()
            return "⚠️ Database Jadwal Kosong", []
        
        df = pd.read_sql_query(f"SELECT * FROM jadwal_it WHERE tanggal IN ({tgl_kmrn}, {tgl_ini})", db)
        db.close()
        
        petugas_on = []
        if df.empty: 
            return f"⚠️ Tidak Ada Jadwal", []
            
        for _, row in df.iterrows():
            nama = row['nama']
            shift = str(row['shift']).upper().strip()
            tgl_data = int(row['tanggal'])
            
            if shift == "PS" and tgl_data == tgl_ini:
                if 7 <= jam_ini < 16:
                    petugas_on.append(nama)
            elif shift == "P" and tgl_data == tgl_ini:
                if 7 <= jam_ini < 14:
                    petugas_on.append(nama)
            elif shift == "S" and tgl_data == tgl_ini:
                if "HISYAM" in nama.upper():
                    if 14 <= jam_ini < 22:
                        petugas_on.append(nama)
                else:
                    if 14 <= jam_ini < 21:
                        petugas_on.append(nama)
            elif "M" in shift and tgl_data == tgl_kmrn and jam_ini < 7:
                petugas_on.append(nama)
            elif "M" in shift and tgl_data == tgl_ini and jam_ini >= 21:
                petugas_on.append(nama)
        
        if petugas_on:
            return "✅ Petugas Tersedia", sorted(list(set(petugas_on)))
        else:
            return f"⏸️ Tidak Ada Petugas Standby", []
            
    except Exception as e:
        return f"⚠️ Error: {str(e)}", []

def update_jadwal_dari_pdf(file_pdf):
    """
    Update jadwal dari PDF
    """
    try:
        with pdfplumber.open(file_pdf) as pdf:
            text = pdf.pages[0].extract_text()
            
            mapping_nama = {
                "Reynold": "Rey",
                "Isfan": "Isfan",
                "Jaka": "Jaka",
                "Teguh": "Teguh",
                "Hisyam": "Hisyam",
                "Ahmad Haerudin": "Udin",
                "Ferdi": "Ferdi"
            }
            
            lines = text.split('\n')
            data_jadwal = []
            
            for line in lines:
                for nama_pdf, nama_singkat in mapping_nama.items():
                    if nama_pdf.lower() in line.lower():
                        shifts = []
                        for char in line:
                            if char in ['P','S','M','L']:
                                if char == 'P' and shifts and shifts[-1] == 'P':
                                    shifts[-1] = 'PS'
                                else:
                                    shifts.append(char)
                        
                        shifts = shifts[:31]
                        
                        for tgl in range(1, 32):
                            if tgl-1 < len(shifts):
                                shift = shifts[tgl-1]
                            else:
                                shift = 'L'
                            
                            data_jadwal.append({
                                "nama": nama_singkat,
                                "tanggal": tgl,
                                "shift": shift
                            })
            
            if data_jadwal:
                db = init_db()
                db.execute("DELETE FROM jadwal_it")
                for d in data_jadwal:
                    db.execute("INSERT INTO jadwal_it (nama, tanggal, shift) VALUES (?, ?, ?)",
                             (d['nama'], d['tanggal'], d['shift']))
                db.commit()
                db.close()
                return True
                
    except Exception as e:
        st.error(f"Error parsing PDF: {e}")
        return False
    
    return False

# =========================================================
# 6. SIDEBAR & NAVIGATION
# =========================================================
with st.sidebar:
    st.title("🏥 SIRS RME PRO")
    
    # Cek hapus otomatis setiap kali sidebar di-load
    cek_dan_hapus_data_lama()
    
    status_msg, petugas_list = get_status_petugas()
    if "✅" in status_msg:
        st.success(f"🟢 {status_msg}")
        with st.expander("👨‍💻 Petugas Aktif"):
            for p in petugas_list:
                st.write(f"• {p}")
    else:
        st.warning(f"🟡 {status_msg}")
    
    ucapan = get_ucapan_spesial()
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 10px;
        border-radius: 10px;
        margin-bottom: 15px;
        text-align: center;
        color: white;
        font-weight: bold;
        font-size: 14px;
    ">
        {ucapan['judul']}
    </div>
    """, unsafe_allow_html=True)
    
    # Tombol hapus data tes dipindah ke menu IT
    if 'is_it_authenticated' not in st.session_state: 
        st.session_state.is_it_authenticated = False
        st.session_state.it_logged_in = False
        st.session_state.it_nama = ""
        st.session_state.user_logged_in = False
        st.session_state.user_nama = ""
        st.session_state.user_nip = ""
    
    menu_umum = ["🏠 Dashboard Info", "📊 Monitor Antrian", "📝 Input Form"]
    
    if not st.session_state.is_it_authenticated:
        # Mode User (bisa login sebagai user)
        if not st.session_state.user_logged_in:
            with st.expander("👤 Login User", expanded=False):
                user_nama = st.text_input("Nama Lengkap")
                user_nip = st.text_input("NIP")
                if st.button("Login sebagai User"):
                    if user_nama and user_nip:
                        st.session_state.user_logged_in = True
                        st.session_state.user_nama = user_nama
                        st.session_state.user_nip = user_nip
                        st.rerun()
        else:
            # Tampilkan notifikasi lonceng untuk user
            col1, col2 = st.columns([3, 1])
            with col1:
                st.info(f"👋 {st.session_state.user_nama}")
            with col2:
                jml_notif = get_jumlah_notif_belum_dibaca(st.session_state.user_nip)
                if jml_notif > 0:
                    st.markdown(f"""
                    <div style="
                        background-color: #FF4444;
                        color: white;
                        border-radius: 50%;
                        width: 30px;
                        height: 30px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-weight: bold;
                        float: right;
                    ">
                        {jml_notif}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("🔔")
            
            if st.button("Logout User"):
                st.session_state.user_logged_in = False
                st.session_state.user_nama = ""
                st.session_state.user_nip = ""
                st.rerun()
        
        with st.expander("🔑 IT LOGIN"):
            pin = st.text_input("PIN Admin IT:", type="password")
            if st.button("Masuk"):
                if pin == "1234": 
                    st.session_state.is_it_authenticated = True
                    st.rerun()
                else: 
                    st.error("PIN Salah!")
        menu = st.radio("Pilih Halaman:", menu_umum)
    else:
        st.success("✅ Mode IT Aktif")
        
        if not st.session_state.it_logged_in:
            with st.expander("👤 Login Sebagai IT", expanded=True):
                it_nama = st.selectbox("Pilih Nama IT:", LIST_IT)
                it_pin = st.text_input("PIN IT:", type="password")
                if st.button("Login"):
                    if it_pin == "1234":
                        st.session_state.it_logged_in = True
                        st.session_state.it_nama = it_nama
                        st.rerun()
                    else:
                        st.error("PIN Salah!")
        else:
            st.info(f"👋 **{st.session_state.it_nama}**")
            if st.button("Logout"):
                st.session_state.it_logged_in = False
                st.session_state.it_nama = ""
                st.rerun()
        
        menu = st.radio("Pilih Halaman:", menu_umum + ["👨‍💻 Workspace IT", "📂 Arsip Digital", "📦 Arsip Bulanan", "📅 Dashboard Jadwal", "⚙️ Admin Tools"])
        if st.button("Logout Admin"): 
            st.session_state.is_it_authenticated = False
            st.session_state.it_logged_in = False
            st.rerun()

# =========================================================
# 7. DASHBOARD INFO
# =========================================================
if menu == "🏠 Dashboard Info":
    tampilkan_banner_ucapan()
    
    st.markdown("""
        # 🏥 SIRS RME PRO 2026
        **Digitalisasi Layanan IT untuk Akurasi & Efisiensi RS**
        
        ---
        ### 🎯 Fitur Unggulan:
        * **🚀 Satu Klik:** Pengajuan langsung ke IT tujuan
        * **📄 Paperless:** Dokumen PDF terbit otomatis
        * **🔔 Notifikasi:** Status tiket di dashboard user
        * **📦 Arsip Bulanan:** Download semua berita acara sekali klik
        * **🔄 Auto Clean:** Data lama otomatis terarsip tiap bulan
    """)
    
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📋 Status Petugas IT Hari Ini")
        status_msg, petugas_list = get_status_petugas()
        if petugas_list:
            st.success(f"✅ Petugas IT Aktif: {', '.join(petugas_list)}")
        else:
            st.warning(f"⚠️ {status_msg}")
    
    with col2:
        st.subheader("📦 Arsip Bulan Ini")
        bulan_ini = get_now_jakarta().strftime("%Y-%m")
        st.info(f"Bulan: {bulan_ini}")
        
        db = init_db()
        jml_tiket_bulan_ini = db.execute("SELECT COUNT(*) FROM rme_tasks WHERE status='Selesai' AND bulan=?", (bulan_ini,)).fetchone()[0]
        db.close()
        st.metric("Tiket Selesai Bulan Ini", jml_tiket_bulan_ini)
    
    if st.session_state.user_logged_in:
        st.divider()
        st.subheader("🔔 Notifikasi Saya")
        notif = get_notifikasi_user(st.session_state.user_nip)
        if notif:
            for n in notif:
                if n[4] == 'BARU':
                    st.success(f"🆕 {n[3]} - {n[5]}")
                else:
                    st.info(f"📌 {n[3]} - {n[5]}")
            if st.button("Tandai Semua Sudah Dibaca"):
                tandai_notif_dibaca(st.session_state.user_nip)
                st.rerun()
        else:
            st.info("Belum ada notifikasi")
    
    st.info("💡 Klik menu **📝 Input Form** untuk mulai mengajukan.")

# =========================================================
# 8. MONITOR ANTRIAN
# =========================================================
elif menu == "📊 Monitor Antrian":
    ucapan = get_ucapan_spesial()
    st.info(f"📌 {ucapan['judul']} - {ucapan['deskripsi']}")
    
    status_msg, petugas_list = get_status_petugas()
    if petugas_list:
        st.success(f"🟢 Petugas Standby: {', '.join(petugas_list)}")
    else:
        st.warning(f"🟡 {status_msg}")
    
    st_autorefresh(5000)
    st.header("📊 Monitor Antrian Real-Time")
    db = init_db()
    df = pd.read_sql_query("SELECT id, waktu_input, pasien_display, it_executor, status, unit FROM rme_tasks ORDER BY id DESC LIMIT 9", db)
    db.close()

    if not df.empty:
        cols = st.columns(3)
        for index, row in df.iterrows():
            with cols[index % 3]:
                if row['status'] == "Masuk Antrian":
                    bg = "#FFE5E5"
                    border = "#FF4444"
                    lbl = "🔴 Menunggu IT"
                elif row['status'] == "Menunggu":
                    bg = "#FFF4E0"
                    border = "#FFA500"
                    lbl = "🟡 Sedang Diproses"
                else:
                    bg = "#E5FFEA"
                    border = "#4CAF50"
                    lbl = "🟢 Selesai"
                
                st.markdown(f"""
                <div style="
                    background-color: {bg};
                    padding: 15px;
                    border-radius: 10px;
                    border-left: 5px solid {border};
                    margin-bottom: 15px;
                    box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
                ">
                    <div style="display:flex; justify-content:space-between; color: #000000;">
                        <small><b>Tiket #{row['id']}</b></small>
                        <small>{row['waktu_input']}</small>
                    </div>
                    <div style="margin:10px 0; color: #000000;">
                        <div style="font-size:18px; font-weight:bold;">{row['pasien_display']}</div>
                        <div style="font-size:14px;">Unit: {row['unit']}</div>
                    </div>
                    <div style="border-top:1px solid #ccc; padding-top:5px; font-size:13px; color: #000000;">
                        Petugas IT: <b>{row['it_executor']}</b>
                    </div>
                    <div style="margin-top:10px; text-align:center; font-weight:bold; font-size:14px; color: #000000;">
                        {lbl}
                    </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Belum ada antrian saat ini.")

# =========================================================
# 9. INPUT FORM
# =========================================================
elif menu == "📝 Input Form":
    if not st.session_state.user_logged_in:
        st.warning("⚠️ Silakan login sebagai user terlebih dahulu di sidebar!")
        st.stop()
    
    ucapan = get_ucapan_spesial()
    st.success(f"✨ {ucapan['judul']} - {ucapan['deskripsi']}")
    
    st.header("📝 Form Penghapusan RME")
    
    status_msg, petugas_list = get_status_petugas()
    
    if petugas_list:
        st.success(f"✅ Petugas IT Tersedia: {', '.join(petugas_list)}")
    else:
        st.error(f"⛔ {status_msg}")
        st.warning("Form tidak dapat digunakan karena tidak ada petugas IT yang standby.")
        st.stop()
    
    if 'step' not in st.session_state: 
        st.session_state.step = 1
        st.session_state.data_p = []

    with st.expander("👤 Identitas Pemohon", expanded=True):
        c1, c2 = st.columns(2)
        u_nama = c1.text_input("Nama Pemohon", value=st.session_state.user_nama)
        u_unit = c2.text_input("Unit/Ruangan")
        u_nip = c1.text_input("NIP Pemohon", value=st.session_state.user_nip)
        u_it = c2.selectbox("Kirim ke Petugas IT Piket:", petugas_list)

    if st.session_state.step == 1:
        st.session_state.jml = st.number_input("Jumlah Pasien", 1, 4, 1)

    if st.session_state.step <= st.session_state.get('jml', 1):
        s = st.session_state.step
        with st.container(border=True):
            st.subheader(f"📍 Data Pasien ke-{s}")
            p_nama = st.text_input(f"Nama Pasien {s}", key=f"nm_{s}")
            p_rm = st.text_input(f"No. RM {s}", max_chars=9, key=f"rm_{s}")
            p_als = st.text_area(f"Alasan {s}", key=f"al_{s}")
            if st.button("Simpan & Lanjut ➡️", key=f"btn_{s}"):
                if len(p_rm) == 9 and p_nama:
                    st.session_state.data_p.append({"nama": p_nama, "rm": p_rm, "alasan": p_als})
                    st.session_state.step += 1
                    st.rerun()
                else: 
                    st.error("Data Belum Lengkap!")
    else:
        st.success("✅ Data Lengkap. Silahkan Tanda Tangan:")
        canvas = st_canvas(stroke_width=3, stroke_color="#000", background_color="#fff", height=150, width=400, key="can_u")
        
        if st.button("🚀 KIRIM KE IT", type="primary"):
            if canvas.image_data is not None and u_nama and u_nip:
                jam_sekarang_wib = get_now_jakarta().strftime("%H:%M")
                path_ttd = f"temp/ttd_u_{datetime.now().strftime('%H%M%S')}.png"
                Image.fromarray(canvas.image_data.astype('uint8')).save(path_ttd)
                
                rm_utama = st.session_state.data_p[0]['rm']
                nama_utama = st.session_state.data_p[0]['nama']
                
                now = get_now_jakarta()
                bulan = now.strftime("%Y-%m")
                
                db = init_db()
                db.execute('''INSERT INTO rme_tasks 
                              (unit, data_pasien, status, file_name, waktu_input, 
                               pemohon, nip_user, it_executor, ttd_user_path, rm_utama, pasien_display,
                               notif_user, notif_dibaca, bulan, tahun) 
                              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                            (u_unit, json.dumps(st.session_state.data_p), "Masuk Antrian", f"HAPUS_RME_{rm_utama}.docx", 
                             jam_sekarang_wib, u_nama, u_nip, u_it, path_ttd, rm_utama, nama_utama,
                             'NO', 'NO', bulan, str(now.year)))
                db.commit()
                db.close()

                # WA OTOMATIS KE IT
                it_info = MAPPING_IT_DETAIL.get(u_it, {"wa": "628123456789"})
                pesan = f"""🔔 *NOTIFIKASI PENGAJUAN RME*

Halo Mas {u_it}, saya *{u_nama}* dari *{u_unit}* baru saja mengirim pengajuan penghapusan RME.

📋 *Data Pasien:*
• Nama: {nama_utama}
• No. RM: {rm_utama}
• Jumlah Pasien: {len(st.session_state.data_p)}

Status: ✅ Masuk ke antrian Workspace IT Anda.

- SIRS RME PRO 2026 -"""
                
                wa_url = f"https://wa.me/{it_info['wa']}?text={urllib.parse.quote(pesan)}"
                
                st.markdown(f'''
                    <meta http-equiv="refresh" content="0; url={wa_url}" />
                ''', unsafe_allow_html=True)
                
                st.session_state.form_done = True
                st.session_state.wa_sent = True
                st.session_state.wa_url = wa_url
                st.rerun()
            else: 
                st.error("Mohon tanda tangan pemohon!")

        if st.session_state.get('form_done'):
            st.success("✅ Pengajuan Berhasil Terkirim!")
            st.success("📲 WA otomatis telah dikirim ke petugas IT")
            
            if st.session_state.get('wa_url'):
                st.link_button("📱 Klik jika WA tidak terbuka otomatis", st.session_state.wa_url)
            
            if st.button("Isi Form Baru"):
                st.session_state.clear()
                st.rerun()

# =========================================================
# 10. WORKSPACE IT
# =========================================================
elif menu == "👨‍💻 Workspace IT":
    if not st.session_state.it_logged_in:
        st.warning("⚠️ Silakan login terlebih dahulu di sidebar!")
        st.stop()
    
    status_msg, petugas_list = get_status_petugas()
    ucapan = get_ucapan_spesial()
    st.info(f"💻 **{st.session_state.it_nama}** - {ucapan['judul']}")
    
    if petugas_list:
        st.success(f"🟢 Petugas Standby Hari Ini: {', '.join(petugas_list)}")
    else:
        st.warning(f"🟡 {status_msg}")
    
    st_autorefresh(5000)
    st.header(f"👨‍💻 Workspace: {st.session_state.it_nama}")
    
    db = init_db()
    
    query = """
        SELECT * FROM rme_tasks 
        WHERE it_executor = ? 
        AND status IN ('Masuk Antrian', 'Menunggu')
        ORDER BY 
            CASE status 
                WHEN 'Masuk Antrian' THEN 1 
                WHEN 'Menunggu' THEN 2 
            END,
            id DESC
    """
    tasks = db.execute(query, (st.session_state.it_nama,)).fetchall()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Tugas", len(tasks))
    with col2:
        antrian = len([t for t in tasks if t[3] == "Masuk Antrian"])
        st.metric("Menunggu Diterima", antrian)
    with col3:
        proses = len([t for t in tasks if t[3] == "Menunggu"])
        st.metric("Sedang Diproses", proses)
    
    st.divider()
    
    if tasks:
        play_notification()
        
        for status_group in ["Masuk Antrian", "Menunggu"]:
            group_tasks = [t for t in tasks if t[3] == status_group]
            
            if group_tasks:
                status_label = "📥 MENUNGGU DITERIMA" if status_group == "Masuk Antrian" else "⚙️ SEDANG DIPROSES"
                st.subheader(f"{status_label} ({len(group_tasks)})")
                
                for t in group_tasks:
                    with st.expander(f"🎫 Tiket #{t[0]} - {t[14]} ({t[1]})", expanded=True):
                        col_info1, col_info2 = st.columns(2)
                        with col_info1:
                            st.markdown(f"**👤 Pemohon:** {t[7]}")
                            st.markdown(f"**🆔 NIP:** {t[8]}")
                            st.markdown(f"**⏰ Masuk:** {t[5]}")
                        with col_info2:
                            st.markdown(f"**🏥 Unit:** {t[1]}")
                            st.markdown(f"**📋 Status:** {t[3]}")
                        
                        if t[3] == "Masuk Antrian":
                            if st.button(f"✅ Terima & Proses Tiket #{t[0]}", key=f"acc_{t[0]}", use_container_width=True):
                                db.execute("UPDATE rme_tasks SET status='Menunggu' WHERE id=?", (t[0],))
                                db.commit()
                                st.rerun()
                        
                        elif t[3] == "Menunggu":
                            st.warning("⚠️ Silakan proses penghapusan di sistem, lalu tandatangani.")
                            
                            with st.container(border=True):
                                st.caption("📋 DATA PASIEN")
                                try:
                                    data_pasien = json.loads(t[2])
                                    for i, ps in enumerate(data_pasien, 1):
                                        st.markdown(f"**{i}. {ps.get('nama', '-')}** (RM: {ps.get('rm', '-')})")
                                        st.caption(f"   Alasan: {ps.get('alasan', '-')}")
                                except:
                                    st.info("Data pasien tidak tersedia")
                            
                            can_it = st_canvas(
                                stroke_width=3, 
                                stroke_color="#000000", 
                                background_color="#FFFFFF", 
                                height=150, 
                                width=400, 
                                key=f"it_can_{t[0]}"
                            )
                            
                            if st.button(f"✅ Selesaikan Tiket #{t[0]}", type="primary", key=f"fin_{t[0]}", use_container_width=True):
                                if can_it.image_data is not None:
                                    ttd_path = f"temp/ttd_it_{t[0]}_{datetime.now().strftime('%H%M%S')}.png"
                                    Image.fromarray(can_it.image_data.astype('uint8')).save(ttd_path)
                                    
                                    waktu_selesai = get_now_jakarta().strftime("%H:%M")
                                    
                                    # Generate DOCX dari template
                                    doc = DocxTemplate("template_rme.docx")
                                    context = {
                                        'tgl_full': get_now_jakarta().strftime("%A, %d %B %Y"),
                                        'unit': t[1],
                                        'pemohon': t[7],
                                        'nip_user': t[8],
                                        'penerima': st.session_state.it_nama,
                                        'nip_it': MAPPING_IT_DETAIL[st.session_state.it_nama]['nip'],
                                        'ttd_user': InlineImage(doc, t[11], width=Inches(1.5)),
                                        'ttd_it': InlineImage(doc, ttd_path, width=Inches(1.5))
                                    }
                                    
                                    data_pasien = json.loads(t[2])
                                    for i, ps in enumerate(data_pasien, 1):
                                        context[f'nama{i}'] = ps.get('nama', '')
                                        context[f'rm{i}'] = ps.get('rm', '')
                                        context[f'tgl{i}'] = get_now_jakarta().strftime("%d-%m-%Y")
                                        context[f'alasan{i}'] = ps.get('alasan', '')
                                    
                                    doc.render(context)
                                    docx_path = f"arsip_rme/{t[14]}_{t[13]}.docx"
                                    doc.save(docx_path)
                                    
                                    convert_to_pdf(docx_path, "arsip_rme")
                                    
                                    # Buat notifikasi untuk user
                                    pesan_notif = f"✅ Tiket #{t[0]} - {t[14]} telah selesai diproses oleh IT {st.session_state.it_nama} pada {waktu_selesai} WIB."
                                    buat_notifikasi_user(t[0], t[8], pesan_notif)
                                    
                                    db.execute("""
                                        UPDATE rme_tasks 
                                        SET status='Selesai', waktu_selesai=?, nip_it=?, notif_user='YES'
                                        WHERE id=?
                                    """, (waktu_selesai, MAPPING_IT_DETAIL[st.session_state.it_nama]['nip'], t[0]))
                                    db.commit()
                                    
                                    st.success(f"✅ Tiket #{t[0]} Selesai!")
                                    st.success("📢 Notifikasi telah dikirim ke user")
                                    st.balloons()
                                    time.sleep(2)
                                    st.rerun()
                                else:
                                    st.error("Harap tanda tangan terlebih dahulu!")
    else:
        st.info(f"🎉 Selamat **{st.session_state.it_nama}**, tidak ada tugas untuk Anda saat ini.")
        
        with st.expander("📜 Lihat Riwayat Tugas Selesai"):
            history_query = """
                SELECT * FROM rme_tasks 
                WHERE it_executor = ? AND status='Selesai' 
                ORDER BY id DESC LIMIT 5
            """
            history = db.execute(history_query, (st.session_state.it_nama,)).fetchall()
            if history:
                for h in history:
                    st.caption(f"🎫 #{h[0]} - {h[14]} ({h[5]} selesai {h[6]})")
            else:
                st.caption("Belum ada riwayat")
    
    db.close()

# =========================================================
# 11. ARSIP DIGITAL (File Individual)
# =========================================================
elif menu == "📂 Arsip Digital":
    st.header("📂 Arsip File Individual")
    
    db = init_db()
    filter_it = st.selectbox("Filter berdasarkan IT:", ["Semua"] + LIST_IT)
    
    if filter_it == "Semua":
        df_arsip = pd.read_sql_query("SELECT * FROM rme_tasks WHERE status='Selesai' ORDER BY id DESC", db)
    else:
        df_arsip = pd.read_sql_query("SELECT * FROM rme_tasks WHERE status='Selesai' AND it_executor=? ORDER BY id DESC", db, params=(filter_it,))
    
    db.close()
    
    if not df_arsip.empty:
        st.success(f"Total {len(df_arsip)} arsip ditemukan")
        
        for _, r in df_arsip.iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
                
                c1.markdown(f"**{r['pasien_display']}**")
                c1.caption(f"No. RM: {r['rm_utama']}")
                
                c2.write(f"💻 IT: {r['it_executor']}")
                c2.caption(f"Selesai: {r['waktu_selesai']}")
                
                nama_file_fix = f"{r['pasien_display']}_{r['rm_utama']}.docx"
                f_docx = f"arsip_rme/{nama_file_fix}"
                f_pdf = f_docx.replace(".docx", ".pdf")
                
                if os.path.exists(f_docx):
                    with open(f_docx, "rb") as f:
                        c3.download_button("📂 DOCX", f, file_name=nama_file_fix, key=f"d_{r['id']}")
                else:
                    c3.button("📂 Docx ❌", disabled=True, key=f"d_disabled_{r['id']}")

                if os.path.exists(f_pdf):
                    with open(f_pdf, "rb") as f:
                        c4.download_button("🖨️ PDF", f, file_name=nama_file_fix.replace(".docx", ".pdf"), mime="application/pdf", key=f"p_{r['id']}")
                else:
                    c4.button("🖨️ PDF ❌", disabled=True, key=f"p_disabled_{r['id']}")
    else:
        st.info("📭 Arsip belum tersedia.")

# =========================================================
# 12. ARSIP BULANAN (Download Semua Sekali Klik)
# =========================================================
elif menu == "📦 Arsip Bulanan":
    st.header("📦 Arsip Bulanan (Download Semua Sekali Klik)")
    
    st.info("""
    Di sini IT bisa mendownload semua arsip dalam satu bulan:
    - 📁 **ZIP**: Kumpulan semua file PDF
    - 📚 **Gabungan PDF**: Semua file digabung jadi 1
    """)
    
    # Pilih bulan
    bulan_list = []
    for f in os.listdir("arsip_bulanan"):
        if os.path.isdir(f"arsip_bulanan/{f}"):
            bulan_list.append(f)
    
    if bulan_list:
        bulan_pilih = st.selectbox("Pilih Bulan:", sorted(bulan_list, reverse=True))
        
        arsip_folder = f"arsip_bulanan/{bulan_pilih}"
        
        col1, col2 = st.columns(2)
        
        with col1:
            zip_file = f"{arsip_folder}/arsip_{bulan_pilih}.zip"
            if os.path.exists(zip_file):
                with open(zip_file, "rb") as f:
                    st.download_button(
                        "📥 Download ZIP (Semua File)",
                        f,
                        file_name=f"arsip_{bulan_pilih}.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
        
        with col2:
            merged_file = f"{arsip_folder}/gabungan_{bulan_pilih}.pdf"
            if os.path.exists(merged_file):
                with open(merged_file, "rb") as f:
                    st.download_button(
                        "📥 Download Gabungan PDF (1 File)",
                        f,
                        file_name=f"gabungan_{bulan_pilih}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
        
        # Tampilkan daftar file di bulan tersebut
        with st.expander("📋 Lihat Daftar File"):
            files = os.listdir(arsip_folder)
            for f in sorted(files):
                if f.endswith('.pdf'):
                    st.caption(f"• {f}")
    else:
        st.info("Belum ada arsip bulanan. Arsip akan otomatis terbentuk saat pergantian bulan.")

# =========================================================
# 13. DASHBOARD JADWAL
# =========================================================
elif menu == "📅 Dashboard Jadwal":
    st.header("📅 Pengaturan Jadwal IT")
    
    ucapan = get_ucapan_spesial()
    st.markdown(f"📌 *{ucapan['judul']}*")
    
    with st.container(border=True):
        pdf_file = st.file_uploader("Upload PDF Jadwal Baru", type="pdf")
        if st.button("🔄 Update Database Jadwal"):
            if pdf_file:
                with st.spinner("Memproses PDF..."):
                    if update_jadwal_dari_pdf(pdf_file):
                        st.success("✅ Database Jadwal Berhasil Diperbarui!")
                        time.sleep(1)
                        st.rerun()
                    else: 
                        st.error("Format PDF tidak sesuai atau Gagal proses.")
            else:
                st.error("Pilih file PDF terlebih dahulu")
    
    st.divider()
    
    db = init_db()
    df_v = pd.read_sql_query("SELECT * FROM jadwal_it ORDER BY tanggal ASC", db)
    
    if not df_v.empty:
        st.subheader("📋 Jadwal IT Saat Ini")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Data Jadwal", len(df_v))
        with col2:
            st.metric("Jumlah IT", df_v['nama'].nunique())
        with col3:
            st.metric("Rentang Tanggal", f"{df_v['tanggal'].min()} - {df_v['tanggal'].max()}")
        
        t_skrg = get_now_jakarta().day
        t_pilih = st.slider("Cek Petugas Tanggal:", 1, 31, t_skrg)
        
        df_filter = df_v[df_v['tanggal'] == t_pilih].copy()
        
        if not df_filter.empty:
            st.dataframe(df_filter, use_container_width=True)
        else:
            st.warning(f"⚠️ Tidak ada jadwal untuk tanggal {t_pilih}")
            
        with st.expander("📊 Lihat Semua Data Jadwal"):
            st.dataframe(df_v, use_container_width=True)
    else:
        st.info("📅 Belum ada jadwal. Silakan upload PDF.")
    
    db.close()

# =========================================================
# 14. ADMIN TOOLS
# =========================================================
elif menu == "⚙️ Admin Tools":
    st.header("⚙️ Tools Admin IT")
    
    tab1, tab2 = st.tabs(["🗑️ Hapus Data", "📊 Statistik"])
    
    with tab1:
        st.warning("⚠️ Hati-hati! Fitur ini akan menghapus data.")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔥 Hapus SEMUA Data Tes", type="primary"):
                conn = sqlite3.connect('rme_system.db'); c = conn.cursor()
                c.execute("DELETE FROM rme_tasks")
                c.execute("DELETE FROM notifikasi_user")
                conn.commit(); conn.close()
                
                # Hapus file di temp
                for f in os.listdir("temp"):
                    os.remove(f"temp/{f}")
                
                st.success("✅ Semua data tes berhasil dihapus!")
                st.rerun()
        
        with col2:
            if st.button("📦 Hapus Tapi Backup Dulu"):
                # Backup manual sebelum hapus
                bulan_ini = get_now_jakarta().strftime("%Y-%m")
                buat_arsip_bulanan(bulan_ini)
                
                conn = sqlite3.connect('rme_system.db'); c = conn.cursor()
                c.execute("DELETE FROM rme_tasks")
                c.execute("DELETE FROM notifikasi_user")
                conn.commit(); conn.close()
                
                st.success("✅ Data dihapus setelah di-backup!")
                st.rerun()
    
    with tab2:
        db = init_db()
        
        total_tasks = db.execute("SELECT COUNT(*) FROM rme_tasks").fetchone()[0]
        total_selesai = db.execute("SELECT COUNT(*) FROM rme_tasks WHERE status='Selesai'").fetchone()[0]
        total_antrian = db.execute("SELECT COUNT(*) FROM rme_tasks WHERE status='Masuk Antrian'").fetchone()[0]
        total_proses = db.execute("SELECT COUNT(*) FROM rme_tasks WHERE status='Menunggu'").fetchone()[0]
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Tiket", total_tasks)
        col2.metric("Selesai", total_selesai)
        col3.metric("Antrian", total_antrian)
        col4.metric("Diproses", total_proses)
        
        # Statistik per IT
        st.subheader("📊 Statistik per IT")
        df_it = pd.read_sql_query("""
            SELECT it_executor, 
                   COUNT(*) as total,
                   SUM(CASE WHEN status='Selesai' THEN 1 ELSE 0 END) as selesai,
                   SUM(CASE WHEN status='Masuk Antrian' THEN 1 ELSE 0 END) as antrian
            FROM rme_tasks 
            GROUP BY it_executor
        """, db)
        st.dataframe(df_it, use_container_width=True)
        
        db.close()
