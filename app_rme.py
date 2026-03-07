import streamlit as st
import streamlit.components.v1 as components
from streamlit_drawable_canvas import st_canvas
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Inches
import os, json, pandas as pd
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
st.set_page_config(page_title="SIRS RME Pro 2026", layout="wide", page_icon="🏥")

# FITUR: Auto Refresh setiap 30 detik (Keep Server Alive)
st_autorefresh(interval=30000, key="datarefresh")

url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

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

def play_notification():
    audio_url = "https://www.soundjay.com/buttons/sounds/button-3.mp3"
    html_code = f'<audio autoplay><source src="{audio_url}" type="audio/mpeg"></audio>'
    components.html(html_code, height=0)

# Folder temp untuk file sementara
for folder in ["temp"]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# =========================================================
# 2. DATABASE & LOGIKA JADWAL (SUPABASE)
# =========================================================

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
                # Hapus jadwal lama lalu insert baru
                supabase.table("jadwal_it").delete().neq("nama", "").execute()
                supabase.table("jadwal_it").insert(data_jadwal).execute()
                return True
    except:
        return False
    return False

def get_it_aktif_sekarang():
    try:
        now = get_now_jakarta()
        tgl_ini, tgl_kmrn, jam_ini = now.day, (now - timedelta(days=1)).day, now.hour

        res = supabase.table("jadwal_it").select("*").in_("tanggal", [tgl_kmrn, tgl_ini]).execute()
        df = pd.DataFrame(res.data)

        petugas_on = []
        if df.empty:
            return ["⚠️ Database Kosong"]

        for _, row in df.iterrows():
            nama, s, tgl_data = row['nama'], str(row['shift']).upper().strip(), int(row['tanggal'])
            if "M" in s:
                if (tgl_data == tgl_ini and jam_ini < 7) or (tgl_data == tgl_ini and jam_ini >= 21): petugas_on.append(nama)
            elif ("P" in s or "PS" in s) and tgl_data == tgl_ini:
                if 7 <= jam_ini < 16:
                    petugas_on.append(nama)
            elif s == "S" and tgl_data == tgl_ini:
                limit = 22 if "HISYAM" in nama.upper() else 21
                if 14 <= jam_ini < limit:
                    petugas_on.append(nama)

        return sorted(list(set(petugas_on))) if petugas_on else ["Tidak ada petugas standby"]
    except:
        return ["⚠️ Error Jadwal"]

# =========================================================
# 3. SIDEBAR & NAVIGATION
# =========================================================
with st.sidebar:
    st.title("🏥 SIRS RME PRO")

    # FITUR: Ucapan Puasa Berdasarkan Jam Jakarta
    now_jk = get_now_jakarta()
    if 4 <= now_jk.hour < 18:
        st.info("🌙 Selamat Menjalankan Ibadah Puasa!")
    elif 18 <= now_jk.hour < 20:
        st.success("🍲 Selamat Berbuka Puasa!")

    # FITUR: Lonceng Notifikasi Tiket Baru
    try:
        res_count = supabase.table("rme_tasks").select("id", count="exact").eq("status", "Masuk Antrian").execute()
        antrian_db = res_count.count if res_count.count else 0
    except:
        antrian_db = 0

    if antrian_db > 0:
        st.warning(f"🔔 {antrian_db} Tiket Baru!")
        if st.session_state.get('last_antrian_count', 0) < antrian_db:
            play_notification()
            st.session_state.last_antrian_count = antrian_db

    if st.button("🔥 HAPUS SEMUA DATA TES"):
        supabase.table("rme_tasks").delete().neq("id", 0).execute()
        st.success("Database Bersih!")

    if 'is_it_authenticated' not in st.session_state:
        st.session_state.is_it_authenticated = False

    menu_umum = ["🏠 Dashboard Info", "📊 Monitor Antrian", "📝 Input Form", "📈 Statistik Performa"]

    if not st.session_state.is_it_authenticated:
        with st.expander("🔑 IT LOGIN"):
            pin = st.text_input("PIN Admin IT:", type="password")
            if st.button("Masuk"):
                if pin == "1234":
                    st.session_state.is_it_authenticated = True
                    st.rerun()
                else:
                    st.error("PIN Salah!")
        menu = st.radio("Pilih Halaman:", menu_umum)
    else:
        st.success("✅ Mode IT Aktif")
        menu = st.radio("Pilih Halaman:", menu_umum + ["👨‍💻 Workspace IT", "📂 Arsip Digital", "📅 Dashboard Jadwal"])
        if st.button("Logout Admin"):
            st.session_state.is_it_authenticated = False
            st.rerun()

# =========================================================
# 4. DASHBOARD & STATISTIK
# =========================================================
if menu == "🏠 Dashboard Info":
    st.markdown("""
        # 🏥 SIRS RME PRO 2026
        **Digitalisasi Layanan IT untuk Akurasi & Efisiensi RS**
        ---
        ### 🎯 Mengapa Sistem Ini Dibuat?
        Sistem ini adalah wujud dukungan Departemen IT untuk memudahkan rekan-rekan medis dalam proses administrasi pembatalan RME.
    """)
    st.info("💡 Klik menu **📝 Input Form** untuk mulai mengajukan.")

elif menu == "📈 Statistik Performa":
    st.header("📈 Monitoring Kinerja IT")
    res_stat = supabase.table("rme_tasks").select("it_executor, status").execute()
    df_stat = pd.DataFrame(res_stat.data)
    if not df_stat.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.write("### Beban Kerja IT")
            st.bar_chart(df_stat['it_executor'].value_counts())
        with c2:
            st.write("### Status Tiket")
            st.bar_chart(df_stat['status'].value_counts())
    else:
        st.info("Data statistik belum tersedia.")

# =========================================================
# 5. MONITOR ANTRIAN (STYLE TIKET)
# =========================================================
elif menu == "📊 Monitor Antrian":
    st.header("📊 Monitor Antrian Real-Time")

    res = supabase.table("rme_tasks").select("id, waktu_input, pasien_display, it_executor, status, unit").order("id", desc=True).limit(9).execute()
    df = pd.DataFrame(res.data)

    if not df.empty:
        cols = st.columns(3)
        for index, row in df.iterrows():
            with cols[index % 3]:
                if row['status'] == "Masuk Antrian":
                    bg, lbl = "#FFE5E5", "🔴 Menunggu IT"
                elif row['status'] == "Menunggu":
                    bg, lbl = "#FFF4E0", "🟡 Sedang Diproses"
                else:
                    bg, lbl = "#E5FFEA", "🟢 Selesai"

                st.markdown(f"""
                <div style="background-color:{bg}; padding:15px; border-radius:10px; border-left: 5px solid #333; margin-bottom:15px; color:black;">
                    <div style="display:flex; justify-content:space-between;"><b>Tiket #{row['id']}</b><small>{row['waktu_input']}</small></div>
                    <div style="margin:10px 0;"><div style="font-size:18px; font-weight:bold;">{row['pasien_display']}</div>Unit: {row['unit']}</div>
                    <div style="border-top:1px solid #999; padding-top:5px; font-size:13px;">Petugas IT: <b>{row['it_executor']}</b></div>
                    <div style="margin-top:10px; text-align:center; font-weight:bold;">{lbl}</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Belum ada antrian saat ini.")

# =========================================================
# 6. INPUT FORM
# =========================================================
elif menu == "📝 Input Form":
    st.header("📝 Form Penghapusan RME")
    if 'step' not in st.session_state: st.session_state.step = 1
    if 'data_p' not in st.session_state: st.session_state.data_p = []

    petugas_ready = get_it_aktif_sekarang()

    with st.expander("👤 Identitas Pemohon", expanded=True):
        c1, c2 = st.columns(2)
        u_nama = c1.text_input("Nama Pemohon")
        u_unit = c2.text_input("Unit/Ruangan")
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
                    st.session_state.step += 1
                    st.rerun()
                else:
                    st.error("Data Belum Lengkap!")
    else:
        st.success("✅ Data Lengkap. Silahkan Tanda Tangan:")
        canvas = st_canvas(stroke_width=3, stroke_color="#000", background_color="#fff", height=150, width=400, key="can_u")

        if st.button("🚀 KIRIM KE IT", type="primary"):
            if canvas.image_data is not None and u_nama and u_nip:
                jam_wib = get_now_jakarta().strftime("%H:%M")

                # Simpan TTD sementara lalu upload ke Supabase Storage
                path_ttd_tmp = f"temp/ttd_u_{datetime.now().strftime('%H%M%S')}.png"
                Image.fromarray(canvas.image_data.astype('uint8')).save(path_ttd_tmp)

                ttd_storage_path = f"ttd/{os.path.basename(path_ttd_tmp)}"
                with open(path_ttd_tmp, "rb") as f:
                    supabase.storage.from_("arsip-rme").upload(ttd_storage_path, f)

                rm_utama = st.session_state.data_p[0]['rm']
                nama_utama = st.session_state.data_p[0]['nama']

                # Insert ke Supabase table
                supabase.table("rme_tasks").insert({
                    "unit": u_unit,
                    "data_pasien": json.dumps(st.session_state.data_p),
                    "status": "Masuk Antrian",
                    "file_name": f"HAPUS_RME_{rm_utama}.docx",
                    "waktu_input": jam_wib,
                    "pemohon": u_nama,
                    "nip_user": u_nip,
                    "it_executor": u_it,
                    "ttd_user_path": ttd_storage_path,
                    "rm_utama": rm_utama,
                    "pasien_display": nama_utama
                }).execute()

                it_info = MAPPING_IT_DETAIL.get(u_it, {"wa": "628123456789"})
                pesan = f"Halo Mas {u_it}, saya {u_nama} dari {u_unit} mengirim pengajuan RME untuk pasien {nama_utama}."
                st.session_state.url_wa = f"https://wa.me/{it_info['wa']}?text={urllib.parse.quote(pesan)}"
                st.session_state.form_done = True
                st.rerun()

    if st.session_state.get('form_done'):
        st.success("✅ Terkirim!")
        st.link_button("📲 HUBUNGI IT VIA WHATSAPP", st.session_state.url_wa)
        if st.button("Isi Form Baru"):
            st.session_state.clear()
            st.rerun()

# =========================================================
# 7. WORKSPACE IT (EKSKLUSIF)
# =========================================================
elif menu == "👨‍💻 Workspace IT":
    st.header("👨‍💻 Workspace Eksekusi IT")

    # Ambil IT yang punya antrian aktif
    res_it = supabase.table("rme_tasks").select("it_executor").neq("status", "Selesai").execute()
    it_aktif_antrian = list(set([r["it_executor"] for r in res_it.data])) if res_it.data else []

    if it_aktif_antrian:
        it_nama = st.selectbox("Konfirmasi Identitas Anda:", it_aktif_antrian)

        res_tasks = supabase.table("rme_tasks").select("*").neq("status", "Selesai").eq("it_executor", it_nama).execute()
        tasks = res_tasks.data

        for t in tasks:
            with st.expander(f"📥 Tiket #{t['id']} - {t['pasien_display']}", expanded=True):
                st.write(f"Unit: **{t['unit']}** | Pemohon: **{t['pemohon']}**")

                if t['status'] == "Masuk Antrian":
                    if st.button(f"Terima Tugas {t['id']}", key=f"acc_{t['id']}"):
                        supabase.table("rme_tasks").update({"status": "Menunggu"}).eq("id", t['id']).execute()
                        st.rerun()

                elif t['status'] == "Menunggu":
                    can_it = st_canvas(stroke_width=3, stroke_color="#000", background_color="#fff", height=150, width=400, key=f"it_{t['id']}")

                    if st.button(f"Selesaikan & Generate Dokumen #{t['id']}", type="primary", key=f"fin_{t['id']}"):
                        now = get_now_jakarta()
                        hari_map = {
                            'Monday': 'Senin', 'Tuesday': 'Selasa', 'Wednesday': 'Rabu',
                            'Thursday': 'Kamis', 'Friday': 'Jumat', 'Saturday': 'Sabtu', 'Sunday': 'Minggu'
                        }
                        bulan_map = {
                            'January': 'Januari', 'February': 'Februari', 'March': 'Maret',
                            'April': 'April', 'May': 'Mei', 'June': 'Juni', 'July': 'Juli',
                            'August': 'Agustus', 'September': 'September', 'October': 'Oktober',
                            'November': 'November', 'December': 'Desember'
                        }
                        tgl_indo = f"{now.strftime('%d')} {bulan_map[now.strftime('%B')]} {now.strftime('%Y')}"
                        hari_tgl = f"{hari_map[now.strftime('%A')]}, {tgl_indo}"

                        it_info = MAPPING_IT_DETAIL.get(it_nama, {"nip": "NIP. ..........."})

                        # Download TTD user dari Supabase Storage
                        path_ttd_user_tmp = f"temp/ttd_user_dl_{t['id']}.png"
                        ttd_bytes = supabase.storage.from_("arsip-rme").download(t['ttd_user_path'])
                        with open(path_ttd_user_tmp, "wb") as f:
                            f.write(ttd_bytes)

                        # Simpan TTD IT sementara lalu upload ke Storage
                        path_it_tmp = f"temp/ttd_it_{t['id']}.png"
                        Image.fromarray(can_it.image_data.astype('uint8')).save(path_it_tmp)

                        # Generate dokumen
                        doc = DocxTemplate("template_rme.docx")
                        ctx = {
                            'tgl_full': hari_tgl, 'unit': t['unit'].upper(), 'penerima': it_nama,
                            'nip_it': it_info['nip'], 'pemohon': t['pemohon'], 'nip_user': t['nip_user'],
                            'ttd_user': InlineImage(doc, path_ttd_user_tmp, width=Inches(1.0)),
                            'ttd_it': InlineImage(doc, path_it_tmp, width=Inches(1.0))
                        }

                        p_json = json.loads(t['data_pasien'])
                        for i in range(4):
                            sfx = "" if i == 0 else str(i + 1)
                            if i < len(p_json):
                                ctx.update({
                                    f'nama{sfx}': p_json[i]['nama'], f'rm{sfx}': p_json[i]['rm'],
                                    f'tgl{sfx}': tgl_indo, f'alasan{sfx}': p_json[i]['alasan']
                                })
                            else:
                                ctx.update({f'nama{sfx}': "", f'rm{sfx}': "", f'tgl{sfx}': "", f'alasan{sfx}': ""})

                        fn = f"{t['pasien_display']}_{t['rm_utama']}.docx"
                        path_docx_tmp = f"temp/{fn}"
                        doc.render(ctx)
                        doc.save(path_docx_tmp)

                        # Konversi ke PDF
                        path_pdf_tmp = convert_to_pdf(path_docx_tmp, "temp/")

                        # Upload DOCX ke Supabase Storage
                        with open(path_docx_tmp, "rb") as f:
                            supabase.storage.from_("arsip-rme").upload(f"arsip/{fn}", f)

                        # Upload PDF ke Supabase Storage
                        if path_pdf_tmp and os.path.exists(path_pdf_tmp):
                            fn_pdf = fn.replace(".docx", ".pdf")
                            with open(path_pdf_tmp, "rb") as f:
                                supabase.storage.from_("arsip-rme").upload(f"arsip/{fn_pdf}", f)

                        # Update status ke Selesai
                        supabase.table("rme_tasks").update({
                            "status": "Selesai",
                            "waktu_selesai": now.strftime("%H:%M")
                        }).eq("id", t['id']).execute()

                        st.success(f"✅ Tiket #{t['id']} Selesai!")
                        time.sleep(1)
                        st.rerun()
    else:
        st.info("Antrian kosong.")

# =========================================================
# 8. ARSIP DIGITAL
# =========================================================
elif menu == "📂 Arsip Digital":
    st.header("📂 Arsip Digital")

    res_arsip = supabase.table("rme_tasks").select("*").eq("status", "Selesai").order("id", desc=True).execute()
    df_arsip = pd.DataFrame(res_arsip.data)

    if not df_arsip.empty:
        for _, r in df_arsip.iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
                c1.write(f"**{r['pasien_display']}** ({r['rm_utama']})")
                c2.write(f"💻 IT: {r['it_executor']} | {r['waktu_selesai']}")

                nama_file_fix = f"{r['pasien_display']}_{r['rm_utama']}.docx"
                nama_pdf_fix = nama_file_fix.replace(".docx", ".pdf")

                # Download DOCX dari Supabase Storage
                try:
                    docx_bytes = supabase.storage.from_("arsip-rme").download(f"arsip/{nama_file_fix}")
                    c3.download_button("📂 DOCX", docx_bytes, file_name=nama_file_fix, key=f"d_{r['id']}")
                except:
                    c3.write("–")

                # Download PDF dari Supabase Storage
                try:
                    pdf_bytes = supabase.storage.from_("arsip-rme").download(f"arsip/{nama_pdf_fix}")
                    c4.download_button("🖨️ PDF", pdf_bytes, file_name=nama_pdf_fix, key=f"p_{r['id']}")
                except:
                    c4.write("–")
    else:
        st.info("Arsip kosong.")

# =========================================================
# 9. DASHBOARD JADWAL
# =========================================================
elif menu == "📅 Dashboard Jadwal":
    st.header("📅 Update Jadwal IT")
    pdf_file = st.file_uploader("Upload PDF Jadwal Baru", type="pdf")
    if st.button("🔄 Update Database Jadwal"):
        if pdf_file and update_jadwal_dari_pdf(pdf_file):
            st.success("✅ Berhasil!")
            time.sleep(1)
            st.rerun()

    st.divider()
    res_jadwal = supabase.table("jadwal_it").select("*").order("tanggal").execute()
    df_v = pd.DataFrame(res_jadwal.data)
    if not df_v.empty:
        t_pilih = st.slider("Cek Tanggal:", 1, 31, get_now_jakarta().day)
        st.table(df_v[df_v['tanggal'] == t_pilih])

