# -*- coding: utf-8 -*-
import re

GRADE_RANKS = {
    'new': 1,
    'junior': 2,
    'senior': 3,
    'executive': 4,
    'star': 5,
    'supervisor': 99,
}

GRADE_LABELS = {
    'supervisor': 'Supervisor',
    'new': 'New Sales',
    'junior': 'Junior Sales',
    'senior': 'Senior Sales',
    'executive': 'Executive Sales',
    'star': 'Star Sales',
}

# TABEL A: TARGET GP DAN TUNJANGAN SALESMAN (Bukan Penentu Grade)
TABEL_A_DATA = {
    'supervisor': {'target_gp': 200_000_000, 'gaji_pokok': 2_592_154, 'tunjangan': 0, 'label': 'Supervisor'},
    'star': {'target_gp': 100_000_000, 'gaji_pokok': 2_592_154, 'tunjangan': 2_250_000, 'label': 'Star Sales'},
    'executive': {'target_gp': 77_000_000, 'gaji_pokok': 2_592_154, 'tunjangan': 1_500_000, 'label': 'Executive Sales'},
    'senior': {'target_gp': 55_000_000, 'gaji_pokok': 2_592_154, 'tunjangan': 750_000, 'label': 'Senior Sales'},
    'junior': {'target_gp': 30_000_000, 'gaji_pokok': 2_592_154, 'tunjangan': 300_000, 'label': 'Junior Sales'},
    'new': {'target_gp': 15_000_000, 'gaji_pokok': 2_592_154, 'tunjangan': 0, 'label': 'New Sales'},
}

# SUPERVISOR GRADING & TARGETS (2 Grade Resmi: Supervisor & Senior Supervisor)
SUPERVISOR_GRADES = [
    ('supervisor', 'Supervisor'),
    ('senior_spv', 'Senior Supervisor'),
]

SUPERVISOR_GRADE_RANKS = {
    'supervisor': 1,
    'senior_spv': 2,
}

SUPERVISOR_GRADE_LABELS = dict(SUPERVISOR_GRADES)

SUPERVISOR_TARGETS = {
    'supervisor': {
        'label': 'Supervisor',
        'monthly': 200_000_000.0,
        'quarterly': 600_000_000.0,
        'annual': 2_400_000_000.0,
        'sales_min': 6,
        'sales_max': 8,
        'team_composition': '6 - 8 Sales + 1 Supervisor',
        'promotion_rule': 'Promosi ke Senior Supervisor jika rata-rata 3 triwulan >= 100%',
    },
    'senior_spv': {
        'label': 'Senior Supervisor',
        'monthly': 300_000_000.0,
        'quarterly': 900_000_000.0,
        'annual': 3_600_000_000.0,
        'sales_min': 9,
        'sales_max': 11,
        'team_composition': '9 - 11 Sales + 1 Supervisor',
        'demotion_rule': 'Turun ke Supervisor jika pencapaian target di bawah 70% selama 3 triwulan',
    },
}

QUARTER_SELECTION = [
    ('Q1', 'Triwulan I (Jan - Mar)'),
    ('Q2', 'Triwulan II (Apr - Jun)'),
    ('Q3', 'Triwulan III (Jul - Sep)'),
    ('Q4', 'Triwulan IV (Okt - Des)'),
]

QUARTER_SHORT_LABELS = {
    'Q1': 'Triwulan I',
    'Q2': 'Triwulan II',
    'Q3': 'Triwulan III',
    'Q4': 'Triwulan IV',
}

QUARTER_MONTHS = {
    'Q1': ('01', '02', '03'),
    'Q2': ('04', '05', '06'),
    'Q3': ('07', '08', '09'),
    'Q4': ('10', '11', '12'),
}

MONTH_TO_QUARTER = {
    '01': 'Q1', '02': 'Q1', '03': 'Q1',
    '04': 'Q2', '05': 'Q2', '06': 'Q2',
    '07': 'Q3', '08': 'Q3', '09': 'Q3',
    '10': 'Q4', '11': 'Q4', '12': 'Q4',
}

MONTH_NAMES_ID = {
    '01': 'Januari', '02': 'Februari', '03': 'Maret',
    '04': 'April', '05': 'Mei', '06': 'Juni',
    '07': 'Juli', '08': 'Agustus', '09': 'September',
    '10': 'Oktober', '11': 'November', '12': 'Desember',
}


def tentukan_grade_tabel_b(rata_rata_gp, env=None):
    """
    TABEL B: SATU-SATUNYA ACUAN RESMI PENENTUAN GRADE SALESMAN
    Jika env diberikan, mengambil batas acuan dinamis dari sales.grading.rules.config.
    Jika tidak, fallback ke standar:
    Star Sales      : >= Rp77.000.000
    Executive Sales : >= Rp55.000.000 s/d < Rp77.000.000
    Senior Sales    : >= Rp30.000.000 s/d < Rp55.000.000
    Junior Sales    : >= Rp15.000.000 s/d < Rp30.000.000
    New Sales       : < Rp15.000.000
    """
    val = float(rata_rata_gp or 0.0)
    if env:
        try:
            cfg = env['sales.grading.rules.config'].sudo().get_active_config()
            for r in cfg.salesman_rule_ids:
                if val >= r.min_avg_gp_monthly:
                    return r.grade
            return 'new'
        except Exception:
            pass

    if val >= 77_000_000:
        return 'star'
    elif val >= 55_000_000:
        return 'executive'
    elif val >= 30_000_000:
        return 'senior'
    elif val >= 15_000_000:
        return 'junior'
    return 'new'


def evaluate_supervisor_annual(current_grade, pct_avg_3tw, count_below_70=0, env=None):
    """
    Aturan Evaluasi Grading Supervisor (2 Grade Resmi):
    1. Supervisor (Target Rp200 Jt/bln, Tim 6-8 Sales + 1 Spv):
       - Promosi ke Senior Supervisor jika rata-rata pencapaian 3 triwulan >= 100%
       - Jika < 100% : Tetap Supervisor (tidak ada grade di bawah Supervisor)
    2. Senior Supervisor (Target Rp300 Jt/bln, Tim 9-11 Sales + 1 Spv):
       - Turun Grade ke Supervisor jika pencapaian target di bawah 70% selama 3 triwulan
       - Jika >= 70% : Tetap Senior Supervisor (grade tertinggi)
    Returns tuple (next_grade, decision_key) where decision_key in ('naik', 'tetap', 'turun')
    """
    if current_grade not in ('supervisor', 'senior_spv'):
        current_grade = 'supervisor'
    pct = float(pct_avg_3tw or 0.0)

    promo_thresh = 100.0
    demo_thresh = 70.0
    if env:
        try:
            cfg = env['sales.grading.rules.config'].sudo().get_active_config()
            spv_dict = {r.grade: r for r in cfg.supervisor_rule_ids}
            if 'supervisor' in spv_dict:
                promo_thresh = spv_dict['supervisor'].eval_threshold_pct
            if 'senior_spv' in spv_dict:
                demo_thresh = spv_dict['senior_spv'].eval_threshold_pct
        except Exception:
            pass

    if current_grade == 'supervisor':
        if pct >= promo_thresh:
            return 'senior_spv', 'naik'
        return 'supervisor', 'tetap'
    elif current_grade == 'senior_spv':
        if pct < demo_thresh or count_below_70 >= 3:
            return 'supervisor', 'turun'
        return 'senior_spv', 'tetap'
    return current_grade, 'tetap'


def format_periode_label(year, quarter):
    labels = {
        'Q1': f'Triwulan I (Jan - Mar {year})',
        'Q2': f'Triwulan II (Apr - Jun {year})',
        'Q3': f'Triwulan III (Jul - Sep {year})',
        'Q4': f'Triwulan IV (Okt - Des {year})',
    }
    return labels.get(quarter, f'{quarter} {year}')


def parse_periode_year_quarter(periode_str):
    """Best-effort parse of legacy periode strings into (year_str, quarter_key)."""
    s = (periode_str or '').strip()
    year_match = re.search(r'(20\d{2})', s)
    year = year_match.group(1) if year_match else False
    s_up = s.upper()
    quarter = False
    if 'TRIWULAN IV' in s_up or 'Q4' in s_up or 'OKT' in s_up or 'DES' in s_up:
        quarter = 'Q4'
    elif 'TRIWULAN III' in s_up or 'Q3' in s_up or 'JUL' in s_up or 'SEP' in s_up:
        quarter = 'Q3'
    elif 'TRIWULAN II' in s_up or 'Q2' in s_up or 'APR' in s_up or 'JUN' in s_up:
        quarter = 'Q2'
    elif 'TRIWULAN I' in s_up or 'Q1' in s_up or 'JAN' in s_up or 'MAR' in s_up:
        quarter = 'Q1'
    return year, quarter


def normalize_quarter_from_orimax(triwulan_str, month_str):
    mo = str(month_str or '').zfill(2)
    if mo in MONTH_TO_QUARTER:
        return MONTH_TO_QUARTER[mo]
    tw = (triwulan_str or '').upper().strip()
    if tw.endswith('IV') or 'Q4' in tw:
        return 'Q4'
    if tw.endswith('III') or 'Q3' in tw:
        return 'Q3'
    if tw.endswith('II') or 'Q2' in tw:
        return 'Q2'
    if tw.endswith('I') or 'Q1' in tw:
        return 'Q1'
    return 'Q1'


def format_idr(amount):
    val = float(amount or 0.0)
    sign = '-' if val < 0 else ''
    formatted = f"{abs(round(val)):,.0f}".replace(',', '.')
    return f"{sign}Rp{formatted}"


def format_pct(value):
    val = float(value or 0.0)
    return f"{val:,.2f}%".replace(',', 'X').replace('.', ',').replace('X', '.')
