# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from odoo import models, fields, api, _
from .grading_rules import (
    GRADE_LABELS,
    SUPERVISOR_GRADE_LABELS,
    QUARTER_SHORT_LABELS,
    QUARTER_MONTHS,
    MONTH_NAMES_ID,
    TABEL_A_DATA,
    SUPERVISOR_TARGETS,
)

# Batas minimal tahun data yang ditampilkan di seluruh sistem
MIN_DISPLAY_YEAR = '2026'


def get_current_period_wib():
    """Menghitung periode berjalan otomatis berdasarkan zona waktu Asia/Jakarta (WIB: UTC+7)."""
    try:
        wib = timezone(timedelta(hours=7))
        now = datetime.now(wib)
    except Exception:
        now = datetime.utcnow()
    year = str(now.year)
    month = now.month
    if month in (1, 2, 3):
        quarter = 'Q1'
    elif month in (4, 5, 6):
        quarter = 'Q2'
    elif month in (7, 8, 9):
        quarter = 'Q3'
    else:
        quarter = 'Q4'
    return year, month, quarter


class SalesGradingDashboardAPI(models.AbstractModel):
    _name = 'sales.grading.dashboard.api'
    _description = 'Unified RPC API untuk 4 Submenu Dashboard Grading Sales'

    @api.model
    def _get_user_access_context(self):
        user = self.env.user
        is_admin = user.has_group('base.group_system')
        is_manager = is_admin or user.has_group('sales_grading_triwulan.group_sales_grading_manager')

        Supervisor = self.env['sales.grading.supervisor'].sudo()
        Employee = self.env['hr.employee'].sudo()
        emp = user.employee_id
        if not emp and user.name:
            emp = Employee.search([('name', '=ilike', user.name.strip())], limit=1)

        spv = Supervisor.search([('user_id', '=', user.id), ('active', '=', True)], limit=1)
        if not spv and emp:
            spv = Supervisor.search([('employee_id', '=', emp.id), ('active', '=', True)], limit=1)

        is_supervisor = bool(spv) and not is_manager
        is_salesman_only = (not is_manager) and (not is_supervisor)

        return {
            'uid': user.id,
            'user_name': user.name,
            'is_admin': is_admin,
            'is_manager': is_manager,
            'is_supervisor': is_supervisor,
            'is_salesman_only': is_salesman_only,
            'supervisor_id': spv.id if spv else False,
            'supervisor_team_ids': spv.team_ids.ids if spv else [],
            'employee_id': emp.id if emp else False,
            'can_sync': is_admin,
            'can_manage_supervisor': is_admin,
            'role_label': 'Administrator' if is_admin else ('Manager / Direksi' if is_manager else ('Supervisor' if is_supervisor else 'Salesman')),
        }

    @api.model
    def _get_excluded_salesman_spec(self):
        # Hanya kecualikan data non-sales yang dinonaktifkan (Ufayr Maaris)
        # Satriyo Wibowo dan Muhammad Nashirudin tetap dimunculkan dengan keterangan 'Supervisor'
        return [], [], ['ufayr maaris']

    @api.model
    def _base_salesman_domain(self, ctx_info, filters):
        domain = [('state', '!=', 'cancel'), ('year', '>=', MIN_DISPLAY_YEAR)]
        if not filters.get('include_demo'):
            domain.append(('data_validity', '!=', 'demo'))
            Mapping = self.env['sales.grading.mapping'].sudo()
            active_maps = Mapping.search([
                ('is_active', '=', True),
                ('salesman_raw', 'not ilike', 'ufayr maaris')
            ])
            active_emp_ids = active_maps.mapped('employee_id').ids
            active_names = [m.salesman_raw for m in active_maps if m.salesman_raw]
            active_emp_names = [m.employee_id.name for m in active_maps if m.employee_id and m.employee_id.name]
            all_valid_active_names = list(set(active_names + active_emp_names))
            if active_emp_ids or all_valid_active_names:
                domain.extend(['|', ('employee_id', 'in', active_emp_ids), ('employee_name', 'in', all_valid_active_names)])
            else:
                domain.append(('id', '=', 0))
        domain.append(('employee_name', 'not ilike', 'ufayr maaris'))

        # Access control scoping (Section 13)
        if ctx_info['is_supervisor']:
            spv_id = ctx_info['supervisor_id']
            team_ids = ctx_info['supervisor_team_ids']
            domain.append('|')
            domain.append(('supervisor_id', '=', spv_id))
            domain.append(('team_id', 'in', team_ids or [0]))
        elif ctx_info['is_salesman_only']:
            if ctx_info['employee_id']:
                domain.extend(['|', ('employee_id', '=', ctx_info['employee_id']), ('user_id', '=', ctx_info['uid'])])
            else:
                domain.append(('user_id', '=', ctx_info['uid']))

        if filters.get('year') and str(filters['year']) != 'ALL':
            yr = str(filters['year'])
            domain.append(('year', '=', yr if yr >= MIN_DISPLAY_YEAR else '0000'))
        if filters.get('quarter') and filters['quarter'] != 'ALL':
            domain.append(('quarter', '=', filters['quarter']))
        if filters.get('team_id') and str(filters['team_id']) != 'ALL':
            domain.append(('team_id', '=', int(filters['team_id'])))
        if filters.get('employee_name') and filters['employee_name'] != 'ALL':
            domain.append(('employee_name', '=', filters['employee_name']))
        if filters.get('grading_awal') and filters['grading_awal'] != 'ALL':
            domain.append(('grading_awal', '=', filters['grading_awal']))
        if filters.get('grading_terbaru') and filters['grading_terbaru'] != 'ALL':
            domain.append(('grading_terbaru', '=', filters['grading_terbaru']))
        if filters.get('status_perubahan') and filters['status_perubahan'] != 'ALL':
            domain.append(('status_perubahan', '=', filters['status_perubahan']))
        if filters.get('search'):
            q = filters['search'].strip()
            domain.extend(['|', ('employee_name', 'ilike', q), ('team_name', 'ilike', q)])
        return domain

    @api.model
    def _get_relevant_teams(self, recs=None):
        Team = self.env['sales.grading.team'].sudo()
        Assignment = self.env['sales.grading.supervisor.assignment'].sudo()
        Grading = self.env['sales.grading.triwulan'].sudo()
        if recs is None:
            recs = Grading.search([('state', '!=', 'cancel'), ('year', '>=', MIN_DISPLAY_YEAR)])
        relevant_ids = set(recs.mapped('team_id').ids)
        relevant_ids.update(Assignment.search([('status', '=', 'active')]).mapped('team_id').ids)
        domain = [('active', '=', True)]
        if relevant_ids:
            domain.append(('id', 'in', list(relevant_ids)))
        return Team.search(domain, order='name asc')

    @api.model
    def _get_salesman_filter_options(self, ctx_info):
        Grading = self.env['sales.grading.triwulan'].sudo()
        Mapping = self.env['sales.grading.mapping'].sudo()
        spv_emp_ids, _spv_names, excluded_names = self._get_excluded_salesman_spec()
        ex_domain = []
        if spv_emp_ids:
            ex_domain.extend(['|', ('employee_id', '=', False), ('employee_id', 'not in', spv_emp_ids)])
        for ex_name in excluded_names:
            ex_domain.append(('employee_name', 'not ilike', ex_name))

        active_maps = Mapping.search([
            ('is_active', '=', True),
            ('salesman_raw', 'not ilike', 'ufayr maaris')
        ])
        active_emp_ids = active_maps.mapped('employee_id').ids
        active_names = [m.salesman_raw for m in active_maps if m.salesman_raw]
        active_emp_names = [m.employee_id.name for m in active_maps if m.employee_id and m.employee_id.name]
        all_valid_active_names = list(set(active_names + active_emp_names))
        if active_emp_ids or all_valid_active_names:
            ex_domain.extend(['|', ('employee_id', 'in', active_emp_ids), ('employee_name', 'in', all_valid_active_names)])
        else:
            ex_domain.append(('id', '=', 0))

        recs = Grading.search([
            ('state', '!=', 'cancel'),
            ('data_validity', '!=', 'demo'),
            ('year', '>=', MIN_DISPLAY_YEAR),
        ] + ex_domain)
        if not recs:
            recs = Grading.search([('state', '!=', 'cancel'), ('year', '>=', MIN_DISPLAY_YEAR)] + ex_domain)

        cur_year, cur_month, cur_quarter = get_current_period_wib()
        years_set = set(recs.mapped('year')) | {cur_year, MIN_DISPLAY_YEAR}
        years = sorted([y for y in years_set if y and str(y) >= MIN_DISPLAY_YEAR], reverse=True)
        names = sorted(set(recs.mapped('employee_name')) - {False, ''})
        teams = [{'id': t.id, 'name': t.name} for t in self._get_relevant_teams(recs)]

        return {
            'years': years,
            'quarters': [{'key': q, 'label': QUARTER_SHORT_LABELS[q]} for q in ('Q1', 'Q2', 'Q3', 'Q4')],
            'teams': teams,
            'salesmen': names,
            'grades': [{'key': k, 'label': v} for k, v in GRADE_LABELS.items()],
            'statuses': [
                {'key': 'promosi', 'label': 'Promosi'},
                {'key': 'stabil', 'label': 'Stabil'},
                {'key': 'demosi', 'label': 'Demosi'},
            ],
            'current_period': {
                'year': cur_year,
                'month': cur_month,
                'quarter': cur_quarter,
                'quarter_label': QUARTER_SHORT_LABELS.get(cur_quarter, cur_quarter),
            },
            'default_year': cur_year,
            'default_quarter': cur_quarter,
            'default_valid_year': cur_year,
            'default_valid_quarter': cur_quarter,
        }

    @api.model
    def _serialize_salesman_row(self, rec, idx=0):
        Supervisor = self.env['sales.grading.supervisor'].sudo().with_context(active_test=False)
        spv_emp_ids = set(Supervisor.search([('active', '=', True)]).mapped('employee_id').ids)
        emp_clean = (rec.employee_name or '').strip().upper()
        is_spv = (
            rec.grading_awal == 'supervisor' or
            rec.grading_terbaru == 'supervisor' or
            emp_clean in ('SATRIYO WIBOWO', 'MUHAMMAD NASHIRUDIN') or
            (rec.employee_id and rec.employee_id.id in spv_emp_ids)
        )
        grade_awal = 'supervisor' if is_spv else rec.grading_awal
        grade_terbaru = 'supervisor' if is_spv else rec.grading_terbaru
        next_grade = 'supervisor' if is_spv else rec.next_grade_potential

        grade_awal_label = 'Supervisor' if is_spv else GRADE_LABELS.get(rec.grading_awal, rec.grading_awal)
        grade_terbaru_label = 'Supervisor' if is_spv else GRADE_LABELS.get(rec.grading_terbaru, rec.grading_terbaru)
        next_grade_label = 'Supervisor' if is_spv else GRADE_LABELS.get(rec.next_grade_potential, '-')

        return {
            'no': idx,
            'id': rec.id,
            'doc_no': rec.name,
            'year': rec.year or '-',
            'quarter': rec.quarter or '-',
            'quarter_label': QUARTER_SHORT_LABELS.get(rec.quarter, rec.periode),
            'periode': rec.periode,
            'employee_id': rec.employee_id.id if rec.employee_id else False,
            'employee_name': rec.employee_name,
            'team_id': rec.team_id.id if rec.team_id else False,
            'team_name': rec.team_name or 'Belum Ditentukan',
            'supervisor_name': rec.supervisor_id.name if rec.supervisor_id else '-',
            'grading_awal': grade_awal,
            'grading_awal_label': grade_awal_label,
            'grading_terbaru': grade_terbaru,
            'grading_terbaru_label': grade_terbaru_label,
            'next_grade_potential': next_grade,
            'next_grade_potential_label': next_grade_label,
            'is_supervisor': is_spv,
            'target_gp_bulanan': rec.target_gp_tabel_a,
            'target_gp_triwulan': rec.target_gp_tabel_a * 3.0,
            'gp_bulan_1': rec.gp_bulan_1,
            'gp_bulan_2': rec.gp_bulan_2,
            'gp_bulan_3': rec.gp_bulan_3,
            'total_gp': rec.total_gp,
            'rata_rata_gp': rec.rata_rata_gp,
            'persentase_pencapaian': rec.persentase_pencapaian,
            'status_perubahan': 'stabil' if is_spv else rec.status_perubahan,
            'status_perubahan_label': 'Supervisor' if is_spv else (rec.status_perubahan or 'stabil').capitalize(),
            'tunjangan_fungsional': rec.tunjangan_fungsional,
            'take_home_pay': rec.take_home_pay,
            'state': rec.state,
            'data_validity': rec.data_validity,
            'validity_note': rec.validity_note or '',
            'is_valid_final': rec.is_valid_final,
            'tx_count': rec.tx_count,
        }

    # ------------------------------------------------------------------
    # SUBMENU 1: DASHBOARD GRADING SALESMAN
    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_salesman_data(self, filters=None):
        filters = dict(filters or {})
        ctx_info = self._get_user_access_context()
        options = self._get_salesman_filter_options(ctx_info)
        sync_info = self.env['sales.grading.sync.log'].sudo().get_last_sync_summary()

        # Apply default latest period if initial load
        if not filters.get('_initialized'):
            if not filters.get('year'):
                filters['year'] = options['default_year']
            if not filters.get('quarter'):
                filters['quarter'] = options['default_quarter']
            filters['_initialized'] = True

        Grading = self.env['sales.grading.triwulan'].sudo()
        domain = self._base_salesman_domain(ctx_info, filters)

        sort_by = filters.get('sort_by') or 'total_gp'
        sort_dir = filters.get('sort_dir') or 'desc'
        allowed_sorts = {
            'total_gp': 'total_gp',
            'rata_rata_gp': 'rata_rata_gp',
            'persentase_pencapaian': 'persentase_pencapaian',
            'grading_terbaru': 'grading_terbaru',
            'employee_name': 'employee_name',
        }
        order_field = allowed_sorts.get(sort_by, 'total_gp')
        order_dir = 'asc' if sort_dir == 'asc' else 'desc'
        recs = Grading.search(domain, order=f'{order_field} {order_dir}, id desc')

        # KPI Cards (10 cards)
        total_salesman = len(recs)
        total_gp = sum(recs.mapped('total_gp'))
        avg_gp_salesman = round(total_gp / total_salesman) if total_salesman else 0.0
        grade_counts = {k: 0 for k in GRADE_LABELS}
        status_counts = {'promosi': 0, 'stabil': 0, 'demosi': 0}
        team_totals = defaultdict(float)

        for r in recs:
            if r.grading_terbaru in grade_counts:
                grade_counts[r.grading_terbaru] += 1
            if r.status_perubahan in status_counts:
                status_counts[r.status_perubahan] += 1
            team_totals[r.team_name or 'Belum Ditentukan'] += r.total_gp

        kpis = {
            'total_salesman': total_salesman,
            'total_gp': total_gp,
            'avg_gp_per_salesman': avg_gp_salesman,
            'count_star': grade_counts['star'],
            'count_executive': grade_counts['executive'],
            'count_senior': grade_counts['senior'],
            'count_junior': grade_counts['junior'],
            'count_new': grade_counts['new'],
            'count_promosi': status_counts['promosi'],
            'count_demosi': status_counts['demosi'],
            'invalid_count': len(recs.filtered(lambda r: not r.is_valid_final)),
        }

        # Charts (5 charts)
        # 1. Grade Distribution
        chart_grade_dist = {
            'labels': ['Star Sales', 'Executive Sales', 'Senior Sales', 'Junior Sales', 'New Sales'],
            'values': [grade_counts[k] for k in ('star', 'executive', 'senior', 'junior', 'new')],
        }
        # 2. Total GP per Team
        sorted_teams = sorted(team_totals.items(), key=lambda x: x[1], reverse=True)
        chart_team_gp = {
            'labels': [x[0] for x in sorted_teams],
            'values': [x[1] for x in sorted_teams],
        }
        # 3. Target GP vs Realisasi GP (Top 10 by GP or all filtered)
        top_recs = sorted(recs, key=lambda r: r.total_gp, reverse=True)[:12]
        chart_target_vs_real = {
            'labels': [r.employee_name for r in top_recs],
            'target': [r.target_gp_tabel_a * 3.0 for r in top_recs],
            'realisasi': [r.total_gp for r in top_recs],
        }
        # 4. Perubahan Grading
        chart_status_changes = {
            'labels': ['Promosi', 'Stabil', 'Demosi'],
            'values': [status_counts['promosi'], status_counts['stabil'], status_counts['demosi']],
        }
        # 5. Tren GP berdasarkan Triwulan (tahun >= 2026, sesuai scope filter/user)
        trend_filters = dict(filters)
        trend_filters['quarter'] = 'ALL'
        trend_domain = self._base_salesman_domain(ctx_info, trend_filters)
        trend_recs = Grading.search(trend_domain)
        trend_map = defaultdict(float)
        for tr in trend_recs:
            if tr.year and tr.quarter:
                trend_map[(tr.year, tr.quarter)] += tr.total_gp
        q_order = {'Q1': 1, 'Q2': 2, 'Q3': 3, 'Q4': 4}
        sorted_trend = sorted(trend_map.items(), key=lambda x: (x[0][0], q_order.get(x[0][1], 0)))
        chart_quarterly_trend = {
            'labels': [f"{k[0]} {QUARTER_SHORT_LABELS.get(k[1], k[1])}" for k, _ in sorted_trend],
            'values': [v for _, v in sorted_trend],
        }

        rows = [self._serialize_salesman_row(r, idx + 1) for idx, r in enumerate(recs)]

        return {
            'access': ctx_info,
            'sync': sync_info,
            'options': options,
            'active_filters': filters,
            'kpis': kpis,
            'charts': {
                'grade_distribution': chart_grade_dist,
                'team_gp': chart_team_gp,
                'target_vs_realization': chart_target_vs_real,
                'status_changes': chart_status_changes,
                'quarterly_trend': chart_quarterly_trend,
            },
            'rows': rows,
        }

    # ------------------------------------------------------------------
    # SUBMENU 2: REKAP GRADING SALESMAN + DETAIL MODAL
    # ------------------------------------------------------------------
    @api.model
    def get_rekap_salesman_data(self, filters=None):
        filters = dict(filters or {})
        ctx_info = self._get_user_access_context()
        options = self._get_salesman_filter_options(ctx_info)
        sync_info = self.env['sales.grading.sync.log'].sudo().get_last_sync_summary()

        if not filters.get('_initialized'):
            if not filters.get('year'):
                filters['year'] = options['default_year']
            if not filters.get('quarter'):
                filters['quarter'] = options['default_quarter']
            filters['_initialized'] = True

        Grading = self.env['sales.grading.triwulan'].sudo()
        domain = self._base_salesman_domain(ctx_info, filters)

        sort_by = filters.get('sort_by') or 'total_gp'
        sort_dir = filters.get('sort_dir') or 'desc'
        allowed_sorts = {
            'year': 'year',
            'total_gp': 'total_gp',
            'rata_rata_gp': 'rata_rata_gp',
            'persentase_pencapaian': 'persentase_pencapaian',
            'employee_name': 'employee_name',
        }
        order_field = allowed_sorts.get(sort_by, 'total_gp')
        order_dir = 'asc' if sort_dir == 'asc' else 'desc'
        order_str = f'{order_field} {order_dir}, quarter desc, total_gp desc, id desc'
        if order_field != 'year':
            order_str = f'{order_field} {order_dir}, year desc, quarter desc'

        recs = Grading.search(domain, order=order_str)
        rows = [self._serialize_salesman_row(r, idx + 1) for idx, r in enumerate(recs)]

        # 5 Kartu KPI Summary Aktual Sesuai Master Prompt Section 6
        grade_counts = {k: 0 for k in GRADE_LABELS}
        for r in recs:
            if r.grading_terbaru in grade_counts:
                grade_counts[r.grading_terbaru] += 1

        kpis = {
            'total_salesman': len(recs),
            'count_senior': grade_counts.get('senior', 0),
            'count_executive': grade_counts.get('executive', 0),
            'count_junior': grade_counts.get('junior', 0),
            'count_star': grade_counts.get('star', 0),
            'count_new': grade_counts.get('new', 0),
            'invalid_count': len(recs.filtered(lambda r: not r.is_valid_final)),
        }

        summary = {
            'total_records': len(recs),
            'total_gp': sum(recs.mapped('total_gp')),
            'avg_gp': round(sum(recs.mapped('rata_rata_gp')) / len(recs)) if recs else 0.0,
            'count_promosi': len(recs.filtered(lambda r: r.status_perubahan == 'promosi')),
            'count_stabil': len(recs.filtered(lambda r: r.status_perubahan == 'stabil')),
            'count_demosi': len(recs.filtered(lambda r: r.status_perubahan == 'demosi')),
        }
        return {
            'access': ctx_info,
            'sync': sync_info,
            'options': options,
            'active_filters': filters,
            'kpis': kpis,
            'summary': summary,
            'rows': rows,
        }

    @api.model
    def get_salesman_detail(self, employee_id=False, employee_name=False):
        ctx_info = self._get_user_access_context()
        Grading = self.env['sales.grading.triwulan'].sudo()
        Tx = self.env['sales.grading.gp.transaction'].sudo()
        History = self.env['sales.grading.history'].sudo()
        Employee = self.env['hr.employee'].sudo().with_context(active_test=False)

        emp = Employee.browse(int(employee_id)) if employee_id else Employee.search([('name', '=ilike', employee_name or '')], limit=1)
        spv_emp_ids, _spv_names, excluded_names = self._get_excluded_salesman_spec()
        check_name = ((emp.name if emp else '') or employee_name or '').strip().lower()
        if (emp and emp.id in spv_emp_ids) or any(ex in check_name for ex in excluded_names):
            return {'error': _('Data tidak ditampilkan pada Grading Salesman (Supervisor / non-aktif).')}

        domain = [('state', '!=', 'cancel'), ('data_validity', '!=', 'demo'), ('year', '>=', MIN_DISPLAY_YEAR)]
        if emp:
            domain.extend(['|', ('employee_id', '=', emp.id), ('employee_name', '=ilike', emp.name)])
            name_key = emp.name
        else:
            domain.append(('employee_name', '=ilike', employee_name or ''))
            name_key = employee_name or '-'

        # Scope check for salesman-only users
        if ctx_info['is_salesman_only']:
            if ctx_info['employee_id'] and emp and emp.id != ctx_info['employee_id']:
                return {'error': _('Akses ditolak: Anda hanya dapat melihat detail grading Anda sendiri.')}

        q_order = {'Q1': 1, 'Q2': 2, 'Q3': 3, 'Q4': 4}
        recs = Grading.search(domain)
        sorted_recs = sorted(recs, key=lambda r: (r.year or '0000', q_order.get(r.quarter, 0), r.id))

        latest = sorted_recs[-1] if sorted_recs else False
        # Monthly breakdown across synced transactions (year >= 2026)
        tx_domain = [('year', '>=', MIN_DISPLAY_YEAR)]
        if emp:
            tx_domain.extend(['|', ('employee_id', '=', emp.id), ('salesman_raw', '=ilike', emp.name)])
        else:
            tx_domain.append(('salesman_raw', '=ilike', name_key))
        txs = Tx.search(tx_domain, order='tx_date desc')

        monthly_map = defaultdict(lambda: {'gp': 0.0, 'omzet': 0.0, 'count': 0})
        for t in txs:
            monthly_map[(t.year, t.month)]['gp'] += t.gross_profit
            monthly_map[(t.year, t.month)]['omzet'] += t.total_net_omzet
            monthly_map[(t.year, t.month)]['count'] += 1

        monthly_rows = []
        for (yr, mo), stats in sorted(monthly_map.items(), reverse=True):
            monthly_rows.append({
                'year': yr,
                'month': mo,
                'month_name': MONTH_NAMES_ID.get(mo, mo),
                'tx_count': stats['count'],
                'omzet': stats['omzet'],
                'gp': stats['gp'],
            })

        history_recs = History.search([('grading_id', 'in', recs.ids)], order='changed_at desc, id desc')
        history_rows = [{
            'id': h.id,
            'periode': h.periode or f"{h.year} {h.quarter}",
            'grade_before': GRADE_LABELS.get(h.grade_before, h.grade_before),
            'grade_after': GRADE_LABELS.get(h.grade_after, h.grade_after),
            'change_status': h.change_status,
            'change_reason': h.change_reason,
            'avg_gp': h.avg_gp,
            'pct': h.pct_achievement,
            'changed_by': h.changed_by.name,
            'changed_at': fields.Datetime.to_string(h.changed_at),
            'notes': h.notes or '',
        } for h in history_recs]

        quarterly_rows = [self._serialize_salesman_row(r, i + 1) for i, r in enumerate(sorted_recs)]
        promo_demosi = [r for r in quarterly_rows if r['status_perubahan'] in ('promosi', 'demosi')]

        return {
            'identity': {
                'employee_id': emp.id if emp else False,
                'name': name_key,
                'job_title': emp.job_title if emp else '-',
                'department': emp.department_id.name if emp and emp.department_id else '-',
                'work_email': emp.work_email if emp else '-',
                'team_name': latest.team_name if latest else '-',
                'supervisor_name': latest.supervisor_id.name if latest and latest.supervisor_id else '-',
                'grading_awal': latest.grading_awal_label if latest and hasattr(latest, 'grading_awal_label') else GRADE_LABELS.get(latest.grading_awal, '-') if latest else '-',
                'grading_terbaru': GRADE_LABELS.get(latest.grading_terbaru, '-') if latest else '-',
                'grading_terbaru_key': latest.grading_terbaru if latest else 'new',
                'target_gp_bulanan': latest.target_gp_tabel_a if latest else 0.0,
                'rata_rata_gp': latest.rata_rata_gp if latest else 0.0,
                'persentase_pencapaian': latest.persentase_pencapaian if latest else 0.0,
            },
            'quarterly_rows': quarterly_rows,
            'monthly_rows': monthly_rows,
            'promo_demosi': promo_demosi,
            'history_rows': history_rows,
            'chart_trend': {
                'labels': [f"{r['year']} {r['quarter']}" for r in quarterly_rows],
                'gp_values': [r['total_gp'] for r in quarterly_rows],
                'target_values': [r['target_gp_triwulan'] for r in quarterly_rows],
            },
        }

    # ------------------------------------------------------------------
    # SUBMENU 3: RANGKING SALESMAN
    # ------------------------------------------------------------------
    @api.model
    def get_ranking_salesman_data(self, filters=None):
        filters = dict(filters or {})
        ctx_info = self._get_user_access_context()
        options = self._get_salesman_filter_options(ctx_info)
        sync_info = self.env['sales.grading.sync.log'].sudo().get_last_sync_summary()

        # Default: latest valid period (Section 6A)
        if not filters.get('_initialized'):
            if not filters.get('year'):
                filters['year'] = options['default_valid_year']
            if not filters.get('quarter'):
                filters['quarter'] = options['default_valid_quarter']
            filters['_initialized'] = True

        Grading = self.env['sales.grading.triwulan'].sudo()
        domain = self._base_salesman_domain(ctx_info, filters)
        all_recs = Grading.search(domain)

        # Separate valid final records vs invalid/incomplete records
        valid_recs = [r for r in all_recs if r.is_valid_final]
        invalid_recs = [r for r in all_recs if not r.is_valid_final]

        # Sort by Total GP DESC, tie-breaker Persentase Pencapaian DESC
        valid_recs.sort(key=lambda r: (r.total_gp, r.persentase_pencapaian, r.rata_rata_gp), reverse=True)

        ranked_rows = [self._serialize_salesman_row(r, idx + 1) for idx, r in enumerate(valid_recs)]
        invalid_rows = [self._serialize_salesman_row(r, idx + 1) for idx, r in enumerate(invalid_recs)]

        top3 = ranked_rows[:3]
        top10 = ranked_rows[:10]

        team_gp = defaultdict(float)
        for r in valid_recs:
            team_gp[r.team_name or 'Belum Ditentukan'] += r.total_gp
        sorted_teams = sorted(team_gp.items(), key=lambda x: x[1], reverse=True)

        return {
            'access': ctx_info,
            'sync': sync_info,
            'options': options,
            'active_filters': filters,
            'top3': top3,
            'rows': ranked_rows,
            'invalid_rows': invalid_rows,
            'charts': {
                'top10_gp': {
                    'labels': [r['employee_name'] for r in top10],
                    'values': [r['total_gp'] for r in top10],
                },
                'team_comparison': {
                    'labels': [t[0] for t in sorted_teams],
                    'values': [t[1] for t in sorted_teams],
                },
                'target_achievement': {
                    'labels': [r['employee_name'] for r in top10],
                    'values': [r['persentase_pencapaian'] for r in top10],
                },
            },
        }

    # ------------------------------------------------------------------
    # SUBMENU 4: DASHBOARD SUPERVISOR / TIM
    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_supervisor_data(self, filters=None):
        filters = dict(filters or {})
        ctx_info = self._get_user_access_context()
        sync_info = self.env['sales.grading.sync.log'].sudo().get_last_sync_summary()

        Supervisor = self.env['sales.grading.supervisor'].sudo().with_context(active_test=False)
        SpvEval = self.env['sales.grading.supervisor.eval'].sudo()
        Team = self.env['sales.grading.team'].sudo()

        # Dynamic Supervisor list strictly from Master Data Supervisor (NEVER hardcoded!)
        active_spvs = Supervisor.search([('active', '=', True)], order='name asc')
        all_evals = SpvEval.search([('year', '>=', MIN_DISPLAY_YEAR)], order='year desc, quarter desc')
        cur_year, cur_month, cur_quarter = get_current_period_wib()
        years_set = set(all_evals.mapped('year')) | {cur_year, MIN_DISPLAY_YEAR}
        years = sorted([y for y in years_set if y and str(y) >= MIN_DISPLAY_YEAR], reverse=True)

        if not filters.get('_initialized'):
            if not filters.get('year'):
                filters['year'] = cur_year
            if not filters.get('quarter'):
                filters['quarter'] = cur_quarter
            filters['_initialized'] = True

        domain = [('year', '>=', MIN_DISPLAY_YEAR)]
        if ctx_info['is_supervisor']:
            domain.append(('supervisor_id', '=', ctx_info['supervisor_id']))
        elif ctx_info['is_salesman_only']:
            # Salesman shouldn't see confidential supervisor evaluations unless no restriction
            domain.append(('supervisor_id', '=', -1))

        if filters.get('year') and str(filters['year']) != 'ALL':
            yr = str(filters['year'])
            domain.append(('year', '=', yr if yr >= MIN_DISPLAY_YEAR else '0000'))
        if filters.get('quarter') and filters['quarter'] != 'ALL':
            domain.append(('quarter', '=', filters['quarter']))
        if filters.get('supervisor_id') and str(filters['supervisor_id']) != 'ALL':
            domain.append(('supervisor_id', '=', int(filters['supervisor_id'])))
        if filters.get('grade') and filters['grade'] != 'ALL':
            domain.append(('grade_supervisor', '=', filters['grade']))
        if filters.get('status_evaluasi') and filters['status_evaluasi'] != 'ALL':
            domain.append(('status_evaluasi', '=', filters['status_evaluasi']))
        if filters.get('team_id') and str(filters['team_id']) != 'ALL':
            team_obj = Team.browse(int(filters['team_id']))
            if team_obj.exists():
                domain.append(('team_names', 'ilike', team_obj.name))

        eval_recs = SpvEval.search(domain, order='persentase_triwulan desc, id desc')

        relevant_teams = self._get_relevant_teams()
        # 4 KPI Cards Sesuai Evaluasi Supervisor 2 Grade
        count_spv = len(active_spvs.filtered(lambda s: s.grade == 'supervisor'))
        count_sr = len(active_spvs.filtered(lambda s: s.grade == 'senior_spv'))
        potensi_naik = len(eval_recs.filtered(lambda e: e.potensi_keputusan == 'naik'))
        potensi_turun = len(eval_recs.filtered(lambda e: e.potensi_keputusan == 'turun'))
        potensi_tetap = len(eval_recs.filtered(lambda e: e.potensi_keputusan == 'tetap'))

        total_target = sum(eval_recs.mapped('target_gp_triwulan'))
        total_realisasi = sum(eval_recs.mapped('realisasi_gp_triwulan'))
        pct_total = (total_realisasi / total_target * 100.0) if total_target > 0 else 0.0
        pct_avg = (sum(eval_recs.mapped('persentase_triwulan')) / len(eval_recs)) if eval_recs else 0.0

        kpis = {
            'total_supervisor_aktif': len(active_spvs),
            'total_gp_all_teams': total_realisasi,
            'total_target_all_teams': total_target,
            'pct_achievement_total': round(pct_total, 2),
            'pct_achievement_avg': round(pct_avg, 2),
            'total_tim_sales': len(relevant_teams),
            'count_supervisor': count_spv,
            'count_senior_spv': count_sr,
            'count_potensi_naik': potensi_naik,
            'count_potensi_turun': potensi_turun,
            'count_potensi_tetap': potensi_tetap,
        }

        rows = []
        for idx, e in enumerate(eval_recs):
            rows.append({
                'no': idx + 1,
                'id': e.id,
                'supervisor_id': e.supervisor_id.id,
                'supervisor_name': e.supervisor_name,
                'supervisor_active': e.supervisor_id.active,
                'year': e.year,
                'quarter': e.quarter,
                'quarter_label': QUARTER_SHORT_LABELS.get(e.quarter, e.quarter),
                'team_names': e.team_names or 'Belum Ditugaskan',
                'grade': e.grade_supervisor,
                'grade_label': SUPERVISOR_GRADE_LABELS.get(e.grade_supervisor, e.grade_supervisor),
                'team_composition_desc': e.team_composition_desc or ('6 - 8 Sales + 1 Supervisor' if e.grade_supervisor == 'supervisor' else '9 - 11 Sales + 1 Supervisor'),
                'rata_rata_pencapaian_3tw': e.rata_rata_pencapaian_3tw,
                'triwulan_dibawah_70_count': e.triwulan_dibawah_70_count,
                'target_gp_triwulan': e.target_gp_triwulan,
                'realisasi_gp': e.realisasi_gp_triwulan,
                'persentase_triwulan': e.persentase_triwulan,
                'akumulasi_gp_tahunan': e.akumulasi_gp_tahunan,
                'target_gp_tahunan': e.target_gp_tahunan,
                'persentase_tahunan': e.persentase_tahunan,
                'potensi_grade': e.potensi_grade_berikutnya,
                'potensi_grade_label': SUPERVISOR_GRADE_LABELS.get(e.potensi_grade_berikutnya, '-'),
                'potensi_keputusan': e.potensi_keputusan,
                'status_evaluasi': e.status_evaluasi,
                'annual_complete': e.annual_complete,
                'data_validity': e.data_validity,
                'validity_note': e.validity_note or '',
                'member_count': e.member_count,
                'tx_count': e.tx_count,
            })

        options = {
            'years': years,
            'quarters': [{'key': q, 'label': QUARTER_SHORT_LABELS[q]} for q in ('Q1', 'Q2', 'Q3', 'Q4')],
            'supervisors': [{'id': s.id, 'name': s.name, 'active': s.active} for s in Supervisor.search([], order='active desc, name asc')],
            'teams': [{'id': t.id, 'name': t.name, 'status': t.assignment_status_label} for t in relevant_teams],
            'grades': [{'key': k, 'label': v} for k, v in SUPERVISOR_GRADE_LABELS.items()],
            'statuses': [
                {'key': 'berjalan', 'label': 'Berjalan (Sementara)'},
                {'key': 'final', 'label': 'Final (4 Triwulan Lengkap)'},
                {'key': 'invalid', 'label': 'Data Belum Valid'},
            ],
            'current_period': {
                'year': cur_year,
                'month': cur_month,
                'quarter': cur_quarter,
                'quarter_label': QUARTER_SHORT_LABELS.get(cur_quarter, cur_quarter),
            },
            'default_year': cur_year,
            'default_quarter': cur_quarter,
        }

        return {
            'access': ctx_info,
            'sync': sync_info,
            'options': options,
            'active_filters': filters,
            'kpis': kpis,
            'rows': rows,
            'charts': {
                'target_vs_realization': {
                    'labels': [r['supervisor_name'] for r in rows],
                    'target': [r['target_gp_triwulan'] for r in rows],
                    'realisasi': [r['realisasi_gp'] for r in rows],
                },
                'annual_progress': {
                    'labels': [r['supervisor_name'] for r in rows],
                    'pct_triwulan': [r['persentase_triwulan'] for r in rows],
                    'pct_tahunan': [r['persentase_tahunan'] for r in rows],
                },
            },
        }

    @api.model
    def get_supervisor_detail(self, supervisor_id, year=None):
        ctx_info = self._get_user_access_context()
        if ctx_info['is_salesman_only']:
            return {'error': _('Akses ditolak.')}
        if ctx_info['is_supervisor'] and int(supervisor_id) != ctx_info['supervisor_id']:
            return {'error': _('Akses ditolak: Anda hanya dapat melihat detail tim Anda sendiri.')}

        Supervisor = self.env['sales.grading.supervisor'].sudo().with_context(active_test=False)
        SpvEval = self.env['sales.grading.supervisor.eval'].sudo()
        Tx = self.env['sales.grading.gp.transaction'].sudo()
        History = self.env['sales.grading.history'].sudo()

        spv = Supervisor.browse(int(supervisor_id))
        if not spv.exists():
            return {'error': _('Supervisor tidak ditemukan.')}

        yr = str(year) if year and str(year) != 'ALL' and str(year) >= MIN_DISPLAY_YEAR else MIN_DISPLAY_YEAR
        txs = Tx.search([('supervisor_id', '=', spv.id), ('year', '=', yr)])

        # Member GP breakdown (exclude Ufayr Maaris, tag Supervisors clearly)
        spv_emp_ids, spv_names, _excluded_names = self._get_excluded_salesman_spec()
        member_map = defaultdict(lambda: {'gp': 0.0, 'omzet': 0.0, 'tx_count': 0, 'team': '-', 'is_supervisor': False, 'role_label': 'Salesman'})
        for t in txs:
            mname = t.employee_id.name if t.employee_id else (t.salesman_raw or 'Unknown')
            mlower = mname.strip().lower()
            if 'ufayr maaris' in mlower:
                continue
            is_spv_member = bool(t.employee_id and t.employee_id.id in spv_emp_ids) or any(s in mlower for s in spv_names)
            member_map[mname]['gp'] += t.gross_profit
            member_map[mname]['omzet'] += t.total_net_omzet
            member_map[mname]['tx_count'] += 1
            if is_spv_member:
                member_map[mname]['is_supervisor'] = True
                member_map[mname]['role_label'] = 'Supervisor'
            if t.team_id:
                member_map[mname]['team'] = t.team_id.name
        members = [
            {'name': k, **v}
            for k, v in sorted(member_map.items(), key=lambda x: x[1]['gp'], reverse=True)
        ]

        # Monthly GP (01..12)
        monthly = []
        for m in [f'{i:02d}' for i in range(1, 13)]:
            m_tx = txs.filtered(lambda t: t.month == m)
            monthly.append({
                'month': m,
                'month_name': MONTH_NAMES_ID.get(m, m),
                'gp': sum(m_tx.mapped('gross_profit')),
                'tx_count': len(m_tx),
            })

        # Quarterly GP (Q1..Q4)
        evals = SpvEval.search([('supervisor_id', '=', spv.id), ('year', '=', yr)], order='quarter asc')
        eval_by_q = {e.quarter: e for e in evals}
        quarterly = []
        target_q = SUPERVISOR_TARGETS.get(spv.grade, SUPERVISOR_TARGETS['supervisor'])['quarterly']
        for q in ('Q1', 'Q2', 'Q3', 'Q4'):
            ev = eval_by_q.get(q)
            q_gp = ev.realisasi_gp_triwulan if ev else sum(txs.filtered(lambda t: t.quarter == q).mapped('gross_profit'))
            pct_q = round((q_gp / target_q) * 100.0, 2) if target_q else 0.0
            quarterly.append({
                'quarter': q,
                'label': QUARTER_SHORT_LABELS[q],
                'gp': q_gp,
                'target': target_q,
                'pct': pct_q,
                'complete': ev.quarter_complete if ev else False,
            })

        annual_gp = sum(q['gp'] for q in quarterly)
        target_annual = SUPERVISOR_TARGETS.get(spv.grade, SUPERVISOR_TARGETS['supervisor'])['annual']
        pct_annual = round((annual_gp / target_annual) * 100.0, 2) if target_annual else 0.0

        assignments = [{
            'id': a.id,
            'team_name': a.team_id.name,
            'grade': SUPERVISOR_GRADE_LABELS.get(a.grade_at_assignment, a.grade_at_assignment),
            'date_start': str(a.date_start),
            'date_end': str(a.date_end) if a.date_end else 'Aktif',
            'status': a.status,
            'members': a.member_snapshot or '-',
            'notes': a.notes or '',
        } for a in spv.assignment_ids]

        histories = [{
            'id': h.id,
            'periode': h.periode or f"{h.year or ''} {h.quarter or ''}".strip(),
            'grade_before': SUPERVISOR_GRADE_LABELS.get(h.grade_before, h.grade_before),
            'grade_after': SUPERVISOR_GRADE_LABELS.get(h.grade_after, h.grade_after),
            'change_status': h.change_status,
            'changed_by': h.changed_by.name,
            'changed_at': fields.Datetime.to_string(h.changed_at),
            'notes': h.notes or '',
        } for h in History.search([
            ('supervisor_id', '=', spv.id),
            '|', ('year', '=', False), ('year', '>=', MIN_DISPLAY_YEAR),
        ], order='changed_at desc')]

        return {
            'identity': {
                'id': spv.id,
                'name': spv.name,
                'grade': spv.grade,
                'grade_label': SUPERVISOR_GRADE_LABELS.get(spv.grade, spv.grade),
                'team_composition_desc': spv.team_composition_desc or ('6 - 8 Sales + 1 Supervisor' if spv.grade == 'supervisor' else '9 - 11 Sales + 1 Supervisor'),
                'team_display': spv.team_display,
                'status': spv.status,
                'date_start': str(spv.date_start),
                'date_end': str(spv.date_end) if spv.date_end else 'Aktif',
                'year': yr,
                'target_bulanan': spv.target_gp_bulanan,
                'target_triwulan': spv.target_gp_triwulan,
                'target_tahunan': spv.target_gp_tahunan,
                'akumulasi_tahunan': annual_gp,
                'persentase_tahunan': pct_annual,
                'annual_complete': all(q['complete'] for q in quarterly),
            },
            'members': members,
            'monthly': monthly,
            'quarterly': quarterly,
            'assignments': assignments,
            'histories': histories,
            'chart_annual': {
                'labels': [m['month_name'] for m in monthly],
                'gp_values': [m['gp'] for m in monthly],
                'monthly_target': [spv.target_gp_bulanan for _ in monthly],
            },
        }
