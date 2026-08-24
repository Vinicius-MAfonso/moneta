import hmac
import logging
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from moneta.common import TransactionType, get_month_calendar_grid, get_month_context
from planning.models import Goal
from planning.services import get_active_budgets
from transactions.models import Transaction
from wallets.models import Account

from .services import get_category_breakdown

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
    from wallets.tasks import notify_due_credit_card_bills
    try:
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
    from planning.tasks import notify_budget_warnings
    try:
        notify_budget_warnings()
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
def cron_check_alerts_view(request):
    """Executa a checagem e envio de alertas por e-mail de forma síncrona."""
    if not _verify_cron_auth(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    from moneta.tasks import check_and_send_alerts
    try:
        check_and_send_alerts()
        return JsonResponse({'status': 'ok', 'task': 'check_and_send_alerts'})
    except Exception:
        logger.exception("Erro ao verificar alertas via cron.")
        return JsonResponse({'status': 'error', 'message': 'Falha ao verificar alertas.'}, status=500)


@csrf_exempt
@require_POST
def cron_wake_view(request):
    """Endpoint unificado / run-all para executar todas as tarefas agendadas de forma síncrona."""
    if not _verify_cron_auth(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    from moneta.tasks import check_and_send_alerts
    from planning.tasks import notify_budget_warnings
    from transactions.tasks import notify_due_transactions, process_all_recurring_transactions
    from wallets.tasks import notify_due_credit_card_bills

    tasks = [
        ('process_all_recurring_transactions', process_all_recurring_transactions),
        ('notify_due_credit_card_bills', notify_due_credit_card_bills),
        ('notify_budget_warnings', notify_budget_warnings),
        ('notify_due_transactions', notify_due_transactions),
        ('check_and_send_alerts', check_and_send_alerts),
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
    user = request.user

    month_param = request.GET.get('month')
    account_id_param = request.GET.get('account_id')
    month_ctx = get_month_context(month_param)

    from django_q.tasks import async_task
    async_task('transactions.services.process_recurring_transactions', user, month_ctx['end_date'])

    accounts_qs = Account.objects.filter(user=user, active=True).exclude(type=Account.Types.CREDIT_CARD)
    from wallets.services import get_expected_balances_bulk
    
    expected_balances = get_expected_balances_bulk(accounts_qs, month_ctx['end_date'])
    
    accounts = []
    total_balance = Decimal('0.00')
    total_expected_balance = Decimal('0.00')
    
    for account in accounts_qs:
        account.expected_balance = expected_balances.get(account.id, account.balance)
        accounts.append(account)
        if account.type != Account.Types.CREDIT_CARD:
            total_balance += account.balance
            total_expected_balance += account.expected_balance

    selected_account = None
    if account_id_param:
        selected_account = next((a for a in accounts if str(a.id) == account_id_param), None)

    if selected_account:
        total_balance = selected_account.balance
        total_expected_balance = selected_account.expected_balance
        base_tx_qs = Transaction.objects.filter(user=user, account=selected_account)
    else:
        base_tx_qs = Transaction.objects.filter(user=user)

    monthly_income = base_tx_qs.filter(
        category__type=TransactionType.INCOME,
        date__range=(month_ctx['start_date'], month_ctx['end_date']),
    ).aggregate(total=Coalesce(Sum('amount'), Decimal('0.00')))['total']

    monthly_expense = base_tx_qs.filter(
        category__type=TransactionType.EXPENSE,
        date__range=(month_ctx['start_date'], month_ctx['end_date']),
    ).aggregate(total=Coalesce(Sum('amount'), Decimal('0.00')))['total']

    monthly_net_balance = monthly_income - monthly_expense

    economy_pct = Decimal('0.00')
    if monthly_income > 0:
        economy_pct = (monthly_expense / monthly_income) * 100
    elif monthly_expense > 0:
        economy_pct = Decimal('100.00')
        
    economy_pct_clamped = min(economy_pct, Decimal('100.00'))
    if economy_pct >= 100:
        economy_status = 'danger'
        economy_message = f"Cuidado! Este mês você gastou R$ {monthly_expense - monthly_income:.2f} a mais do que ganhou."
    elif economy_pct >= 80:
        economy_status = 'warning'
        economy_message = "Atenção! Você já gastou a maior parte da sua renda neste mês."
    else:
        economy_status = 'success'
        economy_message = "Você está no verde! Seus gastos estão controlados."

    recent_transactions = base_tx_qs.filter(
        date__range=(month_ctx['start_date'], month_ctx['end_date'])
    ).select_related('account', 'category').prefetch_related('tags').order_by('-date', '-created_at')[:6]

    goals = Goal.objects.filter(user=user)[:3]

    active_budgets = get_active_budgets(user, month_ctx['start_date'])
    top_budgets = active_budgets[:3]

    expenses_by_category = get_category_breakdown(base_tx_qs, TransactionType.EXPENSE, month_ctx['start_date'], month_ctx['end_date'])

    incomes_by_category = get_category_breakdown(base_tx_qs, TransactionType.INCOME, month_ctx['start_date'], month_ctx['end_date'])

    calendar_grid = get_month_calendar_grid(user, month_ctx['start_date'], month_ctx['end_date'], account=selected_account)

    current_year = month_ctx['year']
    current_month_num = month_ctx['month_num']
    
    start_m_num = current_month_num - 5
    start_y_num = current_year
    while start_m_num < 1:
        start_m_num += 12
        start_y_num -= 1
        
    six_months_start = get_month_context(f"{start_y_num}-{start_m_num:02d}")['start_date']
    
    monthly_stats = base_tx_qs.filter(
        date__range=(six_months_start, month_ctx['end_date']),
    ).annotate(
        month=TruncMonth('date')
    ).values('month', 'category__type').annotate(
        total=Sum('amount')
    ).order_by('month')

    stats_dict = {}
    for stat in monthly_stats:
        m_key = f"{stat['month'].year}-{stat['month'].month:02d}"
        if m_key not in stats_dict:
            stats_dict[m_key] = {'income': Decimal('0.00'), 'expense': Decimal('0.00')}
        if stat['category__type'] == TransactionType.INCOME:
            stats_dict[m_key]['income'] += stat['total']
        elif stat['category__type'] == TransactionType.EXPENSE:
            stats_dict[m_key]['expense'] += stat['total']

    chart_labels = []
    chart_incomes = []
    chart_expenses = []
    chart_balances = []

    for i in range(5, -1, -1):
        m_num = current_month_num - i
        y_num = current_year
        while m_num < 1:
            m_num += 12
            y_num -= 1

        m_ctx = get_month_context(f"{y_num}-{m_num:02d}")
        chart_labels.append(m_ctx['month_label'])
        m_key = f"{y_num}-{m_num:02d}"
        
        inc = float(stats_dict.get(m_key, {}).get('income', 0))
        exp = float(stats_dict.get(m_key, {}).get('expense', 0))
        chart_incomes.append(inc)
        chart_expenses.append(exp)
        chart_balances.append(inc - exp)

    context = {
        'total_balance': total_balance,
        'total_expected_balance': total_expected_balance,
        'monthly_income': monthly_income,
        'monthly_expense': monthly_expense,
        'monthly_net_balance': monthly_net_balance,
        'economy_pct': economy_pct,
        'economy_pct_clamped': economy_pct_clamped,
        'economy_status': economy_status,
        'economy_message': economy_message,
        'accounts': accounts,
        'selected_account': selected_account,
        'selected_account_id': str(selected_account.id) if selected_account else '',
        'recent_transactions': recent_transactions,
        'goals': goals,
        'top_budgets': top_budgets,
        'month_info': month_ctx,
        'expenses_by_category': expenses_by_category,
        'incomes_by_category': incomes_by_category,
        'calendar_grid': calendar_grid,
        'chart_labels': chart_labels,
        'chart_incomes': [float(v) for v in chart_incomes],
        'chart_expenses': [float(v) for v in chart_expenses],
        'chart_balances': [float(v) for v in chart_balances],
    }
    return render(request, 'dashboard.html', context)


@login_required(login_url='users_web:login')
def reports_view(request):
    import datetime

    from django.utils import timezone

    from .services import get_report_data
    
    user = request.user
    today = timezone.now().date()
    default_start = today - datetime.timedelta(days=30)
    
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    try:
        start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else default_start
        end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else today
    except (ValueError, TypeError):
        start_date = default_start
        end_date = today

    report_data = get_report_data(user, start_date, end_date)
    
    pie_data = [float(item['total']) for item in report_data['expenses_by_category']]
    
    context = {
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'report_data': report_data,
        'chart_labels': report_data['timeline_labels'],
        'chart_incomes': [float(v) for v in report_data['timeline_incomes']],
        'chart_expenses': [float(v) for v in report_data['timeline_expenses']],
        'pie_labels': [item['name'] for item in report_data['expenses_by_category']],
        'pie_data': pie_data,
        'pie_colors': [item['color'] for item in report_data['expenses_by_category']],
    }
    
    return render(request, 'moneta/reports.html', context)


@login_required(login_url='users_web:login')
def export_transactions_csv_view(request):
    import datetime

    from django.utils import timezone

    from .services import generate_csv_export
    
    user = request.user
    today = timezone.now().date()
    default_start = today - datetime.timedelta(days=30)
    
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    try:
        start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else default_start
        end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else today
    except (ValueError, TypeError):
        start_date = default_start
        end_date = today

    from transactions.models import Transaction

    transactions = Transaction.objects.filter(
        user=user,
        date__gte=start_date,
        date__lte=end_date,
    ).select_related('category', 'account').order_by('-date', '-created_at')

    return generate_csv_export(transactions)
