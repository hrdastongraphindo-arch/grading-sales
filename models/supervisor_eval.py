# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from .grading_rules import (
    SUPERVISOR_GRADES,
    SUPERVISOR_TARGETS,
    SUPERVISOR_GRADE_LABELS,
    QUARTER_SELECTION,
    QUARTER_MONTHS,
    evaluate_supervisor_annual,
)


class SalesGradingSupervisorEval(models.Model):
    _name = 'sales.grading.supervisor.eval'
    _description = 'Evaluasi Kinerja Triwulan & Tahunan Supervisor'
    _order = 'year desc, quarter desc, persentase_triwulan desc, id desc'

    supervisor_id = fields.Many2one(
        'sales.grading.supervisor',
        string='Supervisor',
        required=True,
        ondelete='cascade',
        index=True
    )
    supervisor_name = fields.Char(related='supervisor_id.name', store=True, string='Nama Supervisor')
    year = fields.Char(string='Tahun', size=4, required=True, index=True)
    quarter = fields.Selection(QUARTER_SELECTION, string='Triwulan', required=True, index=True)

    grade_supervisor = fields.Selection(
        SUPERVISOR_GRADES,
        string='Grade Supervisor',
        required=True,
        default='supervisor'
    )
    team_names = fields.Char(string='Tim Sales', default='Belum Ditugaskan')

    currency_id = fields.Many2one(
        'res.currency',
        string='Mata Uang',
        default=lambda self: self.env.ref('base.IDR', raise_if_not_found=False) or self.env.company.currency_id
    )

    gp_bulan_1 = fields.Monetary(string='GP Tim Bulan 1', currency_field='currency_id', default=0.0)
    gp_bulan_2 = fields.Monetary(string='GP Tim Bulan 2', currency_field='currency_id', default=0.0)
    gp_bulan_3 = fields.Monetary(string='GP Tim Bulan 3', currency_field='currency_id', default=0.0)
    realisasi_gp_triwulan = fields.Monetary(
        string='Realisasi GP Triwulan',
        currency_field='currency_id',
        compute='_compute_metrics',
        store=True
    )
    target_gp_bulanan = fields.Monetary(
        string='Target GP / Bulan',
        currency_field='currency_id',
        compute='_compute_metrics',
        store=True
    )
    target_gp_triwulan = fields.Monetary(
        string='Target GP / Triwulan',
        currency_field='currency_id',
        compute='_compute_metrics',
        store=True
    )
    persentase_triwulan = fields.Float(
        string='% Pencapaian Triwulan',
        compute='_compute_metrics',
        store=True,
        digits=(6, 2)
    )

    # Akumulasi Tahunan (4 Triwulan Kalender)
    akumulasi_gp_tahunan = fields.Monetary(
        string='Akumulasi GP 4 Triwulan',
        currency_field='currency_id',
        default=0.0
    )
    target_gp_tahunan = fields.Monetary(
        string='Target GP Tahunan',
        currency_field='currency_id',
        compute='_compute_metrics',
        store=True
    )
    persentase_tahunan = fields.Float(
        string='% Pencapaian Tahunan',
        compute='_compute_metrics',
        store=True,
        digits=(6, 2)
    )

    # Status Validitas & Evaluasi Tahunan
    quarter_complete = fields.Boolean(string='Triwulan Lengkap (3 Bulan)', default=False)
    annual_complete = fields.Boolean(string='4 Triwulan Lengkap & Valid', default=False)
    data_validity = fields.Selection([
        ('valid', 'Valid'),
        ('incomplete', 'Triwulan / Tahun Belum Lengkap'),
        ('unmapped', 'Data Belum Valid (Mapping/Konflik)'),
    ], string='Status Validitas', default='incomplete')
    validity_note = fields.Char(string='Catatan Validitas')

    potensi_grade_berikutnya = fields.Selection(
        SUPERVISOR_GRADES,
        string='Potensi Grade Berikutnya',
        compute='_compute_metrics',
        store=True
    )
    potensi_keputusan = fields.Selection([
        ('naik', 'Berpotensi Naik Grade'),
        ('tetap', 'Tetap'),
        ('turun', 'Berpotensi Turun Grade'),
    ], string='Potensi Keputusan', compute='_compute_metrics', store=True)

    status_evaluasi = fields.Selection([
        ('berjalan', 'Berjalan (Sementara)'),
        ('final', 'Final (4 Triwulan Lengkap)'),
        ('invalid', 'Data Belum Valid'),
    ], string='Status Evaluasi', compute='_compute_metrics', store=True)

    rata_rata_pencapaian_3tw = fields.Float(
        string='Rata-rata 3 Triwulan (%)',
        compute='_compute_metrics',
        store=True,
        digits=(6, 2),
        help='Rata-rata persentase pencapaian target selama 3 triwulan terakhir.'
    )
    triwulan_dibawah_70_count = fields.Integer(
        string='Jumlah TW < 70%',
        compute='_compute_metrics',
        store=True,
        help='Jumlah triwulan dengan pencapaian di bawah 70% dalam 3 triwulan terakhir.'
    )
    team_composition_desc = fields.Char(
        string='Komposisi Tim Ideal',
        compute='_compute_metrics',
        store=True
    )

    tx_count = fields.Integer(string='Jumlah Transaksi SO', default=0)
    member_count = fields.Integer(string='Jumlah Anggota Salesman', default=0)

    _sql_constraints = [
        ('unique_spv_year_quarter', 'unique(supervisor_id, year, quarter)',
         'Evaluasi Supervisor per tahun & triwulan sudah ada!'),
    ]

    @api.depends(
        'supervisor_id', 'year', 'quarter', 'grade_supervisor',
        'gp_bulan_1', 'gp_bulan_2', 'gp_bulan_3',
        'akumulasi_gp_tahunan', 'quarter_complete', 'annual_complete', 'data_validity'
    )
    def _compute_metrics(self):
        QuarterOrder = {'Q1': 1, 'Q2': 2, 'Q3': 3, 'Q4': 4}
        for rec in self:
            t = None
            if rec.env:
                try:
                    cfg = rec.env['sales.grading.rules.config'].sudo().get_active_config()
                    r = cfg.supervisor_rule_ids.filtered(lambda x: x.grade == rec.grade_supervisor)
                    if r:
                        r0 = r[0]
                        t = {
                            'monthly': r0.target_gp_monthly,
                            'quarterly': r0.target_gp_triwulan,
                            'annual': r0.target_gp_annual,
                            'sales_min': r0.sales_min,
                            'sales_max': r0.sales_max,
                            'team_composition': r0.team_composition,
                        }
                except Exception:
                    pass
            if not t:
                t = SUPERVISOR_TARGETS.get(rec.grade_supervisor, SUPERVISOR_TARGETS['supervisor'])
            rec.target_gp_bulanan = t['monthly']
            rec.target_gp_triwulan = t['quarterly']
            rec.target_gp_tahunan = t['annual']
            rec.team_composition_desc = t.get('team_composition', '6 - 8 Sales + 1 Supervisor')

            real_q = (rec.gp_bulan_1 or 0.0) + (rec.gp_bulan_2 or 0.0) + (rec.gp_bulan_3 or 0.0)
            rec.realisasi_gp_triwulan = real_q
            rec.persentase_triwulan = round((real_q / t['quarterly']) * 100.0, 2) if t['quarterly'] > 0 else 0.0

            pct_yr = round(((rec.akumulasi_gp_tahunan or 0.0) / t['annual']) * 100.0, 2) if t['annual'] > 0 else 0.0
            rec.persentase_tahunan = pct_yr

            # Evaluasi 3 Triwulan (promosi jika rata-rata 3 TW >= 100%, demosi jika < 70% selama 3 TW)
            cur_yr = int(rec.year) if rec.year and str(rec.year).isdigit() else 2026
            cur_q_idx = QuarterOrder.get(rec.quarter, 1)

            sibling_evals = self.search([
                ('supervisor_id', '=', rec.supervisor_id.id),
                ('id', '!=', rec.id or 0),
            ])
            all_evals_list = []
            for s in sibling_evals:
                s_yr = int(s.year) if s.year and str(s.year).isdigit() else 0
                s_q_idx = QuarterOrder.get(s.quarter, 1)
                if s_yr < cur_yr or (s_yr == cur_yr and s_q_idx <= cur_q_idx):
                    all_evals_list.append((s_yr, s_q_idx, s.persentase_triwulan))
            all_evals_list.append((cur_yr, cur_q_idx, rec.persentase_triwulan))
            all_evals_list.sort(key=lambda x: (x[0], x[1]))

            recent_3 = all_evals_list[-3:]
            pcts_3 = [x[2] for x in recent_3]
            avg_3tw = round(sum(pcts_3) / len(pcts_3), 2) if pcts_3 else rec.persentase_triwulan
            count_below_70 = sum(1 for p in pcts_3 if p < 70.0)

            rec.rata_rata_pencapaian_3tw = avg_3tw
            rec.triwulan_dibawah_70_count = count_below_70

            next_grade, decision = evaluate_supervisor_annual(rec.grade_supervisor, avg_3tw, count_below_70, env=rec.env)
            rec.potensi_grade_berikutnya = next_grade
            rec.potensi_keputusan = decision

            if rec.data_validity == 'unmapped':
                rec.status_evaluasi = 'invalid'
            elif rec.annual_complete and rec.data_validity == 'valid':
                rec.status_evaluasi = 'final'
            else:
                rec.status_evaluasi = 'berjalan'

    @api.model
    def recompute_from_transactions(self, synced_months_set=None):
        """
        Menghitung ulang evaluasi semua Supervisor per (tahun, triwulan) dari
        sales.grading.gp.transaction tanpa double counting.
        """
        Supervisor = self.env['sales.grading.supervisor'].with_context(active_test=False)
        Tx = self.env['sales.grading.gp.transaction']
        synced_months_set = synced_months_set or set()

        all_tx = Tx.search([])
        years = sorted(set(all_tx.mapped('year')) - {False, ''})
        if not years:
            return 0

        # If synced_months_set wasn't passed, infer from distinct (year, month) in transactions
        if not synced_months_set:
            synced_months_set = {(tx.year, tx.month) for tx in all_tx if tx.year and tx.month}

        all_spvs = Supervisor.search([])
        count = 0
        for spv in all_spvs:
            for yr in years:
                yr_tx = all_tx.filtered(lambda t: t.year == yr and t.supervisor_id.id == spv.id)
                # Also check if supervisor has active assignment in that year even with 0 tx
                yr_start = fields.Date.from_string(f'{yr}-01-01')
                yr_end = fields.Date.from_string(f'{yr}-12-31')
                has_assign_in_yr = bool(spv.assignment_ids.filtered(
                    lambda a: a.date_start <= yr_end and (not a.date_end or a.date_end >= yr_start)
                ))
                if not yr_tx and not has_assign_in_yr:
                    continue

                # Determine teams managed in this year
                teams_in_yr = spv.assignment_ids.filtered(
                    lambda a: a.date_start <= yr_end and (not a.date_end or a.date_end >= yr_start)
                ).mapped('team_id')
                team_label = ', '.join(sorted(set(teams_in_yr.mapped('name')))) if teams_in_yr else _('Belum Ditugaskan')

                # Check invalid/unmapped transactions on the teams handled by this supervisor
                team_tx_all = all_tx.filtered(lambda t: t.year == yr and t.team_id.id in teams_in_yr.ids)
                invalid_team_tx = team_tx_all.filtered(lambda t: not t.is_valid or not t.supervisor_id)

                # Compute annual GP & completeness across Q1..Q4
                q_totals = {}
                q_complete = {}
                for q_key, months in QUARTER_MONTHS.items():
                    q_tx = yr_tx.filtered(lambda t: t.quarter == q_key)
                    m_sums = [sum(q_tx.filtered(lambda t: t.month == m).mapped('gross_profit')) for m in months]
                    q_totals[q_key] = sum(m_sums)
                    q_complete[q_key] = all((yr, m) in synced_months_set for m in months)

                annual_gp = sum(q_totals.values())
                all_4q_synced = all(q_complete.values())
                has_invalid = bool(invalid_team_tx) or not teams_in_yr
                annual_complete = bool(all_4q_synced and not has_invalid)

                for q_key, months in QUARTER_MONTHS.items():
                    # Only create quarter rows for quarters that have at least one synced month or existing eval
                    any_m_synced = any((yr, m) in synced_months_set for m in months)
                    q_tx = yr_tx.filtered(lambda t: t.quarter == q_key)
                    existing = self.search([
                        ('supervisor_id', '=', spv.id),
                        ('year', '=', yr),
                        ('quarter', '=', q_key),
                    ], limit=1)
                    if not any_m_synced and not q_tx and not existing:
                        continue

                    m1, m2, m3 = [
                        sum(q_tx.filtered(lambda t: t.month == m).mapped('gross_profit'))
                        for m in months
                    ]
                    q_invalid = team_tx_all.filtered(lambda t: t.quarter == q_key and (not t.is_valid or not t.supervisor_id))
                    if not teams_in_yr:
                        validity = 'unmapped'
                        v_note = _('Supervisor Belum Ditugaskan ke Tim Sales')
                    elif q_invalid:
                        validity = 'unmapped'
                        v_note = _('%s transaksi tim belum valid / konflik penugasan') % len(q_invalid)
                    elif not q_complete[q_key]:
                        validity = 'incomplete'
                        missing = [m for m in months if (yr, m) not in synced_months_set]
                        v_note = _('Bulan %s belum tersinkronisasi') % ', '.join(missing)
                    elif not annual_complete:
                        validity = 'valid'
                        v_note = _('Triwulan valid; evaluasi tahunan menunggu 4 triwulan lengkap')
                    else:
                        validity = 'valid'
                        v_note = _('4 Triwulan lengkap dan valid')

                    members = set(q_tx.mapped('salesman_raw')) - {False, ''}
                    vals = {
                        'supervisor_id': spv.id,
                        'year': yr,
                        'quarter': q_key,
                        'grade_supervisor': spv.grade,
                        'team_names': team_label,
                        'gp_bulan_1': m1,
                        'gp_bulan_2': m2,
                        'gp_bulan_3': m3,
                        'akumulasi_gp_tahunan': annual_gp,
                        'quarter_complete': q_complete[q_key],
                        'annual_complete': annual_complete,
                        'data_validity': validity,
                        'validity_note': v_note,
                        'tx_count': len(q_tx),
                        'member_count': len(members),
                    }
                    if existing:
                        existing.write(vals)
                    else:
                        self.create(vals)
                    count += 1
        return count
