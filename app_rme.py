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
import time  # <--- WAJIB ADA INI BIAR GAK ERROR PAS UPDATE

# =========================================================
# 1. CORE CONFIG & SUPABASE
# =========================================================
# Pastikan secrets sudah diatur di Streamlit Cloud / .streamlit/secrets.toml
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="SIRS RME Pro 2026", layout="wide", page_icon="🏥")

# Folder Setup
for folder in ["temp", "arsip_rme"]:
    if not os.path.exists(folder): os.makedirs(folder)

# LIST TIM ELITE
LIST_IT = ["Isfan", "Udin", "Rey", "Jaka", "Teguh", "Ferdi", "Hisyam"]

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
    # Pastikan tabel jadwal selalu ada
    c.execute("CREATE TABLE IF NOT EXISTS jadwal_it (nama TEXT, tanggal INTEGER, shift TEXT)")
    conn.commit()
    return conn

def update_jadwal_dari_pdf(file_pdf):
    try:
        with pdfplumber.open(file_pdf) as pdf:
            table = pdf.pages[0].extract_table()
            mapping_nama = {
                "Teguh Adi Pradana": "Teguh",
                "Jaka Gilang R": "Jaka",
                "Ahmad Haerudin": "Udin", 
                "Isfan Fajar Anugrah": "Isfan",
                "M. Hisyam Rizky": "Hisyam",
                "Ferdyansyah Zaelani": "Ferdi",
                "Reynold": "Rey"
            }
            data_jadwal = []
            for row in table:
                if not row[1]: continue
                nama_full = str(row[1]).replace('\n', ' ')
                for key_pdf, nama_singkat in mapping_nama.items():
                    if key_pdf.lower() in nama_full.lower():
                        for tgl in range(1, 32):
                            col_idx = tgl + 1
                            if col_idx < len(row) and row[col_idx]:
                                shift = str(row[col_idx]).replace('\n', '').strip().upper()
                                data_jadwal.append({"nama": nama_singkat, "tanggal": tgl, "shift": shift})
            
            if data_jadwal:
                db = init_db()
                # Gunakan replace agar tabel lama dibuang dan dibuat baru dengan data fresh
                pd.DataFrame(data_jadwal).to_sql('jadwal_it', db, if_exists='replace', index=False)
                db.commit()
                db.close()
                return True
    except Exception as e:
        print(f"Error PDF: {e}")
        return False
    return False

def get_it_aktif_sekarang():
    now = datetime.now()
    tgl_ini, tgl_kmrn, jam_ini = now.day, (now - timedelta(days=1)).day, now.hour
    
    db = init_db()
    try:
        df = pd.read_sql_query(f"SELECT * FROM jadwal_it WHERE tanggal IN ({tgl_kmrn}, {tgl_ini})", db)
    except:
        df = pd.DataFrame()
    db.close()
    
    petugas_on = []
    if df.empty: return ["⚠️ Database Kosong"]

    for _, row in df.iterrows():
        nama, s, tgl_data = row['nama'], str(row['shift']).upper().strip(), int(row['tanggal'])

        # 1. Shift MALAM (M/MM) - Transisi hari
        if "M" in s:
            # Shift malam kemarin: muncul sampai jam 07:00 pagi ini
            if tgl_data == tgl_kmrn and jam_ini < 7:
                petugas_on.append(f"{nama} (Malam)")
            # Shift malam hari ini: baru muncul jam 21:00 nanti
            elif tgl_data == tgl_ini and jam_ini >= 21:
                petugas_on.append(f"{nama} (Malam)")

        # 2. Shift PAGI / NON-SHIFT (P/PS)
        elif ("P" in s or "PS" in s) and tgl_data == tgl_ini:
            if 7 <= jam_ini < 16:
                petugas_on.append(f"{nama} (Standby)")

        # 3. Shift SIANG (S)
        elif s == "S" and tgl_data == tgl_ini:
            limit = 22 if "HISYAM" in nama.upper() else 21
            if 14 <= jam_ini < limit:
                petugas_on.append(f"{nama} (Siang)")

    return sorted(list(set(petugas_on))) if petugas_on else ["Tidak ada petugas standby"]

# ... (Menu Sidebar, Monitor Antrian, dan Input Form tetap sama, pastikan pemanggilan fungsi bener) ...

# =========================================================
# 8. MENU: DASHBOARD JADWAL (REVISED)
# =========================================================
elif menu == "📊 Dashboard Jadwal":
    st.header("📊 Dashboard Jadwal IT")
    
    with st.container(border=True):
        pdf_file = st.file_uploader("Upload PDF Jadwal Baru", type="pdf")
        if st.button("🚀 Proses Update Sekarang"):
            if pdf_file is not None:
                with st.spinner('Sedang memproses jadwal...'):
                    hasil = update_jadwal_dari_pdf(pdf_file)  
                if hasil:
                    st.success("✅ Jadwal Berhasil Diupdate!")
                    # Balon dihapus sesuai request
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Gagal Update. Pastikan PDF sesuai format.")
            else:
                st.warning("⚠️ Pilih file PDF jadwal dulu!")

    st.divider()
    st.subheader("📅 Preview Database Jadwal")
    
    try:
        db = init_db()
        df_view = pd.read_sql_query("SELECT * FROM jadwal_it ORDER BY tanggal ASC", db)
        db.close()
        
        if not df_view.empty:
            tgl_skrg = datetime.now().day
            cek_tgl = st.slider("Lihat jadwal tanggal:", 1, 31, tgl_skrg)
            df_filtered = df_view[df_view['tanggal'] == cek_tgl]
            if not df_filtered.empty:
                st.table(df_filtered)
            else:
                st.info(f"Tidak ada jadwal untuk tanggal {cek_tgl}")
        else:
            st.warning("Database Jadwal Kosong.")
    except Exception as e:
        st.error(f"Gagal load pratinjau: {e}")
