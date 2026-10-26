import hmac
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

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


def _verify_cron_auth(request):
    from django.conf import settings
    expected_token = getattr(settings, 'CRON_SECRET', '')
    auth_header = request.headers.get('Authorization', '')
    provided_token = auth_header.removeprefix('Bearer ').strip()
    return bool(expected_token and hmac.compare_digest(provided_token, expected_token))


@csrf_exempt
@require_POST
def cron_process_recurring_view(request):
    """Executa o processamento de transações recorrentes de forma síncrona."""
    if not _verify_cron_auth(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    from transactions.tasks import process_all_recurring_transactions
    try:
        process_all_recurring_transactions()
        return JsonResponse({'status': 'ok', 'task': 'process_all_recurring_transactions'})
    except Exception:
        logger.exception("Erro ao processar transações recorrentes via cron.")
        return JsonResponse({'status': 'error', 'message': 'Falha ao processar recorrências.'}, status=500)


@csrf_exempt
@require_POST
def cron_notify_bills_view(request):
    """Executa a notificação de faturas a vencer de forma síncrona."""
    if not _verify_cron_auth(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    from wallets.tasks import (
        notify_due_credit_card_bills,
        update_and_notify_closed_credit_card_bills,
    )
    try:
        update_and_notify_closed_credit_card_bills()
        notify_due_credit_card_bills()
        return JsonResponse({'status': 'ok', 'task': 'notify_due_credit_card_bills'})
    except Exception:
        logger.exception("Erro ao notificar faturas via cron.")
        return JsonResponse({'status': 'error', 'message': 'Falha ao notificar faturas.'}, status=500)


@csrf_exempt
@require_POST
def cron_notify_budgets_view(request):
    """Executa a notificação de avisos de orçamento de forma síncrona."""
    if not _verify_cron_auth(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    from planning.tasks import notify_budget_warnings, notify_goal_progress
    try:
        notify_budget_warnings()
        notify_goal_progress()
        return JsonResponse({'status': 'ok', 'task': 'notify_budget_warnings'})
    except Exception:
        logger.exception("Erro ao notificar orçamentos via cron.")
        return JsonResponse({'status': 'error', 'message': 'Falha ao notificar orçamentos.'}, status=500)


@csrf_exempt
@require_POST
def cron_notify_transactions_view(request):
    """Executa a notificação de transações do dia de forma síncrona."""
    if not _verify_cron_auth(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    from transactions.tasks import notify_due_transactions
    try:
        notify_due_transactions()
        return JsonResponse({'status': 'ok', 'task': 'notify_due_transactions'})
    except Exception:
        logger.exception("Erro ao notificar transações via cron.")
        return JsonResponse({'status': 'error', 'message': 'Falha ao notificar transações.'}, status=500)


@csrf_exempt
@require_POST
def cron_wake_view(request):
    """Endpoint unificado / run-all para executar todas as tarefas agendadas de forma síncrona."""
    if not _verify_cron_auth(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    from planning.tasks import notify_budget_warnings, notify_goal_progress
    from transactions.tasks import (
        notify_due_transactions,
        process_all_recurring_transactions,
    )
    from wallets.tasks import (
        notify_due_credit_card_bills,
        update_and_notify_closed_credit_card_bills,
    )

    tasks = [
        ('process_all_recurring_transactions', process_all_recurring_transactions),
        ('update_and_notify_closed_credit_card_bills', update_and_notify_closed_credit_card_bills),
        ('notify_due_credit_card_bills', notify_due_credit_card_bills),
        ('notify_budget_warnings', notify_budget_warnings),
        ('notify_goal_progress', notify_goal_progress),
        ('notify_due_transactions', notify_due_transactions),
    ]

    executed = []
    for name, func in tasks:
        try:
            func()
            executed.append(name)
        except Exception:
            logger.exception(f"Erro ao executar tarefa {name} via cron wake.")

    return JsonResponse({'status': 'ok', 'executed_tasks': executed, 'total': len(executed)})


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
