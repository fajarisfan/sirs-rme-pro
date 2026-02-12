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
import pdfplumber

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

# LIST TIM ELITE (Sesuai Request)
LIST_IT = ["Isfan", "Udin", "Rey", "Jaka", "Teguh", "Ferdi", "Hisyam"]

# --- FUNGSI NOTIFIKASI SUARA ---
def play_notification():
    audio_url = "https://www.soundjay.com/buttons/sounds/button-3.mp3"
    html_code = f'<audio autoplay><source src="{audio_url}" type="audio/mpeg"></audio>'
    components.html(html_code, height=0)

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
    c.execute("CREATE TABLE IF NOT EXISTS jadwal_it (nama TEXT, tanggal INTEGER, shift TEXT)")
    conn.commit()
    return conn
def update_jadwal_dari_pdf(file_pdf):
    try:
        import pdfplumber
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
                db.execute("DELETE FROM jadwal_it") # Bersihin data lama
                pd.DataFrame(data_jadwal).to_sql('jadwal_it', db, if_exists='append', index=False)
                db.commit() # Simpan permanen
                db.close()
                return True # <--- INI KUNCI BIAR NOTIF MUNCUL
    except Exception as e:
        print(f"Error: {e}")
    return False # <--- Kalo gagal balikannya False
    
def get_it_aktif_sekarang():
    from datetime import datetime
    now = datetime.now()
    tgl_ini, jam_ini = now.day, now.hour
    
    db = init_db()
    try:
        # Ambil jadwal tim sesuai tanggal hari ini saja
        df_hari_ini = pd.read_sql_query(f"SELECT * FROM jadwal_it WHERE tanggal={tgl_ini}", db)
    except:
        df_hari_ini = pd.DataFrame()
    db.close()
    
    petugas_on = []
    if df_hari_ini.empty: return ["⚠️ Upload PDF Jadwal Dulu!"]

    for _, row in df_hari_ini.iterrows():
        nama, s = row['nama'], str(row['shift']).upper().strip()
        
        # 1. KALO KODE L (LIBUR) ATAU KOSONG, JANGAN MUNCULIN
        if s in ["L", "OFF", "LL", "/L", ""] or s is None:
            continue

        # 2. SHIFT PAGI (P) & PS (PAGI SIANG)
        # Sesuai PDF: Pulang jam 14.00 (P) atau 16.00 (PS).
        # Kita ambil batas aman jam 16.00 (4 sore) harus ilang.
        if s == "P" or "PS" in s:
            if 7 <= jam_ini < 16:
                petugas_on.append(f"{nama} ({s})")

        # 3. SHIFT SIANG (S)
        elif s == "S":
            # Hisyam (Siang) pulang jam 22.00
            if nama == "Hisyam":
                if 13 <= jam_ini < 22:
                    petugas_on.append(f"{nama} ({s})")
            # Teguh dkk (Siang) pulang jam 21.00
            else:
                if 14 <= jam_ini < 21:
                    petugas_on.append(f"{nama} ({s})")

        # 4. SHIFT MALAM (M / MM)
        # Baru muncul jam 21.00 (9 malem) sampai jam 07.00 pagi
        elif "M" in s:
            if jam_ini >= 21 or jam_ini < 7:
                petugas_on.append(f"{nama} ({s})")
    
    # Hapus nama ganda dan urutkan
    petugas_on = sorted(list(set(petugas_on)))
    
    return petugas_on if petugas_on else ["Tidak ada petugas standby"]
# =========================================================
# 3. SIDEBAR NAVIGATION
# =========================================================
with st.sidebar:
    st.title("🏥 SIRS RME PRO")
    if 'is_it_authenticated' not in st.session_state: 
        st.session_state.is_it_authenticated = False
    
    menu_umum_list = ["📊 Monitor Antrian", "📝 Input Form"]
    
    st.divider()
    if not st.session_state.is_it_authenticated:
        with st.expander("🔐 IT LOGIN"):
            pin_input = st.text_input("PIN Admin IT:", type="password")
            if st.button("Masuk"):
                if pin_input == "1234":
                    st.session_state.is_it_authenticated = True
                    st.rerun()
                else: st.error("PIN Salah!")
        menu = st.radio("Pilih Halaman:", menu_umum_list)
    else:
        st.success("✅ Mode IT Aktif")
        menu_it_list = ["👨‍💻 Workspace IT", "📁 Arsip Digital", "📊 Dashboard Jadwal"]
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
    if 'step' not in st.session_state: st.session_state.step = 1
    if 'data_p' not in st.session_state: st.session_state.data_p = []
    
    petugas_ready = get_it_aktif_sekarang()

    with st.expander("👤 Identitas Pemohon", expanded=(st.session_state.step == 1)):
        c1, c2 = st.columns(2)
        u_nama = c1.text_input("Nama Pemohon")
        u_nip = c1.text_input("NIP/NIK")
        u_unit = c2.text_input("Unit/Ruangan")
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
                             datetime.now().strftime("%H:%M"), u_nama, u_nip, u_it, path_ttd, rm_utama, nama_utama))
                db.commit()
                db.close()
                st.session_state.clear()
                st.rerun()

# =========================================================
# 6. MENU: WORKSPACE IT
# =========================================================
elif menu == "👨‍💻 Workspace IT":
    st_autorefresh(5000)
    st.header("👨‍💻 Workspace IT")
    it_nama = st.selectbox("Pilih Nama Lu:", LIST_IT)
    db = init_db()
    tasks = db.execute("SELECT * FROM rme_tasks WHERE status='Masuk Antrian' AND it_executor=?", (it_nama,)).fetchall()
    
    if tasks:
        play_notification()
        st.warning(f"🔔 Ada {len(tasks)} Permintaan!")
        for t in tasks:
            with st.expander(f"📥 Task: {t[14]} (RM: {t[13]})", expanded=True):
                p_json = json.loads(t[2])
                for p in p_json: st.write(f"- {p['nama']} (RM: {p['rm']})")
                can_it = st_canvas(stroke_width=3, stroke_color="#000", background_color="#fff", height=150, width=400, key=f"it_{t[0]}")
                if st.button(f"Selesaikan {t[0]}", type="primary"):
                    path_it = f"temp/ttd_it_{t[0]}.png"
                    Image.fromarray(can_it.image_data.astype('uint8')).save(path_it)
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
                    supabase.table("arsip_rme").insert({"nama_pasien": t[14], "no_rm": t[13], "it_executor": it_nama, "status": "Selesai"}).execute()
                    db.execute("UPDATE rme_tasks SET status='Selesai', waktu_selesai=? WHERE id=?", (datetime.now().strftime("%H:%M"), t[0]))
                    db.commit()
                    st.rerun()
    else:
        st.info("Belum ada antrian penghapusan RME.")
    db.close()

# =========================================================
# 7. MENU: ARSIP DIGITAL
# =========================================================
elif menu == "📁 Arsip Digital":
    st.header("📁 Arsip Digital")
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
                        c3.download_button("📥 Word", f, file_name=r['file_name'], key=f"dl_{r['id']}")
    else:
        st.info("Belum ada arsip tersimpan.")
    db.close()

# =========================================================
# 8. MENU: DASHBOARD JADWAL
# =========================================================
elif menu == "📊 Dashboard Jadwal":
    st.header("📊 Dashboard Jadwal IT")
    with st.container(border=True):
        pdf_file = st.file_uploader("Upload PDF Jadwal Baru", type="pdf")
        if st.button("🚀 Proses Update"):
            if pdf_file is not None:
                with st.spinner('Sedang memproses jadwal...'):
                    # Cek hasil balikan fungsi
                    hasil = update_jadwal_dari_pdf(pdf_file)
                    
                if hasil:
                    st.success("✅ Jadwal Berhasil Diupdate!")
                    st.toast("Data Ahmad Haerudin (Udin) & Tim Masuk Database!", icon="🔥")
                    st.balloons()
                    # Kasih jeda dikit sebelum rerun biar notif kebaca
                    import time
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error("❌ Gagal Update! Cek format PDF atau Mapping Nama.")
            else:
                st.warning("Pilih file PDF jadwal dulu)
    except:
        st.error("Gagal load pratinjau.")
    db.close()







