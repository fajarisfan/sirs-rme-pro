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
# 0. FUNGSI UCAPAN HARI BESAR OTOMATIS
# =========================================================
def get_hari_besar_ucapan():
    """
    Mendeteksi hari besar nasional/keagamaan dan mengembalikan ucapan yang sesuai
    """
    now = get_now_jakarta()
    tanggal = now.date()
    bulan = now.month
    hari = now.day
    tahun = now.year
    
    # Dictionary hari besar tetap (tanggal tetap setiap tahun)
    hari_besar_tetap = {
        (1, 1): ("🎉 Selamat Tahun Baru Masehi 2026", "Tahun baru, semangat baru dalam pelayanan!"),
        (1, 25): ("🕯️ Selamat Isra Mi'raj 1447 H", "Semoga hikmah perjalanan Rasulullah menginspirasi kita"),
        (2, 10): ("✨ Selamat Tahun Baru Imlek 2577", "Gong Xi Fa Cai, semoga keberuntungan menyertai"),
        (2, 18): ("🕊️ Selamat Isra Mikraj", "Mari tingkatkan kualitas ibadah"),
        (3, 11): ("🌙 Selamat Menjalankan Ibadah Puasa Ramadhan 1447 H", "Marhaban ya Ramadhan, mohon maaf lahir dan batin"),
        (3, 31): ("🌙 Nuzulul Qur'an", "Malam penuh berkah, perbanyak membaca Al-Qur'an"),
        (4, 10): ("🕌 Selamat Hari Raya Idul Fitri 1447 H", "Minal aidin wal faizin, mohon maaf lahir dan batin"),
        (4, 11): ("🕌 Selamat Hari Raya Idul Fitri 1447 H", "Kembali ke fitri, saling memaafkan"),
        (5, 1): ("💪 Selamat Hari Buruh Internasional", "Apresiasi untuk para pekerja kesehatan"),
        (5, 2): ("☸️ Selamat Hari Raya Waisak 2569", "Semoga kedamaian selalu menyertai"),
        (5, 21): ("✝️ Selamat Kenaikan Yesus Kristus", "Damai Kristus menyertai kita semua"),
        (6, 1): ("🇮🇩 Selamat Hari Lahir Pancasila", "Bersama Pancasila kita maju"),
        (6, 17): ("🕌 Selamat Hari Raya Idul Adha 1447 H", "Semoga berkurban membawa keberkahan"),
        (7, 7): ("🌙 Tahun Baru Islam 1448 H", "Hijrah menuju lebih baik"),
        (8, 17): ("🇮🇩 Dirgahayu Republik Indonesia ke-81", "Indonesia maju, kesehatan prima"),
        (9, 16): ("🕋 Maulid Nabi Muhammad SAW", "Teladani akhlak Rasulullah"),
        (10, 5): ("🇮🇩 Selamat Hari Ulang Tahun TNI", "TNI kebanggaan rakyat"),
        (10, 28): ("🇮🇩 Selamat Hari Sumpah Pemuda", "Bersatu kita teguh"),
        (11, 10): ("🇮🇩 Selamat Hari Pahlawan", "Teladani semangat pahlawan"),
        (12, 25): ("🎄 Selamat Hari Raya Natal 2026", "Damai Natal menyertai kita semua"),
        (12, 26): ("🎄 Selamat Hari Raya Natal 2026", "Kasih Natal untuk semua")
    }
    
    # Cek hari besar tetap
    if (bulan, hari) in hari_besar_tetap:
        return hari_besar_tetap[(bulan, hari)]
    
    # Cek hari Jumat (ucapan khusus Jumat)
    if now.weekday() == 4:  # Jumat
        return ("🤲 Jumat Berkah", "Semoga hari penuh keberkahan untuk kita semua")
    
    # Cek akhir pekan (Sabtu-Minggu)
    if now.weekday() in [5, 6]:  # Sabtu atau Minggu
        return ("🎊 Selamat Akhir Pekan", "Istirahat yang cukup, tetap semangat melayani")
    
    # Cek tanggal cantik (misal 11.11, 22.22 dll)
    if str(hari) == str(bulan) * 2 and hari <= 31 and bulan <= 12:
        return (f"✨ Selamat Hari {hari}.{bulan}", "Semoga keberuntungan menyertai")
    
    # Default: ucapan semangat biasa
    if 5 <= now.hour < 12:
        return ("🌅 Selamat Pagi", "Semoga hari ini penuh semangat dalam melayani")
    elif 12 <= now.hour < 15:
        return ("🌤️ Selamat Siang", "Tetap produktif dan sehat selalu")
    elif 15 <= now.hour < 18:
        return ("🌆 Selamat Sore", "Jangan lupa istirahat sejenak")
    else:
        return ("🌃 Selamat Malam", "Terima kasih atas dedikasi hari ini")

def tampilkan_banner_ucapan():
    """
    Menampilkan banner ucapan di dashboard
    """
    judul_ucapan, deskripsi_ucapan = get_hari_besar_ucapan()
    
    # Warna berbeda untuk tipe hari besar
    if "Fitri" in judul_ucapan or "Natal" in judul_ucapan or "Tahun Baru" in judul_ucapan:
        bg_color = "linear-gradient(90deg, #FFD700 0%, #FFA500 100%)"
        emoji = "🎉"
    elif "Ramadhan" in judul_ucapan:
        bg_color = "linear-gradient(90deg, #2E8B57 0%, #228B22 100%)"
        emoji = "🌙"
    elif "Jumat" in judul_ucapan:
        bg_color = "linear-gradient(90deg, #4B0082 0%, #800080 100%)"
        emoji = "🤲"
    else:
        bg_color = "linear-gradient(90deg, #1E90FF 0%, #00BFFF 100%)"
        emoji = "⭐"
    
    # Hitung hari spesial yang akan datang
    hari_spesial_terdekat = cek_hari_besar_terdekat()
    
    banner_html = f"""
    <div style="
        background: {bg_color};
        padding: 15px 25px;
        border-radius: 15px;
        margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        border-left: 8px solid white;
        animation: pulse 2s infinite;
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
            <div style="display: flex; align-items: center; gap: 15px;">
                <span style="font-size: 48px;">{emoji}</span>
                <div>
                    <h2 style="color: white; margin: 0; font-size: 28px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);">
                        {judul_ucapan}
                    </h2>
                    <p style="color: white; margin: 5px 0 0 0; font-size: 18px; opacity: 0.95;">
                        {deskripsi_ucapan}
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
                {get_now_jakarta().strftime("%d %B %Y")}
            </div>
        </div>
        {f'<div style="margin-top: 10px; padding-top: 10px; border-top: 2px dashed rgba(255,255,255,0.5); color: white; font-size: 16px;">{hari_spesial_terdekat}</div>' if hari_spesial_terdekat else ''}
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

def cek_hari_besar_terdekat():
    """
    Mengecek hari besar apa yang akan datang dalam waktu dekat
    """
    now = get_now_jakarta()
    tanggal_sekarang = now.date()
    tahun = now.year
    
    # Daftar hari besar dengan tanggal perkiraan
    hari_besar_mendatang = [
        (datetime(tahun, 3, 1).date(), "Awal Ramadhan (perkiraan)"),
        (datetime(tahun, 4, 10).date(), "Idul Fitri (perkiraan)"),
        (datetime(tahun, 6, 17).date(), "Idul Adha (perkiraan)"),
        (datetime(tahun, 8, 17).date(), "HUT RI ke-81"),
        (datetime(tahun, 12, 25).date(), "Hari Natal")
    ]
    
    for tgl, nama in hari_besar_mendatang:
        selisih = (tgl - tanggal_sekarang).days
        if 0 < selisih <= 14:  # 2 minggu ke depan
            if selisih == 1:
                return f"⏰ Besok: {nama}"
            elif selisih <= 7:
                return f"⏰ {selisih} hari lagi: {nama}"
    
    return ""

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
    "Ferdi":  {"nip": "NIP. .....................", "wa": "628112223334"}
}

LIST_IT = list(MAPPING_IT_DETAIL.keys())

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
    try:
        with pdfplumber.open(file_pdf) as pdf:
            table = pdf.pages[0].extract_table()
            mapping_nama_pdf = {
                "Teguh Adi Pradana": "Teguh", "Jaka Gilang R": "Jaka",
                "Ahmad Haerudin": "Udin", "Isfan Fajar Anugrah": "Isfan",
                "M. Hisyam Rizky": "Hisyam", "Ferdyansyah Zaelani": "Ferdi",
                "Reynold": "Rey"
            }
            data_jadwal = []
            for row in table:
                if not row[1]: continue
                nama_full = str(row[1]).replace('\n', ' ')
                for key_pdf, nama_singkat in mapping_nama_pdf.items():
                    if key_pdf.lower() in nama_full.lower():
                        for tgl in range(1, 32):
                            col_idx = tgl + 1
                            if col_idx < len(row) and row[col_idx]:
                                shift = str(row[col_idx]).replace('\n', '').strip().upper()
                                data_jadwal.append({"nama": nama_singkat, "tanggal": tgl, "shift": shift})
            if data_jadwal:
                db = init_db()
                pd.DataFrame(data_jadwal).to_sql('jadwal_it', db, if_exists='replace', index=False)
                db.commit(); db.close()
                return True
    except: return False
    return False

def get_it_aktif_sekarang():
    try:
        now = get_now_jakarta()
        tgl_ini, tgl_kmrn, jam_ini = now.day, (now - timedelta(days=1)).day, now.hour
        db = init_db()
        df = pd.read_sql_query(f"SELECT * FROM jadwal_it WHERE tanggal IN ({tgl_kmrn}, {tgl_ini})", db)
        db.close()
        petugas_on = []
        if df.empty: return ["⚠️ Database Kosong"]
        for _, row in df.iterrows():
            nama, s, tgl_data = row['nama'], str(row['shift']).upper().strip(), int(row['tanggal'])
            if "M" in s:
                if (tgl_data == tgl_kmrn and jam_ini < 7) or (tgl_data == tgl_ini and jam_ini >= 21):
                    petugas_on.append(nama)
            elif ("P" in s or "PS" in s) and tgl_data == tgl_ini:
                if 7 <= jam_ini < 16: petugas_on.append(nama)
            elif s == "S" and tgl_data == tgl_ini:
                limit = 22 if "HISYAM" in nama.upper() else 21
                if 14 <= jam_ini < limit: petugas_on.append(nama)
        return sorted(list(set(petugas_on))) if petugas_on else ["Tidak ada petugas standby"]
    except: return ["⚠️ Error Jadwal"]

# =========================================================
# 3. SIDEBAR & NAVIGATION
# =========================================================
with st.sidebar:
    st.title("🏥 SIRS RME PRO")
    
    # Tampilkan ucapan kecil di sidebar
    judul, _ = get_hari_besar_ucapan()
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
        {judul}
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🔥 HAPUS SEMUA DATA TES"):
        conn = sqlite3.connect('rme_system.db'); c = conn.cursor()
        c.execute("DELETE FROM rme_tasks"); conn.commit(); conn.close()
        st.success("Database Bersih!")
    
    if 'is_it_authenticated' not in st.session_state: st.session_state.is_it_authenticated = False
    
    menu_umum = ["🏠 Dashboard Info", "📊 Monitor Antrian", "📝 Input Form"]
    
    if not st.session_state.is_it_authenticated:
        with st.expander("🔑 IT LOGIN"):
            pin = st.text_input("PIN Admin IT:", type="password")
            if st.button("Masuk"):
                if pin == "1234": st.session_state.is_it_authenticated = True; st.rerun()
                else: st.error("PIN Salah!")
        menu = st.radio("Pilih Halaman:", menu_umum)
    else:
        st.success("✅ Mode IT Aktif")
        menu = st.radio("Pilih Halaman:", menu_umum + ["👨‍💻 Workspace IT", "📂 Arsip Digital", "📅 Dashboard Jadwal"])
        if st.button("Logout Admin"): st.session_state.is_it_authenticated = False; st.rerun()

# =========================================================
# 3.1 DASHBOARD INFO (DENGAN UCAPAN)
# =========================================================
if menu == "🏠 Dashboard Info":
    # Tampilkan banner ucapan di atas dashboard
    tampilkan_banner_ucapan()
    
    st.markdown("""
        # 🏥 SIRS RME PRO 2026
        **Digitalisasi Layanan IT untuk Akurasi & Efisiensi RS**
        
        ---
        ### 🎯 Mengapa Sistem Ini Dibuat?
        Sistem ini adalah wujud dukungan Departemen IT untuk memudahkan rekan-rekan medis dalam proses administrasi pembatalan RME:
        
        * **🚀 Sat-Set:** Pengajuan langsung masuk ke sistem monitor IT secara real-time.
        * **📄 Paperless:** Tidak perlu lagi berkas fisik, dokumen PDF terbit otomatis.
        * **📲 Notifikasi WA:** Terhubung langsung dengan nomor WhatsApp petugas IT yang sedang piket.
        * **⚖️ Akurat:** Legalitas terjamin dengan pencatatan NIP dan Waktu yang sistematis.
        
        ### 👨‍💻 Pesan IT Support
        > *"Kami ingin Anda fokus pada pelayanan pasien, biar urusan sistem kami yang mudahkan."*
        
        ---
        **Status Sistem:** ✅ Beroperasi Normal
    """)
    
    # Tambahkan informasi hari besar yang akan datang
    with st.expander("📅 Kalender Hari Besar 2026", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            **Januari - Maret**
            - 1 Jan: Tahun Baru Masehi
            - 25 Jan: Isra Mi'raj
            - 10 Feb: Tahun Baru Imlek
            - 11 Mar: Awal Ramadhan
            - 31 Mar: Nuzulul Qur'an
            """)
        with col2:
            st.markdown("""
            **April - Desember**
            - 10 Apr: Idul Fitri
            - 1 Mei: Hari Buruh
            - 2 Mei: Waisak
            - 17 Agu: HUT RI ke-81
            - 25 Des: Natal
            """)
    
    st.info("💡 Klik menu **📝 Input Form** untuk mulai mengajukan.")

# =========================================================
# 4. MONITOR ANTRIAN (PERBAIKAN WARNA UNTUK DARK/LIGHT MODE)
# =========================================================
elif menu == "📊 Monitor Antrian":
    # Tampilkan ucapan kecil di monitor
    judul, desk = get_hari_besar_ucapan()
    st.info(f"📌 {judul} - {desk}")
    
    st_autorefresh(5000)
    st.header("📊 Monitor Antrian Real-Time")
    db = init_db()
    df = pd.read_sql_query("SELECT id, waktu_input, pasien_display, it_executor, status, unit FROM rme_tasks ORDER BY id DESC LIMIT 9", db)
    db.close()

    if not df.empty:
        cols = st.columns(3)
        for index, row in df.iterrows():
            with cols[index % 3]:
                # Logika Warna & Label dengan warna yang aman untuk dark/light mode
                if row['status'] == "Masuk Antrian":
                    bg = "#FFE5E5"  # Pink muda (aman)
                    border = "#FF4444"  # Merah
                    lbl = "🔴 Menunggu IT"
                    text_color = "#000000"  # Hitam untuk teks
                elif row['status'] == "Menunggu":
                    bg = "#FFF4E0"  # Krem (aman)
                    border = "#FFA500"  # Oranye
                    lbl = "🟡 Sedang Diproses"
                    text_color = "#000000"
                else:
                    bg = "#E5FFEA"  # Hijau muda (aman)
                    border = "#4CAF50"  # Hijau
                    lbl = "🟢 Selesai"
                    text_color = "#000000"
                
                # Tambahkan CSS untuk memastikan teks selalu terbaca
                st.markdown(f"""
                <div style="
                    background-color: {bg};
                    padding: 15px;
                    border-radius: 10px;
                    border-left: 5px solid {border};
                    margin-bottom: 15px;
                    box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
                ">
                    <div style="display:flex; justify-content:space-between; color: {text_color};">
                        <small><b>Tiket #{row['id']}</b></small>
                        <small>{row['waktu_input']}</small>
                    </div>
                    <div style="margin:10px 0; color: {text_color};">
                        <div style="font-size:18px; font-weight:bold;">{row['pasien_display']}</div>
                        <div style="font-size:14px;">Unit: {row['unit']}</div>
                    </div>
                    <div style="border-top:1px solid #ccc; padding-top:5px; font-size:13px; color: {text_color};">
                        Petugas IT: <b>{row['it_executor']}</b>
                    </div>
                    <div style="margin-top:10px; text-align:center; font-weight:bold; font-size:14px; color: {text_color};">
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
    # Tampilkan ucapan motivasi di form
    judul, desk = get_hari_besar_ucapan()
    st.success(f"✨ {judul} - {desk}")
    
    st.header("📝 Form Penghapusan RME")
    if 'step' not in st.session_state: st.session_state.step = 1
    if 'data_p' not in st.session_state: st.session_state.data_p = []
    
    petugas_ready = get_it_aktif_sekarang()

    with st.expander("👤 Identitas Pemohon", expanded=True):
        c1, c2 = st.columns(2)
        u_nama, u_unit = c1.text_input("Nama Pemohon"), c2.text_input("Unit/Ruangan")
        u_nip = c1.text_input("NIP Pemohon")
        u_it = c2.selectbox("Kirim ke Petugas IT Piket:", petugas_ready if "⚠️" not in petugas_ready[0] else LIST_IT)

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
                    st.session_state.step += 1; st.rerun()
                else: st.error("Data Belum Lengkap!")
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
                db.execute('''INSERT INTO rme_tasks (unit, data_pasien, status, file_name, waktu_input, 
                              pemohon, nip_user, it_executor, ttd_user_path, rm_utama, pasien_display) 
                              VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                            (u_unit, json.dumps(st.session_state.data_p), "Masuk Antrian", f"HAPUS_RME_{rm_utama}.docx", 
                             jam_sekarang_wib, u_nama, u_nip, u_it, path_ttd, rm_utama, nama_utama))
                db.commit(); db.close()

                # LOGIKA WA OTOMATIS
                it_info = MAPPING_IT_DETAIL.get(u_it, {"wa": "628123456789"})
                pesan = f"Halo Mas {u_it}, saya {u_nama} dari {u_unit} baru saja mengirim pengajuan RME untuk pasien {nama_utama}. Mohon dibantu proses ya. Terima kasih!"
                st.session_state.url_wa = f"https://wa.me/{it_info['wa']}?text={urllib.parse.quote(pesan)}"
                st.session_state.form_done = True
                st.rerun()
            else: st.error("Mohon tanda tangan pemohon!")

        if st.session_state.get('form_done'):
            st.success("✅ Pengajuan Berhasil Terkirim ke Sistem Monitor IT!")
            st.link_button("📲 HUBUNGI IT VIA WHATSAPP", st.session_state.url_wa)
            if st.button("Isi Form Baru"):
                st.session_state.clear(); st.rerun()

# =========================================================
# 6. WORKSPACE IT (HANYA MENAMPILKAN TUGAS UNTUK IT YANG DIPILIH)
# =========================================================
elif menu == "👨‍💻 Workspace IT":
    # Tampilkan ucapan khusus IT
    judul, desk = get_hari_besar_ucapan()
    if "Fitri" in judul or "Natal" in judul:
        st.balloons()
    st.info(f"💻 {judul} - {desk}")
    
    st_autorefresh(5000)
    st.header("👨‍💻 Workspace Eksekusi IT")
    
    # PILIH IDENTITAS IT - INI YAKAN MENENTUKAN TUGAS YANG TAMPIL
    it_nama = st.selectbox("🔑 Pilih Identitas Anda (Hanya tugas untuk Anda yang akan tampil):", LIST_IT, key="it_identity")
    
    db = init_db()
    
    # AMBIL SEMUA TUGAS DENGNA FILTER KETAT: HANYA UNTUK IT YANG DIPILIH DAN STATUS SESUAI
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
    tasks = db.execute(query, (it_nama,)).fetchall()
    
    # BUAT RINGKASAN CEPAT
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
        st.success(f"🎯 **{it_nama}**, Anda memiliki {len(tasks)} tugas yang perlu diproses!")
        
        # GROUP TUGAS BERDASARKAN STATUS
        for status_group in ["Masuk Antrian", "Menunggu"]:
            group_tasks = [t for t in tasks if t[3] == status_group]
            
            if group_tasks:
                status_label = "📥 MENUNGGU DITERIMA" if status_group == "Masuk Antrian" else "⚙️ SEDANG DIPROSES"
                st.subheader(f"{status_label} ({len(group_tasks)})")
                
                for t in group_tasks:
                    # t[14] adalah pasien_display, t[0] adalah ID Tiket
                    with st.expander(f"🎫 Tiket #{t[0]} - {t[14]} ({t[1]})", expanded=True):
                        col_info1, col_info2 = st.columns(2)
                        with col_info1:
                            st.markdown(f"**👤 Pemohon:** {t[7]}")
                            st.markdown(f"**🆔 NIP:** {t[8]}")
                            st.markdown(f"**⏰ Masuk:** {t[5]}")
                        with col_info2:
                            st.markdown(f"**🏥 Unit:** {t[1]}")
                            st.markdown(f"**📋 Status:** {t[3]}")
                        
                        # Tombol Terima Tugas (hanya untuk status Masuk Antrian)
                        if t[3] == "Masuk Antrian":
                            if st.button(f"✅ Terima & Proses Tiket #{t[0]}", key=f"acc_{t[0]}", use_container_width=True):
                                db.execute("UPDATE rme_tasks SET status='Menunggu' WHERE id=?", (t[0],))
                                db.commit()
                                st.rerun()
                        
                        # Form Penyelesaian (hanya untuk status Menunggu)
                        elif t[3] == "Menunggu":
                            st.warning("⚠️ Silakan proses penghapusan di sistem, lalu tandatangani untuk menyelesaikan.")
                            
                            # Tampilkan data pasien
                            with st.container(border=True):
                                st.caption("📋 DATA PASIEN")
                                try:
                                    data_pasien = json.loads(t[2])
                                    for i, ps in enumerate(data_pasien, 1):
                                        st.markdown(f"**{i}. {ps.get('nama', '-')}** (RM: {ps.get('rm', '-')})")
                                        st.caption(f"   Alasan: {ps.get('alasan', '-')}")
                                except:
                                    st.info("Data pasien tidak tersedia")
                            
                            # Canvas untuk TTD IT
                            can_it = st_canvas(
                                stroke_width=3, 
                                stroke_color="#000000", 
                                background_color="#FFFFFF", 
                                height=150, 
                                width=400, 
                                key=f"it_can_{t[0]}"
                            )
                            
                            if st.button(f"✅ Selesaikan & Cetak Berita Acara #{t[0]}", type="primary", key=f"fin_{t[0]}", use_container_width=True):
                                if can_it.image_data is not None:
                                    # Simpan TTD IT
                                    ttd_path = f"temp/ttd_it_{t[0]}_{datetime.now().strftime('%H%M%S')}.png"
                                    Image.fromarray(can_it.image_data.astype('uint8')).save(ttd_path)
                                    
                                    # Update status dan waktu selesai
                                    waktu_selesai = get_now_jakarta().strftime("%H:%M")
                                    db.execute("""
                                        UPDATE rme_tasks 
                                        SET status='Selesai', waktu_selesai=?, nip_it=? 
                                        WHERE id=?
                                    """, (waktu_selesai, MAPPING_IT_DETAIL[it_nama]['nip'], t[0]))
                                    db.commit()
                                    
                                    st.success(f"✅ Tiket #{t[0]} Selesai!")
                                    st.balloons()
                                    time.sleep(2)
                                    st.rerun()
                                else:
                                    st.error("Harap tanda tangan terlebih dahulu!")
    else:
        # Tampilan kalau tidak ada tugas untuk IT yang dipilih
        st.info(f"🎉 Selamat **{it_nama}**, tidak ada tugas untuk Anda saat ini. Silakan istirahat sejenak atau cek lagi nanti.")
        
        # Tampilkan history tugas yang sudah selesai (opsional)
        with st.expander("📜 Lihat Riwayat Tugas Selesai"):
            history_query = """
                SELECT * FROM rme_tasks 
                WHERE it_executor = ? AND status='Selesai' 
                ORDER BY id DESC LIMIT 5
            """
            history = db.execute(history_query, (it_nama,)).fetchall()
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
    
    # Filter berdasarkan IT
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
                
                # Gunakan warna teks yang aman
                c1.markdown(f"**{r['pasien_display']}**")
                c1.caption(f"No. RM: {r['rm_utama']}")
                
                c2.write(f"💻 IT: {r['it_executor']}")
                c2.caption(f"Selesai: {r['waktu_selesai']}")
                
                # Nama file
                nama_file_fix = f"{r['pasien_display']}_{r['rm_utama']}.docx"
                f_docx = f"arsip_rme/{nama_file_fix}"
                f_pdf = f_docx.replace(".docx", ".pdf")
                
                # Cek keberadaan file
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
    
    db.close()

# =========================================================
# 8. DASHBOARD JADWAL
# =========================================================
elif menu == "📅 Dashboard Jadwal":
    st.header("📅 Pengaturan Jadwal IT")
    
    # Tampilkan info hari besar di jadwal
    judul, _ = get_hari_besar_ucapan()
    st.markdown(f"📌 *{judul}*")
    
    with st.container(border=True):
        pdf_file = st.file_uploader("Upload PDF Jadwal Baru", type="pdf")
        if st.button("🔄 Update Database Jadwal"):
            if pdf_file and update_jadwal_dari_pdf(pdf_file):
                st.success("✅ Database Jadwal Berhasil Diperbarui!"); time.sleep(1); st.rerun()
            else: st.error("Format PDF tidak sesuai atau Gagal proses.")
    
    st.divider()
    db = init_db()
    df_v = pd.read_sql_query("SELECT * FROM jadwal_it ORDER BY tanggal ASC", db)
    if not df_v.empty:
        t_skrg = get_now_jakarta().day
        t_pilih = st.slider("Cek Petugas Tanggal:", 1, 31, t_skrg)
        
        # Filter berdasarkan tanggal
        df_filter = df_v[df_v['tanggal'] == t_pilih].copy()
        
        # Tandai jika tanggal termasuk hari besar
        tanggal_besar = [(1,1), (25,1), (10,2), (11,3), (10,4), (1,5), (2,5), (17,8), (25,12)]
        bulan_ini = get_now_jakarta().month
        if (t_pilih, bulan_ini) in tanggal_besar:
            st.warning("⚠️ Tanggal ini termasuk hari besar nasional!")
        
        if not df_filter.empty:
            st.dataframe(df_filter, use_container_width=True)
        else:
            st.info(f"Tidak ada jadwal untuk tanggal {t_pilih}")
    db.close()
