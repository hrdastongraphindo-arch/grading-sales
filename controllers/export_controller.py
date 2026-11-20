# -*- coding: utf-8 -*-
import io
import json
from datetime import datetime
import xlsxwriter

from odoo import http
from odoo.http import request
from ..models.grading_rules import format_idr, format_pct


class SalesGradingExportController(http.Controller):

    def _parse_filters(self, kwargs):
        filters = dict(kwargs or {})
        filters['_initialized'] = True
        return filters

    def _get_submenu_payload(self, submenu, filters):
        api_model = request.env['sales.grading.dashboard.api']
        if submenu in ('rekap_salesman', 'grading_sales', 'sales_grading_main'):
            return 'Rekap Grading Sales', api_model.get_rekap_salesman_data(filters)
        elif submenu == 'dashboard_salesman':
            return 'Dashboard Grading Salesman', api_model.get_dashboard_salesman_data(filters)
        elif submenu == 'ranking_salesman':
            return 'Rangking Salesman', api_model.get_ranking_salesman_data(filters)
        elif submenu == 'dashboard_supervisor':
            return 'Dashboard Supervisor & Tim', api_model.get_dashboard_supervisor_data(filters)
        return None, None

    @http.route('/sales_grading/export/xlsx/<string:submenu>', type='http', auth='user')
    def export_xlsx(self, submenu, **kwargs):
        filters = self._parse_filters(kwargs)
        title, data = self._get_submenu_payload(submenu, filters)
        if not data:
            return request.not_found()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = workbook.add_worksheet(title[:31])
        ws.set_landscape()
        ws.set_paper(9)  # A4

        # Formats
        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 14, 'font_color': '#0F172A', 'align': 'left', 'valign': 'vcenter'
        })
        subtitle_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'font_color': '#1E40AF', 'align': 'left'
        })
        meta_fmt = workbook.add_format({'font_size': 9, 'font_color': '#475569'})
        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#0F172A', 'font_color': '#FFFFFF',
            'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True, 'font_size': 10
        })
        text_fmt = workbook.add_format({'border': 1, 'valign': 'vcenter', 'font_size': 9.5})
        center_fmt = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'font_size': 9.5})
        money_fmt = workbook.add_format({
            'border': 1, 'valign': 'vcenter', 'align': 'right', 'num_format': '"Rp"#,##0', 'font_size': 9.5
        })
        pct_fmt = workbook.add_format({
            'border': 1, 'valign': 'vcenter', 'align': 'right', 'num_format': '0.00"%"', 'font_size': 9.5
        })

        now_str = datetime.now().strftime('%d/%m/%Y %H:%M')
        yr_val = filters.get('year')
        yr_label = '≥ 2026' if not yr_val or yr_val == 'ALL' else yr_val
        q_label = filters.get('quarter') or 'Semua Triwulan'

        ws.write(0, 0, f'PT ASTON GRAPHINDO INDONESIA — {title.upper()}', title_fmt)
        ws.write(1, 0, 'Sistem Grading Sales Triwulan & Evaluasi Supervisor', subtitle_fmt)
        ws.write(2, 0, f'Periode: {yr_label} / {q_label}   |   Tanggal Cetak: {now_str}   |   Dicetak oleh: {request.env.user.name}', meta_fmt)

        start_row = 4
        if submenu == 'dashboard_salesman':
            headers = [
                'No', 'Tahun', 'Triwulan', 'Nama Salesman', 'Tim', 'Grading Sekarang',
                'Potensi Grading TW Berikutnya', 'Target GP/Bln', 'Total GP 3 Bulan', 'Rata-rata GP/Bln',
                '% Pencapaian', 'Status Validitas'
            ]
            widths = [6, 8, 13, 24, 15, 16, 16, 17, 18, 18, 13, 18]
            rows = data.get('rows', [])
            for c, (h, w) in enumerate(zip(headers, widths)):
                ws.write(start_row, c, h, header_fmt)
                ws.set_column(c, c, w)
            for idx, r in enumerate(rows, start=start_row + 1):
                ws.write(idx, 0, r['no'], center_fmt)
                ws.write(idx, 1, r['year'], center_fmt)
                ws.write(idx, 2, r['quarter_label'], center_fmt)
                ws.write(idx, 3, r['employee_name'], text_fmt)
                ws.write(idx, 4, r['team_name'], text_fmt)
                ws.write(idx, 5, r['grading_awal_label'], center_fmt)
                ws.write(idx, 6, r['grading_terbaru_label'], center_fmt)
                ws.write(idx, 7, r['target_gp_bulanan'], money_fmt)
                ws.write(idx, 8, r['total_gp'], money_fmt)
                ws.write(idx, 9, r['rata_rata_gp'], money_fmt)
                ws.write(idx, 10, r['persentase_pencapaian'], pct_fmt)
                ws.write(idx, 11, 'Valid' if r['is_valid_final'] else (r['validity_note'] or 'Belum Valid'), text_fmt)

        elif submenu in ('rekap_salesman', 'grading_sales', 'sales_grading_main'):
            headers = [
                'No', 'Tahun', 'Triwulan', 'Nama Salesman', 'Tim', 'Grading Sekarang',
                'Potensi Grading TW Berikutnya', 'Total GP 3 Bulan', 'Rata-rata GP/Bln', 'Target GP/Bln',
                '% Pencapaian', 'Status Perubahan'
            ]
            widths = [6, 8, 13, 24, 15, 16, 16, 18, 18, 17, 13, 16]
            rows = data.get('rows', [])
            for c, (h, w) in enumerate(zip(headers, widths)):
                ws.write(start_row, c, h, header_fmt)
                ws.set_column(c, c, w)
            for idx, r in enumerate(rows, start=start_row + 1):
                ws.write(idx, 0, r['no'], center_fmt)
                ws.write(idx, 1, r['year'], center_fmt)
                ws.write(idx, 2, r['quarter_label'], center_fmt)
                ws.write(idx, 3, r['employee_name'], text_fmt)
                ws.write(idx, 4, r['team_name'], text_fmt)
                ws.write(idx, 5, r['grading_awal_label'], center_fmt)
                ws.write(idx, 6, r['grading_terbaru_label'], center_fmt)
                ws.write(idx, 7, r['total_gp'], money_fmt)
                ws.write(idx, 8, r['rata_rata_gp'], money_fmt)
                ws.write(idx, 9, r['target_gp_bulanan'], money_fmt)
                ws.write(idx, 10, r['persentase_pencapaian'], pct_fmt)
                ws.write(idx, 11, r['status_perubahan_label'], center_fmt)

        elif submenu == 'ranking_salesman':
            headers = [
                'Ranking', 'Tahun', 'Triwulan', 'Nama Salesman', 'Tim',
                'Total GP', 'Rata-rata GP/Bln', 'Target GP/Bln', '% Pencapaian', 'Grading'
            ]
            widths = [9, 8, 13, 25, 15, 19, 19, 18, 14, 16]
            rows = data.get('rows', [])
            for c, (h, w) in enumerate(zip(headers, widths)):
                ws.write(start_row, c, h, header_fmt)
                ws.set_column(c, c, w)
            for idx, r in enumerate(rows, start=start_row + 1):
                ws.write(idx, 0, r['no'], center_fmt)
                ws.write(idx, 1, r['year'], center_fmt)
                ws.write(idx, 2, r['quarter_label'], center_fmt)
                ws.write(idx, 3, r['employee_name'], text_fmt)
                ws.write(idx, 4, r['team_name'], text_fmt)
                ws.write(idx, 5, r['total_gp'], money_fmt)
                ws.write(idx, 6, r['rata_rata_gp'], money_fmt)
                ws.write(idx, 7, r['target_gp_bulanan'], money_fmt)
                ws.write(idx, 8, r['persentase_pencapaian'], pct_fmt)
                ws.write(idx, 9, r['grading_terbaru_label'], center_fmt)

        elif submenu == 'dashboard_supervisor':
            headers = [
                'No', 'Tahun', 'Triwulan', 'Nama Supervisor', 'Tim', 'Grade Supervisor',
                'Target GP Triwulan', 'Realisasi GP', '% Pencapaian',
                'Akumulasi GP 4 Triwulan', '% Tahunan', 'Potensi Grade Berikutnya', 'Status Evaluasi'
            ]
            widths = [6, 8, 12, 24, 18, 18, 19, 19, 13, 21, 13, 21, 20]
            rows = data.get('rows', [])
            for c, (h, w) in enumerate(zip(headers, widths)):
                ws.write(start_row, c, h, header_fmt)
                ws.set_column(c, c, w)
            for idx, r in enumerate(rows, start=start_row + 1):
                ws.write(idx, 0, r['no'], center_fmt)
                ws.write(idx, 1, r['year'], center_fmt)
                ws.write(idx, 2, r['quarter_label'], center_fmt)
                ws.write(idx, 3, r['supervisor_name'], text_fmt)
                ws.write(idx, 4, r['team_names'], text_fmt)
                ws.write(idx, 5, r['grade_label'], center_fmt)
                ws.write(idx, 6, r['target_gp_triwulan'], money_fmt)
                ws.write(idx, 7, r['realisasi_gp'], money_fmt)
                ws.write(idx, 8, r['persentase_triwulan'], pct_fmt)
                ws.write(idx, 9, r['akumulasi_gp_tahunan'], money_fmt)
                ws.write(idx, 10, r['persentase_tahunan'], pct_fmt)
                ws.write(idx, 11, r['potensi_grade_label'], center_fmt)
                ws.write(idx, 12, 'Final' if r['annual_complete'] else 'Sementara', center_fmt)

        workbook.close()
        output.seek(0)
        filename = f"{submenu}_{yr_label}_{q_label}.xlsx".replace(' ', '_')
        return request.make_response(
            output.read(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
            ]
        )

    @http.route('/sales_grading/report/<string:fmt>/<string:submenu>', type='http', auth='user')
    def export_qweb_report(self, fmt, submenu, **kwargs):
        if fmt not in ('pdf', 'html'):
            return request.not_found()
        filters = self._parse_filters(kwargs)
        title, data = self._get_submenu_payload(submenu, filters)
        if not data:
            return request.not_found()

        report_ref = 'sales_grading_triwulan.action_report_grading_submenu_pdf'
        if fmt == 'html':
            report_ref = 'sales_grading_triwulan.action_report_grading_submenu_html'

        report = request.env.ref(report_ref).sudo()
        yr_val = filters.get('year')
        render_ctx = {
            'submenu': submenu,
            'report_title': title,
            'data': data,
            'filters': filters,
            'year_label': '≥ 2026' if not yr_val or yr_val == 'ALL' else yr_val,
            'quarter_label': filters.get('quarter') or 'Semua Triwulan',
            'print_date': datetime.now().strftime('%d %B %Y %H:%M'),
            'printed_by': request.env.user.name,
            'company': request.env.company,
            'format_idr': format_idr,
            'format_pct': format_pct,
            'is_html_print': (fmt == 'html'),
        }

        company_id = request.env.company.id
        if fmt == 'pdf':
            pdf_bytes, _ = report._render_qweb_pdf(report.report_name, res_ids=[company_id], data=render_ctx)
            filename = f"{submenu}_{render_ctx['year_label']}_{render_ctx['quarter_label']}.pdf".replace(' ', '_')
            return request.make_response(
                pdf_bytes,
                headers=[
                    ('Content-Type', 'application/pdf'),
                    ('Content-Disposition', f'inline; filename="{filename}"'),
                ]
            )
        else:
            html_bytes, _ = report._render_qweb_html(report.report_name, [company_id], data=render_ctx)
            return request.make_response(
                html_bytes,
                headers=[('Content-Type', 'text/html; charset=utf-8')]
            )
