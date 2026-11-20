# -*- coding: utf-8 -*-
import logging
from datetime import date
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from .grading_rules import SUPERVISOR_GRADES, SUPERVISOR_TARGETS

_logger = logging.getLogger(__name__)


class SalesGradingSupervisor(models.Model):
    _name = 'sales.grading.supervisor'
    _description = 'Master Data Supervisor Sales'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'active desc, name asc'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Karyawan Supervisor (HR)',
        required=True,
        tracking=True,
        help='Pilih karyawan dari menu Employees Odoo (hr.employee).'
    )
    name = fields.Char(
        string='Nama Supervisor',
        related='employee_id.name',
        store=True,
        readonly=True
    )
    user_id = fields.Many2one(
        'res.users',
        string='Akun User Odoo',
        compute='_compute_user_id',
        store=True,
        readonly=False,
        tracking=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Mata Uang',
        default=lambda self: self.env.ref('base.IDR', raise_if_not_found=False) or self.env.company.currency_id
    )
    grade = fields.Selection(
        SUPERVISOR_GRADES,
        string='Jabatan / Grade',
        required=True,
        default='supervisor',
        tracking=True
    )
    primary_team_id = fields.Many2one(
        'sales.grading.team',
        string='Tim Sales Utama',
        tracking=True,
        help='Pilih Tim Sales yang menjadi tanggung jawab Supervisor ini.'
    )
    team_ids = fields.Many2many(
        'sales.grading.team',
        string='Tim Sales Aktif',
        compute='_compute_active_teams',
        compute_sudo=True
    )
    team_display = fields.Char(
        string='Tim Sales',
        compute='_compute_active_teams',
        store=True
    )
    allow_multi_team = fields.Boolean(
        string='Izinkan Multi-Tim',
        default=True,
        help='Jika aktif, Supervisor dapat menangani lebih dari satu tim.'
    )
    date_start = fields.Date(
        string='Tanggal Mulai',
        required=True,
        default=fields.Date.context_today,
        tracking=True
    )
    date_end = fields.Date(
        string='Tanggal Berakhir',
        tracking=True,
        help='Boleh kosong jika penugasan masih aktif.'
    )
    active = fields.Boolean(string='Aktif', default=True, tracking=True)
    status = fields.Selection([
        ('active', 'Aktif'),
        ('inactive', 'Tidak Aktif'),
    ], string='Status', default='active', required=True, tracking=True)
    notes = fields.Text(string='Keterangan')

    # Target sesuai Grade Supervisor
    target_gp_bulanan = fields.Monetary(
        string='Target GP / Bulan',
        currency_field='currency_id',
        compute='_compute_targets',
        store=True
    )
    target_gp_triwulan = fields.Monetary(
        string='Target GP / Triwulan',
        currency_field='currency_id',
        compute='_compute_targets',
        store=True
    )
    target_gp_tahunan = fields.Monetary(
        string='Target GP / Tahun',
        currency_field='currency_id',
        compute='_compute_targets',
        store=True
    )
    sales_min = fields.Integer(
        string='Min Sales',
        compute='_compute_targets',
        store=True
    )
    sales_max = fields.Integer(
        string='Max Sales',
        compute='_compute_targets',
        store=True
    )
    team_composition_desc = fields.Char(
        string='Komposisi Tim Ideal',
        compute='_compute_targets',
        store=True
    )

    assignment_ids = fields.One2many(
        'sales.grading.supervisor.assignment',
        'supervisor_id',
        string='Riwayat Penugasan Tim'
    )
    assignment_count = fields.Integer(
        string='Jumlah Penugasan',
        compute='_compute_counts'
    )
    eval_ids = fields.One2many(
        'sales.grading.supervisor.eval',
        'supervisor_id',
        string='Evaluasi Kinerja Supervisor'
    )
    grade_history_ids = fields.One2many(
        'sales.grading.history',
        'supervisor_id',
        string='Riwayat Perubahan Grade'
    )

    @api.depends('employee_id', 'employee_id.user_id')
    def _compute_user_id(self):
        Users = self.env['res.users'].with_context(active_test=False)
        for rec in self:
            if rec.user_id:
                continue
            if rec.employee_id and rec.employee_id.user_id:
                rec.user_id = rec.employee_id.user_id
            elif rec.employee_id and rec.employee_id.name:
                matched_user = Users.search([('partner_id.name', '=ilike', rec.employee_id.name)], limit=1)
                rec.user_id = matched_user or False

    @api.depends('grade')
    def _compute_targets(self):
        for rec in self:
            t = None
            if rec.env:
                try:
                    cfg = rec.env['sales.grading.rules.config'].sudo().get_active_config()
                    r = cfg.supervisor_rule_ids.filtered(lambda x: x.grade == rec.grade)
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
                t = SUPERVISOR_TARGETS.get(rec.grade, SUPERVISOR_TARGETS['supervisor'])
            rec.target_gp_bulanan = t['monthly']
            rec.target_gp_triwulan = t['quarterly']
            rec.target_gp_tahunan = t['annual']
            rec.sales_min = t.get('sales_min', 6)
            rec.sales_max = t.get('sales_max', 8)
            rec.team_composition_desc = t.get('team_composition', '6 - 8 Sales + 1 Supervisor')

    @api.depends('assignment_ids', 'assignment_ids.status', 'assignment_ids.team_id',
                 'assignment_ids.date_start', 'assignment_ids.date_end', 'primary_team_id', 'active')
    def _compute_active_teams(self):
        today = fields.Date.context_today(self)
        for rec in self:
            active_assigns = rec.assignment_ids.filtered(
                lambda a: a.status == 'active'
                and a.date_start <= today
                and (not a.date_end or a.date_end >= today)
            )
            teams = active_assigns.mapped('team_id')
            if not teams and rec.primary_team_id and rec.active:
                teams = rec.primary_team_id
            rec.team_ids = teams
            rec.team_display = ', '.join(teams.mapped('name')) if teams else _('Belum Ditugaskan')

    def _compute_counts(self):
        for rec in self:
            rec.assignment_count = len(rec.assignment_ids)

    @api.onchange('status')
    def _onchange_status(self):
        for rec in self:
            rec.active = (rec.status == 'active')

    @api.onchange('active')
    def _onchange_active(self):
        for rec in self:
            rec.status = 'active' if rec.active else 'inactive'

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_end and rec.date_start and rec.date_end < rec.date_start:
                raise ValidationError(_('Tanggal Berakhir tidak boleh lebih awal dari Tanggal Mulai.'))

    @api.constrains('employee_id', 'date_start', 'date_end', 'status', 'active')
    def _check_no_duplicate_active_employee(self):
        for rec in self:
            if not rec.active or rec.status != 'active' or not rec.employee_id:
                continue
            others = self.search([
                ('id', '!=', rec.id),
                ('employee_id', '=', rec.employee_id.id),
                ('active', '=', True),
                ('status', '=', 'active'),
            ])
            for other in others:
                # Overlap check between [rec.date_start, rec.date_end] and [other.date_start, other.date_end]
                r_end = rec.date_end or date(9999, 12, 31)
                o_end = other.date_end or date(9999, 12, 31)
                if rec.date_start <= o_end and other.date_start <= r_end:
                    raise ValidationError(_(
                        'Duplikasi Supervisor ditolak: Karyawan %s sudah terdaftar sebagai Supervisor aktif pada periode yang bertumpuk (%s s/d %s).'
                    ) % (rec.employee_id.name, other.date_start, other.date_end or 'Aktif'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'status' in vals and 'active' not in vals:
                vals['active'] = (vals['status'] == 'active')
            elif 'active' in vals and 'status' not in vals:
                vals['status'] = 'active' if vals['active'] else 'inactive'
        records = super().create(vals_list)
        for rec in records:
            if rec.primary_team_id and not rec.assignment_ids.filtered(lambda a: a.team_id == rec.primary_team_id and a.status == 'active'):
                self.env['sales.grading.supervisor.assignment'].create({
                    'supervisor_id': rec.id,
                    'team_id': rec.primary_team_id.id,
                    'grade_at_assignment': rec.grade,
                    'date_start': rec.date_start,
                    'date_end': rec.date_end,
                    'status': 'active' if rec.active else 'inactive',
                    'notes': rec.notes or 'Penugasan awal Supervisor',
                })
        return records

    def write(self, vals):
        if 'status' in vals and 'active' not in vals:
            vals['active'] = (vals['status'] == 'active')
        elif 'active' in vals and 'status' not in vals:
            vals['status'] = 'active' if vals['active'] else 'inactive'

        old_grades = {rec.id: rec.grade for rec in self}
        res = super().write(vals)

        # Log grade change if grade modified manually
        if 'grade' in vals:
            History = self.env['sales.grading.history']
            for rec in self:
                if old_grades.get(rec.id) != rec.grade:
                    History.create({
                        'record_type': 'supervisor',
                        'supervisor_id': rec.id,
                        'employee_id': rec.employee_id.id,
                        'grade_before': old_grades.get(rec.id),
                        'grade_after': rec.grade,
                        'change_status': 'manual',
                        'change_reason': 'manual_correction',
                        'notes': _('Perubahan grade Supervisor pada Master Data'),
                    })

        # If primary_team_id updated directly, ensure assignment history reflects it without overwriting past assignments
        if 'primary_team_id' in vals and vals.get('primary_team_id'):
            Assignment = self.env['sales.grading.supervisor.assignment']
            today = fields.Date.context_today(self)
            for rec in self:
                existing_active = rec.assignment_ids.filtered(
                    lambda a: a.team_id.id == vals['primary_team_id'] and a.status == 'active'
                )
                if not existing_active:
                    Assignment.create({
                        'supervisor_id': rec.id,
                        'team_id': vals['primary_team_id'],
                        'grade_at_assignment': rec.grade,
                        'date_start': today if rec.date_start < today else rec.date_start,
                        'date_end': rec.date_end,
                        'status': 'active' if rec.active else 'inactive',
                        'notes': 'Penambahan/perubahan tim dari form Supervisor',
                    })
        return res

    def action_deactivate_supervisor(self):
        """Nonaktifkan Supervisor tanpa menghapus data atau histori penugasan."""
        today = fields.Date.context_today(self)
        for rec in self:
            rec.write({
                'active': False,
                'status': 'inactive',
                'date_end': rec.date_end or today,
            })
            for assign in rec.assignment_ids.filtered(lambda a: a.status == 'active'):
                assign.write({
                    'status': 'ended',
                    'date_end': assign.date_end or today,
                })
        return True

    def action_activate_supervisor(self):
        for rec in self:
            rec.write({
                'active': True,
                'status': 'active',
                'date_end': False,
            })
        return True

    def action_view_assignments(self):
        self.ensure_one()
        return {
            'name': _('Riwayat Penugasan: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'sales.grading.supervisor.assignment',
            'view_mode': 'tree,form',
            'domain': [('supervisor_id', '=', self.id)],
            'context': {
                'default_supervisor_id': self.id,
                'default_grade_at_assignment': self.grade,
            },
        }

    def unlink(self):
        raise UserError(_(
            'Supervisor tidak boleh dihapus agar histori penugasan dan evaluasi tetap terjaga. '
            'Gunakan tombol "Nonaktifkan Supervisor".'
        ))

    @api.model
    def _match_employee_by_name(self, target_name):
        """
        Mencocokkan nama supervisor terhadap hr.employee TANPA membuat record baru.
        Memprioritaskan karyawan aktif agar arsip lama tidak dianggap ganda.
        Returns (employee_or_False, warning_msg_or_Empty).
        """
        EmployeeActive = self.env['hr.employee']
        EmployeeAll = self.env['hr.employee'].with_context(active_test=False)
        name_clean = target_name.strip()

        for model_env in (EmployeeActive, EmployeeAll):
            exact = model_env.search([('name', '=ilike', name_clean)])
            if len(exact) == 1:
                return exact[0], ''
            if len(exact) > 1:
                return False, _('Ditemukan %s karyawan dengan nama "%s" di Employees Odoo. Harap tentukan manual.') % (
                    len(exact), target_name
                )
            partial = model_env.search([('name', 'ilike', name_clean)])
            if len(partial) == 1:
                return partial[0], ''
            if len(partial) > 1:
                return False, _('Ditemukan beberapa karyawan mirip "%s" (%s). Harap tentukan manual.') % (
                    target_name, ', '.join(partial.mapped('name'))
                )
        return False, _('Karyawan "%s" belum ditemukan di menu Employees Odoo (hr.employee). Harap periksa data karyawan.') % target_name

    @api.model
    def _init_default_supervisors_and_teams(self):
        """
        Inisialisasi idempoten data awal:
        - Tim Sales: Tim Satriyo (alias Telesales I), Tim Nashir (alias Telesales II)
        - Supervisor Awal: Satriyo Wibowo & Muhammad Nashirudin (dicocokkan dengan hr.employee)
        Tidak akan menimpa data jika sudah dikonfigurasi Administrator.
        """
        Team = self.env['sales.grading.team'].with_context(active_test=False)
        CrmTeam = self.env['crm.team'].with_context(active_test=False)

        telesales_1 = CrmTeam.search([('name', '=ilike', 'Telesales I')], limit=1)
        telesales_2 = CrmTeam.search([('name', '=ilike', 'Telesales II')], limit=1)

        tim_satriyo = Team.search([('name', '=ilike', 'Tim Satriyo')], limit=1)
        if not tim_satriyo:
            tim_satriyo = Team.create({
                'name': 'Tim Satriyo',
                'code': 'TIM-SATRIYO',
                'crm_team_id': telesales_1.id if telesales_1 else False,
                'orimax_team_aliases': 'Tim Satriyo, Telesales I',
            })

        tim_nashir = Team.search([('name', '=ilike', 'Tim Nashir')], limit=1)
        if not tim_nashir:
            tim_nashir = Team.create({
                'name': 'Tim Nashir',
                'code': 'TIM-NASHIR',
                'crm_team_id': telesales_2.id if telesales_2 else False,
                'orimax_team_aliases': 'Tim Nashir, Telesales II',
            })

        # Tim aktual lainnya di GP ORIMAX (tanpa Supervisor -> tampil "Belum Ditugaskan")
        for extra_name, extra_code in (('Tim Anwas', 'TIM-ANWAS'), ('Tim Sales', 'TIM-SALES'), ('AGI', 'TIM-AGI')):
            if not Team.search([('name', '=ilike', extra_name)], limit=1):
                Team.create({
                    'name': extra_name,
                    'code': extra_code,
                    'orimax_team_aliases': extra_name,
                })

        initial_specs = [
            ('Satriyo Wibowo', tim_satriyo, 'supervisor'),
            ('Muhammad Nashirudin', tim_nashir, 'supervisor'),
        ]
        warnings = []
        for spv_name, team, grade in initial_specs:
            emp, warn = self._match_employee_by_name(spv_name)
            if not emp:
                _logger.warning('Grading Sales Init Supervisor: %s', warn)
                warnings.append(warn)
                continue
            existing = self.with_context(active_test=False).search([('employee_id', '=', emp.id)], limit=1)
            if not existing:
                self.create({
                    'employee_id': emp.id,
                    'grade': grade,
                    'primary_team_id': team.id,
                    'date_start': date(2024, 1, 1),
                    'status': 'active',
                    'active': True,
                    'notes': 'Supervisor (tidak diikutkan dalam Grading Salesman)',
                })
        return warnings


class SalesGradingSupervisorAssignment(models.Model):
    _name = 'sales.grading.supervisor.assignment'
    _description = 'Histori Penugasan Supervisor ke Tim Sales'
    _order = 'date_start desc, id desc'

    supervisor_id = fields.Many2one(
        'sales.grading.supervisor',
        string='Supervisor',
        required=True,
        ondelete='restrict',
        index=True
    )
    team_id = fields.Many2one(
        'sales.grading.team',
        string='Tim yang Ditangani',
        required=True,
        ondelete='restrict',
        index=True
    )
    grade_at_assignment = fields.Selection(
        SUPERVISOR_GRADES,
        string='Grade Saat Penugasan',
        required=True,
        default='supervisor'
    )
    date_start = fields.Date(
        string='Tanggal Mulai Penugasan',
        required=True,
        default=fields.Date.context_today
    )
    date_end = fields.Date(string='Tanggal Berakhir')
    status = fields.Selection([
        ('active', 'Aktif'),
        ('ended', 'Selesai'),
        ('inactive', 'Tidak Aktif'),
    ], string='Status Penugasan', default='active', required=True)
    member_snapshot = fields.Text(
        string='Anggota Salesman pada Penugasan',
        compute='_compute_member_snapshot'
    )
    notes = fields.Char(string='Keterangan')

    @api.depends('team_id', 'date_start', 'date_end')
    def _compute_member_snapshot(self):
        Tx = self.env['sales.grading.gp.transaction']
        for rec in self:
            if not rec.team_id:
                rec.member_snapshot = ''
                continue
            members = rec.team_id.member_ids.filtered(
                lambda m: m.date_start <= (rec.date_end or date(9999, 12, 31))
                and (not m.date_end or m.date_end >= rec.date_start)
            ).mapped('salesman_name')
            if not members:
                domain = [('team_id', '=', rec.team_id.id)]
                if rec.date_start:
                    domain.append(('tx_date', '>=', rec.date_start))
                if rec.date_end:
                    domain.append(('tx_date', '<=', rec.date_end))
                txs = Tx.search(domain)
                members = sorted(set(txs.mapped('salesman_raw')) - {False, ''})
            rec.member_snapshot = ', '.join(sorted(set(members))) if members else '-'

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_end and rec.date_start and rec.date_end < rec.date_start:
                raise ValidationError(_('Tanggal Berakhir tidak boleh lebih awal dari Tanggal Mulai.'))

    @api.constrains('team_id', 'supervisor_id', 'date_start', 'date_end', 'status')
    def _check_no_conflict_team(self):
        for rec in self:
            if rec.status != 'active':
                continue
            # Check multi-team permission on supervisor
            if rec.supervisor_id and not rec.supervisor_id.allow_multi_team:
                other_teams = self.search([
                    ('id', '!=', rec.id),
                    ('supervisor_id', '=', rec.supervisor_id.id),
                    ('status', '=', 'active'),
                    ('team_id', '!=', rec.team_id.id),
                ])
                r_end = rec.date_end or date(9999, 12, 31)
                for ot in other_teams:
                    o_end = ot.date_end or date(9999, 12, 31)
                    if rec.date_start <= o_end and ot.date_start <= r_end:
                        raise ValidationError(_(
                            'Supervisor %s tidak diizinkan menangani lebih dari satu tim secara bersamaan.'
                        ) % rec.supervisor_id.name)

            # Check conflict: same team cannot have >1 active supervisor on overlapping period
            others = self.search([
                ('id', '!=', rec.id),
                ('team_id', '=', rec.team_id.id),
                ('status', '=', 'active'),
            ])
            r_end = rec.date_end or date(9999, 12, 31)
            for other in others:
                o_end = other.date_end or date(9999, 12, 31)
                if rec.date_start <= o_end and other.date_start <= r_end:
                    raise ValidationError(_(
                        'Konflik Penugasan Tim %s: Sudah ditugaskan ke %s pada periode %s s/d %s. '
                        'Akhiri penugasan sebelumnya terlebih dahulu agar histori tetap konsisten.'
                    ) % (rec.team_id.name, other.supervisor_id.name, other.date_start, other.date_end or 'Aktif'))

    def action_end_assignment(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.write({
                'status': 'ended',
                'date_end': rec.date_end or today,
            })
        return True
