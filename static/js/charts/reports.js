(function() {
    window.monetaCharts = window.monetaCharts || {};

    window.initChartWhenReady = window.initChartWhenReady || function(canvasId, renderFn) {
        function tryInit() {
            const canvas = document.getElementById(canvasId);
            if (!canvas) return;
            if (typeof Chart === 'undefined') {
                setTimeout(tryInit, 50);
                return;
            }
            renderFn(canvas);
        }

        if (document.readyState === 'loading') {
            document.addEventListener("DOMContentLoaded", tryInit);
        } else {
            tryInit();
        }
        document.addEventListener("htmx:afterSettle", function(evt) {
            if (document.getElementById(canvasId)) {
                tryInit();
            }
        });
    };

    function renderTimelineChart(canvas) {
        const timelineLabelsEl = document.getElementById('timeline-labels');
        const timelineIncomesEl = document.getElementById('timeline-incomes');
        const timelineExpensesEl = document.getElementById('timeline-expenses');
        if (!timelineLabelsEl || !timelineIncomesEl || !timelineExpensesEl) return;

        if (window.monetaCharts.reportsTimeline) {
            window.monetaCharts.reportsTimeline.destroy();
        }

        const timelineLabels = JSON.parse(timelineLabelsEl.textContent || '[]');
        const timelineIncomes = JSON.parse(timelineIncomesEl.textContent || '[]');
        const timelineExpenses = JSON.parse(timelineExpensesEl.textContent || '[]');

        const ctx = canvas.getContext('2d');
        window.monetaCharts.reportsTimeline = new Chart(ctx, {
            type: 'line',
            data: {
                labels: timelineLabels,
                datasets: [
                    {
                        label: 'Receitas',
                        data: timelineIncomes,
                        borderColor: 'rgba(16, 185, 129, 1)',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true
                    },
                    {
                        label: 'Despesas',
                        data: timelineExpenses,
                        borderColor: 'rgba(244, 63, 94, 1)',
                        backgroundColor: 'rgba(244, 63, 94, 0.1)',
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { labels: { color: '#475569' } },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) { label += ': '; }
                                if (context.parsed.y !== null) {
                                    label += new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(context.parsed.y);
                                }
                                return label;
                            }
                        }
                    }
                },
                scales: {
                    x: { ticks: { color: '#475569' }, grid: { display: false } },
                    y: {
                        ticks: {
                            color: '#475569',
                            callback: function(value) {
                                return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', notation: "compact", compactDisplay: "short" }).format(value);
                            }
                        },
                        grid: { color: 'rgba(128,128,128,0.1)' }
                    }
                }
            }
        });
    }

    function renderCategoryChart(canvas) {
        const pieLabelsEl = document.getElementById('pie-labels');
        const pieDataEl = document.getElementById('pie-data');
        const pieColorsEl = document.getElementById('pie-colors');
        if (!pieLabelsEl || !pieDataEl || !pieColorsEl) return;

        if (window.monetaCharts.reportsCategory) {
            window.monetaCharts.reportsCategory.destroy();
        }

        const pieLabels = JSON.parse(pieLabelsEl.textContent || '[]');
        const pieData = JSON.parse(pieDataEl.textContent || '[]');
        const pieColors = JSON.parse(pieColorsEl.textContent || '[]');

        const ctx = canvas.getContext('2d');
        window.monetaCharts.reportsCategory = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: pieLabels,
                datasets: [{
                    data: pieData,
                    backgroundColor: pieColors,
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { color: '#475569', boxWidth: 12, padding: 15 } },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                let label = context.label || '';
                                if (label) { label += ': '; }
                                if (context.parsed !== null) {
                                    label += new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(context.parsed);
                                }
                                return label;
                            }
                        }
                    }
                },
                cutout: '70%'
            }
        });
    }

    window.initChartWhenReady('timelineChart', renderTimelineChart);
    window.initChartWhenReady('categoryChart', renderCategoryChart);
})();
