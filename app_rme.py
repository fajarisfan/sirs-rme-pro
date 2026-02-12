import streamlit as st
import streamlit.components.v1 as components
from streamlit_drawable_canvas import st_canvas
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Inches
import sqlite3, os, json, pandas as pd
from datetime import datetime
from PIL import Image
from streamlit_autorefresh import st_autorefresh
from supabase import create_client

# =========================================================
# 1. CORE CONFIG & SUPABASE
# =========================================================
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="SIRS RME Pro 2026", layout="wide", page_icon="🏥")

# Folder Setup
for folder in ["temp", "arsip_rme"]:
    if not os.path.exists(folder): os.makedirs(folder)

# LIST TIM ELITE (Sesuai Request: No Bapak Template & Bu Cipta)
LIST_IT = ["Isfan", "Udin", "Rey", "Jaka", "Teguh", "Ferdi", "Hisyam"]

# --- FUNGSI TANGGAL INDONESIA ---
def get_tgl_indo():
    hari_dict = {'Monday': 'Senin', 'Tuesday': 'Selasa', 'Wednesday': 'Rabu', 'Thursday': 'Kamis', 'Friday': 'Jumat', 'Saturday': 'Sabtu', 'Sunday': 'Minggu'}
    bulan_dict = {1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April', 5: 'Mei', 6: 'Juni', 7: 'Juli', 8: 'Agustus', 9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember'}
    now = datetime.now()
    return f"{hari_dict.get(now.strftime('%A'))}, {now.day} {bulan_dict.get(now.month)} {now.year}"

# =========================================================
# 2. DATABASE & PDF LOGIC
# =========================================================
def init_db():
    conn = sqlite3.connect('rme_system.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS rme_tasks 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, unit TEXT, data_pasien TEXT, 
                  status TEXT, file_name TEXT, waktu_input TEXT, waktu_selesai TEXT,
                  pemohon TEXT, nip_user TEXT, it_executor TEXT, nip_it TEXT, 
                  ttd_user_path TEXT, ip_address TEXT, rm_utama TEXT, pasien_display TEXT)''')
    # Tabel Jadwal
    c.execute("CREATE TABLE IF NOT EXISTS jadwal_it (nama TEXT, tanggal INTEGER, shift TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS profiles (nama TEXT PRIMARY KEY, nip TEXT)")
    conn.commit()
    return conn

import pdfplumber

def update_jadwal_dari_pdf(file_pdf):
    try:
        with pdfplumber.open(file_pdf) as pdf:
            table = pdf.pages[0].extract_table()
            mapping_nama = {
                "Teguh Adi Pradana": "Teguh", "Jaka Gilang R": "Jaka",
                "Ahmad Haerudin": "Udin", "Isfan Fajar Anugrah": "Isfan",
                "M. Hisyam Rizky": "Hisyam", "Ferdy Apriadi": "Ferdi", "Reynold": "Rey"
            }
            data_jadwal = []
            for row in table:
                nama_full = row[1] if row[1] else ""
                for key_pdf, nama_singkat in mapping_nama.items():
                    if key_pdf in nama_full:
                        # Scan tgl 1-28/31
                        for tgl in range(1, 32):
                            if tgl+1 < len(row) and row[tgl+1]:
                                shift = row[tgl+1].replace('\n', '').strip()
                                data_jadwal.append({"nama": nama_singkat, "tanggal": tgl, "shift": shift})
            
            if data_jadwal:
                df_hasil = pd.DataFrame(data_jadwal)
                db = init_db()
                df_hasil.to_sql('jadwal_it', db, if_exists='replace', index=False)
                db.close()
                return True
    except Exception as e:
        st.error(f"Error baca PDF: {e}")
    return False

def get_it_aktif_sekarang():
    now = datetime.now()
    tgl_ini, jam_ini = now.day, now.hour
    db = init_db()
    df_hari_ini = pd.read_sql_query(f"SELECT * FROM jadwal_it WHERE tanggal={tgl_ini}", db)
    db.close()
    
    petugas_on = []
    for _, row in df_hari_ini.iterrows():
        nama, s = row['nama'], row['shift']
        # Logika Jam Shift
        if s in ["PS", "LPS"]:
            if nama == "Rey" and 7 <= jam_ini < 15: petugas_on.append(nama)
            elif nama == "Hisyam" and 12 <= jam_ini < 20: petugas_on.append(nama)
            elif 7 <= jam_ini < 16: petugas_on.append(nama)
        elif s == "P" and 7 <= jam_ini < 14: petugas_on.append(nama)
        elif s == "S" and 14 <= jam_ini < 21: petugas_on.append(nama)
        elif s == "M" and (jam_ini >= 21 or jam_ini < 7): petugas_on.append(nama)
    return petugas_on

# =========================================================
# 3. SIDEBAR & NAV
# =========================================================
with st.sidebar:
    st.title("🏥 SIRS RME PRO")
    # Menu Navigasi
    if 'is_it_authenticated' not in st.session_state: st.session_state.is_it_authenticated = False
    
    st.subheader("🌐 Menu Umum")
    menu_umum = st.radio("Pilih Layanan:", ["📊 Monitor Antrian", "📝 Input Form"], label_visibility="collapsed")
    
    st.divider()
    with st.expander("📅 Update Jadwal (Admin PDF)"):
        pdf_file = st.file_uploader("Upload PDF Baru", type="pdf")
        if pdf_file and st.button("Proses PDF"):
            if update_jadwal_dari_pdf(pdf_file):
                st.success("Jadwal Terupdate!")
                st.rerun()

    st.divider()
    if not st.session_state.is_it_authenticated:
        with st.expander("🔒 Login IT"):
            if st.text_input("PIN:", type="password") == "1234":
                st.session_state.is_it_authenticated = True
                st.rerun()
    else:
        menu_it = st.radio("Workspace IT:", ["👨‍💻 Workspace IT", "📁 Arsip Digital"])
        if st.button("Logout"): 
            st.session_state.is_it_authenticated = False
            st.rerun()

    menu = menu_it if st.session_state.is_it_authenticated else menu_umum

# =========================================================
# 4. MENU 2: INPUT FORM (DENGAN AUTO-JADWAL)
# =========================================================
if menu == "📝 Input Form":
    st.header("📝 Form Penghapusan RME")
    if 'step' not in st.session_state: st.session_state.step = 1
    if 'data_p' not in st.session_state: st.session_state.data_p = []

    # Cek siapa yang standby
    petugas_ready = get_it_aktif_sekarang()

    with st.expander("👤 Identitas Pemohon", expanded=True):
        c1, c2 = st.columns(2)
        u_nama = c1.text_input("Nama Pemohon")
        u_nip = c1.text_input("NIP/NIK")
        u_unit = c2.text_input("Unit/Ruangan")
        # OTOMATISASI SELECTBOX
        u_it = c2.selectbox("Petugas IT Standby", petugas_ready if petugas_ready else ["Semua Off/Libur"])

    if st.session_state.step == 1:
        st.session_state.jml = st.number_input("Jumlah Pasien", 1, 4, 1)

    # ... (Logika input bertahap 1-4 pasien tetap sama seperti script lu sebelumnya)
    if st.session_state.step <= st.session_state.get('jml', 1):
        s = st.session_state.step
        st.subheader(f"📍 Data Pasien ke-{s}")
        with st.container(border=True):
            p_nama = st.text_input(f"Nama Pasien {s}")
            p_rm = st.text_input(f"No. RM {s}", max_chars=9)
            p_als = st.text_area(f"Alasan {s}")
            if st.button("Lanjut ➡️"):
                st.session_state.data_p.append({"nama":p_nama, "rm":p_rm, "tgl": str(datetime.now().date()), "alasan":p_als})
                st.session_state.step += 1
                st.rerun()
    else:
        st.success("Data Lengkap, Silahkan Tanda Tangan")
        canvas = st_canvas(stroke_width=3, stroke_color="#000", background_color="#fff", height=150, width=400, key="can_u")
        if st.button("🚀 KIRIM KE IT"):
            if petugas_ready:
                # Simpan & Input ke DB
                path_ttd = f"temp/ttd_u_{datetime.now().strftime('%H%M%S')}.png"
                Image.fromarray(canvas.image_data.astype('uint8')).save(path_ttd)
                
                db = init_db()
                db.execute("INSERT INTO rme_tasks (unit, data_pasien, status, file_name, waktu_input, pemohon, nip_user, it_executor, ttd_user_path, rm_utama, pasien_display) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                           (u_unit, json.dumps(st.session_state.data_p), "Masuk Antrian", f"DOC_{p_rm}.docx", datetime.now().strftime("%H:%M"), u_nama, u_nip, u_it, path_ttd, p_rm, p_nama))
                db.commit()
                st.session_state.clear()
                st.success("Berhasil Dikirim!")
                st.rerun()

# =========================================================
# 5. MENU 3: WORKSPACE IT (LOGIKA TTD & DOCX TETAP)
# =========================================================
elif menu == "👨‍💻 Workspace IT":
    st.header("👨‍💻 IT Workspace")
    it_nama = st.selectbox("Pilih Nama Lu:", LIST_IT)
    
    db = init_db()
    tasks = db.execute("SELECT * FROM rme_tasks WHERE status='Masuk Antrian' AND it_executor=?", (it_nama,)).fetchall()
    
    for t in tasks:
        with st.expander(f"Task: {t[14]}"):
            st.write(f"Unit: {t[1]} | Pemohon: {t[7]}")
            can_it = st_canvas(stroke_width=3, stroke_color="#000", background_color="#fff", height=150, width=400, key=f"it_{t[0]}")
            if st.button(f"Selesaikan & TTD", key=f"btn_{t[0]}"):
                # 1. Supabase Backup
                supabase.table("arsip_rme").insert({"nama_pasien": t[14], "no_rm": t[13], "it_executor": it_nama}).execute()
                
                # 2. Generate Docx (Pakai template_rme.docx lu)
                path_it = f"temp/ttd_it_{t[0]}.png"
                Image.fromarray(can_it.image_data.astype('uint8')).save(path_it)
                
                doc = DocxTemplate("template_rme.docx")
                # Context mapping (sesuaikan dengan tag {{}} di word lu)
                ctx = {
                    'unit': t[1], 'pemohon': t[7], 'penerima': it_nama,
                    'ttd_user': InlineImage(doc, t[11], width=Inches(1.2)),
                    'ttd_it': InlineImage(doc, path_it, width=Inches(1.2))
                }
                doc.render(ctx)
                doc.save(f"arsip_rme/{t[4]}")
                
                db.execute("UPDATE rme_tasks SET status='Selesai', waktu_selesai=? WHERE id=?", (datetime.now().strftime("%H:%M"), t[0]))
                db.commit()
                st.rerun()
    db.close()

# (Logika Monitor Antrian & Arsip tetap sama seperti sebelumnya)
elif menu == "📊 Monitor Antrian":
    st_autorefresh(5000)
    db = init_db()
    df = pd.read_sql_query("SELECT waktu_input, pasien_display, it_executor, status FROM rme_tasks ORDER BY id DESC", db)
    st.table(df)
    db.close()

elif menu == "📁 Arsip Digital":
    st.header("📁 Arsip Filtered (No Bapak Template)")
    db = init_db()
    # Query HANYA yang dieksekusi oleh LIST_IT (Elite Team)
    query = f"SELECT * FROM rme_tasks WHERE it_executor IN ({','.join(['?']*len(LIST_IT))}) AND status='Selesai'"
    df_arsip = pd.read_sql_query(query, db, params=LIST_IT)
    st.dataframe(df_arsip)
    
    if st.button("📥 Download CSV untuk Arsip"):
        st.download_button("Klik Download", df_arsip.to_csv().encode('utf-8'), "ARSIP_CLEAN.csv")
    db.close()
