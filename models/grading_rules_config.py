# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

DEFAULT_WORKFLOW_GUIDE = """
<div style="font-family: inherit; color: #334155; line-height: 1.6;">
    <div style="background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%); color: white; padding: 20px 24px; border-radius: 12px; margin-bottom: 24px;">
        <h2 style="margin: 0 0 6px 0; font-size: 20px; font-weight: 800; color: #FFFFFF;">
            SOP &amp; Regulasi Resmi Grading Sales PT Aston Graphindo Indonesia
        </h2>
        <p style="margin: 0; font-size: 13px; opacity: 0.9;">
            Panduan lengkap alur kerja, integrasi live data GP ORIMAX, pemisahan mutlak dua tabel, dan evaluasi 3 triwulan supervisor.
        </p>
    </div>

    <!-- BAGIAN 1: PEMISAHAN DUA TABEL -->
    <div style="margin-bottom: 24px; border: 1px solid #E2E8F0; border-radius: 10px; padding: 18px 20px; background: #FFFFFF;">
        <h3 style="margin-top: 0; color: #1E293B; font-size: 16px; font-weight: 700; border-bottom: 2px solid #3B82F6; padding-bottom: 8px;">
            1. Prinsip Mutlak: Pemisahan Dua Tabel dengan Fungsi Berbeda
        </h3>
        <p style="font-size: 13.5px; margin-bottom: 12px;">
            Sistem Grading Salesman menganut pemisahan mutlak antara penetapan grade karir dengan pemenuhan target kinerja bulanan:
        </p>
        <ul style="font-size: 13px; padding-left: 20px; margin-bottom: 0;">
            <li style="margin-bottom: 8px;">
                <strong style="color: #1E3A8A;">TABEL B (Satu-satunya Penentu Grade):</strong> Grade salesman ditentukan <em>murni</em> oleh <strong>Rata-rata Gross Profit (GP) Bulanan</strong> yang dicapai dalam 1 triwulan (Total GP 3 Bulan / 3). Nilai ini diuji langsung terhadap batas minimal pada Tabel B:
                <div style="margin-top: 6px; padding: 8px 14px; background: #F8FAFC; border-left: 4px solid #3B82F6; border-radius: 4px;">
                    • <strong>Star Sales:</strong> Rata-rata GP &ge; Rp 77.000.000 / bulan<br/>
                    • <strong>Executive Sales:</strong> Rata-rata GP &ge; Rp 55.000.000 s/d &lt; Rp 77.000.000<br/>
                    • <strong>Senior Sales:</strong> Rata-rata GP &ge; Rp 30.000.000 s/d &lt; Rp 55.000.000<br/>
                    • <strong>Junior Sales:</strong> Rata-rata GP &ge; Rp 15.000.000 s/d &lt; Rp 30.000.000<br/>
                    • <strong>New Sales:</strong> Rata-rata GP &lt; Rp 15.000.000
                </div>
            </li>
            <li style="margin-top: 10px;">
                <strong style="color: #047857;">TABEL A (Acuan Target Kinerja &amp; Hak Tunjangan):</strong> Tabel A <em>tidak menentukan grade</em>, melainkan menjadi tolok ukur target penjualan triwulan berjalan dan menentukan besaran <strong>Tunjangan Fungsional</strong> yang diterima salesman sesuai grade yang disandangnya.
            </li>
        </ul>
    </div>

    <!-- BAGIAN 2: ALUR SINKRONISASI GP ORIMAX -->
    <div style="margin-bottom: 24px; border: 1px solid #E2E8F0; border-radius: 10px; padding: 18px 20px; background: #FFFFFF;">
        <h3 style="margin-top: 0; color: #1E293B; font-size: 16px; font-weight: 700; border-bottom: 2px solid #10B981; padding-bottom: 8px;">
            2. Alur Sinkronisasi Data Real-Time (GP ORIMAX &rarr; Odoo)
        </h3>
        <ol style="font-size: 13px; padding-left: 20px; margin-bottom: 0;">
            <li style="margin-bottom: 8px;">
                <strong>Sumber Data Live:</strong> Data omzet, HPP, dan Gross Profit ditarik langsung dari API GP SO ORIMAX (<code>https://gp.orimax.co.id/?v=48f078437ab9</code>).
            </li>
            <li style="margin-bottom: 8px;">
                <strong>Filter Status AKTIF / TIDAK AKTIF:</strong> Pada menu <em>Mapping Salesman (ORIMAX &harr; HR)</em>, admin dapat mengaktifkan / menonaktifkan salesman. Hanya salesman yang berstatus <strong>AKTIF</strong> yang akan dimunculkan pada antarmuka Grading Sales. Salesman non-aktif (seperti yang telah resign) disembunyikan secara otomatis.
            </li>
            <li style="margin-bottom: 8px;">
                <strong>Penanganan Khusus Supervisor:</strong> Nama Supervisor (<em>Satriyo Wibowo</em> dan <em>Muhammad Nashirudin</em>) tetap ditampilkan pada tabel Rekap Grading dengan badge khusus berwarna biru gelap <strong>Supervisor</strong>, dan evaluasi tim mereka dimonitor melalui Dashboard Supervisor.
            </li>
            <li>
                <strong>Pencatatan Riwayat (Audit Trail):</strong> Setiap kali sinkronisasi dijalankan, log transaksi disimpan di <code>sales.grading.sync.log</code> dan <code>sales.grading.gp.transaction</code> lengkap dengan status mapping dan rincian per SO.
            </li>
        </ol>
    </div>

    <!-- BAGIAN 3: ATURAN EVALUASI & PROMOSI/DEMOSI -->
    <div style="margin-bottom: 24px; border: 1px solid #E2E8F0; border-radius: 10px; padding: 18px 20px; background: #FFFFFF;">
        <h3 style="margin-top: 0; color: #1E293B; font-size: 16px; font-weight: 700; border-bottom: 2px solid #F59E0B; padding-bottom: 8px;">
            3. Aturan Evaluasi Karir Salesman &amp; Kode Warna Status
        </h3>
        <p style="font-size: 13px; margin-bottom: 10px;">
            Pada setiap penutupan triwulan, sistem membandingkan <strong>Grading Sekarang (Grading Awal)</strong> dengan <strong>Grading Hasil Triwulan (Tabel B)</strong>:
        </p>
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 12px;">
            <div style="padding: 12px; border-radius: 8px; background: #ECFDF5; border: 1px solid #A7F3D0; text-align: center;">
                <span style="display: inline-block; padding: 4px 10px; background: #059669; color: white; border-radius: 20px; font-weight: 700; font-size: 11px;">Naik (Grade)</span>
                <p style="font-size: 12px; margin: 6px 0 0; color: #065F46;">Rata-rata GP triwulan melampaui grade awal salesman.</p>
            </div>
            <div style="padding: 12px; border-radius: 8px; background: #EFF6FF; border: 1px solid #BFDBFE; text-align: center;">
                <span style="display: inline-block; padding: 4px 10px; background: #2563EB; color: white; border-radius: 20px; font-weight: 700; font-size: 11px;">Tetap (Grade)</span>
                <p style="font-size: 12px; margin: 6px 0 0; color: #1E40AF;">Rata-rata GP stabil di rentang grade awal salesman.</p>
            </div>
            <div style="padding: 12px; border-radius: 8px; background: #FEF2F2; border: 1px solid #FECACA; text-align: center;">
                <span style="display: inline-block; padding: 4px 10px; background: #DC2626; color: white; border-radius: 20px; font-weight: 700; font-size: 11px;">Turun (Grade)</span>
                <p style="font-size: 12px; margin: 6px 0 0; color: #991B1B;">Rata-rata GP triwulan jatuh ke rentang grade di bawahnya.</p>
            </div>
        </div>
        <p style="font-size: 12.5px; color: #64748B; margin: 0;">
            * <em>Insentif Surplus Kinerja:</em> Apabila salesman mencapai target &gt; 100% pada Tabel A, salesman berhak atas insentif akselerasi <strong>1% dari surplus GP</strong> di atas target.
        </p>
    </div>

    <!-- BAGIAN 4: ATURAN EVALUASI SUPERVISOR -->
    <div style="border: 1px solid #E2E8F0; border-radius: 10px; padding: 18px 20px; background: #FFFFFF;">
        <h3 style="margin-top: 0; color: #1E293B; font-size: 16px; font-weight: 700; border-bottom: 2px solid #8B5CF6; padding-bottom: 8px;">
            4. Ketentuan Resmi Grading Supervisor (2 Grade) &amp; Evaluasi 3 Triwulan
        </h3>
        <table style="width: 100%; border-collapse: collapse; font-size: 12.5px; margin-top: 10px;">
            <thead>
                <tr style="background: #F1F5F9; border-bottom: 2px solid #CBD5E1; text-align: left;">
                    <th style="padding: 8px 10px;">Jabatan</th>
                    <th style="padding: 8px 10px;">Target GP / Bulan</th>
                    <th style="padding: 8px 10px;">Target GP / Triwulan</th>
                    <th style="padding: 8px 10px;">Komposisi Tim</th>
                    <th style="padding: 8px 10px;">Regulasi Promosi / Demosi 3 Triwulan</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom: 1px solid #E2E8F0;">
                    <td style="padding: 10px; font-weight: 700; color: #1E3A8A;">Supervisor</td>
                    <td style="padding: 10px;">Rp 200.000.000</td>
                    <td style="padding: 10px;">Rp 600.000.000</td>
                    <td style="padding: 10px;">6 &ndash; 8 Sales + 1 Spv</td>
                    <td style="padding: 10px; color: #047857;">
                        <strong>Promosi ke Senior Supervisor</strong> apabila rata-rata pencapaian 3 triwulan berturut-turut <strong>&ge; 100%</strong>. Jika &lt; 100%, tetap Supervisor (grade dasar).
                    </td>
                </tr>
                <tr>
                    <td style="padding: 10px; font-weight: 700; color: #4F46E5;">Senior Supervisor</td>
                    <td style="padding: 10px;">Rp 300.000.000</td>
                    <td style="padding: 10px;">Rp 900.000.000</td>
                    <td style="padding: 10px;">9 &ndash; 11 Sales + 1 Spv</td>
                    <td style="padding: 10px; color: #B91C1C;">
                        <strong>Turun Grade ke Supervisor</strong> apabila pencapaian target <strong>&lt; 70% selama 3 triwulan</strong>. Jika &ge; 70%, tetap Senior Supervisor.
                    </td>
                </tr>
            </tbody>
        </table>
    </div>
</div>
"""


class SalesGradingRulesConfig(models.Model):
    _name = 'sales.grading.rules.config'
    _description = 'Konfigurasi Ketentuan & Peraturan Grading Sales'
    _rec_name = 'name'

    name = fields.Char(
        string='Nama Regulasi',
        default='Ketentuan & Peraturan Resmi Grading Sales PT Aston Graphindo Indonesia',
        required=True
    )
    is_active = fields.Boolean(string='Status Aktif', default=True)
    currency_id = fields.Many2one(
        'res.currency',
        string='Mata Uang',
        default=lambda self: self.env.ref('base.IDR', raise_if_not_found=False) or self.env.company.currency_id
    )

    salesman_rule_ids = fields.One2many(
        'sales.grading.salesman.rule',
        'config_id',
        string='Ketentuan Grade Salesman (Tabel B & Tabel A)'
    )
    supervisor_rule_ids = fields.One2many(
        'sales.grading.supervisor.rule',
        'config_id',
        string='Ketentuan Grade Supervisor'
    )
    workflow_guide_html = fields.Html(
        string='Panduan Alur Kerja & Regulasi',
        default=DEFAULT_WORKFLOW_GUIDE
    )

    last_updated = fields.Datetime(string='Terakhir Diperbarui', default=fields.Datetime.now)
    updated_by = fields.Many2one(
        'res.users',
        string='Diperbarui Oleh',
        default=lambda self: self.env.user
    )

    @api.model
    def get_active_config(self):
        """Singleton getter for active configuration."""
        cfg = self.search([('is_active', '=', True)], limit=1, order='id desc')
        if not cfg:
            cfg = self.create({
                'name': 'Ketentuan & Peraturan Resmi Grading Sales PT Aston Graphindo Indonesia',
                'is_active': True,
                'workflow_guide_html': DEFAULT_WORKFLOW_GUIDE,
            })
            cfg._seed_default_lines()
        elif not cfg.salesman_rule_ids or not cfg.supervisor_rule_ids:
            cfg._seed_default_lines()
        return cfg

    def _seed_default_lines(self):
        self.ensure_one()
        # Seed Salesman default lines
        if not self.salesman_rule_ids:
            salesman_defaults = [
                {
                    'sequence': 10,
                    'grade': 'star',
                    'name': 'Star Sales',
                    'min_avg_gp_monthly': 77_000_000.0,
                    'target_gp_monthly': 100_000_000.0,
                    'tunjangan_fungsional': 2_250_000.0,
                    'gaji_pokok': 2_592_154.0,
                    'keterangan': 'Grade Tertinggi Salesman (Tabel B >= Rp77 Jt, Target Tabel A Rp100 Jt)',
                },
                {
                    'sequence': 20,
                    'grade': 'executive',
                    'name': 'Executive Sales',
                    'min_avg_gp_monthly': 55_000_000.0,
                    'target_gp_monthly': 77_000_000.0,
                    'tunjangan_fungsional': 1_500_000.0,
                    'gaji_pokok': 2_592_154.0,
                    'keterangan': 'Executive Level (Tabel B >= Rp55 Jt, Target Tabel A Rp77 Jt)',
                },
                {
                    'sequence': 30,
                    'grade': 'senior',
                    'name': 'Senior Sales',
                    'min_avg_gp_monthly': 30_000_000.0,
                    'target_gp_monthly': 55_000_000.0,
                    'tunjangan_fungsional': 750_000.0,
                    'gaji_pokok': 2_592_154.0,
                    'keterangan': 'Senior Level (Tabel B >= Rp30 Jt, Target Tabel A Rp55 Jt)',
                },
                {
                    'sequence': 40,
                    'grade': 'junior',
                    'name': 'Junior Sales',
                    'min_avg_gp_monthly': 15_000_000.0,
                    'target_gp_monthly': 30_000_000.0,
                    'tunjangan_fungsional': 300_000.0,
                    'gaji_pokok': 2_592_154.0,
                    'keterangan': 'Junior Level (Tabel B >= Rp15 Jt, Target Tabel A Rp30 Jt)',
                },
                {
                    'sequence': 50,
                    'grade': 'new',
                    'name': 'New Sales',
                    'min_avg_gp_monthly': 0.0,
                    'target_gp_monthly': 15_000_000.0,
                    'tunjangan_fungsional': 0.0,
                    'gaji_pokok': 2_592_154.0,
                    'keterangan': 'Pemula / New Sales (Tabel B < Rp15 Jt, Target Tabel A Rp15 Jt)',
                },
            ]
            for s_def in salesman_defaults:
                self.env['sales.grading.salesman.rule'].create({
                    'config_id': self.id,
                    **s_def
                })

        # Seed Supervisor default lines
        if not self.supervisor_rule_ids:
            supervisor_defaults = [
                {
                    'sequence': 10,
                    'grade': 'supervisor',
                    'name': 'Supervisor',
                    'target_gp_monthly': 200_000_000.0,
                    'sales_min': 6,
                    'sales_max': 8,
                    'eval_threshold_pct': 100.0,
                    'eval_rule_description': 'Promosi ke Senior Supervisor jika rata-rata pencapaian target 3 triwulan >= 100%',
                },
                {
                    'sequence': 20,
                    'grade': 'senior_spv',
                    'name': 'Senior Supervisor',
                    'target_gp_monthly': 300_000_000.0,
                    'sales_min': 9,
                    'sales_max': 11,
                    'eval_threshold_pct': 70.0,
                    'eval_rule_description': 'Turun ke Supervisor jika pencapaian target di bawah 70% selama 3 triwulan',
                },
            ]
            for spv_def in supervisor_defaults:
                self.env['sales.grading.supervisor.rule'].create({
                    'config_id': self.id,
                    **spv_def
                })

    def action_apply_and_recalculate(self):
        """Simpan perubahan & trigger perhitungan ulang pada seluruh data evaluasi."""
        self.ensure_one()
        self.write({
            'last_updated': fields.Datetime.now(),
            'updated_by': self.env.user.id,
        })

        _logger.info("Applying updated rules config and recalculating all grading records...")
        GradingSalesman = self.env['sales.grading.triwulan'].sudo()
        Supervisor = self.env['sales.grading.supervisor'].sudo().with_context(active_test=False)
        SpvEval = self.env['sales.grading.supervisor.eval'].sudo()

        # 1. Recompute Salesman records
        all_salesmen = GradingSalesman.search([])
        if all_salesmen:
            all_salesmen._compute_grading_data()

        # 2. Recompute Supervisor master targets
        all_spvs = Supervisor.search([])
        if all_spvs:
            all_spvs._compute_targets()

        # 3. Recompute Supervisor evaluations
        all_evals = SpvEval.search([])
        if all_evals:
            all_evals._compute_metrics()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Perubahan Berhasil Diterapkan!'),
                'message': _('Ketentuan & Peraturan telah disimpan. Seluruh data Grading Salesman (%s) dan Evaluasi Supervisor (%s) berhasil dikalkulasi ulang sesuai aturan terbaru.') % (len(all_salesmen), len(all_evals)),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_reset_to_default(self):
        """Reset seluruh nilai ke standar default PT Aston Graphindo Indonesia."""
        self.ensure_one()
        self.salesman_rule_ids.unlink()
        self.supervisor_rule_ids.unlink()
        self.write({
            'name': 'Ketentuan & Peraturan Resmi Grading Sales PT Aston Graphindo Indonesia',
            'workflow_guide_html': DEFAULT_WORKFLOW_GUIDE,
            'last_updated': fields.Datetime.now(),
            'updated_by': self.env.user.id,
        })
        self._seed_default_lines()
        return self.action_apply_and_recalculate()

    @api.model
    def action_open_active_config(self):
        """Action handler for menu and button Ketentuan & Peraturan."""
        cfg = self.get_active_config()
        return {
            'name': _('Ketentuan & Peraturan Grading Sales'),
            'type': 'ir.actions.act_window',
            'res_model': 'sales.grading.rules.config',
            'res_id': cfg.id,
            'view_mode': 'form',
            'target': 'current',
        }


class SalesGradingSalesmanRule(models.Model):
    _name = 'sales.grading.salesman.rule'
    _description = 'Ketentuan Grade Salesman'
    _order = 'sequence asc, id asc'

    config_id = fields.Many2one('sales.grading.rules.config', string='Konfigurasi', ondelete='cascade', required=True)
    sequence = fields.Integer(string='Urutan', default=10)
    grade = fields.Selection([
        ('star', 'Star Sales'),
        ('executive', 'Executive Sales'),
        ('senior', 'Senior Sales'),
        ('junior', 'Junior Sales'),
        ('new', 'New Sales'),
    ], string='Grade', required=True)
    name = fields.Char(string='Nama Jabatan / Grade', required=True)
    currency_id = fields.Many2one('res.currency', related='config_id.currency_id')

    # Tabel B: Penentu Grade Resmi
    min_avg_gp_monthly = fields.Monetary(
        string='Min Rata-rata GP / Bulan (Tabel B)',
        currency_field='currency_id',
        required=True,
        help='Batas minimum pencapaian rata-rata GP bulanan dalam satu triwulan untuk menyandang grade ini.'
    )

    # Tabel A: Target & Tunjangan
    target_gp_monthly = fields.Monetary(
        string='Target GP / Bulan (Tabel A)',
        currency_field='currency_id',
        required=True,
        help='Target penjualan bulanan sesuai Tabel A.'
    )
    target_gp_quarterly = fields.Monetary(
        string='Target GP / Triwulan (Tabel A)',
        currency_field='currency_id',
        compute='_compute_quarterly_target',
        store=True,
        help='Target penjualan triwulan (Target Bulanan x 3).'
    )
    tunjangan_fungsional = fields.Monetary(
        string='Tunjangan Fungsional',
        currency_field='currency_id',
        default=0.0
    )
    gaji_pokok = fields.Monetary(
        string='Gaji Pokok',
        currency_field='currency_id',
        default=2592154.0
    )
    keterangan = fields.Char(string='Keterangan / Kualifikasi')

    @api.depends('target_gp_monthly')
    def _compute_quarterly_target(self):
        for rec in self:
            rec.target_gp_quarterly = (rec.target_gp_monthly or 0.0) * 3.0


class SalesGradingSupervisorRule(models.Model):
    _name = 'sales.grading.supervisor.rule'
    _description = 'Ketentuan Grade Supervisor'
    _order = 'sequence asc, id asc'

    config_id = fields.Many2one('sales.grading.rules.config', string='Konfigurasi', ondelete='cascade', required=True)
    sequence = fields.Integer(string='Urutan', default=10)
    grade = fields.Selection([
        ('supervisor', 'Supervisor'),
        ('senior_spv', 'Senior Supervisor'),
    ], string='Grade', required=True)
    name = fields.Char(string='Nama Jabatan', required=True)
    currency_id = fields.Many2one('res.currency', related='config_id.currency_id')

    target_gp_monthly = fields.Monetary(
        string='Target GP / Bulan',
        currency_field='currency_id',
        required=True
    )
    target_gp_triwulan = fields.Monetary(
        string='Target GP / Triwulan',
        currency_field='currency_id',
        compute='_compute_targets',
        store=True
    )
    target_gp_annual = fields.Monetary(
        string='Target GP / Tahun',
        currency_field='currency_id',
        compute='_compute_targets',
        store=True
    )

    sales_min = fields.Integer(string='Min Salesman', default=6)
    sales_max = fields.Integer(string='Max Salesman', default=8)
    team_composition = fields.Char(
        string='Komposisi Tim',
        compute='_compute_composition',
        store=True
    )

    eval_threshold_pct = fields.Float(
        string='Batas Evaluasi 3-Triwulan (%)',
        digits=(6, 2),
        required=True,
        help='Persentase threshold evaluasi. Supervisor: minimal 100% untuk promosi; Senior Supervisor: batas toleransi minimal 70% agar tidak turun grade.'
    )
    eval_rule_description = fields.Char(
        string='Aturan Evaluasi Promosi / Demosi',
        help='Deskripsi aturan evaluasi 3 triwulan.'
    )

    @api.depends('target_gp_monthly')
    def _compute_targets(self):
        for rec in self:
            m = rec.target_gp_monthly or 0.0
            rec.target_gp_triwulan = m * 3.0
            rec.target_gp_annual = m * 12.0

    @api.depends('sales_min', 'sales_max')
    def _compute_composition(self):
        for rec in self:
            rec.team_composition = f"{rec.sales_min} - {rec.sales_max} Sales + 1 Supervisor"
