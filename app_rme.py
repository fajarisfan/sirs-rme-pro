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

# LIST TIM ELITE
LIST_IT = ["Isfan", "Udin", "Rey", "Jaka", "Teguh", "Ferdi", "Hisyam"]

# --- FUNGSI NOTIFIKASI SUARA ---
def play_notification():
    audio_url = "https://www.soundjay.com/buttons/sounds/button-3.mp3"
    html_code = f'<audio autoplay><source src="{audio_url}" type="audio/mpeg"></audio>'
    components.html(html_code, height=0)

# =========================================================
# 2. DATABASE & LOGIKA JADWAL (AUTOMATIC)
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
            mapping_nama = {
                "Teguh Adi Pradana": "Teguh", "Jaka Gilang R": "Jaka",
                "Ahmad Haerudin": "Udin", "Isfan Fajar Anugrah": "Isfan",
                "M. Hisyam Rizky": "Hisyam", "Ferdyansyah Zaelani": "Ferdi",
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
                pd.DataFrame(data_jadwal).to_sql('jadwal_it', db, if_exists='replace', index=False)
                db.commit()
                db.close()
                return True
    except: return False
    return False
    
@st.cache_data(ttl=60)
def get_it_aktif_sekarang():
    import pytz
    try:
        # 1. SET TIMEZONE JAKARTA
        tz = pytz.timezone('Asia/Jakarta')
        now = datetime.now(tz) 
        
        tgl_ini = now.day
        tgl_kmrn = (now - timedelta(days=1)).day
        jam_ini = now.hour
        
        db = init_db()
        # Ambil data hari ini & kemarin buat cover shift malam
        df = pd.read_sql_query(f"SELECT * FROM jadwal_it WHERE tanggal IN ({tgl_kmrn}, {tgl_ini})", db)
        db.close()
        
        petugas_on = []
        if df.empty: return ["⚠️ Database Kosong"]

        for _, row in df.iterrows():
            nama, s, tgl_data = row['nama'], str(row['shift']).upper().strip(), int(row['tanggal'])

            # --- LOGIKA SHIFT MALAM (M) ---
            if "M" in s:
                # Lepas piket (Malam kemarin, pulang jam 7 pagi ini)
                if tgl_data == tgl_kmrn and jam_ini < 7:
                    petugas_on.append(nama)
                # Masuk piket (Malam ini, baru muncul jam 9 malem)
                elif tgl_data == tgl_ini and jam_ini >= 21:
                    petugas_on.append(nama)

            # --- LOGIKA SHIFT PAGI (P/PS) ---
            elif ("P" in s or "PS" in s) and tgl_data == tgl_ini:
                # Muncul jam 7 pagi sampe jam 4 sore
                if 7 <= jam_ini < 16:
                    petugas_on.append(nama)

            # --- LOGIKA SHIFT SIANG (S) ---
            elif s == "S" and tgl_data == tgl_ini:
                # Muncul jam 2 siang sampe jam 9/10 malem
                limit = 22 if "HISYAM" in nama.upper() else 21
                if 14 <= jam_ini < limit:
                    petugas_on.append(nama)

        return sorted(list(set(petugas_on))) if petugas_on else ["Tidak ada petugas standby"]
    except Exception as e:
        return [f"⚠️ Error Jadwal: {e}"]
# =========================================================
# 3. SIDEBAR NAVIGATION
# =========================================================
with st.sidebar:
    st.title("🏥 SIRS RME PRO")
    # Kode Sementara buat Bersih-bersih
    if st.button("🔥 HAPUS SEMUA DATA TES"):
        conn = sqlite3.connect('rme_system.db')
        c = conn.cursor()
        c.execute("DELETE FROM rme_tasks") # Menghapus semua baris di tabel antrian
        conn.commit()
        conn.close()
        st.success("Database Bersih! Jangan lupa hapus tombol ini di kodingan ya.")
    if 'is_it_authenticated' not in st.session_state: 
        st.session_state.is_it_authenticated = False
    
    menu_umum_list = ["📊 Monitor Antrian", "📝 Input Form"]
    
    if not st.session_state.is_it_authenticated:
        with st.expander("🔑 IT LOGIN"):
            pin_input = st.text_input("PIN Admin IT:", type="password")
            if st.button("Masuk"):
                if pin_input == "1234":
                    st.session_state.is_it_authenticated = True
                    st.rerun()
                else: st.error("PIN Salah!")
        menu = st.radio("Pilih Halaman:", menu_umum_list)
    else:
        st.success("✅ Mode IT Aktif")
        menu_it_list = ["👨‍💻 Workspace IT", "📂 Arsip Digital", "📅 Dashboard Jadwal"]
        menu = st.radio("Pilih Halaman:", menu_umum_list + menu_it_list)
        if st.button("Logout Admin"):
            st.session_state.is_it_authenticated = False
            st.rerun()

# =========================================================
# 4. MENU: MONITOR ANTRIAN
# =========================================================
if menu == "📊 Monitor Antrian":
    st_autorefresh(5000)
    st.header("📊 Monitor Antrian Real-Time")
    db = init_db()
    df = pd.read_sql_query("SELECT waktu_input, pasien_display, it_executor, status FROM rme_tasks ORDER BY id DESC LIMIT 15", db)
    st.table(df)
    db.close()

# =========================================================
# 5. MENU: INPUT FORM
# =========================================================
elif menu == "📝 Input Form":
    st.header("📝 Form Penghapusan RME")
    # INISIALISASI STATE AGAR TIDAK ERROR
    if 'step' not in st.session_state: st.session_state.step = 1
    if 'data_p' not in st.session_state: st.session_state.data_p = []
    # 1. Panggil fungsi sakti lu di sini
    petugas_ready = get_it_aktif_sekarang()

    with st.expander("👤 Identitas Pemohon", expanded=True):
        c1, c2 = st.columns(2)
        u_nama = c1.text_input("Nama Pemohon")
        u_unit = c2.text_input("Unit/Ruangan")
        u_nip = c1.text_input("NIP Pemohon", placeholder="Ketik NIP di sini...")
        # 2. Masukkan hasilnya ke selectbox
        # Jam 18:45 ini, isinya otomatis cuma Teguh & Hisyam
        u_it = c2.selectbox("Petugas IT Standby", petugas_ready)
    if st.session_state.step == 1:
        st.session_state.jml = st.number_input("Jumlah Pasien", 1, 4, 1)

    if st.session_state.step <= st.session_state.get('jml', 1):
        s = st.session_state.step
        st.subheader(f"📍 Data Pasien ke-{s}")
        with st.container(border=True):
            p_nama = st.text_input(f"Nama Pasien {s}", key=f"nm_{s}")
            p_rm = st.text_input(f"No. RM {s} (9 Digit)", max_chars=9, key=f"rm_{s}")
            p_als = st.text_area(f"Alasan Penghapusan {s}", key=f"al_{s}")
            if st.button("Simpan & Lanjut ➡️", key=f"btn_{s}"):
                if len(p_rm) == 9 and p_nama:
                    st.session_state.data_p.append({"nama": p_nama, "rm": p_rm, "alasan": p_als})
                    st.session_state.step += 1
                    st.rerun()
                else: st.error("Lengkapi data!")
    else:
        st.success("✅ Data Lengkap. Silahkan Tanda Tangan:")
        canvas = st_canvas(stroke_width=3, stroke_color="#000", background_color="#fff", height=150, width=400, key="can_u")
        if st.button("🚀 KIRIM KE IT", type="primary"):
            if canvas.image_data is not None:
                path_ttd = f"temp/ttd_u_{datetime.now().strftime('%H%M%S')}.png"
                Image.fromarray(canvas.image_data.astype('uint8')).save(path_ttd)
                rm_utama = st.session_state.data_p[0]['rm']
                nama_utama = st.session_state.data_p[0]['nama']
                db = init_db()
                db.execute('''INSERT INTO rme_tasks (unit, data_pasien, status, file_name, waktu_input, 
                              pemohon, nip_user, it_executor, ttd_user_path, rm_utama, pasien_display) 
                              VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                            (u_unit, json.dumps(st.session_state.data_p), "Masuk Antrian", f"HAPUS_RME_{rm_utama}.docx", 
                            jam_skrg = get_now_jakarta().strftime("%H:%M"), u_nama, u_nip, u_it, path_ttd, rm_utama, nama_utama))
                db.commit()
                db.close()
                st.session_state.clear()
                st.rerun()

# =========================================================
# 6. MENU: WORKSPACE IT (TTD IT & DOCX GENERATE)
# =========================================================
elif menu == "👨‍💻 Workspace IT":
    st_autorefresh(5000)
    st.header("👨‍💻 Workspace IT")
    it_nama = st.selectbox("Pilih Nama Lu:", LIST_IT)
    db = init_db()
    tasks = db.execute("SELECT * FROM rme_tasks WHERE status='Masuk Antrian' AND it_executor=?", (it_nama,)).fetchall()
    
    if tasks:
        play_notification()
        for t in tasks:
            with st.expander(f"📥 Task: {t[14]} (RM: {t[13]})", expanded=True):
                p_json = json.loads(t[2])
                # Ambil alasan dari pasien pertama buat dikirim ke Supabase
                alasan_pertama = p_json[0]['alasan'] if p_json else "-"
                
                can_it = st_canvas(stroke_width=3, stroke_color="#000", background_color="#fff", height=150, width=400, key=f"it_{t[0]}")
                if st.button(f"Selesaikan {t[0]}", type="primary"):
                    path_it = f"temp/ttd_it_{t[0]}.png"
                    Image.fromarray(can_it.image_data.astype('uint8')).save(path_it)
                    
                    # LOGIKA GENERATE DOCX (Tetap sama)
                    doc = DocxTemplate("template_rme.docx")
                    ctx = {'unit': t[1], 'pemohon': t[7], 'nip_user': t[8], 'penerima': it_nama,
                           'ttd_user': InlineImage(doc, t[11], width=Inches(1.2)),
                           'ttd_it': InlineImage(doc, path_it, width=Inches(1.2))}
                    for i in range(4):
                        sfx = "" if i==0 else str(i+1)
                        if i < len(p_json): ctx.update({f'nama{sfx}':p_json[i]['nama'], f'rm{sfx}':p_json[i]['rm'], f'alasan{sfx}':p_json[i]['alasan']})
                        else: ctx.update({f'nama{sfx}':"-", f'rm{sfx}':"-", f'alasan{sfx}':"-"})
                    doc.render(ctx)
                    doc.save(f"arsip_rme/{t[4]}")
                    
                    # --- FIX SUPABASE DISINI ---
                    # Kita sesuaikan dengan kolom di screenshot lu: nama_pasien, no_rm, alasan, status
                    try:
                        supabase.table("arsip_rme").insert({
                            "nama_pasien": str(t[14]), 
                            "no_rm": str(t[13]), 
                            "alasan": str(alasan_pertama), # Ngambil dari data pasien
                            "status": "Selesai"
                        }).execute()
                    except Exception as e:
                        st.error(f"Gagal kirim cloud: {e}")
                    
                    # UPDATE DB LOKAL (Gunakan jam Jakarta)
                    jam_selesai = get_now_jakarta().strftime("%H:%M")
                    db.execute("UPDATE rme_tasks SET status='Selesai', waktu_selesai=? WHERE id=?", (jam_selesai, t[0]))
                    db.commit()
                    st.success("Berhasil diselesaikan!")
                    time.sleep(1)
                    st.rerun()
    else: st.info("Belum ada antrian.")
    db.close()

# =========================================================
# 7. MENU: ARSIP DIGITAL
# =========================================================
elif menu == "📂 Arsip Digital":
    st.header("📂 Arsip Digital")
    db = init_db()
    df_arsip = pd.read_sql_query("SELECT * FROM rme_tasks WHERE status='Selesai' ORDER BY id DESC", db)
    if not df_arsip.empty:
        for _, r in df_arsip.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([3,2,1])
                c1.write(f"**{r['pasien_display']}** (RM: {r['rm_utama']})")
                c2.write(f"Petugas: {r['it_executor']} | Selesai: {r['waktu_selesai']}")
                if os.path.exists(f"arsip_rme/{r['file_name']}"):
                    with open(f"arsip_rme/{r['file_name']}", "rb") as f:
                        c3.download_button("📂 Download", f, file_name=r['file_name'], key=f"dl_{r['id']}")
    else: st.info("Belum ada arsip.")
    db.close()

# =========================================================
# 8. MENU: DASHBOARD JADWAL
# =========================================================
elif menu == "📅 Dashboard Jadwal":
    st.header("📅 Dashboard Jadwal IT")
    with st.container(border=True):
        pdf_file = st.file_uploader("Upload PDF Jadwal Baru", type="pdf")
        if st.button("🚀 Proses Update Sekarang"):
            if pdf_file is not None:
                with st.spinner('Memproses...'):
                    if update_jadwal_dari_pdf(pdf_file):
                        st.success("✅ Jadwal Berhasil Diupdate!")
                        time.sleep(1)
                        st.rerun()
                    else: st.error("❌ Gagal!")
            else: st.warning("Pilih file dulu!")

    st.divider()
    try:
        db = init_db()
        df_view = pd.read_sql_query("SELECT * FROM jadwal_it ORDER BY tanggal ASC", db)
        db.close()
        if not df_view.empty:
            tgl_skrg = datetime.now().day
            cek_tgl = st.slider("Lihat jadwal tanggal:", 1, 31, tgl_skrg)
            st.table(df_view[df_view['tanggal'] == cek_tgl])
    except: st.error("Gagal preview.")







