# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SalesGradingTeam(models.Model):
    _name = 'sales.grading.team'
    _description = 'Master Tim Sales Grading'
    _inherit = ['mail.thread']
    _order = 'name asc'

    name = fields.Char(string='Nama Tim Sales', required=True, tracking=True)
    code = fields.Char(string='Kode Tim', tracking=True)
    crm_team_id = fields.Many2one('crm.team', string='Odoo Sales Team', tracking=True)
    orimax_team_aliases = fields.Char(
        string='Alias Tim GP ORIMAX',
        help='Daftar nama tim di GP ORIMAX dipisahkan koma, contoh: Tim Satriyo, Telesales I'
    )
    active = fields.Boolean(string='Aktif', default=True, tracking=True)
    notes = fields.Text(string='Keterangan')

    assignment_ids = fields.One2many(
        'sales.grading.supervisor.assignment', 'team_id',
        string='Riwayat Penugasan Supervisor'
    )
    member_ids = fields.One2many(
        'sales.grading.team.member', 'team_id',
        string='Anggota Tim (Histori)'
    )
    current_supervisor_id = fields.Many2one(
        'sales.grading.supervisor',
        string='Supervisor Aktif',
        compute='_compute_current_supervisor'
    )
    assignment_status = fields.Selection([
        ('assigned', 'Ditugaskan'),
        ('unassigned', 'Belum Ditugaskan'),
        ('conflict', 'Konflik Penugasan'),
    ], string='Status Penugasan', compute='_compute_current_supervisor')
    assignment_status_label = fields.Char(
        string='Status Supervisor',
        compute='_compute_current_supervisor'
    )

    _sql_constraints = [
        ('unique_team_name', 'unique(name)', 'Nama Tim Sales harus unik!'),
    ]

    @api.depends('assignment_ids.status', 'assignment_ids.date_start', 'assignment_ids.date_end', 'assignment_ids.supervisor_id.active')
    def _compute_current_supervisor(self):
        today = fields.Date.context_today(self)
        for team in self:
            active_assigns = team.assignment_ids.filtered(
                lambda a: a.status == 'active'
                and a.supervisor_id.active
                and a.date_start <= today
                and (not a.date_end or a.date_end >= today)
            )
            if len(active_assigns) == 1:
                team.current_supervisor_id = active_assigns[0].supervisor_id
                team.assignment_status = 'assigned'
                team.assignment_status_label = active_assigns[0].supervisor_id.name
            elif len(active_assigns) > 1:
                team.current_supervisor_id = False
                team.assignment_status = 'conflict'
                names = ', '.join(active_assigns.mapped('supervisor_id.name'))
                team.assignment_status_label = _('Konflik (%s)') % names
            else:
                team.current_supervisor_id = False
                team.assignment_status = 'unassigned'
                team.assignment_status_label = _('Belum Ditugaskan')

    def resolve_supervisor_for_date(self, tx_date):
        """
        Mengembalikan (supervisor_record, status_code, issue_message) berdasarkan tanggal transaksi.
        Jika >1 supervisor aktif pada periode yang sama -> status 'conflict' dan supervisor = False.
        Jika 0 supervisor aktif -> status 'unassigned' dan supervisor = False.
        """
        self.ensure_one()
        if not tx_date:
            tx_date = fields.Date.context_today(self)
        if hasattr(tx_date, 'date'):
            tx_date = tx_date.date()
        matches = self.assignment_ids.filtered(
            lambda a: a.status in ('active', 'ended')
            and a.date_start <= tx_date
            and (not a.date_end or a.date_end >= tx_date)
        )
        if len(matches) == 1:
            return matches[0].supervisor_id, 'ok', ''
        elif len(matches) > 1:
            names = ', '.join(matches.mapped('supervisor_id.name'))
            return self.env['sales.grading.supervisor'], 'conflict', _(
                'Konflik penugasan pada tim %s tanggal %s (%s)'
            ) % (self.name, tx_date, names)
        return self.env['sales.grading.supervisor'], 'unassigned', _(
            'Tim %s Belum Ditugaskan pada tanggal %s'
        ) % (self.name, tx_date)

    @api.model
    def match_team_by_raw_name(self, team_raw):
        raw = (team_raw or '').strip()
        if not raw:
            return self.env['sales.grading.team']
        # Ignore numeric/percentage noise from old spreadsheets
        if '%' in raw or raw == '#N/A':
            return self.env['sales.grading.team']

        exact = self.search([('name', '=ilike', raw)], limit=1)
        if exact:
            return exact

        # Check aliases
        for team in self.search([('active', '=', True)]):
            aliases = [a.strip().lower() for a in (team.orimax_team_aliases or '').split(',') if a.strip()]
            if raw.lower() in aliases:
                return team
            if team.crm_team_id and team.crm_team_id.name.strip().lower() == raw.lower():
                return team
        return self.env['sales.grading.team']


class SalesGradingTeamMember(models.Model):
    _name = 'sales.grading.team.member'
    _description = 'Histori Anggota Salesman per Tim'
    _order = 'date_start desc, id desc'

    team_id = fields.Many2one('sales.grading.team', string='Tim Sales', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Salesman (Odoo Employee)', required=True)
    salesman_name = fields.Char(string='Nama Salesman', related='employee_id.name', store=True)
    date_start = fields.Date(string='Tanggal Mulai', required=True, default=fields.Date.context_today)
    date_end = fields.Date(string='Tanggal Berakhir')
    active = fields.Boolean(string='Aktif', default=True)
    notes = fields.Char(string='Keterangan')

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_end and rec.date_start and rec.date_end < rec.date_start:
                raise ValidationError(_('Tanggal Berakhir tidak boleh lebih awal dari Tanggal Mulai.'))


class SalesGradingMapping(models.Model):
    _name = 'sales.grading.mapping'
    _description = 'Mapping Nama Salesman GP ORIMAX ke Odoo Employees'
    _order = 'is_active desc, mapping_status desc, salesman_raw asc'

    salesman_raw = fields.Char(string='Nama Salesman (GP ORIMAX)', required=True, index=True)
    employee_id = fields.Many2one('hr.employee', string='Karyawan Odoo (hr.employee)', index=True)
    default_team_id = fields.Many2one('sales.grading.team', string='Tim Sales Default')
    is_active = fields.Boolean(
        string='Status Aktif',
        default=False,
        index=True,
        help='Jika Aktif, salesman akan dimunculkan di halaman Grading Sales. Jika Tidak Aktif, salesman disembunyikan.'
    )
    status_label = fields.Char(
        string='Status',
        compute='_compute_status_label',
        store=True
    )
    mapping_status = fields.Selection([
        ('mapped', 'Terpetakan'),
        ('missing', 'Karyawan Tidak Ditemukan'),
        ('ambiguous', 'Perlu Konfirmasi Admin (Ganda)'),
    ], string='Status Mapping', compute='_compute_status', store=True)
    notes = fields.Char(string='Catatan Mapping')

    _sql_constraints = [
        ('unique_salesman_raw', 'unique(salesman_raw)', 'Mapping nama salesman ORIMAX sudah ada!'),
    ]

    @api.depends('is_active')
    def _compute_status_label(self):
        for rec in self:
            rec.status_label = 'AKTIF' if rec.is_active else 'TIDAK AKTIF'

    @api.depends('employee_id', 'notes')
    def _compute_status(self):
        for rec in self:
            if rec.employee_id:
                rec.mapping_status = 'mapped'
            elif rec.notes and 'ganda' in rec.notes.lower():
                rec.mapping_status = 'ambiguous'
            else:
                rec.mapping_status = 'missing'

    def action_toggle_active(self):
        Grading = self.env['sales.grading.triwulan'].sudo()
        for rec in self:
            rec.is_active = not rec.is_active
            emp_ids = [rec.employee_id.id] if rec.employee_id else []
            name_candidates = [rec.salesman_raw, rec.employee_id.name] if rec.employee_id else [rec.salesman_raw]
            name_candidates = [n for n in name_candidates if n]

            domain = []
            if emp_ids and name_candidates:
                domain = ['|', ('employee_id', 'in', emp_ids), ('employee_name', 'in', name_candidates)]
            elif emp_ids:
                domain = [('employee_id', 'in', emp_ids)]
            elif name_candidates:
                domain = [('employee_name', 'in', name_candidates)]

            if domain:
                target_recs = Grading.search(domain + [('data_validity', '!=', 'demo')])
                if not rec.is_active:
                    target_recs.write({'state': 'cancel'})
                else:
                    for tr in target_recs:
                        tr.write({'state': 'done' if tr.is_valid_final else 'draft'})
        return True

    def action_set_active(self):
        for rec in self:
            if not rec.is_active:
                rec.action_toggle_active()
        return True

    def action_set_inactive(self):
        for rec in self:
            if rec.is_active:
                rec.action_toggle_active()
        return True

    @api.model
    def init_default_orimax_mappings(self):
        """
        Inisialisasi & sinkronisasi data mapping salesman GP ORIMAX ke hr.employee.
        Menjamin 12 salesman dari https://gp.orimax.co.id/?v=48f078437ab9 (termasuk nomor 10, 11, 12)
        terpetakan secara sempurna dengan Tim Sales Default masing-masing dan berstatus AKTIF.
        """
        Employee = self.env['hr.employee'].sudo().with_context(active_test=False)
        Team = self.env['sales.grading.team'].sudo()

        tim_satriyo = Team.search([('name', '=ilike', 'Tim Satriyo')], limit=1)
        tim_nashir = Team.search([('name', '=ilike', 'Tim Nashir')], limit=1)

        specs = [
            ('Ady Riyanto', 'ADY RIYANTO', tim_satriyo, 'Auto-match persis dengan hr.employee'),
            ('Ahmad Iran Pradita', 'AHMAD IRAN PRADITA', tim_satriyo, 'Auto-match persis dengan hr.employee'),
            ('Artha Widya Pratama Putra', 'ARTHA WIDYA PUTRA PRATAMA', tim_nashir, 'Auto-match urutan kata dengan hr.employee aktif'),
            ('Bachtiar Al Fariz', 'BACHTIAR AL FARIZ', tim_satriyo, 'Auto-match persis dengan hr.employee'),
            ('Fajar Shodiq', 'FAJAR SHODIQ', tim_satriyo, 'Auto-match persis dengan hr.employee'),
            ('Fajar Sidiq Mukhlisin', 'FAJAR SIDIQ MUKHLISIN', tim_nashir, 'Auto-match persis dengan hr.employee'),
            ('Hamdan Wahyudi', 'HAMDAN WAHYUDI', tim_satriyo, 'Auto-match persis dengan hr.employee'),
            ('Ishar Ady', 'ADY ISHARYANTO', tim_nashir, 'Auto-match potongan nama unik dengan hr.employee aktif'),
            ('Iza Zhulian', 'IKHZA ZHULIAN AZYHARI', tim_satriyo, 'Auto-match nama dengan hr.employee aktif'),
            ('Muhammad Nashirudin', 'MUHAMMAD NASHIRUDIN', tim_nashir, 'Auto-match persis dengan hr.employee'),
            ('Satriyo Wibowo', 'SATRIYO WIBOWO', tim_satriyo, 'Auto-match persis dengan hr.employee'),
            ('Sigit Andri Listiyanto', 'SIGIT ANDRI LISTIYANTO', tim_nashir, 'Auto-match persis dengan hr.employee'),
        ]

        active_raw_names = {s[0].strip().lower() for s in specs}
        for raw_name, emp_name, team, note in specs:
            emp = Employee.search([('name', '=ilike', emp_name)], limit=1)
            rec = self.search([('salesman_raw', '=ilike', raw_name)], limit=1)
            vals = {
                'salesman_raw': raw_name,
                'employee_id': emp.id if emp else False,
                'default_team_id': team.id if team else False,
                'notes': note,
                'is_active': True,
            }
            if rec:
                rec.write(vals)
            else:
                self.create(vals)

    @api.model
    def resolve_or_register(self, salesman_raw):
        """
        Mencocokkan nama salesman GP ORIMAX ke hr.employee TANPA membuat hr.employee baru.
        Mengembalikan (employee_record, mapping_record).
        """
        raw = (salesman_raw or '').strip()
        if not raw:
            return self.env['hr.employee'], self.env['sales.grading.mapping']

        existing = self.search([('salesman_raw', '=ilike', raw)], limit=1)
        if existing:
            return existing.employee_id, existing

        EmployeeActive = self.env['hr.employee']
        EmployeeAll = self.env['hr.employee'].with_context(active_test=False)

        specs_names = {
            'ady riyanto', 'ahmad iran pradita', 'artha widya pratama putra',
            'bachtiar al fariz', 'fajar shodiq', 'fajar sidiq mukhlisin',
            'hamdan wahyudi', 'ishar ady', 'iza zhulian', 'muhammad nashirudin',
            'satriyo wibowo', 'sigit andri listiyanto'
        }
        is_default_active = raw.lower() in specs_names

        # 1. Exact case-insensitive match pada karyawan AKTIF
        matches = EmployeeActive.search([('name', '=ilike', raw)])
        if len(matches) == 1:
            rec = self.create({
                'salesman_raw': raw,
                'employee_id': matches[0].id,
                'is_active': is_default_active,
                'notes': 'Auto-match persis dengan hr.employee aktif',
            })
            return matches[0], rec
        elif len(matches) > 1:
            rec = self.create({
                'salesman_raw': raw,
                'employee_id': False,
                'is_active': is_default_active,
                'notes': _('Ditemukan %s karyawan aktif ganda di hr.employee, harap pilih manual.') % len(matches),
            })
            return self.env['hr.employee'], rec

        # 2. Normalized token-set match pada karyawan AKTIF
        # (contoh: "Artha Widya Pratama Putra" vs "ARTHA WIDYA PUTRA PRATAMA")
        raw_tokens = sorted(raw.lower().split())
        all_active_emps = EmployeeActive.search([])
        if len(raw_tokens) >= 2:
            token_matches = all_active_emps.filtered(lambda e: sorted((e.name or '').lower().split()) == raw_tokens)
            if len(token_matches) == 1:
                rec = self.create({
                    'salesman_raw': raw,
                    'employee_id': token_matches[0].id,
                    'is_active': is_default_active,
                    'notes': 'Auto-match urutan kata dengan hr.employee aktif',
                })
                return token_matches[0], rec

        # 3. Token substring match unik pada karyawan AKTIF (contoh: "Ishar Ady" -> "ADY ISHARYANTO")
        raw_words = [w for w in raw.lower().split() if len(w) >= 3]
        if len(raw_words) >= 2:
            sub_matches = all_active_emps.filtered(
                lambda e: all(w in (e.name or '').lower() for w in raw_words)
            )
            if len(sub_matches) == 1:
                rec = self.create({
                    'salesman_raw': raw,
                    'employee_id': sub_matches[0].id,
                    'is_active': is_default_active,
                    'notes': 'Auto-match potongan nama unik dengan hr.employee aktif',
                })
                return sub_matches[0], rec

        # 4. Fallback ke karyawan arsip (nonaktif) untuk data historis lama
        archived_matches = EmployeeAll.search([('name', '=ilike', raw), ('active', '=', False)])
        if len(archived_matches) == 1:
            rec = self.create({
                'salesman_raw': raw,
                'employee_id': archived_matches[0].id,
                'is_active': False,
                'notes': 'Auto-match persis dengan hr.employee (arsip)',
            })
            return archived_matches[0], rec
        elif len(archived_matches) > 1:
            rec = self.create({
                'salesman_raw': raw,
                'employee_id': False,
                'is_active': False,
                'notes': _('Ditemukan %s karyawan ganda di hr.employee, harap pilih manual.') % len(archived_matches),
            })
            return self.env['hr.employee'], rec

        # Not found -> register missing without creating hr.employee
        rec = self.create({
            'salesman_raw': raw,
            'employee_id': False,
            'is_active': False,
            'notes': _('Tidak ditemukan di hr.employee, harap petakan oleh Administrator.'),
        })
        return self.env['hr.employee'], rec
