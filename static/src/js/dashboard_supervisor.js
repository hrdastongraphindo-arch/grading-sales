/** @odoo-module **/

import { Component, onWillStart, onMounted, onPatched, onWillUnmount, useState, useRef } from "@odoo/owl";
import { loadJS } from "@web/core/assets";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import {
    SG_COLORS,
    getCurrentPeriod,
    formatIDR,
    formatPct,
    spvGradeBadgeClass,
    statusBadgeClass,
    progressClass,
    buildExportUrl,
    renderLineChart,
} from "./dashboard_shared";

export function getInitials(name) {
    if (!name) return "SP";
    const parts = name.trim().split(/\s+/);
    if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function enableRoundedBars(Chart) {
    if (!Chart || Chart._roundedBarsEnabled) return;
    Chart._roundedBarsEnabled = true;
    const origDraw = Chart.elements.Rectangle.prototype.draw;
    Chart.elements.Rectangle.prototype.draw = function() {
        const ctx = this._chart.ctx;
        const vm = this._view;
        if (!vm || vm.horizontal) {
            return origDraw.apply(this, arguments);
        }
        const left = vm.x - vm.width / 2;
        const right = vm.x + vm.width / 2;
        const top = vm.y;
        const bottom = vm.base;
        const radius = Math.min(6, (right - left) / 2);

        ctx.beginPath();
        ctx.fillStyle = vm.backgroundColor;
        ctx.strokeStyle = vm.borderColor;
        ctx.lineWidth = vm.borderWidth || 0;

        ctx.moveTo(left, bottom);
        ctx.lineTo(left, top + radius);
        ctx.quadraticCurveTo(left, top, left + radius, top);
        ctx.lineTo(right - radius, top);
        ctx.quadraticCurveTo(right, top, right, top + radius);
        ctx.lineTo(right, bottom);
        ctx.closePath();
        ctx.fill();
        if (vm.borderWidth) ctx.stroke();
    };
}

const valueLabelsPlugin = {
    afterDatasetsDraw: function(chart) {
        const ctx = chart.ctx;
        chart.data.datasets.forEach(function(dataset, i) {
            const meta = chart.getDatasetMeta(i);
            if (!meta || meta.hidden) return;
            meta.data.forEach(function(element, index) {
                const val = dataset.data[index];
                if (val === undefined || val === null) return;
                ctx.save();
                ctx.fillStyle = "#1E293B";
                ctx.font = "bold 11px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
                ctx.textAlign = "center";
                ctx.textBaseline = "bottom";

                let text = "";
                if (dataset.isCurrency) {
                    if (Math.abs(val) >= 1e9) {
                        text = "Rp " + (val / 1e9).toFixed(1).replace(".", ",") + " M";
                    } else if (Math.abs(val) >= 1e6) {
                        const jt = (val / 1e6);
                        text = "Rp " + (jt % 1 === 0 ? jt.toFixed(0) : jt.toFixed(1)).replace(".", ",") + " Jt";
                    } else {
                        text = "Rp " + Math.round(val).toLocaleString("id-ID");
                    }
                } else {
                    text = Number(val || 0).toFixed(1).replace(".", ",") + "%";
                }
                const pos = element.tooltipPosition();
                ctx.fillText(text, pos.x, pos.y - 4);
                ctx.restore();
            });
        });
    }
};

const thresholdPlugin = {
    afterDraw: function(chart) {
        const yScale = chart.scales["y-axis-0"];
        if (!yScale) return;
        const ctx = chart.ctx;

        // Line 1: 70% Batas Turun Grade
        const y70 = yScale.getPixelForValue(70);
        if (y70 >= chart.chartArea.top && y70 <= chart.chartArea.bottom) {
            ctx.save();
            ctx.beginPath();
            ctx.setLineDash([5, 5]);
            ctx.moveTo(chart.chartArea.left, y70);
            ctx.lineTo(chart.chartArea.right, y70);
            ctx.strokeStyle = "#EF4444";
            ctx.lineWidth = 1.5;
            ctx.stroke();

            ctx.fillStyle = "#EF4444";
            ctx.font = "bold 10px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
            ctx.textAlign = "right";
            ctx.textBaseline = "bottom";
            ctx.fillText("Batas Turun: 70%", chart.chartArea.right, y70 - 2);
            ctx.restore();
        }

        // Line 2: 100% Target Promosi
        const y100 = yScale.getPixelForValue(100);
        if (y100 >= chart.chartArea.top && y100 <= chart.chartArea.bottom) {
            ctx.save();
            ctx.beginPath();
            ctx.setLineDash([5, 5]);
            ctx.moveTo(chart.chartArea.left, y100);
            ctx.lineTo(chart.chartArea.right, y100);
            ctx.strokeStyle = "#10B981";
            ctx.lineWidth = 1.5;
            ctx.stroke();

            ctx.fillStyle = "#059669";
            ctx.font = "bold 10px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
            ctx.textAlign = "right";
            ctx.textBaseline = "bottom";
            ctx.fillText("Target Promosi: 100%", chart.chartArea.right, y100 - 2);
            ctx.restore();
        }
    }
};

export class SupervisorSlideOverDrawer extends Component {
    setup() {
        this.chartRef = useRef("spvAnnualChart");
        this.chart = null;
        onMounted(() => this.drawChart());
        onPatched(() => this.drawChart());
        onWillUnmount(() => {
            if (this.chart) this.chart.destroy();
        });
    }

    drawChart() {
        const ch = this.props.detail && this.props.detail.chart_annual;
        if (!ch || !this.chartRef.el) return;
        this.chart = renderLineChart(
            this.chartRef.el,
            this.chart,
            ch.labels,
            [
                {
                    label: "Realisasi GP Bulanan",
                    data: ch.gp_values,
                    borderColor: "#2563EB",
                    backgroundColor: "rgba(37, 99, 235, 0.12)",
                    borderWidth: 2.5,
                    fill: true,
                },
                {
                    label: "Target GP / Bulan",
                    data: ch.monthly_target,
                    borderColor: "#64748B",
                    borderDash: [5, 5],
                    borderWidth: 2,
                    fill: false,
                },
            ],
            true
        );
    }

    fmtIDR(v) { return formatIDR(v); }
    fmtPct(v) { return formatPct(v); }
    spvClass(k) { return spvGradeBadgeClass(k); }
    statusClass(s) { return statusBadgeClass(s); }
    progClass(p) { return progressClass(p); }
    getInitials(name) { return getInitials(name); }
}

SupervisorSlideOverDrawer.template = "sales_grading_triwulan.SupervisorSlideOverDrawer";
SupervisorSlideOverDrawer.props = {
    detail: Object,
    onClose: Function,
};

export class SalesGradingDashboardSupervisor extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.refChartTarget = useRef("chartSpvTarget");
        this.refChartProgress = useRef("chartSpvProgress");
        this.charts = {};

        const cur = getCurrentPeriod();

        this.state = useState({
            loading: true,
            syncing: false,
            data: null,
            detail: null,
            showExportMenu: false,
            searchSupervisor: "",
            filters: {
                year: cur.year,
                quarter: cur.quarter,
                supervisor_id: "ALL",
                team_id: "ALL",
                grade: "ALL",
                status_evaluasi: "ALL",
                _initialized: true,
            },
        });

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            if (window.Chart) enableRoundedBars(window.Chart);
            await this.fetchData();
        });
        onMounted(() => this.drawCharts());
        onPatched(() => this.drawCharts());
        onWillUnmount(() => {
            Object.values(this.charts).forEach((c) => c && c.destroy());
        });
    }

    get filteredSupervisorRows() {
        const d = this.state.data;
        if (!d || !d.rows) return [];
        if (!this.state.searchSupervisor) return d.rows;
        const q = this.state.searchSupervisor.toLowerCase().trim();
        return d.rows.filter(
            (r) =>
                (r.supervisor_name && r.supervisor_name.toLowerCase().includes(q)) ||
                (r.team_names && r.team_names.toLowerCase().includes(q)) ||
                (r.grade_label && r.grade_label.toLowerCase().includes(q))
        );
    }

    onSearchSupervisorInput(ev) {
        this.state.searchSupervisor = ev.target.value;
    }

    clearSearchSupervisor() {
        this.state.searchSupervisor = "";
    }

    toggleExportMenu() {
        this.state.showExportMenu = !this.state.showExportMenu;
    }

    triggerExport(fmt) {
        this.state.showExportMenu = false;
        this.exportFile(fmt);
    }

    async fetchData() {
        this.state.loading = true;
        try {
            const res = await this.orm.call(
                "sales.grading.dashboard.api",
                "get_dashboard_supervisor_data",
                [this.state.filters]
            );
            this.state.data = res;
        } finally {
            this.state.loading = false;
        }
    }

    async onFilterChange(key, ev) {
        this.state.filters[key] = ev.target.value;
        await this.fetchData();
    }

    async resetToCurrentPeriod() {
        const cur = getCurrentPeriod();
        this.state.filters.year = cur.year;
        this.state.filters.quarter = cur.quarter;
        this.state.filters.supervisor_id = "ALL";
        this.state.filters.team_id = "ALL";
        this.state.filters.grade = "ALL";
        this.state.filters.status_evaluasi = "ALL";
        this.state.searchSupervisor = "";
        await this.fetchData();
        this.notification.add("Filter telah dikembalikan ke periode berjalan (" + cur.year + " " + cur.quarter + ")", {
            type: "info",
        });
    }

    async openDetail(row) {
        const detail = await this.orm.call(
            "sales.grading.dashboard.api",
            "get_supervisor_detail",
            [row.supervisor_id, row.year || this.state.filters.year]
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

    openMasterSupervisor() {
        this.action.doAction("sales_grading_triwulan.action_sales_grading_supervisor");
    }

    openRulesConfig() {
        this.action.doAction("sales_grading_triwulan.action_sales_grading_rules_config");
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
        window.open(buildExportUrl(fmt, "dashboard_supervisor", this.state.filters), "_blank");
    }

    drawCharts() {
        if (!window.Chart) return;
        enableRoundedBars(window.Chart);
        const ch = this.state.data && this.state.data.charts;
        if (!ch) return;

        // 1. Target GP vs Realisasi GP per Supervisor (Rounded Bars + Direct Top Value Labels)
        if (this.refChartTarget && this.refChartTarget.el && ch.target_vs_realization) {
            if (this.charts.target) this.charts.target.destroy();
            const ctx1 = this.refChartTarget.el.getContext("2d");
            this.charts.target = new window.Chart(ctx1, {
                type: "bar",
                data: {
                    labels: ch.target_vs_realization.labels,
                    datasets: [
                        {
                            label: "Target GP Triwulan",
                            data: ch.target_vs_realization.target,
                            backgroundColor: "#E2E8F0",
                            hoverBackgroundColor: "#CBD5E1",
                            isCurrency: true,
                        },
                        {
                            label: "Realisasi GP Triwulan",
                            data: ch.target_vs_realization.realisasi,
                            backgroundColor: "#1E3A8A",
                            hoverBackgroundColor: "#1E40AF",
                            isCurrency: true,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    legend: {
                        position: "bottom",
                        labels: { boxWidth: 12, fontSize: 11, fontColor: "#475569" },
                    },
                    tooltips: {
                        callbacks: {
                            label: (item, data) => {
                                const dsLabel = data.datasets[item.datasetIndex].label || "";
                                return `${dsLabel}: ${formatIDR(item.yLabel)}`;
                            },
                        },
                    },
                    scales: {
                        yAxes: [{
                            ticks: {
                                beginAtZero: true,
                                fontSize: 10,
                                fontColor: "#64748B",
                                callback: (v) => Math.abs(v) >= 1e9 ? (v / 1e9).toFixed(1) + "M" : (v / 1e6).toFixed(0) + " Jt",
                            },
                            gridLines: { color: "#F1F5F9", drawBorder: false },
                        }],
                        xAxes: [{
                            ticks: { fontSize: 11, fontColor: "#1E293B", fontStyle: "bold" },
                            gridLines: { display: false },
                        }],
                    },
                    layout: { padding: { top: 22, bottom: 0 } },
                },
                plugins: [valueLabelsPlugin],
            });
        }

        // 2. Persentase Pencapaian Triwulan vs Akumulasi Tahunan (% Labels + 80% Threshold Line)
        if (this.refChartProgress && this.refChartProgress.el && ch.annual_progress) {
            if (this.charts.progress) this.charts.progress.destroy();
            const ctx2 = this.refChartProgress.el.getContext("2d");
            this.charts.progress = new window.Chart(ctx2, {
                type: "bar",
                data: {
                    labels: ch.annual_progress.labels,
                    datasets: [
                        {
                            label: "% Pencapaian Triwulan",
                            data: ch.annual_progress.pct_triwulan,
                            backgroundColor: "#059669",
                            hoverBackgroundColor: "#047857",
                            isCurrency: false,
                        },
                        {
                            label: "% Akumulasi Tahunan",
                            data: ch.annual_progress.pct_tahunan,
                            backgroundColor: "#4F46E5",
                            hoverBackgroundColor: "#4338CA",
                            isCurrency: false,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    legend: {
                        position: "bottom",
                        labels: { boxWidth: 12, fontSize: 11, fontColor: "#475569" },
                    },
                    tooltips: {
                        callbacks: {
                            label: (item, data) => {
                                const dsLabel = data.datasets[item.datasetIndex].label || "";
                                return `${dsLabel}: ${formatPct(item.yLabel)}`;
                            },
                        },
                    },
                    scales: {
                        yAxes: [{
                            ticks: {
                                beginAtZero: true,
                                max: Math.max(115, ...ch.annual_progress.pct_triwulan, ...ch.annual_progress.pct_tahunan) + 15,
                                fontSize: 10,
                                fontColor: "#64748B",
                                callback: (v) => v + "%",
                            },
                            gridLines: { color: "#F1F5F9", drawBorder: false },
                        }],
                        xAxes: [{
                            ticks: { fontSize: 11, fontColor: "#1E293B", fontStyle: "bold" },
                            gridLines: { display: false },
                        }],
                    },
                    layout: { padding: { top: 22, bottom: 0 } },
                },
                plugins: [valueLabelsPlugin, thresholdPlugin],
            });
        }
    }

    fmtIDR(v) { return formatIDR(v); }
    fmtPct(v) { return formatPct(v); }
    spvClass(k) { return spvGradeBadgeClass(k); }
    statusClass(s) { return statusBadgeClass(s); }
    progClass(p) { return progressClass(p); }
    getInitials(name) { return getInitials(name); }
}

SalesGradingDashboardSupervisor.template = "sales_grading_triwulan.DashboardSupervisor";
SalesGradingDashboardSupervisor.components = { SupervisorSlideOverDrawer };
registry.category("actions").add("sales_grading_dashboard_supervisor", SalesGradingDashboardSupervisor);
