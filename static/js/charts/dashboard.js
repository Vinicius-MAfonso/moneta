(function() {
    function renderCashflowChart(canvas) {
        const labelsEl = document.getElementById('chart-labels');
        const incomesEl = document.getElementById('chart-incomes');
        const expensesEl = document.getElementById('chart-expenses');
        if (!labelsEl || !incomesEl || !expensesEl) return;

        window.monetaCharts = window.monetaCharts || {};
        if (window.monetaCharts.cashflow) {
            window.monetaCharts.cashflow.destroy();
        }

        const labels = JSON.parse(labelsEl.textContent || '[]');
        const incomes = JSON.parse(incomesEl.textContent || '[]');
        const expenses = JSON.parse(expensesEl.textContent || '[]');

        const ctx = canvas.getContext('2d');
        window.monetaCharts.cashflow = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Receitas',
                        data: incomes,
                        backgroundColor: 'rgba(16, 185, 129, 0.8)',
                        borderRadius: 8,
                    },
                    {
                        label: 'Despesas',
                        data: expenses,
                        backgroundColor: 'rgba(244, 63, 94, 0.8)',
                        borderRadius: 8,
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: '#475569' } }
                },
                scales: {
                    x: { ticks: { color: '#475569' }, grid: { display: false } },
                    y: { ticks: { color: '#475569' }, grid: { color: 'rgba(128,128,128,0.1)' } }
                }
            }
        });
    }

    function renderHistoryChart(canvas) {
        const labelsEl = document.getElementById('chart-labels');
        const balancesEl = document.getElementById('chart-balances');
        if (!labelsEl || !balancesEl) return;

        window.monetaCharts = window.monetaCharts || {};
        if (window.monetaCharts.history) {
            window.monetaCharts.history.destroy();
        }

        const labels = JSON.parse(labelsEl.textContent || '[]');
        const balances = JSON.parse(balancesEl.textContent || '[]');

        const ctx = canvas.getContext('2d');
        window.monetaCharts.history = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Balanço (R$)',
                        data: balances,
                        borderColor: 'rgba(99, 102, 241, 1)',
                        backgroundColor: 'rgba(99, 102, 241, 0.1)',
                        borderWidth: 2,
                        tension: 0.4,
                        fill: true,
                        pointBackgroundColor: 'rgba(99, 102, 241, 1)',
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: { ticks: { color: '#475569' }, grid: { display: false } },
                    y: { ticks: { color: '#475569' }, grid: { color: 'rgba(128,128,128,0.1)' } }
                }
            }
        });
    }

    if (window.initChartWhenReady) {
        window.initChartWhenReady('cashflowChart', renderCashflowChart);
        window.initChartWhenReady('historyChart', renderHistoryChart);
    }
})();

