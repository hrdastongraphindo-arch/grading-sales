# -*- coding: utf-8 -*-
{
    'name': 'Sistem Grading Sales Triwulan',
    'version': '16.0.2.0.0',
    'category': 'Sales/Sales',
    'summary': 'Sistem Dashboard & Evaluasi Grading Salesman dan Supervisor (4 Submenu, Integrasi GP ORIMAX)',
    'description': """
Sistem Grading Sales Triwulan - PT Aston Graphindo Indonesia
============================================================

Modul resmi evaluasi kinerja triwulanan sales berbasis Gross Profit (GP) mengacu dokumen direksi:
"KETENTUAN FINAL GRADING SALES: DUA TABEL DENGAN FUNGSI BERBEDA"

Fitur Utama:
------------
1. Pemisahan Mutlak Dua Tabel:
   - TABEL B (Satu-satunya Penentu Grade): New, Junior, Senior, Executive, Star Sales.
   - TABEL A (Target Kinerja & Kompensasi): Acuan target penjualan & tunjangan fungsional (bukan penentu grade).
2. Perhitungan Otomatis: Total GP 3 Bulan, Rata-rata/Bulan, Persentase Pencapaian, dan Status (Promosi, Demosi, Stabil).
3. Insentif Akselerasi Kinerja (1% surplus penjualan di atas target 100%) dan Take Home Pay (THP).
4. Cetak Dokumen Resmi PDF (Section G): Lengkap dengan 3 kolom tanda tangan (Supervisor 1, Supervisor 2, Disetujui Anton Wijaya) dan catatan disclaimer wajib.
5. What-If Simulator Wizard: Simulasi kekurangan GP Bulan 3 untuk merebut target grade tertentu.
6. Rollover Kuartal Otomatis (Section F): Grade awal periode baru otomatis diturunkan dari grade periode lalu.
7. Audit Integritas Data Matematis otomatis.
    """,
    'author': 'PT Aston Graphindo Indonesia',
    'website': 'https://astongraphindo.com',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'hr', 'sales_team', 'web'],
    'data': [
        'security/sales_grading_security.xml',
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'data/master_data.xml',
        'wizard/simulator_wizard_view.xml',
        'views/supervisor_views.xml',
        'views/sales_grading_views.xml',
        'views/rules_config_views.xml',
        'views/dashboard_actions.xml',
        'views/menus.xml',
        'report/report_action.xml',
        'report/report_grading_template.xml',
        'report/report_submenu_templates.xml',
        'data/demo_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sales_grading_triwulan/static/src/css/grading_dashboard.css',
            'sales_grading_triwulan/static/src/js/dashboard_shared.js',
            'sales_grading_triwulan/static/src/js/salesman_detail_modal.js',
            'sales_grading_triwulan/static/src/xml/salesman_detail_modal.xml',
            'sales_grading_triwulan/static/src/js/grading_sales_main.js',
            'sales_grading_triwulan/static/src/xml/grading_sales_main.xml',
            'sales_grading_triwulan/static/src/js/dashboard_salesman.js',
            'sales_grading_triwulan/static/src/xml/dashboard_salesman.xml',
            'sales_grading_triwulan/static/src/js/rekap_salesman.js',
            'sales_grading_triwulan/static/src/xml/rekap_salesman.xml',
            'sales_grading_triwulan/static/src/js/ranking_salesman.js',
            'sales_grading_triwulan/static/src/xml/ranking_salesman.xml',
            'sales_grading_triwulan/static/src/js/dashboard_supervisor.js',
            'sales_grading_triwulan/static/src/xml/dashboard_supervisor.xml',
        ],
    },
    'application': True,
    'installable': True,
    'auto_install': False,
}
