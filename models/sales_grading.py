# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from .grading_rules import (
    GRADE_RANKS,
    TABEL_A_DATA,
    QUARTER_SELECTION,
    tentukan_grade_tabel_b,
    parse_periode_year_quarter,
)


class SalesGradingTriwulan(models.Model):
    _name = 'sales.grading.triwulan'
    _description = 'Evaluasi Grading Sales Triwulan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'year desc, quarter desc, rata_rata_gp desc, id desc'

    name = fields.Char(
        string='No. Dokumen SK',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Karyawan (Employees Odoo)',
        index=True,
        tracking=True
    )
    employee_name = fields.Char(
        string='Nama Karyawan Sales',
        required=True,
        tracking=True
    )
    user_id = fields.Many2one(
        'res.users',
        string='Salesperson / User',
        default=lambda self: self.env.user,
        tracking=True
    )
    team_id = fields.Many2one(
        'sales.grading.team',
        string='Tim Sales',
        index=True,
        tracking=True
    )
    team_name = fields.Char(
        string='Nama Tim',
        compute='_compute_team_name',
        store=True
    )
    supervisor_id = fields.Many2one(
        'sales.grading.supervisor',
        string='Supervisor Tim',
        index=True,
        tracking=True
    )
    year = fields.Char(
        string='Tahun',
        size=4,
        index=True,
        default='2026',
        tracking=True
    )
    quarter = fields.Selection(
        QUARTER_SELECTION,
        string='Triwulan',
        index=True,
        default='Q4',
        tracking=True
    )
    periode = fields.Char(
        string='Periode Triwulan',
        required=True,
        default='Triwulan IV (Okt - Des 2026)',
        tracking=True
    )
    evaluation_date = fields.Date(
        string='Tanggal Evaluasi',
        default=fields.Date.context_today,
        tracking=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Mata Uang',
        default=lambda self: self.env.ref('base.IDR', raise_if_not_found=False) or self.env.company.currency_id
    )

    grading_awal = fields.Selection([
        ('supervisor', 'Supervisor'),
        ('new', 'New Sales'),
        ('junior', 'Junior Sales'),
        ('senior', 'Senior Sales'),
        ('executive', 'Executive Sales'),
        ('star', 'Star Sales')
    ], string='Grading Sekarang', required=True, default='new', tracking=True)

    # Input GP Realisasi (3 Bulan)
    gp_bulan_1 = fields.Monetary(
        string='Gross Profit Bulan 1',
        currency_field='currency_id',
        default=0.0,
        tracking=True
    )
    gp_bulan_2 = fields.Monetary(
        string='Gross Profit Bulan 2',
        currency_field='currency_id',
        default=0.0,
        tracking=True
    )
    gp_bulan_3 = fields.Monetary(
        string='Gross Profit Bulan 3',
        currency_field='currency_id',
        default=0.0,
        tracking=True
    )

    # Status Sinkronisasi per Bulan
    bulan_1_synced = fields.Boolean(string='Bulan 1 Tersinkronisasi', default=True)
    bulan_2_synced = fields.Boolean(string='Bulan 2 Tersinkronisasi', default=True)
    bulan_3_synced = fields.Boolean(string='Bulan 3 Tersinkronisasi', default=True)
    tx_count = fields.Integer(string='Jumlah Transaksi SO', default=0)
    gp_source = fields.Selection([
        ('manual', 'Input Manual / Uji'),
        ('orimax', 'Sinkronisasi GP ORIMAX'),
    ], string='Sumber Data GP', default='manual', tracking=True)

    # Validitas Data
    data_validity = fields.Selection([
        ('valid', 'Valid'),
        ('incomplete', 'Triwulan Belum Lengkap'),
        ('sync_pending', 'Belum Tersinkronisasi'),
        ('unmapped', 'Mapping Belum Lengkap'),
        ('demo', 'Data Uji (Section E)'),
    ], string='Status Validitas', default='valid', index=True, tracking=True)
    validity_note = fields.Char(string='Catatan Validitas')
    is_valid_final = fields.Boolean(
        string='Data Final Valid',
        compute='_compute_validity_flags',
        store=True
    )

    # Hasil Perhitungan Matematis (Section C)
    total_gp = fields.Monetary(
        string='Total GP 3 Bulan',
        currency_field='currency_id',
        compute='_compute_grading_data',
        store=True,
        tracking=True
    )
    rata_rata_gp = fields.Monetary(
        string='Rata-rata GP / Bulan',
        currency_field='currency_id',
        compute='_compute_grading_data',
        store=True,
        tracking=True
    )

    # Penetapan Grade Resmi (TABEL B)
    grading_terbaru = fields.Selection([
        ('supervisor', 'Supervisor'),
        ('new', 'New Sales'),
        ('junior', 'Junior Sales'),
        ('senior', 'Senior Sales'),
        ('executive', 'Executive Sales'),
        ('star', 'Star Sales')
    ], string='Potensi Grading TW Berikutnya (Tabel B)', compute='_compute_grading_data', store=True, tracking=True)

    next_grade_potential = fields.Selection([
        ('supervisor', 'Supervisor'),
        ('new', 'New Sales'),
        ('junior', 'Junior Sales'),
        ('senior', 'Senior Sales'),
        ('executive', 'Executive Sales'),
        ('star', 'Star Sales')
    ], string='Potensi Grading Berikutnya (Indikator)', compute='_compute_grading_data', store=True)

    # Acuan Target & Kompensasi (TABEL A)
    target_gp_tabel_a = fields.Monetary(
        string='Target GP Bulanan (Tabel A)',
        currency_field='currency_id',
        compute='_compute_grading_data',
        store=True
    )
    persentase_pencapaian = fields.Float(
        string='% Pencapaian Target',
        compute='_compute_grading_data',
        store=True,
        digits=(6, 2),
        tracking=True
    )
    status_perubahan = fields.Selection([
        ('promosi', 'Promosi'),
        ('demosi', 'Demosi'),
        ('stabil', 'Stabil')
    ], string='Status Perubahan Karir', compute='_compute_grading_data', store=True, tracking=True)

    gaji_pokok = fields.Monetary(
        string='Gaji Pokok',
        currency_field='currency_id',
        compute='_compute_grading_data',
        store=True
    )
    tunjangan_fungsional = fields.Monetary(
        string='Tunjangan Fungsional (Tabel A)',
        currency_field='currency_id',
        compute='_compute_grading_data',
        store=True
    )
    tunjangan_lama = fields.Monetary(
        string='Tunjangan Sebelumnya',
        currency_field='currency_id',
        compute='_compute_grading_data',
        store=True
    )
    selisih_tunjangan = fields.Monetary(
        string='Penyesuaian / Selisih Tunjangan',
        currency_field='currency_id',
        compute='_compute_grading_data',
        store=True
    )
    total_kompensasi = fields.Monetary(
        string='Total Kompensasi Pokok',
        currency_field='currency_id',
        compute='_compute_grading_data',
        store=True
    )
    insentif_surplus = fields.Monetary(
        string='Insentif Kinerja (1% Surplus)',
        currency_field='currency_id',
        compute='_compute_grading_data',
        store=True
    )
    take_home_pay = fields.Monetary(
        string='Take Home Pay (THP)',
        currency_field='currency_id',
        compute='_compute_grading_data',
        store=True
    )

    state = fields.Selection([
        ('draft', 'Draft Evaluasi'),
        ('confirmed', 'Tervalidasi Supervisor'),
        ('done', 'Disahkan Direktur'),
        ('cancel', 'Dibatalkan')
    ], string='Status Dokumen', default='draft', tracking=True)

    # Pengesahan Resmi Sesuai Section G
    supervisor_1 = fields.Char(string='Diketahui Supervisor 1', default='Supervisor 1', tracking=True)
    supervisor_2 = fields.Char(string='Diketahui Supervisor 2', default='Supervisor 2', tracking=True)
    director_name = fields.Char(string='Disetujui Direktur Utama', default='Anton Wijaya', readonly=True)
    notes = fields.Text(string='Catatan Tambahan')

    history_ids = fields.One2many(
        'sales.grading.history', 'grading_id',
        string='Riwayat Perubahan Grade & Audit'
    )

    @api.depends('team_id', 'team_id.name')
    def _compute_team_name(self):
        for rec in self:
            rec.team_name = rec.team_id.name if rec.team_id else (rec.team_name or 'Belum Ditentukan')

    @api.depends('data_validity', 'state', 'bulan_1_synced', 'bulan_2_synced', 'bulan_3_synced')
    def _compute_validity_flags(self):
        for rec in self:
            all_synced = bool(rec.bulan_1_synced and rec.bulan_2_synced and rec.bulan_3_synced)
            rec.is_valid_final = (rec.data_validity == 'valid' and all_synced and rec.state != 'cancel')

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        for rec in self:
            if rec.employee_id:
                rec.employee_name = rec.employee_id.name
                if rec.employee_id.user_id:
                    rec.user_id = rec.employee_id.user_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sales.grading.triwulan') or _('New')
            if vals.get('employee_id') and not vals.get('employee_name'):
                emp = self.env['hr.employee'].browse(vals['employee_id'])
                vals['employee_name'] = emp.name
            if not vals.get('year') or not vals.get('quarter'):
                yr, qtr = parse_periode_year_quarter(vals.get('periode'))
                if yr and not vals.get('year'):
                    vals['year'] = yr
                if qtr and not vals.get('quarter'):
                    vals['quarter'] = qtr
        records = super().create(vals_list)
        for rec in records:
            self._record_history_entry(rec, 'auto_eval', _('Pembentukan evaluasi grading awal'))
        return records

    @api.depends('gp_bulan_1', 'gp_bulan_2', 'gp_bulan_3', 'grading_awal',
                 'bulan_1_synced', 'bulan_2_synced', 'bulan_3_synced')
    def _compute_grading_data(self):
        Supervisor = self.env['sales.grading.supervisor'].sudo().with_context(active_test=False)
        spv_emp_ids = set(Supervisor.search([('active', '=', True)]).mapped('employee_id').ids)
        for rec in self:
            g1 = rec.gp_bulan_1 or 0.0
            g2 = rec.gp_bulan_2 or 0.0
            g3 = rec.gp_bulan_3 or 0.0
            total = g1 + g2 + g3
            avg = round(total / 3.0)

            rec.total_gp = total
            rec.rata_rata_gp = avg

            is_spv = (
                rec.grading_awal == 'supervisor' or
                (rec.employee_id and rec.employee_id.id in spv_emp_ids) or
                ((rec.employee_name or '').strip().upper() in ('SATRIYO WIBOWO', 'MUHAMMAD NASHIRUDIN'))
            )
            if is_spv:
                rec.grading_awal = 'supervisor'
                rec.grading_terbaru = 'supervisor'
                rec.next_grade_potential = 'supervisor'
                rec.status_perubahan = 'stabil'
                rec.target_gp_tabel_a = 200_000_000.0
                rec.gaji_pokok = 2_592_154.0
                rec.tunjangan_fungsional = 0.0
                rec.tunjangan_lama = 0.0
                rec.selisih_tunjangan = 0.0
                rec.total_kompensasi = 2_592_154.0
                rec.insentif_surplus = 0.0
                rec.take_home_pay = 2_592_154.0
                target_3bln = 600_000_000.0
                rec.persentase_pencapaian = round((total / target_3bln) * 100.0, 2)
                continue

            # 1. Penentuan Grade Otomatis: HANYA DARI TABEL B
            grade_baru = tentukan_grade_tabel_b(avg, env=self.env)
            rec.grading_terbaru = grade_baru

            # Indikator Potensi Grading Berikutnya (berdasarkan run-rate bulan yang sudah tersinkronisasi)
            synced_months = sum([
                1 if rec.bulan_1_synced else 0,
                1 if rec.bulan_2_synced else 0,
                1 if rec.bulan_3_synced else 0,
            ])
            projected_avg = round(total / synced_months) if synced_months > 0 else avg
            rec.next_grade_potential = tentukan_grade_tabel_b(projected_avg, env=self.env)

            # 2. Acuan Target & Hak Kompensasi: HANYA DARI TABEL A
            komp = TABEL_A_DATA.get(grade_baru, TABEL_A_DATA['new'])
            komp_lama = TABEL_A_DATA.get(rec.grading_awal, TABEL_A_DATA['new'])

            # Lookup dinamis dari sales.grading.rules.config jika ada
            try:
                cfg = self.env['sales.grading.rules.config'].sudo().get_active_config()
                cfg_rules = {r.grade: r for r in cfg.salesman_rule_ids}
                if grade_baru in cfg_rules:
                    r_baru = cfg_rules[grade_baru]
                    komp = {
                        'target_gp': r_baru.target_gp_monthly,
                        'gaji_pokok': r_baru.gaji_pokok,
                        'tunjangan': r_baru.tunjangan_fungsional,
                    }
                if rec.grading_awal in cfg_rules:
                    r_lama = cfg_rules[rec.grading_awal]
                    komp_lama = {
                        'target_gp': r_lama.target_gp_monthly,
                        'gaji_pokok': r_lama.gaji_pokok,
                        'tunjangan': r_lama.tunjangan_fungsional,
                    }
            except Exception:
                pass

            rec.target_gp_tabel_a = komp['target_gp']
            rec.gaji_pokok = komp['gaji_pokok']
            rec.tunjangan_fungsional = komp['tunjangan']
            rec.tunjangan_lama = komp_lama['tunjangan']
            rec.selisih_tunjangan = komp['tunjangan'] - komp_lama['tunjangan']
            rec.total_kompensasi = komp['gaji_pokok'] + komp['tunjangan']

            # 3. Formula Persentase Pencapaian Target (Section D):
            # (Rata-rata GP / Target GP Tabel A) * 100%
            if komp['target_gp'] > 0:
                rec.persentase_pencapaian = round((avg / komp['target_gp']) * 100.0, 2)
            else:
                rec.persentase_pencapaian = 0.0

            # 4. Status Perubahan Grade (Section F) - tanpa batas demosi maksimal
            rank_awal = GRADE_RANKS.get(rec.grading_awal, 1)
            rank_baru = GRADE_RANKS.get(grade_baru, 1)
            if rank_baru > rank_awal:
                rec.status_perubahan = 'promosi'
            elif rank_baru < rank_awal:
                rec.status_perubahan = 'demosi'
            else:
                rec.status_perubahan = 'stabil'

            # 5. Insentif Akselerasi Kinerja (1% surplus atas target) & THP
            if avg > komp['target_gp']:
                surplus = avg - komp['target_gp']
                insentif = round(surplus * 0.01)
            else:
                insentif = 0.0
            rec.insentif_surplus = insentif
            rec.take_home_pay = rec.total_kompensasi + insentif

    def _record_history_entry(self, rec, reason='auto_eval', notes=''):
        self.env['sales.grading.history'].create({
            'record_type': 'salesman',
            'grading_id': rec.id,
            'employee_id': rec.employee_id.id if rec.employee_id else False,
            'employee_name': rec.employee_name,
            'year': rec.year,
            'quarter': rec.quarter,
            'periode': rec.periode,
            'grade_before': rec.grading_awal,
            'grade_after': rec.grading_terbaru,
            'change_status': rec.status_perubahan or 'stabil',
            'change_reason': reason,
            'total_gp': rec.total_gp,
            'avg_gp': rec.rata_rata_gp,
            'pct_achievement': rec.persentase_pencapaian,
            'notes': notes,
        })

    def action_recalculate_with_audit(self):
        """Kalkulasi ulang eksplisit yang dicatat pada audit trail."""
        for rec in self:
            rec._compute_grading_data()
            self._record_history_entry(rec, 'recalculation', _('Kalkulasi ulang manual oleh %s') % self.env.user.name)
        return True

    def action_confirm(self):
        for rec in self:
            rec.state = 'confirmed'

    def action_done(self):
        for rec in self:
            rec.state = 'done'

    def action_draft(self):
        for rec in self:
            rec.state = 'draft'

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancel'

    def action_verify_integrity(self):
        """
        Verifikasi Kepatuhan Matematika & Aturan Bisnis (Tabel A & B Terpisah)
        """
        self.ensure_one()
        expected_total = (self.gp_bulan_1 or 0.0) + (self.gp_bulan_2 or 0.0) + (self.gp_bulan_3 or 0.0)
        expected_avg = round(expected_total / 3.0)
        expected_grade = tentukan_grade_tabel_b(expected_avg)
        expected_target = TABEL_A_DATA[expected_grade]['target_gp']
        expected_tunjangan = TABEL_A_DATA[expected_grade]['tunjangan']

        errors = []
        if self.total_gp != expected_total:
            errors.append(f"Total GP tidak sinkron: tercatat {self.total_gp}, seharusnya {expected_total}")
        if abs(self.rata_rata_gp - expected_avg) > 1:
            errors.append(f"Rata-rata GP tidak sinkron: tercatat {self.rata_rata_gp}, seharusnya {expected_avg}")
        if self.grading_terbaru != expected_grade:
            errors.append(f"Pelanggaran Tabel B: grade {self.grading_terbaru}, seharusnya {expected_grade}")
        if self.target_gp_tabel_a != expected_target:
            errors.append(f"Pelanggaran Tabel A: target {self.target_gp_tabel_a}, seharusnya {expected_target}")
        if self.tunjangan_fungsional != expected_tunjangan:
            errors.append(f"Pelanggaran Tabel A: tunjangan {self.tunjangan_fungsional}, seharusnya {expected_tunjangan}")

        if errors:
            raise UserError(_("TERDETEKSI ANOMALI INTEGRITAS:\n") + "\n".join(errors))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Integritas Sempurna (100% Patuh)'),
                'message': _('Evaluasi ini mematuhi 100% Ketentuan Final Pemisahan Tabel A & B!'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_create_rollover(self):
        """
        Ketentuan F: Grading awal diambil dari hasil periode sebelumnya.
        """
        self.ensure_one()
        return {
            'name': _('Rollover Periode Baru'),
            'type': 'ir.actions.act_window',
            'res_model': 'sales.grading.triwulan',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_employee_id': self.employee_id.id if self.employee_id else False,
                'default_employee_name': self.employee_name,
                'default_user_id': self.user_id.id if self.user_id else False,
                'default_team_id': self.team_id.id if self.team_id else False,
                'default_grading_awal': self.grading_terbaru,
                'default_periode': 'Triwulan Berikutnya',
                'default_gp_bulan_1': 0.0,
                'default_gp_bulan_2': 0.0,
                'default_gp_bulan_3': 0.0,
            }
        }

    @api.model
    def _migrate_legacy_grading_records(self):
        """
        Migrasi aman backward-compatible untuk data historis yang sudah ada.
        Tidak mengubah GP, grade, atau menghapus record lama.
        """
        Employee = self.env['hr.employee'].with_context(active_test=False)
        for rec in self.search([]):
            vals = {}
            yr, qtr = parse_periode_year_quarter(rec.periode)
            if yr and not rec.year:
                vals['year'] = yr
            if qtr and not rec.quarter:
                vals['quarter'] = qtr
            if not rec.employee_id and rec.employee_name:
                emp = Employee.search([('name', '=ilike', rec.employee_name.strip())], limit=1)
                if emp:
                    vals['employee_id'] = emp.id
            if (rec.employee_name or '').startswith('Kasus Uji'):
                vals['data_validity'] = 'demo'
                vals['validity_note'] = 'Data uji validasi Section E'
            elif rec.state == 'cancel':
                vals['data_validity'] = 'incomplete'
                vals['validity_note'] = 'Dokumen dibatalkan'
            if vals:
                rec.write(vals)
        return True
