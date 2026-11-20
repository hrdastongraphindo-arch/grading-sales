/** @odoo-module **/

import { Component, onWillStart, onMounted, onPatched, onWillUnmount, useState, useRef } from "@odoo/owl";
import { loadJS } from "@web/core/assets";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { SalesmanDetailModal } from "./salesman_detail_modal";
import {
    SG_COLORS,
    getCurrentPeriod,
    formatIDR,
    formatPct,
    gradeBadgeClass,
    statusBadgeClass,
    progressClass,
    buildExportUrl,
    renderBarChart,
} from "./dashboard_shared";

export class SalesGradingMain extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.refChartTop10 = useRef("chartTop10");
        this.refChartTeams = useRef("chartTeams");
        this.refChartAch = useRef("chartAch");
        this.charts = {};

        const cur = getCurrentPeriod();

        this.state = useState({
            activeTab: "rekap", // 'rekap' | 'ranking'
            loading: true,
            syncing: false,
            dataRekap: null,
            dataRanking: null,
            detail: null,
            filters: {
                year: cur.year,
                quarter: cur.quarter,
                team_id: "ALL",
                employee_name: "ALL",
                grading_awal: "ALL",
                grading_terbaru: "ALL",
                status_perubahan: "ALL",
                search: "",
                sort_by: "total_gp",
                sort_dir: "desc",
                pageSize: 10,
                pageIndex: 1,
                _initialized: true,
            },
        });

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this.fetchData();
        });

        onMounted(() => this.drawRankingCharts());
        onPatched(() => this.drawRankingCharts());
        onWillUnmount(() => {
            Object.values(this.charts).forEach((c) => c && c.destroy());
        });
    }

    get currentData() {
        return this.state.activeTab === "rekap" ? this.state.dataRekap : this.state.dataRanking;
    }

    get paginatedRekapRows() {
        const d = this.state.dataRekap;
        if (!d || !d.rows) return [];
        let rows = d.rows;
        if (this.state.filters.search) {
            const q = this.state.filters.search.toLowerCase();
            rows = rows.filter(
                (r) =>
                    (r.employee_name && r.employee_name.toLowerCase().includes(q)) ||
                    (r.team_name && r.team_name.toLowerCase().includes(q))
            );
        }
        const start = (this.state.filters.pageIndex - 1) * this.state.filters.pageSize;
        return rows.slice(start, start + this.state.filters.pageSize);
    }

    get totalRekapRows() {
        const d = this.state.dataRekap;
        if (!d || !d.rows) return 0;
        if (this.state.filters.search) {
            const q = this.state.filters.search.toLowerCase();
            return d.rows.filter(
                (r) =>
                    (r.employee_name && r.employee_name.toLowerCase().includes(q)) ||
                    (r.team_name && r.team_name.toLowerCase().includes(q))
            ).length;
        }
        return d.rows.length;
    }

    get totalPages() {
        return Math.max(1, Math.ceil(this.totalRekapRows / this.state.filters.pageSize));
    }

    async switchTab(tab) {
        if (this.state.activeTab === tab) return;
        this.state.activeTab = tab;
        await this.fetchData();
    }

    async fetchData() {
        this.state.loading = true;
        try {
            if (this.state.activeTab === "rekap") {
                const res = await this.orm.call(
                    "sales.grading.dashboard.api",
                    "get_rekap_salesman_data",
                    [this.state.filters]
                );
                this.state.dataRekap = res;
            } else {
                const res = await this.orm.call(
                    "sales.grading.dashboard.api",
                    "get_ranking_salesman_data",
                    [this.state.filters]
                );
                this.state.dataRanking = res;
            }
        } finally {
            this.state.loading = false;
        }
    }

    async onFilterChange(key, ev) {
        this.state.filters[key] = ev.target.value;
        this.state.filters.pageIndex = 1;
        await this.fetchData();
    }

    async resetToCurrentPeriod() {
        const cur = getCurrentPeriod();
        this.state.filters.year = cur.year;
        this.state.filters.quarter = cur.quarter;
        this.state.filters.team_id = "ALL";
        this.state.filters.employee_name = "ALL";
        this.state.filters.grading_awal = "ALL";
        this.state.filters.grading_terbaru = "ALL";
        this.state.filters.status_perubahan = "ALL";
        this.state.filters.search = "";
        this.state.filters.pageIndex = 1;
        await this.fetchData();
        this.notification.add("Filter telah dikembalikan ke periode berjalan (" + cur.year + " " + cur.quarter + ")", {
            type: "info",
        });
    }

    async onPageSizeChange(ev) {
        this.state.filters.pageSize = parseInt(ev.target.value, 10) || 10;
        this.state.filters.pageIndex = 1;
    }

    prevPage() {
        if (this.state.filters.pageIndex > 1) {
            this.state.filters.pageIndex -= 1;
        }
    }

    nextPage() {
        if (this.state.filters.pageIndex < this.totalPages) {
            this.state.filters.pageIndex += 1;
        }
    }

    async toggleSort(col) {
        if (this.state.filters.sort_by === col) {
            this.state.filters.sort_dir = this.state.filters.sort_dir === "desc" ? "asc" : "desc";
        } else {
            this.state.filters.sort_by = col;
            this.state.filters.sort_dir = "desc";
        }
        await this.fetchData();
    }

    async openDetail(row) {
        const detail = await this.orm.call(
            "sales.grading.dashboard.api",
            "get_salesman_detail",
            [row.employee_id || false, row.employee_name]
        );
        if (detail && detail.error) {
            this.notification.add(detail.error, { type: "danger" });
            return;
        }
        this.state.detail = detail;
    }

    closeDetail() {
        this.state.detail = null;
    }

    async syncGpData() {
        this.state.syncing = true;
        try {
            const res = await this.orm.call("sales.grading.sync.log", "action_sync_all_now", []);
            if (res && res.params && res.params.message) {
                this.notification.add(res.params.message, {
                    type: res.params.type === "danger" ? "danger" : "success",
                });
            }
            await this.fetchData();
        } catch (e) {
            this.notification.add("Sinkronisasi gagal: " + (e.message || e), { type: "danger" });
        } finally {
            this.state.syncing = false;
        }
    }

    openRulesConfig() {
        this.action.doAction("sales_grading_triwulan.action_sales_grading_rules_config");
    }

    drawRankingCharts() {
        if (this.state.activeTab !== "ranking") return;
        const ch = this.state.dataRanking && this.state.dataRanking.charts;
        if (!ch) return;

        if (this.refChartTop10 && this.refChartTop10.el && ch.top10_gp) {
            this.charts.top10 = renderBarChart(
                this.refChartTop10.el,
                this.charts.top10,
                ch.top10_gp.labels,
                [{ label: "Total GP (Rp)", data: ch.top10_gp.values, backgroundColor: SG_COLORS.navy }],
                true
            );
        }

        if (this.refChartTeams && this.refChartTeams.el && ch.team_comparison) {
            this.charts.teams = renderBarChart(
                this.refChartTeams.el,
                this.charts.teams,
                ch.team_comparison.labels,
                [{ label: "Total GP Tim (Rp)", data: ch.team_comparison.values, backgroundColor: SG_COLORS.burgundy }],
                true
            );
        }

        if (this.refChartAch && this.refChartAch.el && ch.target_achievement) {
            this.charts.ach = renderBarChart(
                this.refChartAch.el,
                this.charts.ach,
                ch.target_achievement.labels,
                [{ label: "% Pencapaian", data: ch.target_achievement.values, backgroundColor: SG_COLORS.greenDark }],
                false
            );
        }
    }

    exportFile(fmt) {
        const sub = this.state.activeTab === "rekap" ? "rekap_salesman" : "ranking_salesman";
        window.open(buildExportUrl(fmt, sub, this.state.filters), "_blank");
    }

    fmtIDR(v) { return formatIDR(v); }
    fmtPct(v) { return formatPct(v); }
    gradeClass(k) { return gradeBadgeClass(k); }
    statusClass(k) { return statusBadgeClass(k); }
    progClass(p) { return progressClass(p); }
}

SalesGradingMain.template = "sales_grading_triwulan.GradingSalesMain";
SalesGradingMain.components = { SalesmanDetailModal };

// Register unified action and backward-compatible aliases
registry.category("actions").add("sales_grading_main", SalesGradingMain);
registry.category("actions").add("sales_grading_rekap_salesman", SalesGradingMain);
registry.category("actions").add("sales_grading_ranking_salesman", SalesGradingMain);
registry.category("actions").add("sales_grading_dashboard_salesman", SalesGradingMain);
