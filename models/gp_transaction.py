# -*- coding: utf-8 -*-
from odoo import models, fields, api
from .grading_rules import QUARTER_SELECTION


class SalesGradingGpTransaction(models.Model):
    _name = 'sales.grading.gp.transaction'
    _description = 'Transaksi GP SO dari GP ORIMAX'
    _order = 'tx_date desc, id desc'

    tx_uid = fields.Char(string='ID Transaksi Unik', required=True, index=True, copy=False)
    source_id = fields.Char(string='ID Sumber ORIMAX', index=True)

    year = fields.Char(string='Tahun', size=4, required=True, index=True)
    quarter = fields.Selection(QUARTER_SELECTION, string='Triwulan', required=True, index=True)
    month = fields.Char(string='Bulan', size=2, required=True, index=True)

    salesman_raw = fields.Char(string='Nama Salesman (ORIMAX)', index=True)
    employee_id = fields.Many2one('hr.employee', string='Karyawan (Odoo)', index=True)

    so_number = fields.Char(string='Nomor SO', index=True)
    tx_date = fields.Datetime(string='Tanggal SO', index=True)
    tx_date_only = fields.Date(string='Tanggal SO (Date)', index=True)
    tx_date_str = fields.Char(string='Tanggal Teks')

    customer = fields.Char(string='Customer')
    product = fields.Char(string='Produk')
    qty = fields.Float(string='Qty', default=1.0)

    currency_id = fields.Many2one(
        'res.currency',
        string='Mata Uang',
        default=lambda self: self.env.ref('base.IDR', raise_if_not_found=False) or self.env.company.currency_id
    )
    total_net_omzet = fields.Monetary(string='Total Net Omzet', currency_field='currency_id', default=0.0)
    hpp_total = fields.Monetary(string='Total HPP', currency_field='currency_id', default=0.0)
    gross_profit = fields.Monetary(string='Gross Profit (GP)', currency_field='currency_id', default=0.0)
    is_negative_gp = fields.Boolean(string='GP Negatif', compute='_compute_flags', store=True)

    team_raw = fields.Char(string='Tim Sales (ORIMAX)')
    team_id = fields.Many2one('sales.grading.team', string='Tim Sales', index=True)
    supervisor_id = fields.Many2one(
        'sales.grading.supervisor',
        string='Supervisor Periode Transaksi',
        index=True,
        help='Ditentukan berdasarkan riwayat penugasan Supervisor pada tim terkait saat tanggal SO.'
    )

    vendor = fields.Char(string='Vendor/Entitas')
    status_do = fields.Char(string='Status DO')
    sync_log_id = fields.Many2one('sales.grading.sync.log', string='Log Sinkronisasi', ondelete='set null')

    is_valid = fields.Boolean(string='Mapping Valid', default=True, index=True)
    mapping_issue = fields.Char(string='Catatan Validitas / Mapping')

    _sql_constraints = [
        ('unique_tx_uid', 'unique(tx_uid)', 'Transaksi GP dengan ID unik ini sudah tercatat (anti-duplikasi)!'),
    ]

    @api.depends('gross_profit')
    def _compute_flags(self):
        for rec in self:
            rec.is_negative_gp = (rec.gross_profit or 0.0) < 0.0
