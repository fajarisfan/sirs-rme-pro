# 🏥 RME Request Portal

A full-cycle internal web application that automates the Electronic Medical Record (RME) deletion request workflow — replacing manual, room-to-room coordination between hospital staff and the IT division with a streamlined digital ticketing system.

---

## 🚨 Problem

The previous RME deletion process required hospital staff to physically visit the IT room, fill out a paper form manually, get it signed, and wait for IT to process it — a slow, inefficient workflow that disrupted both clinical and IT operations.

## ✅ Solution

A self-contained web portal where staff submit requests digitally and IT processes them in real-time — no paperwork, no physical trips, no confusion.

---

## 🔄 Workflow

```
[Staff / User]
  └── Fill form: No. RM · Patient Name · Deletion Reason · Digital Signature
  └── Select IT officer on duty (based on shift schedule)
  └── Submit → Queue number issued instantly

[IT Division]
  └── Receives incoming request notification
  └── Reviews & processes the deletion
  └── Signs digitally → Status updates to ✅ DONE

[Staff / User]
  └── Tracks queue status in real-time
  └── Downloads completed, signed PDF form automatically
```

---

## ✨ Features

- 📋 **Digital Request Form** — Unit, patient names, No. RM, visit dates, deletion reasons (up to 4 patients per request)
- 👨‍💻 **IT Shift Selector** — Staff picks the IT officer currently on duty
- 🔔 **Real-time Notifications** — IT receives instant alert on new request
- 🎫 **Queue Tracking** — Staff monitors request status via queue number
- ✍️ **Auto DOCX Generation** — Auto-fills official Word template with all submitted data including digital signatures — ready to download instantly
- ✅ **Status Management** — Ticket moves from `Pending → In Progress → Done`

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3 |
| Web UI | Streamlit |
| PDF Generation | pdfplumber / FPDF |
| Digital Signature | Pillow / Image Processing |
| Notification System | Streamlit Session State |
| Deployment | Streamlit Cloud |

---

## 🚀 Live Demo

🔗 *(Internal use — not publicly exposed due to operational constraints)*

---

## 💻 Run Locally

```bash
# Clone repo
git clone https://github.com/fajarisfan/rme-request-portal.git
cd rme-request-portal

# Install dependencies
pip install -r requirements.txt

# Run app
streamlit run app.py
```

---

## 📁 Project Structure

```
rme-request-portal/
├── app.py                  # Main Streamlit application & routing
├── form_generator.py       # Auto PDF form filling & digital signature logic
├── requirements.txt
└── README.md
```

---

## 🎯 Impact

- 🚶 Eliminated physical trips to IT room for RME deletion requests
- ⏱️ Reduced average request processing time significantly
- 📄 Auto-generates signed, print-ready PDF — zero manual writing
- 🔔 Real-time queue tracking for both staff and IT division
- 🏥 Designed for real hospital operational environment

---

## ⚠️ Disclaimer

This application does not store or expose any patient data. All form inputs are processed in-session only and exported directly as downloadable PDF. No database retains personal or medical information.

---

## 👤 Author

**Isfan Fajar Anugrah**
- GitHub: [@fajarisfan](https://github.com/fajarisfan)
- LinkedIn: [isfan-fajar-anugrah](https://linkedin.com/in/isfan-fajar-anugrah)
