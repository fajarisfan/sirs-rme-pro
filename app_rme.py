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
                <div style="background-color:{bg}; padding:15px; border-radius:10px; border-left: 5px solid #333; margin-bottom:15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05)">
                    <div style="display:flex; justify-content:space-between">
                        <small><b>Tiket #{row['id']}</b></small>
                        <small>{row['waktu_input']}</small>
                    </div>
                    <div style="margin:10px 0">
                        <div style="font-size:16px; font-weight:bold">{row['pasien_display']}</div>
                        <small>Unit: {row['unit']}</small>
                    </div>
                    <div style="border-top:1px solid #ccc; padding-top:5px; font-size:12px">
                        Petugas: <b>{row['it_executor']}</b>
                    </div>
                    <div style="margin-top:10px; text-align:center; font-weight:bold">{lbl}</div>
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

# =========================================================
# 6. WORKSPACE IT
# =========================================================
elif menu == "👨‍💻 Workspace IT":
    st_autorefresh(5000)
    st.header("👨‍💻 Workspace Eksekusi IT")
    
    petugas_on = get_it_aktif_sekarang()
    it_nama = st.selectbox("Pilih Petugas:", petugas_on if "⚠️" not in petugas_on[0] else LIST_IT)
    
    db = init_db()
    # Tampilkan yang BELUM SELESAI
    tasks = db.execute("SELECT * FROM rme_tasks WHERE status IN ('Masuk Antrian', 'Menunggu') AND it_executor=?", (it_nama,)).fetchall()
    
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
                        bulan_map = {'January': 'Januari', 'February': 'Februari', 'March': 'Maret', 'April': 'April', 'May': 'Mei', 'June': 'Juni', 'July': 'Juli', 'August': 'Agustus', 'September': 'September', 'October': 'Oktober', 'November': 'November', 'December': 'Desember'}
                        tgl_indo = f"{now.strftime('%d')} {bulan_map[now.strftime('%B')]} {now.strftime('%Y')}"
                        hari_tgl = f"{hari_map[now.strftime('%A')]}, {tgl_indo}"
                        
                        # 2. Mapping NIP
                        it_info = MAPPING_IT_DETAIL.get(it_nama, {"nip": "NIP. ..........."})
                        
                        # 3. Render Docx
                        doc = DocxTemplate("template_rme.docx")
                        path_it = f"temp/ttd_it_{t[0]}.png"
                        Image.fromarray(can_it.image_data.astype('uint8')).save(path_it)
                        
                        ctx = {
                            'tgl_full': hari_tgl, 'unit': t[1].upper(), 'penerima': it_nama,
                            'nip_it': it_info['nip'], 'pemohon': t[7], 'nip_user': t[8],
                            'ttd_user': InlineImage(doc, t[11], width=Inches(1.0)),
                            'ttd_it': InlineImage(doc, path_it, width=Inches(1.0))
                        }
                        
                        p_json = json.loads(t[2])
                        for i in range(4):
                            sfx = "" if i==0 else str(i+1)
                            if i < len(p_json):
                                ctx.update({f'nama{sfx}': p_json[i]['nama'], f'rm{sfx}': p_json[i]['rm'], f'tgl{sfx}': tgl_indo, f'alasan{sfx}': p_json[i]['alasan']})
                            else:
                                ctx.update({f'nama{sfx}': "", f'rm{sfx}': "", f'tgl{sfx}': "", f'alasan{sfx}': ""})
                        
                        doc.render(ctx)
                        fn = f"{t[14]}_{t[13]}.docx"
                        doc.save(f"arsip_rme/{fn}")
                        convert_to_pdf(f"arsip_rme/{fn}", "arsip_rme/")
                        
                        # 4. Update DB
                        db.execute("UPDATE rme_tasks SET status='Selesai', waktu_selesai=? WHERE id=?", (now.strftime("%H:%M"), t[0]))
                        db.commit()
                        st.success(f"✅ Tiket #{t[0]} Selesai!")
                        time.sleep(1); st.rerun()
    else:
        st.info("Kopi dulu Mas, antrian lagi kosong!")
    db.close()

# =========================================================
# 7. ARSIP DIGITAL
# =========================================================
elif menu == "📂 Arsip Digital":
    st.header("📂 Arsip Hasil Eksekusi")
    db = init_db()
    df_arsip = pd.read_sql_query("SELECT * FROM rme_tasks WHERE status='Selesai' ORDER BY id DESC", db)
    if not df_arsip.empty:
        for _, r in df_arsip.iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([3,2,1,1])
                c1.write(f"**{r['pasien_display']}** (RM: {r['rm_utama']})")
                c2.write(f"IT: {r['it_executor']} | Jam: {r['waktu_selesai']}")
                
                f_docx = f"arsip_rme/{r['file_name']}"
                f_pdf = f_docx.replace(".docx", ".pdf")
                
                if os.path.exists(f_docx):
                    with open(f_docx, "rb") as f: c3.download_button("📂 DOCX", f, file_name=r['file_name'], key=f"d_{r['id']}")
                if os.path.exists(f_pdf):
                    with open(f_pdf, "rb") as f: c4.download_button("🖨️ CETAK", f, file_name=f_pdf.split("/")[-1], mime="application/pdf", key=f"p_{r['id']}")
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

