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

# MAPPING DATA PETUGAS IT (NIP & WA)
MAPPING_IT_DETAIL = {
    "Isfan":  {"nip": "199709302025211069", "wa": "6282298180077", "nama_full": "Isfan Fajar Anugrah, S.Kom"},
    "Teguh":  {"nip": "199901162025211080", "wa": "628991234567", "nama_full": "Teguh Adi Pradana, A.Md"},
    "Jaka":   {"nip": "199605282025211138", "wa": "628121212121", "nama_full": "Jaka Gilang R, A.Md"},
    "Hisyam": {"nip": "199308302025211114", "wa": "628131313131", "nama_full": "M. Hisyam Rizky F, S.Kom"},
    "Udin":   {"nip": "19880101XXXXXXXX", "wa": "628571234567", "nama_full": "Ahmad Haerudin"},
    "Rey":    {"nip": "19900202XXXXXXXX", "wa": "628991112223", "nama_full": "Reynold Marcelino"},
    "Ferdi":  {"nip": "19920303XXXXXXXX", "wa": "628112223334", "nama_full": "Ferdyansyah Zaelani"}
}
LIST_IT = list(MAPPING_IT_DETAIL.keys())

def get_now_jakarta():
    return datetime.now(pytz.timezone('Asia/Jakarta'))

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

def get_it_aktif_sekarang():
    try:
        now = get_now_jakarta()
        tgl_ini = now.day
        tgl_kmrn = (now - timedelta(days=1)).day
        waktu_float = now.hour + (now.minute / 60)

        db = init_db()
        df = pd.read_sql_query(f"SELECT * FROM jadwal_it WHERE tanggal IN ({tgl_kmrn}, {tgl_ini})", db)
        db.close()

        petugas_on = []
        if df.empty: return ["Admin IT"]

        for _, row in df.iterrows():
            nama_db = row['nama']
            s = str(row['shift']).upper().strip()
            tgl_data = int(row['tanggal'])

            # --- ANTI-SYIHAB LOGIC: NAMA SYIHAB TIDAK BOLEH MUNCUL ---
            if "SYIHABUDIN" in nama_db.upper():
                continue

            if "M" in s:
                if (tgl_data == tgl_kmrn and waktu_float < 7.5) or (tgl_data == tgl_ini and waktu_float >= 21):
                    petugas_on.append(nama_db)
            elif ("P" in s or "PS" in s) and tgl_data == tgl_ini:
                if 7 <= waktu_float < 16:
                    petugas_on.append(nama_db)
            elif "S" in s and tgl_data == tgl_ini:
                limit = 22 if "HISYAM" in nama_db.upper() else 21
                if 14 <= waktu_float < limit:
                    petugas_on.append(nama_db)

        mapping_panggilan = {
            "AHMAD HAERUDIN": "Udin", "M. HISYAM RIZKY": "Hisyam",
            "TEGUH ADI PRADANA": "Teguh", "JAKA GILANG R": "Jaka",
            "ISFAN FAJAR ANUGRAH": "Isfan", "REYNOLD MARCELINO": "Rey",
            "FERDYANSYAH ZAELANI": "Ferdi"
        }

        final_list = []
        for p in petugas_on:
            found = False
            for nama_panjang, panggilan in mapping_panggilan.items():
                if nama_panjang in p.upper():
                    final_list.append(panggilan)
                    found = True
                    break
            if not found: final_list.append(p)

        return sorted(list(set(final_list))) if final_list else ["Admin IT"]
    except:
        return LIST_IT

def update_jadwal_dari_pdf(file_pdf):
    try:
        with pdfplumber.open(file_pdf) as pdf:
            all_text = ""
            for page in pdf.pages:
                all_text += page.extract_text() + "\n"
            
            lines = all_text.split('\n')
            db = init_db()
            db.execute("DELETE FROM jadwal_it")
            
            target_names = [
                "Teguh Adi Pradana", "Jaka Gilang R", "Ahmad Haerudin", 
                "Syihabudin Amien", "Isfan Fajar Anugrah", "M. Hisyam Rizky",
                "Ferdyansyah Zaelani", "Reynold Marcelino"
            ]

            for line in lines:
                for target in target_names:
                    if target.upper() in line.upper():
                        parts = line.split()
                        shifts = [p for p in parts if p in ['P', 'S', 'M', 'L', 'PS', 'MM']]
                        for tgl, shf in enumerate(shifts, 1):
                            db.execute("INSERT INTO jadwal_it (nama, tanggal, shift) VALUES (?,?,?)", (target, tgl, shf))
            db.commit(); db.close()
            return True
    except:
        return False

def convert_to_pdf(docx_path, output_dir):
    try:
        subprocess.run(['libreoffice', '--headless', '--convert-to', 'pdf', docx_path, '--outdir', output_dir], check=True)
        return docx_path.replace(".docx", ".pdf")
    except:
        return None

def get_ucapan_hari_besar():
    now = get_now_jakarta()
    tgl_bln = now.strftime("%d-%m")
    ucapan = {"judul": "Selamat Bekerja!", "pesan": "Semoga pelayanan hari ini berjalan lancar.", "warna": "#2e7d32"}
    events = {
        "01-01": {"judul": "Selamat Tahun Baru 2026!", "pesan": "Semangat baru!", "warna": "#1565c0"},
        "17-08": {"judul": "Dirgahayu RI!", "pesan": "Merdeka!", "warna": "#c62828"},
    }
    if "18-02" <= tgl_bln <= "19-03":
        return {"judul": "Selamat Ramadhan 1447H", "pesan": "Tetap semangat melayani.", "warna": "#fb8c00"}
    return events.get(tgl_bln, ucapan)

for folder in ["temp", "arsip_rme"]:
    if not os.path.exists(folder): os.makedirs(folder)

# =========================================================
# 2. SIDEBAR NAVIGATION
# =========================================================
with st.sidebar:
    st.title("🏥 SIRS RME PRO")
    if 'is_it_authenticated' not in st.session_state: st.session_state.is_it_authenticated = False
    
    menu_pilihan = ["🏠 Dashboard Info", "📊 Monitor Antrian", "📝 Input Form"]
    if st.session_state.is_it_authenticated:
        menu_pilihan += ["👨‍💻 Workspace IT", "📂 Arsip Digital", "📅 Dashboard Jadwal"]
    
    menu = st.radio("Navigasi:", menu_pilihan)
    st.divider()
    if not st.session_state.is_it_authenticated:
        with st.expander("🔑 IT Login"):
            if st.text_input("PIN:", type="password") == "1234":
                if st.button("Masuk"):
                    st.session_state.is_it_authenticated = True
                    st.rerun()
    else:
        if st.button("Logout Admin"):
            st.session_state.is_it_authenticated = False
            st.rerun()

# =========================================================
# 3. DASHBOARD INFO
# =========================================================
if menu == "🏠 Dashboard Info":
    event = get_ucapan_hari_besar()
    st.markdown(f"""<div style="background-color:{event['warna']}; padding:20px; border-radius:15px; text-align:center; color:white;">
                    <h1>{event['judul']}</h1><p>{event['pesan']}</p></div>""", unsafe_allow_html=True)
    db = init_db()
    c1, c2 = st.columns(2)
    c1.metric("📋 Antrian Aktif", f"{db.execute('SELECT COUNT(*) FROM rme_tasks WHERE status!= \"Selesai\"').fetchone()[0]} Berkas")
    c2.metric("✅ Total Selesai", f"{db.execute('SELECT COUNT(*) FROM rme_tasks WHERE status=\"Selesai\"').fetchone()[0]} Kasus")
    db.close()
    st.divider()
    st.subheader("📖 Panduan Penggunaan")
    st.info("1. Isi Form -> 2. Tanda Tangan -> 3. IT Proses -> 4. Download Arsip")

# =========================================================
# 4. MONITOR ANTRIAN
# =========================================================
elif menu == "📊 Monitor Antrian":
    st_autorefresh(5000)
    st.header("📊 Monitor Antrian Real-Time")
    db = init_db()
    df = pd.read_sql_query("SELECT id, pasien_display, unit, status, waktu_input FROM rme_tasks WHERE status != 'Selesai' ORDER BY id DESC", db)
    db.close()
    if not df.empty:
        st.table(df)
    else:
        st.info("Tidak ada antrian aktif.")

# =========================================================
# 5. INPUT FORM
# =========================================================
elif menu == "📝 Input Form":
    st.header("📝 Form Pengajuan Penghapusan RME")
    it_on = get_it_aktif_sekarang()
    with st.form("input_form"):
        c1, c2 = st.columns(2)
        u_nama = c1.text_input("Nama Pemohon")
        u_unit = c2.text_input("Unit/Ruangan")
        u_nip = c1.text_input("NIP/NIK")
        u_it = c2.selectbox("Kirim ke Petugas IT:", it_on)
        p_nama = st.text_input("Nama Pasien")
        p_rm = st.text_input("Nomor Rekam Medis (9 Digit)", max_chars=9)
        p_alasan = st.text_area("Alasan Penghapusan")
        st.write("Tanda Tangan Pemohon:")
        canvas = st_canvas(stroke_width=3, background_color="#fff", height=150, width=400, key="can_u")
        if st.form_submit_button("🚀 KIRIM KE IT", use_container_width=True):
            if p_nama and len(p_rm) == 9 and canvas.image_data is not None:
                path_ttd = f"temp/u_{int(time.time())}.png"
                Image.fromarray(canvas.image_data.astype('uint8')).save(path_ttd)
                db = init_db()
                db.execute("INSERT INTO rme_tasks (unit, data_pasien, status, waktu_input, pemohon, nip_user, it_executor, ttd_user_path, rm_utama, pasien_display) VALUES (?,?,?,?,?,?,?,?,?,?)",
                           (u_unit, json.dumps([{"nama": p_nama, "alasan": p_alasan}]), "Masuk Antrian", get_now_jakarta().strftime("%H:%M"), u_nama, u_nip, u_it, path_ttd, p_rm, p_nama))
                db.commit(); db.close()
                st.success("Terkirim!"); time.sleep(1); st.rerun()

# =========================================================
# 6. WORKSPACE IT
# =========================================================
elif menu == "👨‍💻 Workspace IT":
    it_nama = st.selectbox("Identitas IT Anda:", LIST_IT)
    st.header(f"👨‍💻 Workspace: {it_nama}")
    db = init_db()
    tasks = db.execute("SELECT * FROM rme_tasks WHERE it_executor = ? AND status != 'Selesai'", (it_nama,)).fetchall()
    if tasks:
        for t in tasks:
            with st.expander(f"Tiket #{t[0]} - {t[11]}"):
                if t[3] == "Masuk Antrian":
                    if st.button(f"Terima Tiket #{t[0]}"):
                        db.execute("UPDATE rme_tasks SET status='Proses' WHERE id=?", (t[0],))
                        db.commit(); st.rerun()
                else:
                    st.write("Tanda Tangan IT:")
                    can_it = st_canvas(stroke_width=3, background_color="#fff", height=150, width=400, key=f"it_{t[0]}")
                    if st.button(f"Selesaikan & Cetak #{t[0]}", type="primary"):
                        path_it = f"temp/it_{t[0]}.png"
                        Image.fromarray(can_it.image_data.astype('uint8')).save(path_it)
                        try:
                            doc = DocxTemplate("template_rme.docx")
                            p_data = json.loads(t[2])[0]
                            ctx = {'tgl_full': get_now_jakarta().strftime("%d-%m-%Y"), 'unit': t[1], 'pemohon': t[6], 'penerima': it_nama,
                                   'nip_it': MAPPING_IT_DETAIL[it_nama]['nip'], 'nip_user': t[7],
                                   'ttd_user': InlineImage(doc, t[9], width=Inches(1.2)), 'ttd_it': InlineImage(doc, path_it, width=Inches(1.2)),
                                   'no': '1', 'nama': t[11], 'rm': t[10], 'alasan': p_data['alasan']}
                            doc.render(ctx)
                            fname = f"{t[11]}_{t[10]}".replace(" ", "_")
                            docx_p = f"arsip_rme/{fname}.docx"
                            doc.save(docx_p); convert_to_pdf(docx_p, "arsip_rme")
                            db.execute("UPDATE rme_tasks SET status='Selesai', waktu_selesai=? WHERE id=?", (get_now_jakarta().strftime("%H:%M"), t[0]))
                            db.commit(); st.success("Selesai!"); st.rerun()
                        except Exception as e: st.error(f"Gagal: {e}")
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
                c1, c2, c3 = st.columns([3, 2, 2])
                c1.write(f"**{r['pasien_display']}** ({r['rm_utama']})")
                c2.write(f"💻 IT: {r['it_executor']}")
                fname = f"{r['pasien_display']}_{r['rm_utama']}".replace(" ", "_")
                if os.path.exists(f"arsip_rme/{fname}.pdf"):
                    with open(f"arsip_rme/{fname}.pdf", "rb") as f:
                        c3.download_button("🖨️ PDF", f, file_name=f"{fname}.pdf", mime="application/pdf", key=f"p_{r['id']}")

# =========================================================
# 8. DASHBOARD JADWAL
# =========================================================
elif menu == "📅 Dashboard Jadwal":
    st.header("📅 Pengaturan & Monitoring Jadwal IT")
    tab1, tab2 = st.tabs(["📤 Upload & Sync", "📅 Preview Jadwal Hari Ini"])
    with tab1:
        uploaded_pdf = st.file_uploader("Pilih File PDF", type="pdf")
        if st.button("🔄 Sinkronkan Jadwal"):
            if uploaded_pdf and update_jadwal_dari_pdf(uploaded_pdf):
                st.success("✅ Jadwal Berhasil Sinkron!"); time.sleep(1); st.rerun()
    with tab2:
        now = get_now_jakarta()
        db = init_db()
        df_piket = pd.read_sql_query("SELECT nama, shift FROM jadwal_it WHERE tanggal = ?", db, params=(now.day,))
        db.close()
        # FILTER ANTI-SYIHAB DI PREVIEW JADWAL
        df_piket = df_piket[~df_piket['nama'].str.contains("Syihabudin", case=False)]
        st.table(df_piket)
        st.write(f"🟢 **Sedang Standby:** {', '.join(get_it_aktif_sekarang())}")
