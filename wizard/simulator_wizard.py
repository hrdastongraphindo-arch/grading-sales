# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

TARGET_THRESHOLDS = {
    'star': 77_000_000 * 3,      # Rp231.000.000
    'executive': 55_000_000 * 3, # Rp165.000.000
    'senior': 30_000_000 * 3,    # Rp90.000.000
    'junior': 15_000_000 * 3,    # Rp45.000.000
}

TUNJANGAN_MAP = {
    'star': 2_250_000,
    'executive': 1_500_000,
    'senior': 750_000,
    'junior': 300_000,
    'new': 0,
}

class SalesGradingSimulatorWizard(models.TransientModel):
    _name = 'sales.grading.simulator.wizard'
    _description = 'What-If Simulator Target GP Bulan 3'

    currency_id = fields.Many2one(
        'res.currency',
        string='Mata Uang',
        default=lambda self: self.env.ref('base.IDR', raise_if_not_found=False) or self.env.company.currency_id
    )
    grade_saat_ini = fields.Selection([
        ('new', 'New Sales'),
        ('junior', 'Junior Sales'),
        ('senior', 'Senior Sales'),
        ('executive', 'Executive Sales'),
        ('star', 'Star Sales')
    ], string='Grade Saat Ini', required=True, default='junior')

    target_grade = fields.Selection([
        ('junior', 'Junior Sales'),
        ('senior', 'Senior Sales'),
        ('executive', 'Executive Sales'),
        ('star', 'Star Sales')
    ], string='Target Grade yang Dituju', required=True, default='star')

    gp_bulan_1 = fields.Monetary(string='Realisasi GP Bulan 1', currency_field='currency_id', default=0.0)
    gp_bulan_2 = fields.Monetary(string='Realisasi GP Bulan 2', currency_field='currency_id', default=0.0)

    # Computed simulation results
    total_dua_bulan = fields.Monetary(string='Total Penjualan 2 Bulan', currency_field='currency_id', compute='_compute_simulation')
    target_total_gp = fields.Monetary(string='Target Total GP 3 Bulan (Tabel B)', currency_field='currency_id', compute='_compute_simulation')
    required_gp_bulan_3 = fields.Monetary(string='Kebutuhan GP Minimal Bulan 3', currency_field='currency_id', compute='_compute_simulation')
    selisih_tunjangan = fields.Monetary(string='Kenaikan Tunjangan Fungsional', currency_field='currency_id', compute='_compute_simulation')
    status_kesimpulan = fields.Char(string='Status Proyeksi', compute='_compute_simulation')

    @api.depends('grade_saat_ini', 'target_grade', 'gp_bulan_1', 'gp_bulan_2')
    def _compute_simulation(self):
        for rec in self:
            current_total = (rec.gp_bulan_1 or 0.0) + (rec.gp_bulan_2 or 0.0)
            target_req = TARGET_THRESHOLDS.get(rec.target_grade, 0.0)
            rec.total_dua_bulan = current_total
            rec.target_total_gp = target_req

            tunjangan_now = TUNJANGAN_MAP.get(rec.grade_saat_ini, 0)
            tunjangan_target = TUNJANGAN_MAP.get(rec.target_grade, 0)
            rec.selisih_tunjangan = max(0, tunjangan_target - tunjangan_now)

            if current_total >= target_req:
                rec.required_gp_bulan_3 = 0.0
                rec.status_kesimpulan = _("Target sudah tercapai dalam 2 bulan! Tetap pertahankan ritme penjualan di Bulan 3.")
            else:
                shortfall = target_req - current_total
                rec.required_gp_bulan_3 = shortfall
                rec.status_kesimpulan = _("Diperlukan penjualan minimal Rp%s di Bulan 3 untuk meraih grade tersebut.") % (
                    "{:,.0f}".format(shortfall).replace(',', '.')
                )

    def action_apply_to_record(self):
        # Tutup wizard
        return {'type': 'ir.actions.act_window_close'}
