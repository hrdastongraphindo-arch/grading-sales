/** @odoo-module **/

import { Component, onWillStart, onMounted, onPatched, onWillUnmount, useState, useRef } from "@odoo/owl";
import { loadJS } from "@web/core/assets";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { SalesmanDetailModal } from "./salesman_detail_modal";
import {
    formatIDR,
    formatPct,
    gradeBadgeClass,
    progressClass,
    buildExportUrl,
    renderBarChart,
    renderDoughnutChart,
    renderLineChart,
} from "./dashboard_shared";

export class SalesGradingDashboardSalesman extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.refChartGrade = useRef("chartGrade");
        this.refChartTeam = useRef("chartTeam");
        this.refChartTarget = useRef("chartTarget");
        this.refChartStatus = useRef("chartStatus");
        this.refChartTrend = useRef("chartTrend");
        this.charts = {};

        this.state = useState({
            loading: true,
            syncing: false,
            data: null,
            detail: null,
            filters: {
                year: "",
                quarter: "",
                team_id: "ALL",
                employee_name: "ALL",
                grading_awal: "ALL",
                grading_terbaru: "ALL",
                status_perubahan: "ALL",
                sort_by: "total_gp",
                sort_dir: "desc",
                _initialized: false,
            },
        });

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this.fetchData();
        });
        onMounted(() => this.drawAllCharts());
        onPatched(() => this.drawAllCharts());
        onWillUnmount(() => {
            Object.values(this.charts).forEach((c) => c && c.destroy());
        });
    }

    async fetchData() {
        this.state.loading = true;
        try {
            const res = await this.orm.call(
                "sales.grading.dashboard.api",
                "get_dashboard_salesman_data",
                [this.state.filters]
            );
            this.state.data = res;
            if (!this.state.filters._initialized && res.active_filters) {
                this.state.filters.year = res.active_filters.year || "ALL";
                this.state.filters.quarter = res.active_filters.quarter || "ALL";
                this.state.filters._initialized = true;
            }
        } finally {
            this.state.loading = false;
        }
    }

    async onFilterChange(key, ev) {
        this.state.filters[key] = ev.target.value;
        this.state.filters._initialized = true;
        await this.fetchData();
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
            const res = await this.orm.call("sales.grading.sync.log", "action_run_sync", []);
            this.notification.add(
                `Sinkronisasi selesai: ${res.total_fetched} baris diambil (${res.created_count} baru, ${res.updated_count} diperbarui).`,
                { type: res.status === "success" ? "success" : "warning" }
            );
            await this.fetchData();
        } catch (err) {
            this.action.doAction("sales_grading_triwulan.action_sales_grading_sync_config");
        } finally {
            this.state.syncing = false;
        }
    }

    exportFile(fmt) {
        window.open(buildExportUrl(fmt, "dashboard_salesman", this.state.filters), "_blank");
    }

    drawAllCharts() {
        const ch = this.state.data && this.state.data.charts;
        if (!ch) return;

        this.charts.grade = renderDoughnutChart(
            this.refChartGrade.el,
            this.charts.grade,
            ch.grade_distribution.labels,
            ch.grade_distribution.values,
            ["#f59e0b", "#2563eb", "#16a34a", "#ea580c", "#64748b"]
        );
        this.charts.team = renderBarChart(
            this.refChartTeam.el,
            this.charts.team,
            ch.team_gp.labels,
            [{ label: "Total GP Tim", data: ch.team_gp.values, backgroundColor: "#1e3a8a" }],
            true
        );
        this.charts.target = renderBarChart(
            this.refChartTarget.el,
            this.charts.target,
            ch.target_vs_realization.labels,
            [
                { label: "Realisasi GP (3 Bln)", data: ch.target_vs_realization.realisasi, backgroundColor: "#1d4ed8" },
                { label: "Target GP (Tabel A x 3)", data: ch.target_vs_realization.target, backgroundColor: "#f59e0b" },
            ],
            true
        );
        this.charts.status = renderDoughnutChart(
            this.refChartStatus.el,
            this.charts.status,
            ch.status_changes.labels,
            ch.status_changes.values,
            ["#16a34a", "#0284c7", "#dc2626"]
        );
        this.charts.trend = renderLineChart(
            this.refChartTrend.el,
            this.charts.trend,
            ch.quarterly_trend.labels,
            [{
                label: "Total GP per Triwulan",
                data: ch.quarterly_trend.values,
                borderColor: "#1d4ed8",
                backgroundColor: "rgba(29, 78, 216, 0.14)",
                borderWidth: 2.5,
                fill: true,
            }],
            true
        );
    }

    fmtIDR(v) { return formatIDR(v); }
    fmtPct(v) { return formatPct(v); }
    gradeClass(k) { return gradeBadgeClass(k); }
    progClass(p) { return progressClass(p); }
}

SalesGradingDashboardSalesman.template = "sales_grading_triwulan.DashboardSalesman";
SalesGradingDashboardSalesman.components = { SalesmanDetailModal };
registry.category("actions").add("sales_grading_dashboard_salesman", SalesGradingDashboardSalesman);
