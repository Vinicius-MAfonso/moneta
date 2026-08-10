import json
from decimal import Decimal
from django.shortcuts import render
from django.db.models import Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.contrib.auth.decorators import login_required

from wallets.models import Account
from transactions.models import Transaction
from planning.models import Goal
from moneta.common import TransactionType, get_month_context, get_month_calendar_grid
from transactions.services import process_recurring_transactions
from wallets.services import recalculate_all_user_balances
from planning.services import get_active_budgets
from .services import get_category_breakdown


@login_required(login_url='users_web:login')
def dashboard_view(request):
    user = request.user

    month_param = request.GET.get('month')
    account_id_param = request.GET.get('account_id')
    month_ctx = get_month_context(month_param)

    # Processa transações recorrentes para o usuário até o final do mês selecionado
    process_recurring_transactions(user, month_ctx['end_date'])

    # Recalcula o saldo real de todas as contas
    recalculate_all_user_balances(user)
    accounts_qs = Account.objects.filter(user=user, active=True).select_related('credit_card_details')
    from wallets.services import calculate_expected_balance
    
    accounts = []
    total_balance = Decimal('0.00')
    total_expected_balance = Decimal('0.00')
    
    for account in accounts_qs:
        account.expected_balance = calculate_expected_balance(account, month_ctx['end_date'])
        accounts.append(account)
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
        # total_balance and total_expected_balance already summed
        base_tx_qs = Transaction.objects.filter(user=user)

    monthly_income = base_tx_qs.filter(
        category__type=TransactionType.INCOME,
        date__range=(month_ctx['start_date'], month_ctx['end_date']),
        status=Transaction.Statuses.COMPLETED
    ).aggregate(total=Coalesce(Sum('amount'), Decimal('0.00')))['total']

    monthly_expense = base_tx_qs.filter(
        category__type=TransactionType.EXPENSE,
        date__range=(month_ctx['start_date'], month_ctx['end_date']),
        status=Transaction.Statuses.COMPLETED
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

    # Budgets Overview
    active_budgets = get_active_budgets(user, month_ctx['start_date'])
    top_budgets = active_budgets[:3]

    # Category Breakdown for Expenses
    expenses_by_category = get_category_breakdown(base_tx_qs, TransactionType.EXPENSE, month_ctx['start_date'], month_ctx['end_date'])

    # Category Breakdown for Incomes
    incomes_by_category = get_category_breakdown(base_tx_qs, TransactionType.INCOME, month_ctx['start_date'], month_ctx['end_date'])

    # Monthly Calendar Grid
    calendar_grid = get_month_calendar_grid(user, month_ctx['start_date'], month_ctx['end_date'], account=selected_account)

    # 6-Month Cashflow Chart Data
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
        status=Transaction.Statuses.COMPLETED
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
        else:
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
    from .services import get_report_data
    from django.utils import timezone
    
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
    
    # Use floats for pie_data_json serialization
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
    from .services import get_report_data, generate_csv_export
    from django.utils import timezone
    
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
    return generate_csv_export(report_data['transactions_qs'])
