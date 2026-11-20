# Modul Odoo: Sistem Grading Sales Triwulan & Dashboard Supervisor
### PT. Aston Graphindo Indonesia — Divisi Sales & Marketing
**Versi:** `16.0.2.1.0` | **Kompatibilitas:** Odoo 16.0 Community & Enterprise (Python 3.10+, OWL 2.0)

Modul enterprise resmi evaluasi performa penjualan dan penetapan grade otomatis berbasis realisasi **Gross Profit (GP)** dari Sales Order (SO) terintegrasi dengan sistem GP ORIMAX.

---

## 🚀 Fitur Unggulan Sistem

### 1. Pemisahan Mutlak Dua Tabel (Tabel B vs Tabel A)
- **TABEL B (Satu-satunya Penentu Grade Salesman):**
  Grade karir ditentukan *murni* dari pencapaian rata-rata GP bulanan dalam satu triwulan:
  - **Star Sales:** $\ge$ Rp 77.000.000 / bulan
  - **Executive Sales:** Rp 55.000.000 s/d Rp 76.999.999
  - **Senior Sales:** Rp 30.000.000 s/d Rp 54.999.999
  - **Junior Sales:** Rp 15.000.000 s/d Rp 29.999.999
  - **New Sales:** < Rp 15.000.000
- **TABEL A (Target Penjualan & Hak Tunjangan):**
  Acuan target kinerja triwulan dan hak tunjangan fungsional (Star: Rp 100 Jt / Rp 2,25 Jt, Executive: Rp 77 Jt / Rp 1,5 Jt, Senior: Rp 55 Jt / Rp 750 Rb, Junior: Rp 30 Jt / Rp 300 Rb, New: Rp 15 Jt / Rp 0).
- **Indikator Perubahan Karir:**
  - 🟢 **Naik (Grade):** Blok Hijau
  - 🔵 **Tetap (Grade):** Blok Biru
  - 🔴 **Turun (Grade):** Blok Merah

### 2. Struktur Jabatan Supervisor Resmi (2 Grade) & Evaluasi 3 Triwulan
- **Supervisor:** Target GP **Rp 200 Juta / bulan** (Rp 600 Jt / TW). Komposisi tim: **6 – 8 Sales + 1 Spv**. Promosi ke Senior Supervisor jika rata-rata 3 triwulan berturut-turut $\ge 100\%$.
- **Senior Supervisor:** Target GP **Rp 300 Juta / bulan** (Rp 900 Jt / TW). Komposisi tim: **9 – 11 Sales + 1 Spv**. Turun grade ke Supervisor jika pencapaian target $< 70\%$ selama 3 triwulan.

### 3. Integrasi Live Data Real-Time GP ORIMAX
- Tarik data SO, Customer, Salesman, Net Omzet, HPP, Gross Profit langsung dari endpoint live ORIMAX.
- **Mapping Salesman Dinamis:** Dilengkapi toggle tombol **AKTIF / TIDAK AKTIF**. Salesman yang dinonaktifkan (misal: resign) otomatis disaring dari rekap evaluasi grading.
- Nama supervisor (*Satriyo Wibowo* dan *Muhammad Nashirudin*) tetap ditampilkan dengan badge khusus berwarna biru gelap **Supervisor**.

### 4. Pusat Kendali Dinamis: Tombol "Ketentuan & Peraturan"
- Tombol satu-klik pada top header untuk membuka form regulasi interaktif.
- Nilai target, batas minimal GP, tunjangan, gaji pokok, serta threshold evaluasi supervisor dapat **diedit langsung di browser**.
- Tombol **`Terapkan & Hitung Ulang Semua Grading`** langsung memperbarui komputasi seluruh data evaluasi di database seketika.
- Tombol pengaman **`Reset ke Nilai Standar Default`** untuk mengembalikan ke kebijakan baku perusahaan.

### 5. Dashboard Modern Berstandar SaaS (OWL Web Client)
- **Header Bersih & Bebas Duplikasi:** Dilengkapi jam sinkronisasi live dan action bar ringkas.
- **Compact Pill Filter Bar:** Container pill rounded putih dengan filter Tahun, Triwulan, Tim/Supervisor, dan Status.
- **4 Kartu KPI Eksekutif:** Total GP Seluruh Tim, Rata-rata Capaian (circular progress ring), Distribusi Grade, dan Status Evaluasi Grade.
- **Visualisasi Grafik 2 Kolom:** Grafik batang dengan *direct top value labels* (misal: `Rp327,6 Jt`) dan garis batas acuan evaluasi **70% (Batas Turun)** dan **100% (Target Promosi)**.
- **Slide-Over Detail Drawer:** Panel samping interaktif menampilkan profil supervisor, komposisi tim, target triwulan, grafik tren bulanan, dan kontribusi anggota tim sales.

### 6. Ekspor Multi-Format
- **Excel (.xlsx):** Format lengkap dengan header resmi perusahaan, rumus, dan styling warna.
- **PDF (.pdf):** Format A4 landscape siap cetak untuk rapat direksi.
- **Print Out (.html):** Lembar pratinjau instan dengan tombol cetak browser.

---

## 🛠️ Struktur Direktori Modul

```text
sales_grading_triwulan/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   └── export_controller.py          # Handler ekspor XLSX, PDF, dan HTML
├── data/
│   ├── demo_data.xml
│   ├── master_data.xml
│   └── sequence_data.xml
├── models/
│   ├── __init__.py
│   ├── dashboard_api.py              # API RPC backend untuk antarmuka OWL
│   ├── gp_sync.py                    # Engine sinkronisasi GP ORIMAX live
│   ├── gp_transaction.py             # Log transaksi riil per SO
│   ├── grading_history.py            # Audit trail perubahan grade
│   ├── grading_rules.py              # Konstanta & fungsi matematis acuan
│   ├── grading_rules_config.py       # Pusat kendali dinamis Ketentuan & Peraturan
│   ├── sales_grading.py              # Model evaluasi triwulan salesman
│   ├── sales_team_mapping.py         # Mapping salesman & tim (Aktif/Tidak Aktif)
│   ├── supervisor.py                 # Master data supervisor
│   └── supervisor_eval.py            # Model evaluasi kinerja supervisor
├── report/
│   ├── report_action.xml             # Action deklarasi laporan PDF
│   ├── report_grading_template.xml   # Lembar evaluasi individu resmi (Section G)
│   └── report_submenu_templates.xml  # Template cetak dashboard triwulan
├── security/
│   ├── ir.model.access.csv           # ACL permissions
│   └── sales_grading_security.xml    # Security groups & record rules
├── static/
│   ├── description/
│   │   └── icon.png
│   └── src/
│       ├── css/
│       │   └── grading_dashboard.css # Styling SaaS modern (Indigo & Royal Blue)
│       ├── js/
│       │   ├── dashboard_salesman.js
│       │   ├── dashboard_shared.js
│       │   ├── dashboard_supervisor.js
│       │   ├── grading_sales_main.js
│       │   ├── ranking_salesman.js
│       │   ├── rekap_salesman.js
│       │   └── salesman_detail_modal.js
│       └── xml/
│           ├── dashboard_salesman.xml
│           ├── dashboard_supervisor.xml
│           ├── grading_sales_main.xml
│           ├── ranking_salesman.xml
│           ├── rekap_salesman.xml
│           └── salesman_detail_modal.xml
├── views/
│   ├── dashboard_actions.xml
│   ├── menus.xml                     # Struktur 3 menu utama navigasi Odoo
│   ├── rules_config_views.xml        # Form kendali Ketentuan & Peraturan
│   ├── sales_grading_views.xml
│   └── supervisor_views.xml
└── wizard/
    ├── __init__.py
    ├── simulator_wizard.py
    └── simulator_wizard_view.xml
```

---

## 📦 Petunjuk Pemasangan di Server

```bash
# 1. Ekstrak zip modul ke direktori custom addons Odoo
unzip sales_grading_triwulan.zip -d /path/to/custom-addons/

# 2. Perbarui modul di database Odoo
odoo -c /etc/odoo/odoo.conf -d agi -u sales_grading_triwulan --stop-after-init

# 3. Restart container / service Odoo
docker restart odoo16-dev
```

---

## 📄 Lisensi & Hak Cipta
Hak Cipta © 2026 **PT. Aston Graphindo Indonesia**. Seluruh hak cipta dilindungi undang-undang.
