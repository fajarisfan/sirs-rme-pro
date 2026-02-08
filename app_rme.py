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
# PERBAIKAN: Menggunakan label secrets yang benar
# Cukup tulis begini, JANGAN masukin link-nya di sini
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="SIRS RME Pro 2026", layout="wide", page_icon="🏥")

# Folder Setup
for folder in ["temp", "arsip_rme"]:
    if not os.path.exists(folder): os.makedirs(folder)

LIST_IT = ["Isfan", "Udin", "Rey", "Jaka", "Teguh", "Ferdi", "Hisyam"]

# --- FUNGSI TANGGAL OTOMATIS INDONESIA ---
def get_tgl_indo():
    hari_dict = {
        'Monday': 'Senin', 'Tuesday': 'Selasa', 'Wednesday': 'Rabu',
        'Thursday': 'Kamis', 'Friday': 'Jumat', 'Saturday': 'Sabtu', 'Sunday': 'Minggu'
    }
    bulan_dict = {
        1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April', 5: 'Mei', 6: 'Juni',
        7: 'Juli', 8: 'Agustus', 9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember'
    }
    now = datetime.now()
    nama_hari = hari_dict.get(now.strftime('%A'), now.strftime('%A'))
    tgl = now.day
    nama_bulan = bulan_dict.get(now.month, now.month)
    tahun = now.year
    return f"{nama_hari}, {tgl} {nama_bulan} {tahun}"

# =========================================================
# 2. DATABASE FUNCTIONS
# =========================================================
def init_db():
    conn = sqlite3.connect('rme_system.db', check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS rme_tasks 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, unit TEXT, data_pasien TEXT, 
                  status TEXT, file_name TEXT, waktu_input TEXT, waktu_selesai TEXT,
                  pemohon TEXT, nip_user TEXT, it_executor TEXT, nip_it TEXT, 
                  ttd_user_path TEXT, ip_address TEXT, rm_utama TEXT, pasien_display TEXT)''')
    c.execute("CREATE TABLE IF NOT EXISTS profiles (nama TEXT PRIMARY KEY, nip TEXT)")
    conn.commit()
    return conn

def get_nip_profile(nama):
    if not nama: return ""
    with init_db() as conn:
        res = conn.execute("SELECT nip FROM profiles WHERE nama=?", (nama,)).fetchone()
        return res[0] if res else ""

def save_nip_profile(nama, nip):
    if not nama or not nip: return
    with init_db() as conn:
        conn.execute("INSERT OR REPLACE INTO profiles (nama, nip) VALUES (?, ?)", (nama, nip))
        conn.commit()

def play_notif_sound():
    sound_url = "https://www.soundjay.com/buttons/sounds/button-3.mp3"
    st.markdown(f'<audio autoplay><source src="{sound_url}" type="audio/mp3"></audio>', unsafe_allow_html=True)

# =========================================================
# 3. SIDEBAR NAVIGATION
# =========================================================
with st.sidebar:
    st.title("🏥 SIRS RME PRO")
    
    html_jam = """
    <div style="background-color: #0e1117; padding: 10px; border-radius: 10px; border: 1px solid #00ff00; text-align: center;">
        <span id="clock" style="color: #00ff00; font-family: monospace; font-size: 28px; font-weight: bold;">00:00:00</span>
    </div>
    <script>
        function updateTime() {
            var now = new Date();
            var h = String(now.getHours()).padStart(2, '0');
            var m = String(now.getMinutes()).padStart(2, '0');
            var s = String(now.getSeconds()).padStart(2, '0');
            document.getElementById('clock').innerHTML = h + ":" + m + ":" + s;
        }
        updateTime(); setInterval(updateTime, 1000);
    </script>
    """
    components.html(html_jam, height=75)
    st.divider()

    if 'is_it_authenticated' not in st.session_state:
        st.session_state.is_it_authenticated = False

    st.subheader("🌐 Menu Umum")
    menu_umum = st.radio("Pilih Layanan:", ["📊 Monitor Antrian", "📝 Input Form"], label_visibility="collapsed")
    st.divider()

    st.subheader("🛠️ Panel Kontrol IT")
    menu_it = None
    if not st.session_state.is_it_authenticated:
        with st.expander("🔓 Login Petugas IT"):
            pin_input = st.text_input("PIN IT:", type="password", key="pin_it")
            if pin_input == "1234":
                st.session_state.is_it_authenticated = True
                st.rerun()
            elif pin_input != "":
                st.error("PIN Salah!")
    else:
        st.success("✅ Mode IT Aktif")
        menu_it = st.radio("Workspace IT:", ["👨‍💻 Workspace IT", "📂 Arsip Digital"], label_visibility="collapsed")
        if st.button("🔴 Logout / Kunci"):
            st.session_state.is_it_authenticated = False
            st.rerun()

    menu = menu_it if menu_it else menu_umum
    st.divider()
    
    db = init_db()
    total_antri = db.execute("SELECT count(*) FROM rme_tasks WHERE status='Masuk Antrian'").fetchone()[0]
    db.close()

    if 'old_antri' not in st.session_state: st.session_state.old_antri = total_antri
    if total_antri > st.session_state.old_antri:
        play_notif_sound()
        st.toast("🔔 Ada Permintaan Baru Masuk!")
        st.session_state.old_antri = total_antri

    st.metric("Antrian Terbuka", f"{total_antri} Task")

# =========================================================
# 4. MENU 1: MONITOR REAL-TIME
# =========================================================
if menu == "📊 Monitor Antrian":
    st_autorefresh(5000, key="mon_ref")
    st.header("Real-time Monitor Antrian")
    db = init_db()
    df = pd.read_sql_query("""
        SELECT waktu_input as 'Jam Masuk', pemohon as 'User', 
        pasien_display as 'Pasien', status as 'Status' 
        FROM rme_tasks ORDER BY id DESC LIMIT 10
    """, db)
    st.table(df)
    db.close()

# =========================================================
# 5. MENU 2: INPUT FORM
# =========================================================
elif menu == "📝 Input Form":
    st.header("📝 Form Penghapusan RME")
    if 'step' not in st.session_state: st.session_state.step = 1
    if 'data_p' not in st.session_state: st.session_state.data_p = []

    with st.expander("👤 Identitas Pemohon", expanded=(st.session_state.step == 1)):
        c1, c2 = st.columns(2)
        u_nama = c1.text_input("Nama Pemohon", key="unama")
        u_nip = c1.text_input("NIP/NIK", value=get_nip_profile(u_nama))
        u_unit = c2.text_input("Unit/Ruangan")
        u_it = c2.selectbox("Petugas IT", ["Bebas (Siapa Saja)"] + LIST_IT)

    if st.session_state.step == 1 and not st.session_state.data_p:
        st.session_state.jml = st.number_input("Jumlah Pasien", 1, 4, 1)

    if st.session_state.step <= st.session_state.get('jml', 1):
        s = st.session_state.step
        st.subheader(f"📍 Data Pasien ke-{s}")
        with st.container(border=True):
            p_nama = st.text_input(f"Nama Pasien {s}")
            col_r, col_t = st.columns(2)
            p_rm = col_r.text_input(f"No. RM {s} (9 Digit)", max_chars=9)
            p_tgl = col_t.date_input(f"Tgl Kunjungan {s}")
            p_als = st.text_area(f"Alasan Penghapusan {s}")

            c_nav1, c_nav2 = st.columns(2)
            if s > 1 and c_nav1.button("⬅️ Kembali"):
                st.session_state.step -= 1
                st.session_state.data_p.pop()
                st.rerun()

            if c_nav2.button("Simpan & Lanjut ➡️", type="primary", use_container_width=True):
                if len(p_rm) == 9 and p_nama and p_als:
                    st.session_state.data_p.append({"nama":p_nama, "rm":p_rm, "tgl":str(p_tgl), "alasan":p_als})
                    st.session_state.step += 1
                    st.rerun()
                else: st.error("Lengkapi data & RM harus 9 digit!")
    else:
        st.success("✅ Data Pasien Lengkap")
        canvas = st_canvas(stroke_width=3, stroke_color="#000", background_color="#fff", height=150, width=400, key="can_u")
        if st.button("🚀 KIRIM KE IT", type="primary"):
             if canvas.image_data is not None and not (canvas.image_data[:, :, 3] == 0).all():
                path_ttd = f"temp/ttd_u_{datetime.now().strftime('%H%M%S')}.png"
                Image.fromarray(canvas.image_data.astype('uint8')).save(path_ttd)
                
                final_data = st.session_state.data_p
                clean_name = final_data[0]['nama'].replace(" ", "_").replace("/", "-")
                clean_rm = final_data[0]['rm']
                jam_save = datetime.now().strftime('%H%M%S')
                
                fname = f"PENGAJUAN_HAPUS_{clean_name}_{clean_rm}_{jam_save}.docx"
                p_disp = final_data[0]['nama'] + (f" (+{len(final_data)-1})" if len(final_data)>1 else "")

                waktu_sekarang = datetime.now().strftime("%H:%M:%S")
                
                save_nip_profile(u_nama, u_nip)
                db = init_db()
                db.execute('''INSERT INTO rme_tasks (unit, data_pasien, status, file_name, waktu_input, 
                              pemohon, nip_user, it_executor, ttd_user_path, ip_address, rm_utama, pasien_display) 
                              VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                            (u_unit, json.dumps(final_data), "Masuk Antrian", fname, waktu_sekarang, 
                             u_nama, u_nip, u_it, path_ttd, "127.0.0.1", clean_rm, p_disp))
                db.commit()
                db.close()
                
                st.session_state.clear()
                st.success(f"Terkirim sebagai: {fname}")
                st.rerun()

# =========================================================
# 6. MENU 3: WORKSPACE IT
# =========================================================
elif menu == "👨‍💻 Workspace IT":
    st.header("👨‍💻 IT Workspace & Dashboard")
    it_nama = st.selectbox("Petugas IT:", LIST_IT)
    it_nip = st.text_input("NIP IT", value=get_nip_profile(it_nama))
    
    db = init_db()
    tasks = db.execute("SELECT * FROM rme_tasks WHERE status IN ('Masuk Antrian', 'Proses Antrian') AND (it_executor = ? OR it_executor = 'Bebas (Siapa Saja)')", (it_nama,)).fetchall()
    
    for t in tasks:
        with st.expander(f"📥 {t[14]} ({t[1]}) - Masuk: {t[5]}"):
            p_json = json.loads(t[2])
            for p in p_json: st.code(f"RM: {p['rm']} | {p['nama']}")
            if t[3] == "Masuk Antrian":
                if st.button(f"Ambil Kerja {t[0]}", key=f"take_{t[0]}"):
                    db.execute("UPDATE rme_tasks SET status='Proses Antrian', it_executor=? WHERE id=?", (it_nama, t[0]))
                    db.commit(); st.rerun()
            else:
                can_it = st_canvas(stroke_width=3, stroke_color="#000", background_color="#fff", height=150, width=400, key=f"it_{t[0]}")
                if st.button(f"Selesaikan {t[0]}", type="primary", key=f"done_{t[0]}"):
                    
                    # --- PERBAIKAN: LOGIKA SUPABASE DIMASUKKAN KE SINI ---
                    try:
                        # 1. Simpan ke Supabase (Cloud Permanen)
                        data_supabase = {
                            "nama_pasien": t[14],
                            "no_rm": t[13],
                            "alasan": p_json[0]['alasan'],
                            "status": "Selesai"
                        }
                        supabase.table("arsip_rme").insert(data_supabase).execute()
                        st.info("☁️ Data di-backup ke Cloud")

                        # 2. Lanjut Logika Bikin Word & Simpan Lokal
                        jam_done_detail = datetime.now().strftime("%H:%M:%S")
                        tgl_indo_full = get_tgl_indo()
                        path_it = f"temp/ttd_it_{t[0]}.png"
                        Image.fromarray(can_it.image_data.astype('uint8')).save(path_it)
                        
                        doc = DocxTemplate("template_rme.docx")
                        ctx = {
                            'tgl_full': tgl_indo_full, 'unit': t[1], 'pemohon': t[7], 'nip_user': t[8],
                            'penerima': it_nama, 'nip_it': it_nip,
                            'ttd_user': InlineImage(doc, t[11], width=Inches(1.2)), 
                            'ttd_it': InlineImage(doc, path_it, width=Inches(1.2))
                        }
                        for i in range(4):
                            sfx = "" if i==0 else str(i+1)
                            if i < len(p_json): 
                                ctx.update({f'nama{sfx}':p_json[i]['nama'], f'rm{sfx}':p_json[i]['rm'], f'tgl{sfx}':p_json[i]['tgl'], f'alasan{sfx}':p_json[i]['alasan']})
                            else: 
                                ctx.update({f'nama{sfx}':"", f'rm{sfx}':"", f'tgl{sfx}':"", f'alasan{sfx}':""})
                        
                        doc.render(ctx)
                        doc.save(f"arsip_rme/{t[4]}")
                        
                        db.execute("UPDATE rme_tasks SET status='Selesai', it_executor=?, waktu_selesai=? WHERE id=?", (it_nama, jam_done_detail, t[0]))
                        db.commit()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal simpan: {e}")

    st.divider()
    df_perf = pd.read_sql_query("SELECT it_executor as Petugas, count(*) as Total FROM rme_tasks WHERE status='Selesai' GROUP BY it_executor", db)
    if not df_perf.empty: st.bar_chart(df_perf.set_index('Petugas'))
    db.close()

# =========================================================
# 7. MENU 4: ARSIP DIGITAL (LENGKAP DENGAN SEARCH)
# =========================================================
else:
    st.header("📂 Pusat Arsip Digital")
    db = init_db()
    search = st.text_input("🔍 Cari RM/Nama")
    query = "SELECT * FROM rme_tasks WHERE status='Selesai'"
    if search: query += f" AND (pasien_display LIKE '%{search}%' OR rm_utama LIKE '%{search}%')"
    arsip = pd.read_sql_query(query + " ORDER BY id DESC", db)
    
    for _, r in arsip.iterrows():
        with st.container(border=True):
            ca, cb, cc = st.columns([3, 2, 1])
            ca.write(f"**{r['pasien_display']}**")
            ca.caption(f"🕒 Masuk: {r['waktu_input']} | ✅ Selesai: {r['waktu_selesai']}")
            cb.write(f"Petugas: {r['it_executor']}")
            if os.path.exists(f"arsip_rme/{r['file_name']}"):
                with open(f"arsip_rme/{r['file_name']}", "rb") as f:
                    cc.download_button("💾 Download", f, file_name=r['file_name'], key=f"ars_{r['id']}")
    db.close()
