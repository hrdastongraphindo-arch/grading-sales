# -*- coding: utf-8 -*-
from odoo import models, fields


class SalesGradingHistory(models.Model):
    _name = 'sales.grading.history'
    _description = 'Riwayat Perubahan Grade & Audit Kalkulasi'
    _order = 'changed_at desc, id desc'

    record_type = fields.Selection([
        ('salesman', 'Salesman'),
        ('supervisor', 'Supervisor'),
    ], string='Tipe', required=True, default='salesman', index=True)

    grading_id = fields.Many2one('sales.grading.triwulan', string='Dokumen Grading Salesman', ondelete='cascade', index=True)
    supervisor_id = fields.Many2one('sales.grading.supervisor', string='Supervisor', ondelete='cascade', index=True)
    employee_id = fields.Many2one('hr.employee', string='Karyawan', index=True)
    employee_name = fields.Char(string='Nama Karyawan')

    year = fields.Char(string='Tahun', size=4, index=True)
    quarter = fields.Selection([
        ('Q1', 'Triwulan I'),
        ('Q2', 'Triwulan II'),
        ('Q3', 'Triwulan III'),
        ('Q4', 'Triwulan IV'),
        ('ANNUAL', 'Tahunan'),
    ], string='Triwulan')
    periode = fields.Char(string='Periode')

    grade_before = fields.Char(string='Grade Sebelumnya')
    grade_after = fields.Char(string='Grade Terbaru')
    change_status = fields.Selection([
        ('promosi', 'Promosi / Naik'),
        ('demosi', 'Demosi / Turun'),
        ('stabil', 'Stabil / Tetap'),
        ('recalc', 'Kalkulasi Ulang'),
        ('manual', 'Perubahan Manual'),
    ], string='Status Perubahan', default='stabil')
    change_reason = fields.Selection([
        ('auto_eval', 'Evaluasi Otomatis'),
        ('recalculation', 'Kalkulasi Ulang'),
        ('manual_correction', 'Koreksi / Edit Master'),
    ], string='Alasan Perubahan', default='auto_eval')

    total_gp = fields.Float(string='Total GP')
    avg_gp = fields.Float(string='Rata-rata GP / Bulan')
    pct_achievement = fields.Float(string='% Pencapaian')

    changed_by = fields.Many2one('res.users', string='Diubah Oleh', default=lambda self: self.env.user)
    changed_at = fields.Datetime(string='Waktu Perubahan', default=fields.Datetime.now)
    notes = fields.Text(string='Catatan Audit')
