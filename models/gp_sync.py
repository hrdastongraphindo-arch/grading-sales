# -*- coding: utf-8 -*-
import json
import time
import logging
import urllib.parse
from collections import defaultdict
from datetime import datetime
import requests

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from .grading_rules import (
    QUARTER_MONTHS,
    format_periode_label,
    normalize_quarter_from_orimax,
)

_logger = logging.getLogger(__name__)


class SalesGradingSyncLog(models.Model):
    _name = 'sales.grading.sync.log'
    _description = 'Log Sinkronisasi GP ORIMAX'
    _order = 'sync_date desc, id desc'

    name = fields.Char(string='Referensi Sync', required=True, default=lambda self: _('SYNC-%s') % fields.Datetime.now().strftime('%Y%m%d-%H%M%S'))
    sync_date = fields.Datetime(string='Waktu Sinkronisasi', default=fields.Datetime.now, required=True)
    user_id = fields.Many2one('res.users', string='Dijalankan Oleh', default=lambda self: self.env.user)
    source_url = fields.Char(string='Sumber API GP', default='https://gp.orimax.co.id')
    status = fields.Selection([
        ('running', 'Sedang Berjalan'),
        ('success', 'Berhasil'),
        ('partial', 'Berhasil dengan Peringatan Mapping'),
        ('failed', 'Gagal'),
    ], string='Status Sinkronisasi', default='running', required=True)
    total_fetched = fields.Integer(string='Total Baris Diambil', default=0)
    created_count = fields.Integer(string='Transaksi Baru', default=0)
    updated_count = fields.Integer(string='Transaksi Diperbarui', default=0)
    skipped_count = fields.Integer(string='Dilewati / Duplikat', default=0)
    error_count = fields.Integer(string='Jumlah Gagal / Belum Valid', default=0)
    synced_months = fields.Text(string='Bulan Tersinkronisasi (JSON)')
    error_detail = fields.Text(string='Detail Error / Peringatan')
    duration_sec = fields.Float(string='Durasi (detik)', digits=(6, 2), default=0.0)

    @api.model
    def get_last_sync_summary(self):
        last_ok = self.search([('status', 'in', ('success', 'partial'))], limit=1)
        last_any = self.search([], limit=1)
        return {
            'last_success_date': fields.Datetime.to_string(last_ok.sync_date) if last_ok else False,
            'last_status': last_any.status if last_any else 'never',
            'last_status_label': dict(self._fields['status'].selection).get(last_any.status, 'Belum Pernah Sync') if last_any else 'Belum Pernah Sync',
            'last_error': last_any.error_detail if last_any and last_any.status == 'failed' else '',
            'total_fetched': last_ok.total_fetched if last_ok else 0,
            'source_url': (last_any.source_url if last_any else 'https://gp.orimax.co.id'),
        }

    @api.model
    def cron_run_sync(self):
        """Dipanggil oleh Scheduled Action secara aman (skip jika password belum diisi)."""
        ICP = self.env['ir.config_parameter'].sudo()
        if not ICP.get_param('sales_grading.gp_api_password'):
            return False
        try:
            self.action_run_sync(force_recalc=False)
            return True
        except Exception as exc:
            _logger.warning('Cron sinkronisasi GP ORIMAX gagal: %s', exc)
            return False

    @api.model
    def action_sync_all_now(self):
        """Action sinkronisasi yang dipanggil oleh tombol UI 'Sync Data GP SO'."""
        try:
            res = self.action_run_sync(force_recalc=True)
            cnt = res.get('total_fetched', 0)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sinkronisasi Berhasil'),
                    'message': _('Sinkronisasi GP SO berhasil! %s transaksi berhasil diperbarui.') % cnt,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as exc:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sinkronisasi Gagal'),
                    'message': str(exc),
                    'type': 'danger',
                    'sticky': True,
                }
            }

    @api.model
    def action_run_sync(self, force_recalc=False):
        """
        Sinkronisasi langsung dari API resmi https://gp.orimax.co.id/?v=48f078437ab9.
        Kredensial diambil dari ir.config_parameter, tidak pernah hardcoded atau dicatat di log.
        Jika sinkronisasi gagal, data lama yang valid TIDAK dihapus.
        """
        ICP = self.env['ir.config_parameter'].sudo()
        raw_url = (ICP.get_param('sales_grading.gp_api_url') or 'https://gp.orimax.co.id/?v=48f078437ab9').strip()
        parsed = urllib.parse.urlparse(raw_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}".rstrip('/')
        query_str = parsed.query or 'v=48f078437ab9'
        full_source_url = f"{base_url}/?{query_str}" if query_str else base_url
        role = (ICP.get_param('sales_grading.gp_api_role') or 'manager').strip()
        password = ICP.get_param('sales_grading.gp_api_password') or ''

        log = self.create({
            'source_url': full_source_url,
            'status': 'running',
        })
        t0 = time.time()

        if not password:
            msg = _(
                'Konfigurasi kredensial GP ORIMAX belum diisi oleh Administrator '
                '(Menu: Konfigurasi -> Sinkronisasi GP ORIMAX). Data lama tetap dipertahankan.'
            )
            log.write({
                'status': 'failed',
                'error_count': 1,
                'error_detail': msg,
                'duration_sec': round(time.time() - t0, 2),
            })
            raise UserError(msg)

        headers = {
            'User-Agent': 'AGI-Odoo16-GradingSync/1.0',
            'Accept': 'application/json',
        }
        try:
            login_resp = requests.post(
                f'{base_url}/api/login',
                json={'role': role, 'password': password},
                headers=headers,
                timeout=20,
            )
            if login_resp.status_code != 200:
                raise UserError(_('Autentikasi GP ORIMAX gagal (HTTP %s). Periksa kembali Role & Password.') % login_resp.status_code)
            login_data = login_resp.json()
            token = login_data.get('token')
            if not token:
                raise UserError(_('Token sesi GP ORIMAX tidak diterima dari server.'))

            data_headers = dict(headers)
            data_headers['Authorization'] = f'Bearer {token}'
            data_url = f'{base_url}/api/data?{query_str}' if query_str else f'{base_url}/api/data'
            data_resp = requests.get(data_url, headers=data_headers, timeout=60)
            if data_resp.status_code != 200:
                raise UserError(_('Gagal mengambil data GP SO (HTTP %s).') % data_resp.status_code)

            payload = data_resp.json()
            res = self.ingest_orimax_payload(payload, log_rec=log, force_recalc=force_recalc)
            log.write({'duration_sec': round(time.time() - t0, 2)})
            return res
        except Exception as exc:
            # Never log credentials or password
            err_msg = str(exc)
            _logger.error('Sinkronisasi GP ORIMAX gagal: %s', err_msg)
            log.write({
                'status': 'failed',
                'error_count': 1,
                'error_detail': err_msg,
                'duration_sec': round(time.time() - t0, 2),
            })
            raise

    @api.model
    def ingest_orimax_payload(self, payload, log_rec=None, force_recalc=False):
        """
        Memproses payload JSON {"so": [...], "do": [...]} dari GP ORIMAX secara atomik dan idempoten.
        - Anti duplikasi via tx_uid
        - Mapping salesman -> hr.employee (tanpa membuat karyawan baru)
        - Resolusi supervisor berdasarkan riwayat penugasan tim pada tanggal transaksi
        - Agregasi ke sales.grading.triwulan & sales.grading.supervisor.eval
        """
        so_rows = payload.get('so') if isinstance(payload, dict) else []
        if not isinstance(so_rows, list):
            raise UserError(_('Format data GP ORIMAX tidak valid (key "so" bukan list).'))

        Tx = self.env['sales.grading.gp.transaction']
        Team = self.env['sales.grading.team']
        Mapping = self.env['sales.grading.mapping']

        existing_tx_map = {rec.tx_uid: rec for rec in Tx.search([])}
        occ_counter = defaultdict(int)
        synced_months_set = set()
        warnings = []

        created_count = 0
        updated_count = 0
        skipped_count = 0
        error_count = 0

        # Pre-cache teams & mappings to keep sync fast
        team_cache = {}
        emp_cache = {}

        for row in so_rows:
            if not isinstance(row, dict):
                skipped_count += 1
                continue
            yr = str(row.get('year') or '').strip()
            mo = str(row.get('month') or '').strip().zfill(2)
            if not yr or mo not in ('01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'):
                skipped_count += 1
                continue

            synced_months_set.add((yr, mo))
            quarter = normalize_quarter_from_orimax(row.get('triwulan'), mo)
            raw_id = str(row.get('id') or '').strip()
            so_num = str(row.get('soNum') or '').strip()
            product = str(row.get('product') or '').strip()
            salesman_raw = str(row.get('salesman') or '').strip()
            team_raw = str(row.get('team') or '').strip()

            occ_key = (yr, mo, raw_id, so_num, product, salesman_raw)
            occ_counter[occ_key] += 1
            tx_uid = f"{yr}|{mo}|{raw_id}|{so_num}|{product}|{occ_counter[occ_key]}"

            # Parse rawDate safely
            raw_date_str = str(row.get('rawDate') or '').strip()
            tx_dt = False
            if raw_date_str:
                for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
                    try:
                        tx_dt = datetime.strptime(raw_date_str[:19], fmt)
                        break
                    except ValueError:
                        continue
            if not tx_dt:
                try:
                    tx_dt = datetime.strptime(f'{yr}-{mo}-01 00:00:00', '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    tx_dt = datetime.now()
            tx_date_only = tx_dt.date()

            # Match employee (no auto-creation of hr.employee)
            if salesman_raw not in emp_cache:
                emp, _mp = Mapping.resolve_or_register(salesman_raw)
                emp_cache[salesman_raw] = emp
            emp = emp_cache[salesman_raw]

            # Match team
            if team_raw not in team_cache:
                team_cache[team_raw] = Team.match_team_by_raw_name(team_raw)
            team = team_cache[team_raw]
            if not team and salesman_raw:
                mp = Mapping.search([('salesman_raw', '=ilike', salesman_raw)], limit=1)
                if mp and mp.default_team_id:
                    team = mp.default_team_id

            issues = []
            supervisor = self.env['sales.grading.supervisor']
            if not emp:
                issues.append(_('Karyawan "%s" belum terpetakan ke hr.employee') % salesman_raw)
            if not team:
                issues.append(_('Tim "%s" belum terpetakan') % (team_raw or '-'))
            else:
                spv, spv_status, spv_msg = team.resolve_supervisor_for_date(tx_date_only)
                if spv_status == 'ok':
                    supervisor = spv
                else:
                    issues.append(spv_msg)

            is_valid = (len(issues) == 0)
            if not is_valid:
                error_count += 1
                if len(warnings) < 50:
                    warnings.extend(issues)

            qty = float(row.get('qty') or 0.0)
            hpp_unit = float(row.get('hppUnit') or 0.0)
            vals = {
                'tx_uid': tx_uid,
                'source_id': raw_id,
                'year': yr,
                'quarter': quarter,
                'month': mo,
                'salesman_raw': salesman_raw,
                'employee_id': emp.id if emp else False,
                'so_number': so_num,
                'tx_date': fields.Datetime.to_string(tx_dt),
                'tx_date_only': tx_date_only,
                'tx_date_str': str(row.get('date') or ''),
                'customer': str(row.get('customer') or ''),
                'product': product,
                'qty': qty,
                'total_net_omzet': float(row.get('totalOmzetNetto') or 0.0),
                'hpp_total': hpp_unit * qty,
                'gross_profit': float(row.get('gpRp') or 0.0),
                'team_raw': team_raw,
                'team_id': team.id if team else False,
                'supervisor_id': supervisor.id if supervisor else False,
                'vendor': str(row.get('vendor') or ''),
                'status_do': str(row.get('statusDO') or ''),
                'sync_log_id': log_rec.id if log_rec else False,
                'is_valid': is_valid,
                'mapping_issue': '; '.join(issues) if issues else '',
            }

            existing = existing_tx_map.get(tx_uid)
            if existing:
                existing.write(vals)
                updated_count += 1
            else:
                new_rec = Tx.create(vals)
                existing_tx_map[tx_uid] = new_rec
                created_count += 1

        # Recompute salesman grading & supervisor evaluations from consistent transactions
        self._aggregate_salesman_gradings(synced_months_set, force_recalc=force_recalc)
        self.env['sales.grading.supervisor.eval'].recompute_from_transactions(synced_months_set=synced_months_set)

        status = 'partial' if error_count > 0 else 'success'
        unique_warnings = list(dict.fromkeys(warnings))
        if log_rec:
            log_rec.write({
                'status': status,
                'total_fetched': len(so_rows),
                'created_count': created_count,
                'updated_count': updated_count,
                'skipped_count': skipped_count,
                'error_count': error_count,
                'synced_months': json.dumps(sorted(f'{y}-{m}' for y, m in synced_months_set)),
                'error_detail': '\n'.join(unique_warnings[:50]) if unique_warnings else '',
            })

        return {
            'status': status,
            'total_fetched': len(so_rows),
            'created_count': created_count,
            'updated_count': updated_count,
            'error_count': error_count,
            'synced_months': sorted(f'{y}-{m}' for y, m in synced_months_set),
        }

    @api.model
    def _aggregate_salesman_gradings(self, synced_months_set, force_recalc=False):
        """
        Agregasi sales.grading.gp.transaction ke sales.grading.triwulan.
        - Menyertakan semua nama karyawan aktif (meski nominal Rp 0)
        - Menampilkan Satriyo Wibowo & Muhammad Nashirudin dengan grade 'supervisor'
        - Menjaga aturan rollover grading_awal dan validitas triwulan
        """
        Tx = self.env['sales.grading.gp.transaction']
        Grading = self.env['sales.grading.triwulan']
        History = self.env['sales.grading.history']
        Supervisor = self.env['sales.grading.supervisor'].with_context(active_test=False)
        Employee = self.env['hr.employee'].sudo().with_context(active_test=False)
        Mapping = self.env['sales.grading.mapping'].sudo()
        Team = self.env['sales.grading.team'].sudo()

        active_spvs = Supervisor.search([('active', '=', True)])
        spv_emp_ids = set(active_spvs.mapped('employee_id').ids) - {False}
        spv_names = {'satriyo wibowo', 'muhammad nashirudin'} | {s.name.strip().lower() for s in active_spvs if s.name}

        # Hanya kecualikan data non-sales / dinonaktifkan (Ufayr Maaris)
        excluded_names = {'ufayr maaris'}

        # Teams mapping
        team_satriyo = Team.search([('name', 'ilike', 'satriyo')], limit=1)
        team_nashir = Team.search([('name', 'ilike', 'nashir')], limit=1)

        # Roster khusus karyawan sales berstatus AKTIF sesuai Mapping Salesman (ORIMAX <-> HR)
        Mapping.init_default_orimax_mappings()
        active_maps = Mapping.search([
            ('is_active', '=', True),
            ('salesman_raw', 'not ilike', 'ufayr maaris')
        ])

        roster = {}
        active_emp_ids = set()
        active_names = set()
        for m in active_maps:
            if m.employee_id:
                m_clean = (m.employee_id.name or '').strip().lower()
                if any(ex in m_clean for ex in excluded_names):
                    continue
                tm_id = m.default_team_id.id if m.default_team_id else (team_satriyo.id if 'satriyo' in m_clean else (team_nashir.id if 'nashir' in m_clean else False))
                roster[m.employee_id.id] = {
                    'emp_id': m.employee_id.id,
                    'name': m.employee_id.name,
                    'team_id': tm_id,
                }
                active_emp_ids.add(m.employee_id.id)
                active_names.add(m.employee_id.name.strip().lower())
            if m.salesman_raw:
                active_names.add(m.salesman_raw.strip().lower())

        # Batalkan entri grading triwulan untuk karyawan yang berstatus TIDAK AKTIF
        if active_emp_ids:
            inactive_gradings = Grading.search([
                ('state', '!=', 'cancel'),
                ('data_validity', '!=', 'demo'),
                ('employee_id', 'not in', list(active_emp_ids)),
            ])
            if inactive_gradings:
                inactive_gradings.write({'state': 'cancel'})

        all_tx = Tx.search([])
        # Group by (employee_id, employee_name, year, quarter)
        grouped = defaultdict(list)
        for tx in all_tx:
            key_name = tx.employee_id.name if tx.employee_id else (tx.salesman_raw or 'Unknown')
            grouped[(tx.employee_id.id or 0, key_name, tx.year, tx.quarter)].append(tx)

        # Kumpulkan semua periode yang relevan (tahun >= 2026)
        all_periods = set()
        for yr, mo in synced_months_set:
            if str(yr) >= '2026':
                q = 'Q1' if mo in ('01', '02', '03') else ('Q2' if mo in ('04', '05', '06') else ('Q3' if mo in ('07', '08', '09') else 'Q4'))
                all_periods.add((str(yr), q))
        for tx in all_tx:
            if tx.year and str(tx.year) >= '2026' and tx.quarter:
                all_periods.add((str(tx.year), tx.quarter))
        if not all_periods:
            all_periods = {('2026', 'Q1'), ('2026', 'Q2'), ('2026', 'Q3'), ('2026', 'Q4')}

        # Pastikan seluruh karyawan di roster memiliki entri (meski transaksi Rp 0)
        for yr, qtr in all_periods:
            for p in roster.values():
                k = (p['emp_id'], p['name'], yr, qtr)
                if k not in grouped:
                    grouped[k] = []

        # Sort kronologis untuk rollover grading_awal
        quarter_order = {'Q1': 1, 'Q2': 2, 'Q3': 3, 'Q4': 4}
        sorted_keys = sorted(grouped.keys(), key=lambda k: (k[1], k[2], quarter_order.get(k[3], 0)))

        last_grade_by_salesman = {}
        for emp_id, emp_name, yr, qtr in sorted_keys:
            emp_lower = (emp_name or '').strip().lower()
            is_inactive = (
                any(ex in emp_lower for ex in excluded_names) or
                (emp_id and emp_id not in active_emp_ids) or
                (not emp_id and emp_lower not in active_names)
            )
            if is_inactive:
                domain = [('year', '=', yr), ('quarter', '=', qtr)]
                if emp_id:
                    domain.append(('employee_id', '=', emp_id))
                else:
                    domain.append(('employee_name', '=ilike', emp_name))
                old_recs = Grading.search(domain + [('state', '!=', 'cancel')])
                if old_recs:
                    old_recs.write({'state': 'cancel'})
                continue

            txs = grouped[(emp_id, emp_name, yr, qtr)]
            months = QUARTER_MONTHS.get(qtr, ('01', '02', '03'))
            b1_sync = (yr, months[0]) in synced_months_set
            b2_sync = (yr, months[1]) in synced_months_set
            b3_sync = (yr, months[2]) in synced_months_set

            gp1 = sum(t.gross_profit for t in txs if t.month == months[0]) if txs else 0.0
            gp2 = sum(t.gross_profit for t in txs if t.month == months[1]) if txs else 0.0
            gp3 = sum(t.gross_profit for t in txs if t.month == months[2]) if txs else 0.0

            is_spv = (
                (emp_id and emp_id in spv_emp_ids) or
                any(spv_n in emp_lower for spv_n in ('satriyo wibowo', 'muhammad nashirudin'))
            )

            # Resolusi Tim dan Supervisor
            if txs:
                latest_tx = sorted(txs, key=lambda t: t.tx_date or fields.Datetime.now())[-1]
                team_id = latest_tx.team_id.id if latest_tx.team_id else False
                spv_id = latest_tx.supervisor_id.id if latest_tx.supervisor_id else False
            else:
                team_id = roster.get(emp_id, {}).get('team_id') or False
                spv_id = False
                if team_id:
                    team_obj = Team.browse(team_id)
                    if team_obj.exists() and team_obj.current_supervisor_id:
                        spv_id = team_obj.current_supervisor_id.id

            if is_spv:
                if 'satriyo' in emp_lower:
                    team_id = team_satriyo.id if team_satriyo else team_id
                    spv_id = active_spvs.filtered(lambda s: 'satriyo' in s.name.lower())[:1].id or spv_id
                elif 'nashir' in emp_lower:
                    team_id = team_nashir.id if team_nashir else team_id
                    spv_id = active_spvs.filtered(lambda s: 'nashir' in s.name.lower())[:1].id or spv_id

            if not spv_id and team_id:
                tm_obj = Team.browse(team_id)
                if tm_obj.exists() and tm_obj.current_supervisor_id:
                    spv_id = tm_obj.current_supervisor_id.id

            has_unmapped = any(not t.is_valid for t in txs) or (not emp_id) if txs else (not emp_id)
            if has_unmapped:
                validity = 'unmapped'
                v_note = _('Mapping karyawan/tim/supervisor belum lengkap')
            elif not (b1_sync and b2_sync and b3_sync):
                validity = 'incomplete'
                missing = [m for m, ok in zip(months, (b1_sync, b2_sync, b3_sync)) if not ok]
                v_note = _('Bulan %s belum tersinkronisasi') % ', '.join(missing)
            else:
                validity = 'valid'
                v_note = _('Data 3 bulan lengkap & valid')

            periode_label = format_periode_label(yr, qtr)
            domain = [('year', '=', yr), ('quarter', '=', qtr)]
            if emp_id:
                domain.append(('employee_id', '=', emp_id))
            else:
                domain.append(('employee_name', '=ilike', emp_name))

            sales_key = emp_id or emp_name.lower()
            if is_spv:
                prev_grade = 'supervisor'
            else:
                prev_grade = last_grade_by_salesman.get(sales_key, 'new')

            vals = {
                'employee_id': emp_id or False,
                'employee_name': emp_name,
                'team_id': team_id,
                'supervisor_id': spv_id,
                'year': yr,
                'quarter': qtr,
                'periode': periode_label,
                'grading_awal': prev_grade,
                'gp_bulan_1': gp1,
                'gp_bulan_2': gp2,
                'gp_bulan_3': gp3,
                'bulan_1_synced': b1_sync,
                'bulan_2_synced': b2_sync,
                'bulan_3_synced': b3_sync,
                'tx_count': len(txs),
                'gp_source': 'orimax',
                'data_validity': validity,
                'validity_note': v_note,
                'state': 'done' if validity == 'valid' else 'draft',
            }

            existing = Grading.search(domain, limit=1)
            if existing:
                if existing.state == 'done' and not force_recalc:
                    last_grade_by_salesman[sales_key] = existing.grading_terbaru
                    continue
                old_grade = existing.grading_terbaru
                existing.write(vals)
                if old_grade != existing.grading_terbaru or force_recalc:
                    History.create({
                        'record_type': 'salesman',
                        'grading_id': existing.id,
                        'employee_id': emp_id or False,
                        'employee_name': emp_name,
                        'year': yr,
                        'quarter': qtr,
                        'periode': periode_label,
                        'grade_before': old_grade,
                        'grade_after': existing.grading_terbaru,
                        'change_status': 'recalc' if force_recalc else existing.status_perubahan,
                        'change_reason': 'recalculation' if force_recalc else 'auto_eval',
                        'total_gp': existing.total_gp,
                        'avg_gp': existing.rata_rata_gp,
                        'pct_achievement': existing.persentase_pencapaian,
                        'notes': _('Update sinkronisasi GP ORIMAX'),
                    })
                last_grade_by_salesman[sales_key] = existing.grading_terbaru
            else:
                new_rec = Grading.create(vals)
                last_grade_by_salesman[sales_key] = new_rec.grading_terbaru


class SalesGradingSyncConfigWizard(models.TransientModel):
    _name = 'sales.grading.sync.config.wizard'
    _description = 'Konfigurasi & Sinkronisasi GP ORIMAX'

    gp_api_url = fields.Char(string='URL API GP ORIMAX', required=True, default='https://gp.orimax.co.id/?v=48f078437ab9')
    gp_api_role = fields.Selection([
        ('manager', 'Manajer (Dengan HPP)'),
        ('admin', 'Admin (Dengan HPP)'),
        ('user', 'User (Tanpa HPP Unit)'),
    ], string='Role Login API', required=True, default='manager')
    gp_api_password = fields.Char(string='Password API GP ORIMAX', help='Kosongkan jika tidak ingin mengubah password yang sudah tersimpan.')
    has_saved_password = fields.Boolean(string='Password Tersimpan', readonly=True)
    force_recalc = fields.Boolean(
        string='Kalkulasi Ulang Periode Terkunci (Audit Log)',
        default=False,
        help='Jika dicentang, periode yang sudah berstatus Disahkan (Done) akan dikalkulasi ulang dan dicatat di Audit Trail.'
    )
    last_sync_info = fields.Char(string='Status Sinkronisasi Terakhir', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ICP = self.env['ir.config_parameter'].sudo()
        res['gp_api_url'] = ICP.get_param('sales_grading.gp_api_url') or 'https://gp.orimax.co.id'
        res['gp_api_role'] = ICP.get_param('sales_grading.gp_api_role') or 'manager'
        res['has_saved_password'] = bool(ICP.get_param('sales_grading.gp_api_password'))
        summary = self.env['sales.grading.sync.log'].get_last_sync_summary()
        res['last_sync_info'] = f"{summary['last_status_label']} ({summary['last_success_date'] or '-'})"
        return res

    def action_save_config(self):
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('sales_grading.gp_api_url', (self.gp_api_url or '').strip().rstrip('/'))
        ICP.set_param('sales_grading.gp_api_role', self.gp_api_role or 'manager')
        if self.gp_api_password:
            ICP.set_param('sales_grading.gp_api_password', self.gp_api_password)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Konfigurasi Tersimpan'),
                'message': _('Konfigurasi sinkronisasi GP ORIMAX berhasil disimpan.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_save_and_sync(self):
        self.ensure_one()
        self.action_save_config()
        res = self.env['sales.grading.sync.log'].action_run_sync(force_recalc=self.force_recalc)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sinkronisasi GP ORIMAX Selesai'),
                'message': _(
                    'Diambil: %s baris | Baru: %s | Diperbarui: %s | Peringatan Mapping: %s'
                ) % (res['total_fetched'], res['created_count'], res['updated_count'], res['error_count']),
                'type': 'success' if res['status'] == 'success' else 'warning',
                'sticky': True,
            }
        }
