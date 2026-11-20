/** @odoo-module **/

export const SG_COLORS = {
    burgundy: "#7C1735",
    navy: "#172B50",
    gold: "#D6AD63",
    bg: "#F4F6FA",
    textPrimary: "#182338",
    textSecondary: "#687386",
    border: "#E1E6EF",
    greenDark: "#07865B",
    green: "#72B94C",
    yellow: "#EAB308",
    orange: "#F07822",
    red: "#DC4141",
};

export function getCurrentPeriod() {
    // Current date in Asia/Jakarta (WIB: UTC+7)
    const now = new Date();
    const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
    const jktDate = new Date(utc + (3600000 * 7));
    const year = String(jktDate.getFullYear());
    const month = jktDate.getMonth() + 1; // 1-12
    let quarter = "Q4";
    if (month >= 1 && month <= 3) quarter = "Q1";
    else if (month >= 4 && month <= 6) quarter = "Q2";
    else if (month >= 7 && month <= 9) quarter = "Q3";
    else quarter = "Q4";
    return { year, month, quarter };
}

export function formatIDR(value) {
    const num = Number(value || 0);
    const sign = num < 0 ? "-" : "";
    const absVal = Math.round(Math.abs(num));
    return sign + "Rp" + absVal.toLocaleString("id-ID");
}

export function formatPct(value) {
    const num = Number(value || 0);
    return num.toFixed(2).replace(".", ",") + "%";
}

export function gradeBadgeClass(gradeKey) {
    return "sg-badge sg-grade-" + (gradeKey || "new");
}

export function spvGradeBadgeClass(gradeKey) {
    return "sg-badge sg-spv-" + (gradeKey || "supervisor");
}

export function statusBadgeClass(statusKey) {
    return "sg-badge sg-status-" + (statusKey || "stabil");
}

export function progressClass(pct) {
    const val = Number(pct || 0);
    if (val >= 100) return "sg-progress-fill high-dark"; // Hijau tua #07865B
    if (val >= 90) return "sg-progress-fill high";      // Hijau #72B94C
    if (val >= 70) return "sg-progress-fill medium";    // Kuning #EAB308
    if (val >= 60) return "sg-progress-fill warning";   // Oranye #F07822
    return "sg-progress-fill low";                      // Merah #DC4141
}

export function buildExportUrl(fmt, submenu, filters) {
    const params = new URLSearchParams();
    Object.entries(filters || {}).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== "" && k !== "_initialized") {
            params.set(k, String(v));
        }
    });
    const base = fmt === "xlsx"
        ? `/sales_grading/export/xlsx/${submenu}`
        : `/sales_grading/report/${fmt}/${submenu}`;
    const qs = params.toString();
    return qs ? `${base}?${qs}` : base;
}

export function renderBarChart(canvas, existingChart, labels, datasets, isCurrency = true) {
    if (!canvas || !window.Chart) return null;
    if (existingChart) existingChart.destroy();
    return new window.Chart(canvas.getContext("2d"), {
        type: "bar",
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            legend: { position: "top", labels: { boxWidth: 12, fontSize: 11 } },
            tooltips: {
                callbacks: {
                    label: (item, data) => {
                        const dsLabel = data.datasets[item.datasetIndex].label || "";
                        const val = isCurrency ? formatIDR(item.yLabel) : formatPct(item.yLabel);
                        return `${dsLabel}: ${val}`;
                    },
                },
            },
            scales: {
                yAxes: [{
                    ticks: {
                        beginAtZero: true,
                        fontSize: 10,
                        callback: (v) => isCurrency
                            ? (Math.abs(v) >= 1e9 ? (v / 1e9).toFixed(1) + "M" : (v / 1e6).toFixed(0) + "Jt")
                            : v + "%",
                    },
                }],
                xAxes: [{ ticks: { fontSize: 10, autoSkip: false } }],
            },
        },
    });
}

export function renderDoughnutChart(canvas, existingChart, labels, values, colors) {
    if (!canvas || !window.Chart) return null;
    if (existingChart) existingChart.destroy();
    return new window.Chart(canvas.getContext("2d"), {
        type: "doughnut",
        data: {
            labels,
            datasets: [{ data: values, backgroundColor: colors, borderWidth: 1 }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            legend: { position: "right", labels: { boxWidth: 12, fontSize: 11 } },
        },
    });
}

export function renderLineChart(canvas, existingChart, labels, datasets, isCurrency = true) {
    if (!canvas || !window.Chart) return null;
    if (existingChart) existingChart.destroy();
    return new window.Chart(canvas.getContext("2d"), {
        type: "line",
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            legend: { position: "top", labels: { boxWidth: 12, fontSize: 11 } },
            tooltips: {
                callbacks: {
                    label: (item, data) => {
                        const dsLabel = data.datasets[item.datasetIndex].label || "";
                        return `${dsLabel}: ${isCurrency ? formatIDR(item.yLabel) : formatPct(item.yLabel)}`;
                    },
                },
            },
            scales: {
                yAxes: [{
                    ticks: {
                        beginAtZero: true,
                        fontSize: 10,
                        callback: (v) => isCurrency
                            ? (Math.abs(v) >= 1e9 ? (v / 1e9).toFixed(1) + "M" : (v / 1e6).toFixed(0) + "Jt")
                            : v + "%",
                    },
                }],
                xAxes: [{ ticks: { fontSize: 10 } }],
            },
        },
    });
}
