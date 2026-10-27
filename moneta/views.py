import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from .services import (
    generate_csv_export,
    get_dashboard_data,
    get_export_transactions,
    get_report_data,
    parse_report_dates,
)

logger = logging.getLogger(__name__)


def health_check_view(request):
    """Health check endpoint for Cloud Run and uptime monitoring."""
    from django.db import connection

    try:
        connection.ensure_connection()
        return JsonResponse({'status': 'healthy', 'database': 'connected'}, status=200)
    except Exception:
        logger.exception("Health check failed")
        return JsonResponse({'status': 'unhealthy', 'database': 'disconnected'}, status=503)


@login_required(login_url='users_web:login')
def dashboard_view(request):
    context = get_dashboard_data(
        user=request.user,
        month_param=request.GET.get('month'),
        account_id_param=request.GET.get('account_id'),
    )
    return render(request, 'moneta/dashboard.html', context)


@login_required(login_url='users_web:login')
def reports_view(request):
    start_date, end_date = parse_report_dates(
        request.GET.get('start_date'),
        request.GET.get('end_date'),
    )
    report_data = get_report_data(request.user, start_date, end_date)

    context = {
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'report_data': report_data,
        'chart_labels': report_data['timeline_labels'],
        'chart_incomes': [float(v) for v in report_data['timeline_incomes']],
        'chart_expenses': [float(v) for v in report_data['timeline_expenses']],
        'pie_labels': [item['name'] for item in report_data['expenses_by_category']],
        'pie_data': [float(item['total']) for item in report_data['expenses_by_category']],
        'pie_colors': [item['color'] for item in report_data['expenses_by_category']],
    }
    return render(request, 'moneta/reports.html', context)


@login_required(login_url='users_web:login')
def export_transactions_csv_view(request):
    start_date, end_date = parse_report_dates(
        request.GET.get('start_date'),
        request.GET.get('end_date'),
    )
    transactions = get_export_transactions(request.user, start_date, end_date)
    return generate_csv_export(transactions)


def custom_404_view(request, exception):
    return render(request, '404.html', status=404)
