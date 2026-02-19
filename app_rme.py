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

# =========================================================
# 0. FUNGSI UCAPAN HARI BESAR OTOMATIS DENGAN RAMADHAN
# =========================================================
def get_ramadhan_dates(tahun_masehi=2026):
    """
    Mendapatkan perkiraan tanggal Ramadhan dan Idul Fitri
    Berdasarkan kalender Hijriyah
    """
    # Ramadhan 1447 H jatuh sekitar Maret-April 2026
    # Awal Ramadhan: sekitar 11 Maret 2026
    # Idul Fitri: sekitar 10 April 2026
    
    ramadhan_start = date(tahun_masehi, 3, 11)
    ramadhan_end = date(tahun_masehi, 4, 9)
    idul_fitri = date(tahun_masehi, 4, 10)
    
    return {
        'start': ramadhan_start,
        'end': ramadhan_end,
        'idul_fitri': idul_fitri
    }

def is_ramadhan(tanggal):
    """
    Cek apakah tanggal termasuk dalam bulan Ramadhan
    """
    ramadhan = get_ramadhan_dates(tanggal.year)
    return ramadhan['start'] <= tanggal <= ramadhan['end']

def get_ucapan_spesial():
    """
    Mendapatkan ucapan spesial berdasarkan waktu dan kondisi
    """
    now = get_now_jakarta()
    tanggal = now.date()
    jam = now.hour
    menit = now.minute
    
    # CEK RAMADHAN
    if is_ramadhan(tanggal):
        # Waktu berbuka (Maghrib) - sekitar 18:00-18:30 WIB
        if (jam == 18 and menit >= 15) or (jam == 18 and menit <= 30):
            return {
                'judul': "🌙 Waktu Berbuka Puasa",
                'deskripsi': "Selamat berbuka puasa untuk rekan-rekan yang menjalankan. Semoga ibadah lancar!",
                'emoji': "🥘",
                'bg_color': "linear-gradient(90deg, #FF8C00 0%, #FF4500 100%)"
            }
        # Waktu sahur (03:00 - 04:30)
        elif 3 <= jam < 5:
            return {
                'judul': "🌙 Sahur Telah Tiba",
                'deskripsi': "Jangan lupa sahur, biar kuat puasanya! Semoga ibadah lancar.",
                'emoji': "🍽️",
                'bg_color': "linear-gradient(90deg, #483D8B 0%, #6A5ACD 100%)"
            }
        # Pagi - Siang Ramadhan
        elif 5 <= jam < 12:
            return {
                'judul': "🌙 Selamat Menjalankan Ibadah Puasa",
                'deskripsi': "Semoga puasa dan pekerjaan diberi kelancaran. Tetap semangat melayani!",
                'emoji': "💪",
                'bg_color': "linear-gradient(90deg, #2E8B57 0%, #228B22 100%)"
            }
        # Sore Ramadhan (menjelang berbuka)
        elif 15 <= jam < 18:
            return {
                'judul': "🌙 Menjelang Berbuka Puasa",
                'deskripsi': "Sebentar lagi berbuka, tetap semangat! Jangan lupa siapkan takjil.",
                'emoji': "⏳",
                'bg_color': "linear-gradient(90deg, #CD853F 0%, #D2691E 100%)"
            }
    
    # CEK IDUL FITRI
    ramadhan = get_ramadhan_dates(tanggal.year)
    if tanggal == ramadhan['idul_fitri']:
        return {
            'judul': "🕌 Selamat Hari Raya Idul Fitri 1447 H",
            'deskripsi': "Minal aidin wal faizin, mohon maaf lahir dan batin. Selamat merayakan kemenangan!",
            'emoji': "✨",
            'bg_color': "linear-gradient(90deg, #FFD700 0%, #FFA500 100%)"
        }
    
    # CEK HARI JUMAT
    if now.weekday() == 4:
        if 11 <= jam < 13:
            return {
                'judul': "🕌 Jumat Berkah",
                'deskripsi': "Bagi yang Muslim, jangan lupa shalat Jumat. Semoga ibadah diterima Allah SWT.",
                'emoji': "🤲",
                'bg_color': "linear-gradient(90deg, #4B0082 0%, #800080 100%)"
            }
        else:
            return {
                'judul': "🤲 Jumat Berkah",
                'deskripsi': "Semoga hari Jumat ini membawa keberkahan untuk kita semua dalam melayani pasien.",
                'emoji': "🕌",
                'bg_color': "linear-gradient(90deg, #9370DB 0%, #8A2BE2 100%)"
            }
    
    # CEK HARI KHUSUS
    hari_besar = {
        (1, 1): ("🎉 Selamat Tahun Baru Masehi 2026", "Tahun baru, semangat baru dalam pelayanan!"),
        (5, 1): ("💪 Selamat Hari Buruh", "Apresiasi untuk para pekerja kesehatan yang berdedikasi"),
        (5, 2): ("☸️ Selamat Hari Raya Waisak", "Semoga kedamaian selalu menyertai"),
        (6, 1): ("🇮🇩 Selamat Hari Lahir Pancasila", "Bersama Pancasila kita majukan kesehatan Indonesia"),
        (8, 17): ("🇮🇩 Dirgahayu RI ke-81", "Indonesia maju, kesehatan prima untuk semua"),
        (10, 5): ("🇮🇩 HUT TNI", "TNI dan Rakyat Bersatu Sehat"),
        (10, 28): ("🇮🇩 Selamat Hari Sumpah Pemuda", "Pemuda kesehatan, inspirasi bangsa"),
        (11, 10): ("🇮🇩 Selamat Hari Pahlawan", "Teladani semangat pahlawan dalam melayani"),
        (12, 25): ("🎄 Selamat Hari Raya Natal", "Damai Natal menyertai kita semua")
    }
    
    if (tanggal.month, tanggal.day) in hari_besar:
        judul, desk = hari_besar[(tanggal.month, tanggal.day)]
        return {
            'judul': judul,
            'deskripsi': desk,
            'emoji': "🎉",
            'bg_color': "linear-gradient(90deg, #FF69B4 0%, #FF1493 100%)"
        }
    
    # UCAPAN SEMANGAT KERJA UNTUK ADMIN RS
    if 0 <= jam < 5:
        return {
            'judul': "🌃 Selamat Bertugas Malam",
            'deskripsi': "Terima kasih untuk dedikasi rekan-rekan yang bertugas malam. Jaga kesehatan!",
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
            'deskripsi': "Bersama kita wujudkan pelayanan kesehatan terbaik untuk masyarakat.",
            'emoji': "💪",
            'bg_color': "linear-gradient(90deg, #3498DB 0%, #2980B9 100%)"
        }
    elif 12 <= jam < 14:
        return {
            'judul': "🍽️ Waktu Istirahat",
            'deskripsi': "Jangan lupa istirahat dan makan siang. Tetap jaga stamina!",
            'emoji': "😊",
            'bg_color': "linear-gradient(90deg, #27AE60 0%, #229954 100%)"
        }
    elif 14 <= jam < 17:
        return {
            'judul': "🌆 Selamat Sore, Tetap Produktif!",
            'deskripsi': "Masih semangat? Ayo kita selesaikan tugas dengan baik.",
            'emoji': "📋",
            'bg_color': "linear-gradient(90deg, #E67E22 0%, #D35400 100%)"
        }
    elif 17 <= jam < 19:
        return {
            'judul': "🌇 Selamat Sore Menjelang Malam",
            'deskripsi': "Terima kasih atas pelayanan hari ini. Selamat beristirahat untuk yang pulang.",
            'emoji': "🌃",
            'bg_color': "linear-gradient(90deg, #8E44AD 0%, #9B59B6 100%)"
        }
    else:
        return {
            'judul': "🌃 Selamat Malam, Terima Kasih",
            'deskripsi': "Terima kasih atas dedikasi hari ini. Istirahat yang cukup ya!",
            'emoji': "🌙",
            'bg_color': "linear-gradient(90deg, #2C3E50 0%, #34495E 100%)"
        }

def tampilkan_banner_ucapan():
    """
    Menampilkan banner ucapan di dashboard
    """
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

def get_status_petugas():
    """
    Mendapatkan status petugas IT hari ini berdasarkan jadwal PDF
    """
    try:
        now = get_now_jakarta()
        tgl_ini, tgl_kmrn, jam_ini = now.day, (now - timedelta(days=1)).day, now.hour
        db = init_db()
        
        # Cek apakah tabel jadwal ada isinya
        cek = db.execute("SELECT COUNT(*) FROM jadwal_it").fetchone()
        if cek[0] == 0:
            db.close()
            return "⚠️ Database Jadwal Kosong", []
        
        # Ambil data jadwal
        df = pd.read_sql_query(f"SELECT * FROM jadwal_it WHERE tanggal IN ({tgl_kmrn}, {tgl_ini})", db)
        db.close()
        
        petugas_on = []
        if df.empty: 
            return "⚠️ Tidak Ada Jadwal", []
            
        for _, row in df.iterrows():
            nama = row['nama']
            shift = str(row['shift']).upper().strip()
            tgl_data = int(row['tanggal'])
            
            # Logika shift
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
            return "⏸️ Tidak Ada Petugas Standby", []
            
    except Exception as e:
        return f"⚠️ Error: {str(e)}", []

# =========================================================
# 1. CORE CONFIG & FUNCTIONS
# =========================================================
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="SIRS RME Pro 2026", layout="wide", page_icon="🏥")

# MAPPING DATA PETUGAS IT (NIP & WA)
MAPPING_IT_DETAIL = {
    "Isfan":  {"nip": "199709302025211069", "wa": "6282298180077"},
    "Teguh":  {"nip": "199901162025211080", "wa": "628991234567"},
    "Jaka":   {"nip": "199605282025211138", "wa": "628121212121"},
    "Hisyam": {"nip": "199308302025211114", "wa": "628131313131"},
    "Udin":   {"nip": "NIP. .....................", "wa": "628571234567"},
    "Rey":    {"nip": "NIP. .....................", "wa": "628991112223"},
    "Ferdi":  {"nip": "NIP. .....................", "wa": "628112223334"},
    "Ciptaningtyas": {"nip": "198208172010012016", "wa": "628123456789"}
}

LIST_IT = ["Isfan", "Teguh", "Jaka", "Hisyam", "Udin", "Rey", "Ferdi", "Ciptaningtyas"]

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

for folder in ["temp", "arsip_rme"]:
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
                  ttd_user_path TEXT, ip_address TEXT, rm_utama TEXT, pasien_display TEXT)''')
    c.execute("CREATE TABLE IF NOT EXISTS jadwal_it (nama TEXT, tanggal INTEGER, shift TEXT)")
    conn.commit()
    return conn

def update_jadwal_dari_pdf(file_pdf):
    """
    Update jadwal dari PDF dengan format sesuai file
    """
    try:
        with pdfplumber.open(file_pdf) as pdf:
            text = pdf.pages[0].extract_text()
            
            mapping_nama = {
                "Teguh Adi Pradana": "Teguh",
                "Jaka Gilang R": "Jaka", 
                "Ahmad Haerudin": "Udin",
                "Isfan Fajar Anugrah": "Isfan",
                "M. Hisyam Rizky": "Hisyam",
                "Ferdynasyah Zaelani": "Ferdi",
                "Reynold Marcelino": "Rey",
                "Ciptaningtyas": "Ciptaningtyas"
            }
            
            lines = text.split('\n')
            data_jadwal = []
            
            for line in lines:
                for nama_pdf, nama_singkat in mapping_nama.items():
                    if nama_pdf in line:
                        parts = line.split()
                        shifts = []
                        for part in parts:
                            if any(x in part for x in ['P','S','M','L','PS']):
                                shifts.append(part)
                        
                        for tgl in range(1, min(32, len(shifts) + 1)):
                            if tgl-1 < len(shifts):
                                shift = shifts[tgl-1].replace('-','').strip()
                                if shift:
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
# 3. SIDEBAR & NAVIGATION
# =========================================================
with st.sidebar:
    st.title("🏥 SIRS RME PRO")
    
    # Tampilkan status petugas di sidebar
    status_msg, petugas_list = get_status_petugas()
    if "✅" in status_msg:
        st.success(f"🟢 {status_msg}")
        with st.expander("👨‍💻 Petugas Aktif"):
            for p in petugas_list:
                st.write(f"• {p}")
    else:
        st.warning(f"🟡 {status_msg}")
    
    # Tampilkan ucapan kecil di sidebar
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
    
    if st.button("🔥 HAPUS SEMUA DATA TES"):
        conn = sqlite3.connect('rme_system.db'); c = conn.cursor()
        c.execute("DELETE FROM rme_tasks"); conn.commit(); conn.close()
        st.success("Database Bersih!")
    
    if 'is_it_authenticated' not in st.session_state: 
        st.session_state.is_it_authenticated = False
        st.session_state.it_logged_in = False
        st.session_state.it_nama = ""
    
    menu_umum = ["🏠 Dashboard Info", "📊 Monitor Antrian", "📝 Input Form"]
    
    if not st.session_state.is_it_authenticated:
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
        
        menu = st.radio("Pilih Halaman:", menu_umum + ["👨‍💻 Workspace IT", "📂 Arsip Digital", "📅 Dashboard Jadwal"])
        if st.button("Logout Admin"): 
            st.session_state.is_it_authenticated = False
            st.session_state.it_logged_in = False
            st.rerun()

# =========================================================
# 3.1 DASHBOARD INFO
# =========================================================
if menu == "🏠 Dashboard Info":
    tampilkan_banner_ucapan()
    
    st.markdown("""
        # 🏥 SIRS RME PRO 2026
        **Digitalisasi Layanan IT untuk Akurasi & Efisiensi RS**
        
        ---
        ### 🎯 Mengapa Sistem Ini Dibuat?
        Sistem ini adalah wujud dukungan Departemen IT untuk memudahkan rekan-rekan medis:
        
        * **🚀 Sat-Set:** Pengajuan langsung masuk ke sistem monitor IT secara real-time
        * **📄 Paperless:** Dokumen PDF terbit otomatis
        * **📲 Notifikasi WA:** Terhubung dengan WhatsApp petugas IT piket
        * **⚖️ Akurat:** Legalitas dengan NIP dan Waktu sistematis
        
        ### 👨‍💻 Pesan IT Support
        > *"Kami ingin Anda fokus pada pelayanan pasien, biar urusan sistem kami yang mudahkan."*
        
        ---
        **Status Sistem:** ✅ Beroperasi Normal
    """)
    
    st.divider()
    st.subheader("📋 Status Petugas IT Hari Ini")
    status_msg, petugas_list = get_status_petugas()
    
    if petugas_list:
        st.success(f"✅ Petugas IT Aktif: {', '.join(petugas_list)}")
        for p in petugas_list:
            st.info(f"👨‍💻 {p} - Siap melayani")
    else:
        st.warning(f"⚠️ {status_msg}")
    
    st.info("💡 Klik menu **📝 Input Form** untuk mulai mengajukan.")

# =========================================================
# 4. MONITOR ANTRIAN
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
# 5. INPUT FORM
# =========================================================
elif menu == "📝 Input Form":
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
        u_nama = c1.text_input("Nama Pemohon")
        u_unit = c2.text_input("Unit/Ruangan")
        u_nip = c1.text_input("NIP Pemohon")
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
                
                db = init_db()
                db.execute('''INSERT INTO rme_tasks 
                              (unit, data_pasien, status, file_name, waktu_input, 
                               pemohon, nip_user, it_executor, ttd_user_path, rm_utama, pasien_display) 
                              VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                            (u_unit, json.dumps(st.session_state.data_p), "Masuk Antrian", f"HAPUS_RME_{rm_utama}.docx", 
                             jam_sekarang_wib, u_nama, u_nip, u_it, path_ttd, rm_utama, nama_utama))
                db.commit()
                db.close()

                it_info = MAPPING_IT_DETAIL.get(u_it, {"wa": "628123456789"})
                pesan = f"Halo Mas {u_it}, saya {u_nama} dari {u_unit} baru saja mengirim pengajuan RME untuk pasien {nama_utama}. Mohon dibantu proses ya. Terima kasih!"
                st.session_state.url_wa = f"https://wa.me/{it_info['wa']}?text={urllib.parse.quote(pesan)}"
                st.session_state.form_done = True
                st.rerun()
            else: 
                st.error("Mohon tanda tangan pemohon!")

        if st.session_state.get('form_done'):
            st.success("✅ Pengajuan Berhasil Terkirim ke Sistem Monitor IT!")
            st.link_button("📲 HUBUNGI IT VIA WHATSAPP", st.session_state.url_wa)
            if st.button("Isi Form Baru"):
                st.session_state.clear()
                st.rerun()

# =========================================================
# 6. WORKSPACE IT
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
                                    
                                    # Data pasien
                                    data_pasien = json.loads(t[2])
                                    for i, ps in enumerate(data_pasien, 1):
                                        context[f'nama{i}'] = ps.get('nama', '')
                                        context[f'rm{i}'] = ps.get('rm', '')
                                        context[f'tgl{i}'] = get_now_jakarta().strftime("%d-%m-%Y")
                                        context[f'alasan{i}'] = ps.get('alasan', '')
                                    
                                    doc.render(context)
                                    docx_path = f"arsip_rme/{t[14]}_{t[13]}.docx"
                                    doc.save(docx_path)
                                    
                                    # Konversi ke PDF
                                    convert_to_pdf(docx_path, "arsip_rme")
                                    
                                    db.execute("""
                                        UPDATE rme_tasks 
                                        SET status='Selesai', waktu_selesai=?, nip_it=? 
                                        WHERE id=?
                                    """, (waktu_selesai, MAPPING_IT_DETAIL[st.session_state.it_nama]['nip'], t[0]))
                                    db.commit()
                                    
                                    st.success(f"✅ Tiket #{t[0]} Selesai!")
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
# 7. ARSIP DIGITAL
# =========================================================
elif menu == "📂 Arsip Digital":
    st.header("📂 Arsip Hasil Eksekusi")
    
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
# 8. DASHBOARD JADWAL
# =========================================================
elif menu == "📅 Dashboard Jadwal":
    st.header("📅 Pengaturan Jadwal IT")
    
    ucapan = get_ucapan_spesial()
    st.markdown(f"📌 *{ucapan['judul']}*")
    
    with st.container(border=True):
        pdf_file = st.file_uploader("Upload PDF Jadwal Baru", type="pdf")
        if st.button("🔄 Update Database Jadwal"):
            if pdf_file and update_jadwal_dari_pdf(pdf_file):
                st.success("✅ Database Jadwal Berhasil Diperbarui!")
                time.sleep(1)
                st.rerun()
            else: 
                st.error("Format PDF tidak sesuai atau Gagal proses.")
    
    st.divider()
    
    db = init_db()
    df_v = pd.read_sql_query("SELECT * FROM jadwal_it ORDER BY tanggal ASC", db)
    
    if not df_v.empty:
        t_skrg = get_now_jakarta().day
        t_pilih = st.slider("Cek Petugas Tanggal:", 1, 31, t_skrg)
        
        df_filter = df_v[df_v['tanggal'] == t_pilih].copy()
        
        tanggal_besar = [(1,1), (25,1), (10,2), (11,3), (10,4), (1,5), (2,5), (17,8), (25,12)]
        bulan_ini = get_now_jakarta().month
        if (t_pilih, bulan_ini) in tanggal_besar:
            st.warning("⚠️ Tanggal ini termasuk hari besar nasional!")
        
        if not df_filter.empty:
            st.dataframe(df_filter, use_container_width=True)
        else:
            st.info(f"Tidak ada jadwal untuk tanggal {t_pilih}")
    else:
        st.info("📅 Belum ada jadwal. Silakan upload PDF jadwal terlebih dahulu.")
    
    db.close()
