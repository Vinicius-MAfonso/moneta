import csv
import datetime
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce, TruncDay, TruncMonth
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date


def get_category_breakdown(base_tx_qs, tx_type, start_date, end_date):
    qs = base_tx_qs.filter(
        category__type=tx_type,
        date__range=(start_date, end_date),
    ).values('category__name', 'category__color').annotate(total=Sum('amount')).order_by('-total')

    total_amount = sum(item['total'] for item in qs)

    return [
        {
            'name': item['category__name'],
            'color': item['category__color'],
            'total': item['total'],
            'percentage': round((item['total'] / total_amount * 100), 1) if total_amount > 0 else 0,
        }
        for item in qs
    ]


def get_dashboard_data(user, month_param=None, account_id_param=None):
    from django_q.tasks import async_task

    from moneta.common import (
        TransactionType,
        get_month_calendar_grid,
        get_month_context,
    )
    from planning.models import Goal
    from planning.services import get_active_budgets
    from transactions.models import Transaction
    from wallets.models import Account
    from wallets.services import get_expected_balances_bulk

    month_ctx = get_month_context(month_param)

    async_task('transactions.services.process_recurring_transactions', user, month_ctx['end_date'])

    accounts_qs = Account.objects.filter(user=user, active=True).exclude(type=Account.Types.CREDIT_CARD)
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

    monthly_totals = base_tx_qs.filter(
        date__range=(month_ctx['start_date'], month_ctx['end_date']),
    ).aggregate(
        income=Coalesce(Sum('amount', filter=Q(category__type=TransactionType.INCOME)), Decimal('0.00')),
        expense=Coalesce(Sum('amount', filter=Q(category__type=TransactionType.EXPENSE)), Decimal('0.00')),
    )
    monthly_income = monthly_totals['income']
    monthly_expense = monthly_totals['expense']
    monthly_net_balance = monthly_income - monthly_expense

    economy_pct = Decimal('0.00')
    if monthly_income > 0:
        economy_pct = (monthly_expense / monthly_income) * 100
    elif monthly_expense > 0:
        economy_pct = Decimal('100.00')

    economy_pct_clamped = min(economy_pct, Decimal('100.00'))
    if economy_pct >= 100:
        economy_status = 'danger'
        diff_str = f"{monthly_expense - monthly_income:.2f}".replace('.', ',')
        economy_message = f"Cuidado! Este mês você gastou R$ {diff_str} a mais do que ganhou."
    elif economy_pct >= 80:
        economy_status = 'warning'
        economy_message = "Atenção! Você já gastou a maior parte da sua renda neste mês."
    else:
        economy_status = 'success'
        economy_message = "Você está no verde! Seus gastos estão controlados."

    recent_qs = base_tx_qs.filter(
        date__range=(month_ctx['start_date'], month_ctx['end_date'])
    )
    if not selected_account:
        recent_qs = recent_qs.exclude(transfer_in__isnull=False, account__type=Account.Types.CREDIT_CARD)

    recent_transactions = (
        recent_qs.select_related('account', 'category')
        .prefetch_related('tags')
        .order_by('-date', '-created_at')[:6]
    )

    goals = Goal.objects.filter(user=user)[:3]
    active_budgets = get_active_budgets(user, month_ctx['start_date'])
    top_budgets = active_budgets[:3]

    expenses_by_category = get_category_breakdown(
        base_tx_qs, TransactionType.EXPENSE, month_ctx['start_date'], month_ctx['end_date']
    )
    incomes_by_category = get_category_breakdown(
        base_tx_qs, TransactionType.INCOME, month_ctx['start_date'], month_ctx['end_date']
    )

    calendar_grid = get_month_calendar_grid(
        user, month_ctx['start_date'], month_ctx['end_date'], account=selected_account
    )

    six_months_start = month_ctx['start_date'] - relativedelta(months=5)

    monthly_stats = (
        base_tx_qs.filter(date__range=(six_months_start, month_ctx['end_date']))
        .annotate(month=TruncMonth('date'))
        .values('month', 'category__type')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )

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
        target_month_date = month_ctx['start_date'] - relativedelta(months=i)
        m_key = target_month_date.strftime('%Y-%m')
        m_ctx = get_month_context(m_key)
        chart_labels.append(m_ctx['month_label'])

        inc = float(stats_dict.get(m_key, {}).get('income', 0))
        exp = float(stats_dict.get(m_key, {}).get('expense', 0))
        chart_incomes.append(inc)
        chart_expenses.append(exp)
        chart_balances.append(inc - exp)

    return {
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
        'chart_incomes': chart_incomes,
        'chart_expenses': chart_expenses,
        'chart_balances': chart_balances,
    }


def parse_report_dates(start_date_str=None, end_date_str=None):
    today = timezone.localdate()
    default_start = today - datetime.timedelta(days=30)

    parsed_start = parse_date(start_date_str) if isinstance(start_date_str, str) else None
    parsed_end = parse_date(end_date_str) if isinstance(end_date_str, str) else None

    start_date = parsed_start or default_start
    end_date = parsed_end or today

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    return start_date, end_date


def get_report_data(user, start_date, end_date):
    from moneta.common import TransactionType
    from transactions.models import Transaction

    transactions = Transaction.objects.filter(
        user=user,
        date__gte=start_date,
        date__lte=end_date,
    ).select_related('category', 'account')

    non_transfer_txs = transactions.exclude(category__type=TransactionType.TRANSFER)

    totals = non_transfer_txs.aggregate(
        income=Coalesce(Sum('amount', filter=Q(category__type=TransactionType.INCOME)), Decimal('0.00')),
        expense=Coalesce(Sum('amount', filter=Q(category__type=TransactionType.EXPENSE)), Decimal('0.00')),
    )
    total_income = totals['income']
    total_expense = totals['expense']
    net_savings = total_income - total_expense

    expenses_by_category = get_category_breakdown(non_transfer_txs, TransactionType.EXPENSE, start_date, end_date)

    delta_days = (end_date - start_date).days
    timeline_dict = {}

    if delta_days <= 60:
        daily_stats = (
            non_transfer_txs.annotate(period=TruncDay('date'))
            .values('period', 'category__type')
            .annotate(total=Sum('amount'))
            .order_by('period')
        )

        for stat in daily_stats:
            p_key = stat['period'].strftime('%Y-%m-%d')
            if p_key not in timeline_dict:
                timeline_dict[p_key] = {'income': Decimal('0.00'), 'expense': Decimal('0.00')}
            if stat['category__type'] == TransactionType.INCOME:
                timeline_dict[p_key]['income'] += stat['total']
            elif stat['category__type'] == TransactionType.EXPENSE:
                timeline_dict[p_key]['expense'] += stat['total']

        timeline_labels = []
        timeline_incomes = []
        timeline_expenses = []

        current = start_date
        while current <= end_date:
            p_key = current.strftime('%Y-%m-%d')
            timeline_labels.append(current.strftime('%d/%m'))
            timeline_incomes.append(float(timeline_dict.get(p_key, {}).get('income', 0)))
            timeline_expenses.append(float(timeline_dict.get(p_key, {}).get('expense', 0)))
            current += datetime.timedelta(days=1)

    else:
        monthly_stats = (
            non_transfer_txs.annotate(period=TruncMonth('date'))
            .values('period', 'category__type')
            .annotate(total=Sum('amount'))
            .order_by('period')
        )

        for stat in monthly_stats:
            p_key = stat['period'].strftime('%Y-%m-01')
            label = stat['period'].strftime('%m/%Y')
            if p_key not in timeline_dict:
                timeline_dict[p_key] = {'income': Decimal('0.00'), 'expense': Decimal('0.00'), 'label': label}
            if stat['category__type'] == TransactionType.INCOME:
                timeline_dict[p_key]['income'] += stat['total']
            elif stat['category__type'] == TransactionType.EXPENSE:
                timeline_dict[p_key]['expense'] += stat['total']

        timeline_labels = []
        timeline_incomes = []
        timeline_expenses = []

        for p_key in sorted(timeline_dict.keys()):
            timeline_labels.append(timeline_dict[p_key]['label'])
            timeline_incomes.append(float(timeline_dict[p_key]['income']))
            timeline_expenses.append(float(timeline_dict[p_key]['expense']))

    top_transactions = non_transfer_txs.filter(category__type=TransactionType.EXPENSE).order_by('-amount')[:10]

    return {
        'total_income': total_income,
        'total_expense': total_expense,
        'net_savings': net_savings,
        'expenses_by_category': expenses_by_category,
        'timeline_labels': timeline_labels,
        'timeline_incomes': timeline_incomes,
        'timeline_expenses': timeline_expenses,
        'top_transactions': top_transactions,
    }


def get_export_transactions(user, start_date, end_date):
    from transactions.models import Transaction
    from wallets.models import Account

    return (
        Transaction.objects.filter(
            user=user,
            date__gte=start_date,
            date__lte=end_date,
        )
        .exclude(transfer_in__isnull=False, account__type=Account.Types.CREDIT_CARD)
        .select_related('category', 'account')
        .order_by('-date', '-created_at')
    )


def generate_csv_export(transactions):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="relatorio_transacoes.csv"'
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow(['Data', 'Descrição', 'Categoria', 'Tipo', 'Conta', 'Status', 'Valor'])

    for tx in transactions:
        writer.writerow([
            tx.date.strftime('%d/%m/%Y'),
            tx.description,
            tx.category.name,
            tx.category.get_type_display(),
            tx.account.name,
            tx.get_status_display(),
            f"{tx.amount:.2f}".replace('.', ','),
        ])

    return response
