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
    "Isfan":  {"nip": "199709302025211069", "wa": "6282298180077"},
    "Teguh":  {"nip": "199901162025211080", "wa": "628991234567"},
    "Jaka":   {"nip": "199605282025211138", "wa": "628121212121"},
    "Hisyam": {"nip": "199308302025211114", "wa": "628131313131"},
    "Udin":   {"nip": "NIP. 19880101XXXXXXXX", "wa": "628571234567"},
    "Rey":    {"nip": "NIP. 19900202XXXXXXXX", "wa": "628991112223"},
    "Ferdi":  {"nip": "NIP. 19920303XXXXXXXX", "wa": "628112223334"}
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
        "01-01": {"judul": "Selamat Tahun Baru 2026!", "pesan": "Semangat baru untuk pelayanan yang lebih baik.", "warna": "#1565c0"},
        "17-08": {"judul": "Dirgahayu Republik Indonesia!", "pesan": "Merdeka dalam digitalisasi pelayanan kesehatan.", "warna": "#c62828"},
    }
    # Logic Ramadhan/Lebaran 2026
    if "18-02" <= tgl_bln <= "19-03":
        return {"judul": "Selamat Menjalankan Ibadah Puasa 1447H", "pesan": "Tetap semangat melayani meski sedang berpuasa.", "warna": "#fb8c00"}
    
    return events.get(tgl_bln, ucapan)

# Create folders if not exist
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
            pin = st.text_input("PIN:", type="password")
            if st.button("Masuk"):
                if pin == "1234":
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
    st.markdown(f"""
        <div style="background-color:{event['warna']}; padding:20px; border-radius:15px; text-align:center; color:white; margin-bottom:25px; box-shadow: 0px 4px 15px rgba(0,0,0,0.2);">
            <h1 style="margin:0; font-size:28px;">{event['judul']}</h1>
            <p style="margin:5px 0 0 0; font-size:18px; opacity:0.9;">{event['pesan']}</p>
        </div>
    """, unsafe_allow_html=True)

    db = init_db()
    total_antri = db.execute("SELECT COUNT(*) FROM rme_tasks WHERE status='Masuk Antrian'").fetchone()[0]
    total_selesai = db.execute("SELECT COUNT(*) FROM rme_tasks WHERE status='Selesai'").fetchone()[0]
    db.close()

    m1, m2 = st.columns(2)
    m1.metric("📋 Antrian Aktif", f"{total_antri} Berkas")
    m2.metric("✅ Total Selesai", f"{total_selesai} Kasus")
    
    st.divider()
    st.subheader("📖 Panduan Penggunaan")
    c1, c2, c3 = st.columns(3)
    with c1: st.info("**1. Isi Form**\nMasukkan data pasien & alasan penghapusan di menu Input Form.")
    with c2: st.warning("**2. Tanda Tangan**\nBubuhkan tanda tangan digital pemohon sebagai validitas.")
    with c3: st.success("**3. Selesai**\nIT akan memproses dan Anda bisa mendownload arsip di Workspace IT.")

# =========================================================
# 4. MONITOR ANTRIAN
# =========================================================
elif menu == "📊 Monitor Antrian":
    st_autorefresh(5000)
    st.header("📊 Monitor Antrian Real-Time")
    db = init_db()
    df = pd.read_sql_query("SELECT * FROM rme_tasks WHERE status != 'Selesai' ORDER BY id DESC", db)
    db.close()

    if not df.empty:
        cols = st.columns(3)
        for i, row in df.iterrows():
            with cols[i % 3]:
                bg = "#FFE5E5" if row['status'] == "Masuk Antrian" else "#FFF4E0"
                st.markdown(f"""
                <div style="background-color:{bg}; padding:15px; border-radius:10px; border-left: 5px solid #333; margin-bottom:15px; color:black;">
                    <small>Tiket #{row['id']} | {row['waktu_input']}</small>
                    <div style="font-size:18px; font-weight:bold;">{row['pasien_display']}</div>
                    <div style="font-size:14px;">Unit: {row['unit']}</div>
                    <div style="margin-top:10px; font-weight:bold;">Status: {row['status']}</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Tidak ada antrian aktif saat ini.")

# =========================================================
# 5. INPUT FORM
# =========================================================
elif menu == "📝 Input Form":
    st.header("📝 Form Pengajuan Penghapusan RME")
    db = init_db()
    # Get IT on duty
    it_on = [row[0] for row in db.execute("SELECT DISTINCT nama FROM jadwal_it WHERE tanggal = ?", (get_now_jakarta().day,)).fetchall()]
    db.close()

    with st.form("input_form"):
        c1, c2 = st.columns(2)
        u_nama = c1.text_input("Nama Pemohon")
        u_unit = c2.text_input("Unit/Ruangan")
        u_nip = c1.text_input("NIP/NIK")
        u_it = c2.selectbox("Kirim ke Petugas IT:", it_on if it_on else LIST_IT)
        
        st.divider()
        p_nama = st.text_input("Nama Pasien")
        p_rm = st.text_input("Nomor Rekam Medis (9 Digit)", max_chars=9)
        p_alasan = st.text_area("Alasan Penghapusan")
        
        st.write("Tanda Tangan Pemohon:")
        canvas = st_canvas(stroke_width=3, stroke_color="#000", background_color="#fff", height=150, width=400, key="can_u")
        
        submit = st.form_submit_button("🚀 KIRIM KE IT", use_container_width=True)
        
        if submit:
            if p_nama and len(p_rm) == 9 and canvas.image_data is not None:
                path_ttd = f"temp/u_{int(time.time())}.png"
                Image.fromarray(canvas.image_data.astype('uint8')).save(path_ttd)
                
                db = init_db()
                db.execute("""INSERT INTO rme_tasks (unit, data_pasien, status, waktu_input, pemohon, nip_user, it_executor, ttd_user_path, rm_utama, pasien_display) 
                              VALUES (?,?,?,?,?,?,?,?,?,?)""",
                           (u_unit, json.dumps([{"nama": p_nama, "rm": p_rm, "alasan": p_alasan}]), 
                            "Masuk Antrian", get_now_jakarta().strftime("%H:%M"), u_nama, u_nip, u_it, path_ttd, p_rm, p_nama))
                db.commit(); db.close()
                st.success("Berhasil Terkirim! Silahkan cek Monitor Antrian.")
                time.sleep(2); st.rerun()
            else:
                st.error("Lengkapi data dan tanda tangan!")

# =========================================================
# 6. WORKSPACE IT
# =========================================================
elif menu == "👨‍💻 Workspace IT":
    st_autorefresh(5000)
    it_nama = st.selectbox("Identitas IT Anda:", LIST_IT)
    st.header(f"👨‍💻 Workspace: {it_nama}")
    
    db = init_db()
    tasks = db.execute("SELECT * FROM rme_tasks WHERE it_executor = ? AND status IN ('Masuk Antrian', 'Menunggu')", (it_nama,)).fetchall()
    
    if tasks:
        for t in tasks:
            with st.expander(f"Tiket #{t[0]} - Pasien: {t[11]}", expanded=True):
                st.write(f"Pemohon: {t[6]} ({t[1]})")
                
                if t[3] == "Masuk Antrian":
                    if st.button(f"Terima Tiket #{t[0]}", key=f"acc_{t[0]}"):
                        db.execute("UPDATE rme_tasks SET status='Menunggu' WHERE id=?", (t[0],))
                        db.commit(); st.rerun()
                else:
                    st.write("Tanda Tangan IT:")
                    can_it = st_canvas(stroke_width=3, stroke_color="#000", background_color="#fff", height=150, width=400, key=f"it_{t[0]}")
                    
                    if st.button(f"Selesaikan & Cetak #{t[0]}", type="primary", key=f"fin_{t[0]}"):
                        path_it = f"temp/it_{t[0]}.png"
                        Image.fromarray(can_it.image_data.astype('uint8')).save(path_it)
                        
                        # LOGIC GENERATE DOCX
                        try:
                            doc = DocxTemplate("template_rme.docx")
                            p_data = json.loads(t[2])[0]
                            ctx = {
                                'tgl_full': get_now_jakarta().strftime("%d-%m-%Y"),
                                'unit': t[1], 'pemohon': t[6], 'penerima': it_nama,
                                'nip_it': MAPPING_IT_DETAIL[it_nama]['nip'], 'nip_user': t[7],
                                'ttd_user': InlineImage(doc, t[9], width=Inches(1.2)),
                                'ttd_it': InlineImage(doc, path_it, width=Inches(1.2)),
                                'no': '1', 'nama': p_data['nama'], 'rm': p_data['rm'], 'alasan': p_data['alasan']
                            }
                            doc.render(ctx)
                            fname = f"{t[11]}_{t[10]}".replace(" ", "_")
                            docx_path = f"arsip_rme/{fname}.docx"
                            doc.save(docx_path)
                            
                            # Auto convert to PDF
                            convert_to_pdf(docx_path, "arsip_rme")
                            
                            db.execute("UPDATE rme_tasks SET status='Selesai', waktu_selesai=? WHERE id=?", 
                                       (get_now_jakarta().strftime("%H:%M"), t[0]))
                            db.commit(); st.success("Selesai!"); time.sleep(1); st.rerun()
                        except Exception as e:
                            st.error(f"Gagal generate dokumen: {e}. Pastikan template_rme.docx ada!")
    else:
        st.info("Belum ada tugas untuk Anda.")
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
                c1.markdown(f"**{r['pasien_display']}**")
                c1.caption(f"No. RM: {r['rm_utama']} | {r['unit']}")
                
                c2.write(f"💻 IT: {r['it_executor']}")
                c2.caption(f"Selesai: {r['waktu_selesai']}")
                
                fname = f"{r['pasien_display']}_{r['rm_utama']}".replace(" ", "_")
                f_docx = f"arsip_rme/{fname}.docx"
                f_pdf = f"arsip_rme/{fname}.pdf"
                
                if os.path.exists(f_docx):
                    with open(f_docx, "rb") as f:
                        c3.download_button("📂 DOCX", f, file_name=f"{fname}.docx", key=f"d_{r['id']}")
                
                if os.path.exists(f_pdf):
                    with open(f_pdf, "rb") as f:
                        c4.download_button("🖨️ PDF", f, file_name=f"{fname}.pdf", mime="application/pdf", key=f"p_{r['id']}")
    else:
        st.info("Belum ada arsip selesai.")

# =========================================================
# 8. DASHBOARD JADWAL
# =========================================================
elif menu == "📅 Dashboard Jadwal":
    st.header("📅 Pengaturan Jadwal IT")
    
    uploaded_pdf = st.file_uploader("Upload PDF Jadwal", type="pdf")
    if st.button("🔄 Sync Jadwal dari PDF"):
        # Logic update_jadwal_dari_pdf disini
        st.info("Fitur parsing PDF sedang memproses...")
        # (Tambahkan fungsi update_jadwal_dari_pdf Anda di sini)

    st.divider()
    db = init_db()
    df_v = pd.read_sql_query("SELECT * FROM jadwal_it", db)
    if not df_v.empty:
        st.table(df_v[df_v['tanggal'] == get_now_jakarta().day])
    else:
        st.warning("Jadwal kosong. Silahkan upload PDF.")
    db.close()
