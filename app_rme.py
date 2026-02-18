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
# 3.1 DASHBOARD INFO
# =========================================================
if menu == "🏠 Dashboard Info":
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
    st.info("💡 Klik menu **📝 Input Form** untuk mulai mengajukan.")
# =========================================================
# 4. MONITOR ANTRIAN (STYLE TIKET)
# =========================================================
elif menu == "📊 Monitor Antrian":
    st_autorefresh(5000)
    st.header("📊 Monitor Antrian Real-Time")
    db = init_db()
    df = pd.read_sql_query("SELECT id, waktu_input, pasien_display, it_executor, status, unit FROM rme_tasks ORDER BY id DESC LIMIT 9", db)
    db.close()

    if not df.empty:
        cols = st.columns(3)
        for index, row in df.iterrows():
            with cols[index % 3]:
                # Logika Warna & Label
                if row['status'] == "Masuk Antrian":
                    bg, lbl = "#FFE5E5", "🔴 Menunggu IT"
                elif row['status'] == "Menunggu":
                    bg, lbl = "#FFF4E0", "🟡 Sedang Diproses"
                else:
                    bg, lbl = "#E5FFEA", "🟢 Selesai"
                    
                st.markdown(f"""
<div style="background-color:{bg}; padding:15px; border-radius:10px; border-left: 5px solid #333; margin-bottom:15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); color: #000000 !important;">
    <div style="display:flex; justify-content:space-between; color: #000000 !important;">
        <small style="color: #000000 !important;"><b>Tiket #{row['id']}</b></small>
        <small style="color: #000000 !important;">{row['waktu_input']}</small>
    </div>
    <div style="margin:10px 0; color: #000000 !important;">
        <div style="font-size:18px; font-weight:bold; color: #000000 !important;">{row['pasien_display']}</div>
        <div style="font-size:14px; color: #000000 !important;">Unit: {row['unit']}</div>
    </div>
    <div style="border-top:1px solid #999; padding-top:5px; font-size:13px; color: #000000 !important;">
        Petugas IT: <b style="color: #000000 !important;">{row['it_executor']}</b>
    </div>
    <div style="margin-top:10px; text-align:center; font-weight:bold; font-size:14px; color: #000000 !important;">{lbl}</div>
</div>
""", unsafe_allow_html=True)
    else:
        st.info("Belum ada antrian saat ini.")

# =========================================================
# 5. INPUT FORM
# =========================================================
elif menu == "📝 Input Form":
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

# # =========================================================
# 6. WORKSPACE IT
# =========================================================
elif menu == "👨‍💻 Workspace IT":
    st_autorefresh(5000)
    st.header("👨‍💻 Workspace Eksekusi IT")
    
    # Ambil daftar petugas yang sedang ON sesuai jadwal
    petugas_on = get_it_aktif_sekarang()
    options_it = petugas_on if "⚠️" not in petugas_on[0] else LIST_IT
    
    # Pemilihan Petugas
    it_nama = st.selectbox("Konfirmasi Identitas Anda:", options_it)
    
    db = init_db()
    # LOGIKA FILTER: Hanya ambil tugas yang it_executor-nya sesuai dengan yang dipilih di selectbox
    tasks = db.execute("SELECT * FROM rme_tasks WHERE status IN ('Masuk Antrian', 'Menunggu') AND it_executor = ?", (it_nama,)).fetchall()
    
    if tasks:
        play_notification()
        for t in tasks:
            with st.expander(f"📥 Tiket #{t[0]} - {t[14]}", expanded=True):
                st.write(f"Unit: **{t[1]}** | Pemohon: **{t[7]}**")
                
                # JIKA STATUS MASIH BARU -> TERIMA DULU
                if t[3] == "Masuk Antrian":
                    if st.button(f"Terima Tugas {t[0]}", key=f"acc_{t[0]}"):
                        db.execute("UPDATE rme_tasks SET status='Menunggu' WHERE id=?", (t[0],))
                        db.commit(); st.rerun()
                
                # JIKA STATUS SUDAH DITERIMA -> PROSES SELESAI
                elif t[3] == "Menunggu":
                    st.warning("⚠️ Sedang diproses... Silakan lengkapi tanda tangan IT untuk menutup tiket.")
                    can_it = st_canvas(stroke_width=3, stroke_color="#000", background_color="#fff", height=150, width=400, key=f"it_{t[0]}")
                    
                    if st.button(f"Selesaikan & Generate Dokumen #{t[0]}", type="primary", key=f"fin_{t[0]}"):
                        # 1. Logic Waktu Indo
                        now = get_now_jakarta()
                        hari_map = {'Monday': 'Senin', 'Tuesday': 'Selasa', 'Wednesday': 'Rabu', 'Thursday': 'Kamis', 'Friday': 'Jumat', 'Saturday': 'Sabtu', 'Sunday': 'Minggu'}
import streamlit as st
import streamlit.components.v1 as components
from streamlit_drawable_canvas import st_canvas
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Inches
import sqlite3, os, json, pandas as pd
from datetime import datetime, timedelta
from PIL import Image
from streamlit_autorefresh import st_autorefresh
import pdfplumber
import time
import pytz 
import subprocess
import urllib.parse

# =========================================================
# 1. CORE CONFIG & FUNCTIONS
# =========================================================
st.set_page_config(page_title="SIRS RME Pro 2026", layout="wide", page_icon="🏥")

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

def get_now_jakarta():
    return datetime.now(pytz.timezone('Asia/Jakarta'))

# --- LOGIC HARI BESAR OTOMATIS ---
def get_ucapan_hari_besar():
    now = get_now_jakarta()
    tgl_bln = now.strftime("%d-%m") # Format: Tanggal-Bulan
    
    # Ucapan default
    ucapan = {"judul": "Selamat Bekerja!", "pesan": "Semoga pelayanan hari ini berjalan lancar.", "warna": "#2e7d32"}
    
    # Kalender Hari Besar (Bisa ditambahin sendiri)
    events = {
        "01-01": {"judul": "Selamat Tahun Baru 2026!", "pesan": "Semangat baru untuk pelayanan yang lebih baik.", "warna": "#1565c0"},
        "17-08": {"judul": "Dirgahayu Republik Indonesia!", "pesan": "Merdeka dalam digitalisasi pelayanan kesehatan.", "warna": "#c62828"},
        "25-12": {"judul": "Selamat Hari Natal!", "pesan": "Damai dan sukacita menyertai kita semua.", "warna": "#2e7d32"},
    }

    # Logic Khusus Ramadhan & Lebaran 2026 (Estimasi)
    # Ramadhan 2026 estimasi mulai 18 Feb - 19 Maret
    start_puasa = datetime(2026, 2, 18).date()
    end_puasa = datetime(2026, 3, 19).date()
    
    if start_puasa <= now.date() <= end_puasa:
        return {"judul": "Selamat Menjalankan Ibadah Puasa 1447H", "pesan": "Tetap semangat melayani meski sedang berpuasa. Barakkallah!", "warna": "#fb8c00"}
    
    if "20-03" <= tgl_bln <= "25-03": # Estimasi Lebaran
        return {"judul": "Selamat Hari Raya Idul Fitri 1447H", "pesan": "Minal Aidin Wal Faizin, Mohon Maaf Lahir dan Batin.", "warna": "#2e7d32"}

    return events.get(tgl_bln, ucapan)

def init_db():
    conn = sqlite3.connect('rme_system.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS rme_tasks 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, unit TEXT, data_pasien TEXT, 
                  status TEXT, waktu_input TEXT, waktu_selesai TEXT, pemohon TEXT, 
                  nip_user TEXT, it_executor TEXT, ttd_user_path TEXT, rm_utama TEXT, pasien_display TEXT)''')
    c.execute("CREATE TABLE IF NOT EXISTS jadwal_it (nama TEXT, tanggal INTEGER, shift TEXT)")
    conn.commit()
    return conn

# =========================================================
# 2. SIDEBAR
# =========================================================
with st.sidebar:
    st.title("🏥 SIRS RME PRO")
    if 'is_it_authenticated' not in st.session_state: st.session_state.is_it_authenticated = False
    menu_pilihan = ["🏠 Dashboard Info", "📊 Monitor Antrian", "📝 Input Form"]
    if st.session_state.is_it_authenticated:
        menu_pilihan += ["👨‍💻 Workspace IT", "📂 Arsip Digital", "📅 Dashboard Jadwal"]
    menu = st.radio("Navigasi:", menu_pilihan)
    
    if not st.session_state.is_it_authenticated:
        with st.expander("🔑 IT Login"):
            pin = st.text_input("PIN:", type="password")
            if st.button("Masuk"):
                if pin == "1234": st.session_state.is_it_authenticated = True; st.rerun()

# =========================================================
# 3. DASHBOARD INFO (NEW & LUXURY)
# =========================================================
if menu == "🏠 Dashboard Info":
    # Banner Hari Besar Otomatis
    event = get_ucapan_hari_besar()
    st.markdown(f"""
        <div style="background-color:{event['warna']}; padding:20px; border-radius:15px; text-align:center; color:white; margin-bottom:25px; box-shadow: 0px 4px 15px rgba(0,0,0,0.2);">
            <h1 style="margin:0; font-size:28px;">{event['judul']}</h1>
            <p style="margin:5px 0 0 0; font-size:18px; opacity:0.9;">{event['pesan']}</p>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("<h2 style='text-align: center;'>🏥 SISTEM RME PRO 2026</h2>", unsafe_allow_html=True)
    
    # Statistik Singkat
    db = init_db()
    total_antri = db.execute("SELECT COUNT(*) FROM rme_tasks WHERE status='Masuk Antrian'").fetchone()[0]
    total_selesai = db.execute("SELECT COUNT(*) FROM rme_tasks WHERE status='Selesai'").fetchone()[0]
    db.close()

    m1, m2 = st.columns(2)
    m1.metric("📋 Antrian Aktif", f"{total_antri} Berkas")
    m2.metric("✅ Total Selesai", f"{total_selesai} Kasus")
    
    st.divider()

    # --- TUTORIAL USER ---
    st.subheader("📖 Panduan Penggunaan untuk User/Ruangan")
    
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div style="background-color:#ffffff; padding:20px; border-radius:10px; border-top:5px solid #ff4b4b; box-shadow: 0px 2px 10px rgba(0,0,0,0.05); min-height:220px;">
            <h4 style="color:#ff4b4b;">STEP 1: INPUT DATA</h4>
            <p style="color:gray;">Buka menu <b>📝 Input Form</b>. Masukkan Nama Pasien, No RM (9 digit), dan alasan penghapusan.</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div style="background-color:#ffffff; padding:20px; border-radius:10px; border-top:5px solid #ffa421; box-shadow: 0px 2px 10px rgba(0,0,0,0.05); min-height:220px;">
            <h4 style="color:#ffa421;">STEP 2: TANDA TANGAN</h4>
            <p style="color:gray;">Pilih <b>Petugas IT</b> yang sedang piket, lalu berikan tanda tangan digital Anda pada kolom putih.</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div style="background-color:#ffffff; padding:20px; border-radius:10px; border-top:5px solid #28a745; box-shadow: 0px 2px 10px rgba(0,0,0,0.05); min-height:220px;">
            <h4 style="color:#28a745;">STEP 3: MONITOR</h4>
            <p style="color:gray;">Klik <b>Kirim</b>. Pantau status berkas Anda di menu <b>📊 Monitor Antrian</b> secara real-time.</p>
        </div>
        """, unsafe_allow_html=True)

    st.divider()
    st.caption(f"Server Aktif | RSUD Kota Cilegon | {get_now_jakarta().strftime('%A, %d %B %Y')}")

# =========================================================
# 4. MONITOR ANTRIAN
# =========================================================
elif menu == "📊 Monitor Antrian":
    st_autorefresh(5000)
    st.header("📊 Monitor Antrian")
    db = init_db()
    df = pd.read_sql_query("SELECT * FROM rme_tasks ORDER BY id DESC LIMIT 9", db)
    db.close()
    if not df.empty:
        cols = st.columns(3)
        for i, row in df.iterrows():
            with cols[i % 3]:
                bg = "#ffcccc" if row['status'] == "Masuk Antrian" else "#fff4cc" if row['status'] == "Menunggu" else "#ccffcc"
                st.markdown(f"""<div style="background-color:{bg}; padding:15px; border-radius:10px; border:2px solid #333; margin-bottom:10px; color:black;">
                    <small>#{row['id']} | {row['waktu_input']}</small><h3 style="margin:5px 0;">{row['pasien_display']}</h3>
                    <p style="margin:0;">Unit: {row['unit']}</p><p style="margin:5px 0;">Petugas: <b>{row['it_executor']}</b></p>
                    <div style="text-align:center; font-weight:bold; border:1px solid #333; border-radius:5px;">{row['status']}</div></div>""", unsafe_allow_html=True)

# =========================================================
# 5. INPUT FORM
# =========================================================
elif menu == "📝 Input Form":
    st.header("📝 Form Pengajuan")
    db = init_db()
    it_on = [row[0] for row in db.execute("SELECT DISTINCT nama FROM jadwal_it WHERE tanggal = ?", (get_now_jakarta().day,)).fetchall()]
    db.close()
    
    with st.container(border=True):
        c1, c2 = st.columns(2)
        u_nama = c1.text_input("Nama Pemohon")
        u_unit = c2.text_input("Unit/Ruangan")
        u_nip = c1.text_input("NIP")
        u_it = c2.selectbox("Kirim ke IT:", it_on if it_on else LIST_IT)
        st.divider()
        p_nama = st.text_input("Nama Pasien")
        p_rm = st.text_input("RM (9 Digit)", max_chars=9)
        p_alasan = st.text_area("Alasan")
        st.write("Tanda Tangan Pemohon:")
        can_u = st_canvas(stroke_width=3, stroke_color="#000", background_color="#fff", height=150, width=350, key="can_u")
        
        if st.button("KIRIM KE IT", type="primary"):
            if p_nama and len(p_rm) == 9 and can_u.image_data is not None:
                path_ttd = f"temp/u_{int(time.time())}.png"
                Image.fromarray(can_u.image_data.astype('uint8')).save(path_ttd)
                db = init_db()
                db.execute("INSERT INTO rme_tasks (unit, data_pasien, status, waktu_input, pemohon, nip_user, it_executor, ttd_user_path, rm_utama, pasien_display) VALUES (?,?,?,?,?,?,?,?,?,?)",
                           (u_unit, json.dumps([{"nama": p_nama, "rm": p_rm, "alasan": p_alasan}]), "Masuk Antrian", get_now_jakarta().strftime("%H:%M"), u_nama, u_nip, u_it, path_ttd, p_rm, p_nama))
                db.commit(); db.close()
                st.success("Berhasil dikirim!"); time.sleep(1); st.rerun()

# =========================================================
# 6. WORKSPACE IT (STRICT FILTER)
# =========================================================
elif menu == "👨‍💻 Workspace IT":
    st_autorefresh(5000)
    it_nama = st.selectbox("Identitas IT:", LIST_IT)
    st.header(f"👨‍💻 Tugas: {it_nama}")
    db = init_db()
    tasks = db.execute("SELECT * FROM rme_tasks WHERE it_executor = ? AND status IN ('Masuk Antrian', 'Menunggu')", (it_nama,)).fetchall()
    if tasks:
        for t in tasks:
            with st.expander(f"Tiket #{t[0]} - {t[11]}", expanded=True):
                if t[3] == "Masuk Antrian":
                    if st.button(f"Terima Tiket {t[0]}"):
                        db.execute("UPDATE rme_tasks SET status='Menunggu' WHERE id=?", (t[0],))
                        db.commit(); st.rerun()
                else:
                    can_it = st_canvas(stroke_width=3, stroke_color="#000", background_color="#fff", height=150, width=350, key=f"it_{t[0]}")
                    if st.button(f"Selesaikan & Cetak #{t[0]}", type="primary"):
                        path_it = f"temp/it_{t[0]}.png"
                        Image.fromarray(can_it.image_data.astype('uint8')).save(path_it)
                        doc = DocxTemplate("template_rme.docx")
                        p_data = json.loads(t[2])[0]
                        ctx = {
                            'tgl_full': get_now_jakarta().strftime("%d-%m-%Y"), 'unit': t[1], 'pemohon': t[6], 'penerima': it_nama,
                            'nip_it': MAPPING_IT_DETAIL[it_nama]['nip'], 'nip_user': t[7],
                            'ttd_user': InlineImage(doc, t[9], width=Inches(1)), 'ttd_it': InlineImage(doc, path_it, width=Inches(1)),
                            'no': '1', 'nama': p_data['nama'], 'rm': p_data['rm'], 'alasan': p_data['alasan']
                        }
                        doc.render(ctx)
                        fn = f"arsip_rme/{t[11]}_{t[10]}.docx"
                        doc.save(fn)
                        db.execute("UPDATE rme_tasks SET status='Selesai', waktu_selesai=? WHERE id=?", (get_now_jakarta().strftime("%H:%M"), t[0]))
                        db.commit(); st.success("Selesai!"); time.sleep(1); st.rerun()
    else: st.info("Tidak ada tugas.")
    db.close()

# =========================================================
# 7. ARSIP DIGITAL
# =========================================================
elif menu == "📂 Arsip Digital":
    st.header("📂 Arsip Hasil Eksekusi")
    db = init_db()
    df_arsip = pd.read_sql_query("SELECT * FROM rme_tasks WHERE status='Selesai' ORDER BY id DESC", db)
    db.close()
    
    if not df_arsip.empty:
        for _, r in df_arsip.iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
                c1.markdown(f"<b style='color:white;'>{r['pasien_display']}</b>", unsafe_allow_html=True)
                c1.caption(f"No. RM: {r['rm_utama']}")
                
                c2.write(f"💻 IT: {r['it_executor']}")
                c2.caption(f"Selesai Jam: {r['waktu_selesai']}")
                
                # PERBAIKAN LOGIKA NAMA FILE (Sesuaikan dengan format di Workspace IT)
                # Di workspace lu bikin: {pasien_display}_{rm_utama}.docx
                nama_file_fix = f"{r['pasien_display']}_{r['rm_utama']}.docx"
                f_docx = f"arsip_rme/{nama_file_fix}"
                f_pdf = f_docx.replace(".docx", ".pdf")
                
                # Cek keberadaan file
                if os.path.exists(f_docx):
                    with open(f_docx, "rb") as f:
                        c3.download_button("📂 DOCX", f, file_name=nama_file_fix, key=f"d_{r['id']}")
                else:
                    c3.error("Docx ❌")

                if os.path.exists(f_pdf):
                    with open(f_pdf, "rb") as f:
                        c4.download_button("🖨️ PDF", f, file_name=nama_file_fix.replace(".docx", ".pdf"), mime="application/pdf", key=f"p_{r['id']}")
                else:
                    c4.error("PDF ❌")
    else:
        st.info("Arsip belum tersedia.")
    db.close()
# =========================================================
# 8. DASHBOARD JADWAL
# =========================================================
elif menu == "📅 Dashboard Jadwal":
    st.header("📅 Pengaturan Jadwal IT")
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
        st.table(df_v[df_v['tanggal'] == t_pilih])
    db.close()





