/** @odoo-module **/

import { Component, useRef, onMounted, onPatched, onWillUnmount } from "@odoo/owl";
import {
    formatIDR,
    formatPct,
    gradeBadgeClass,
    statusBadgeClass,
    renderLineChart,
} from "./dashboard_shared";

export class SalesmanDetailModal extends Component {
    setup() {
        this.chartRef = useRef("trendChart");
        this.chart = null;
        onMounted(() => this.drawChart());
        onPatched(() => this.drawChart());
        onWillUnmount(() => {
            if (this.chart) this.chart.destroy();
        });
    }

    drawChart() {
        const trend = this.props.detail && this.props.detail.chart_trend;
        if (!trend || !this.chartRef.el) return;
        this.chart = renderLineChart(
            this.chartRef.el,
            this.chart,
            trend.labels,
            [
                {
                    label: "Realisasi GP Triwulan",
                    data: trend.gp_values,
                    borderColor: "#1d4ed8",
                    backgroundColor: "rgba(29, 78, 216, 0.12)",
                    borderWidth: 2.5,
                    fill: true,
                },
                {
                    label: "Target GP Triwulan (Tabel A x 3)",
                    data: trend.target_values,
                    borderColor: "#f59e0b",
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
    gradeClass(k) { return gradeBadgeClass(k); }
    statusClass(k) { return statusBadgeClass(k); }
}

SalesmanDetailModal.template = "sales_grading_triwulan.SalesmanDetailModal";
SalesmanDetailModal.props = {
    detail: { type: Object },
    onClose: { type: Function },
};
