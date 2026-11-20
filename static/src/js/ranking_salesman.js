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
} from "./dashboard_shared";

export class SalesGradingRankingSalesman extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.refChartTop10 = useRef("chartTop10");
        this.refChartTeams = useRef("chartTeams");
        this.refChartAch = useRef("chartAch");
        this.charts = {};

        this.state = useState({
            loading: true,
            data: null,
            detail: null,
            filters: {
                year: "",
                quarter: "",
                team_id: "ALL",
                employee_name: "ALL",
                _initialized: false,
            },
        });

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this.fetchData();
        });
        onMounted(() => this.drawCharts());
        onPatched(() => this.drawCharts());
        onWillUnmount(() => {
            Object.values(this.charts).forEach((c) => c && c.destroy());
        });
    }

    async fetchData() {
        this.state.loading = true;
        try {
            const res = await this.orm.call(
                "sales.grading.dashboard.api",
                "get_ranking_salesman_data",
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

    drawCharts() {
        const ch = this.state.data && this.state.data.charts;
        if (!ch) return;
        this.charts.top10 = renderBarChart(
            this.refChartTop10.el,
            this.charts.top10,
            ch.top10_gp.labels,
            [{ label: "Total GP", data: ch.top10_gp.values, backgroundColor: "#1d4ed8" }],
            true
        );
        this.charts.teams = renderBarChart(
            this.refChartTeams.el,
            this.charts.teams,
            ch.team_comparison.labels,
            [{ label: "Total GP Tim", data: ch.team_comparison.values, backgroundColor: "#0f172a" }],
            true
        );
        this.charts.ach = renderBarChart(
            this.refChartAch.el,
            this.charts.ach,
            ch.target_achievement.labels,
            [{ label: "% Pencapaian Target", data: ch.target_achievement.values, backgroundColor: "#16a34a" }],
            false
        );
    }

    exportFile(fmt) {
        window.open(buildExportUrl(fmt, "ranking_salesman", this.state.filters), "_blank");
    }

    fmtIDR(v) { return formatIDR(v); }
    fmtPct(v) { return formatPct(v); }
    gradeClass(k) { return gradeBadgeClass(k); }
    progClass(p) { return progressClass(p); }
}

SalesGradingRankingSalesman.template = "sales_grading_triwulan.RankingSalesman";
SalesGradingRankingSalesman.components = { SalesmanDetailModal };
registry.category("actions").add("sales_grading_ranking_salesman", SalesGradingRankingSalesman);
