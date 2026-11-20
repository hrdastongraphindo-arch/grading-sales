/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { loadJS } from "@web/core/assets";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { SalesmanDetailModal } from "./salesman_detail_modal";
import {
    formatIDR,
    formatPct,
    gradeBadgeClass,
    statusBadgeClass,
    progressClass,
    buildExportUrl,
} from "./dashboard_shared";

export class SalesGradingRekapSalesman extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            data: null,
            detail: null,
            filters: {
                year: "",
                quarter: "ALL",
                team_id: "ALL",
                employee_name: "ALL",
                grading_terbaru: "ALL",
                status_perubahan: "ALL",
                search: "",
                sort_by: "year",
                sort_dir: "desc",
                _initialized: false,
            },
        });

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this.fetchData();
        });
    }

    async fetchData() {
        this.state.loading = true;
        try {
            const res = await this.orm.call(
                "sales.grading.dashboard.api",
                "get_rekap_salesman_data",
                [this.state.filters]
            );
            this.state.data = res;
            if (!this.state.filters._initialized && res.active_filters) {
                this.state.filters.year = res.active_filters.year || "2026";
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

    exportFile(fmt) {
        window.open(buildExportUrl(fmt, "rekap_salesman", this.state.filters), "_blank");
    }

    fmtIDR(v) { return formatIDR(v); }
    fmtPct(v) { return formatPct(v); }
    gradeClass(k) { return gradeBadgeClass(k); }
    statusClass(k) { return statusBadgeClass(k); }
    progClass(p) { return progressClass(p); }
}

SalesGradingRekapSalesman.template = "sales_grading_triwulan.RekapSalesman";
SalesGradingRekapSalesman.components = { SalesmanDetailModal };
registry.category("actions").add("sales_grading_rekap_salesman", SalesGradingRekapSalesman);
