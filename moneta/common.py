import calendar
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db import models
from django.utils import timezone


class TransactionType(models.TextChoices):
    INCOME = 'receita', 'Receita'
    EXPENSE = 'despesa', 'Despesa'
    TRANSFER = 'transferência', 'Transferência'


RECURRING_TRANSACTION_TYPE_CHOICES = [
    choice for choice in TransactionType.choices if choice[0] != TransactionType.TRANSFER
]


MONTH_NAMES_PT = [
    'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
]


def get_month_context(month_str=None):
    today = timezone.now().date()
    if not month_str:
        year = today.year
        month_num = today.month
    else:
        try:
            parts = month_str.split('-')
            year = int(parts[0])
            month_num = int(parts[1])
        except (ValueError, TypeError, IndexError):
            year = today.year
            month_num = today.month

    if month_num < 1:
        month_num = 1
    elif month_num > 12:
        month_num = 12

    _, last_day = calendar.monthrange(year, month_num)
    start_date = date(year, month_num, 1)
    end_date = date(year, month_num, last_day)

    if month_num == 1:
        prev_month = f"{year - 1}-12"
    else:
        prev_month = f"{year}-{month_num - 1:02d}"

    if month_num == 12:
        next_month = f"{year + 1}-01"
    else:
        next_month = f"{year}-{month_num + 1:02d}"

    month_label = f"{MONTH_NAMES_PT[month_num - 1]} {year}"
    current_month_str = f"{year}-{month_num:02d}"

    return {
        'current_month_str': current_month_str,
        'month_label': month_label,
        'prev_month': prev_month,
        'next_month': next_month,
        'start_date': start_date,
        'end_date': end_date,
        'year': year,
        'month_num': month_num,
    }


def get_month_calendar_grid(user, start_date, end_date, account=None):
    """
    Builds a 7-column calendar matrix (Sunday to Saturday) for the given month range
    annotated with daily income and expense totals (both completed and pending).
    Completed = realizado; Pending = previsto.
    """
    from django.db.models import Sum

    from transactions.models import Transaction

    # Busca TODAS as transações do mês, sem filtrar por status
    qs = Transaction.objects.filter(
        user=user,
        date__range=(start_date, end_date),
    ).exclude(category__type=TransactionType.TRANSFER)

    if account:
        qs = qs.filter(account=account)

    daily_txs = (
        qs.values('date', 'category__type', 'status')
        .annotate(total=Sum('amount'))
    )

    daily_totals = defaultdict(lambda: {
        'income_done': Decimal('0.00'),
        'expense_done': Decimal('0.00'),
        'income_pending': Decimal('0.00'),
        'expense_pending': Decimal('0.00'),
    })

    for item in daily_txs:
        d_str = item['date'].strftime('%Y-%m-%d')
        c_type = item['category__type']
        is_done = (item['status'] == Transaction.Statuses.COMPLETED)

        if c_type == TransactionType.INCOME:
            if is_done:
                daily_totals[d_str]['income_done'] += item['total']
            else:
                daily_totals[d_str]['income_pending'] += item['total']
        elif c_type == TransactionType.EXPENSE:
            if is_done:
                daily_totals[d_str]['expense_done'] += item['total']
            else:
                daily_totals[d_str]['expense_pending'] += item['total']

    cal = calendar.Calendar(firstweekday=6)  # Domingo = 6
    month_days = list(cal.itermonthdays4(start_date.year, start_date.month))

    grid = []
    today_date = timezone.now().date()
    for year, month, day, _ in month_days:
        day_date = date(year, month, day)
        d_str = day_date.strftime('%Y-%m-%d')
        is_current_month = (month == start_date.month)
        totals = daily_totals.get(d_str, {
            'income_done': Decimal('0.00'),
            'expense_done': Decimal('0.00'),
            'income_pending': Decimal('0.00'),
            'expense_pending': Decimal('0.00'),
        })

        has_data = any(v > 0 for v in totals.values())

        grid.append({
            'day': day,
            'date_str': d_str,
            'is_current_month': is_current_month,
            'is_today': (day_date == today_date),
            'income_done': totals['income_done'],
            'expense_done': totals['expense_done'],
            'income_pending': totals['income_pending'],
            'expense_pending': totals['expense_pending'],
            # totais combinados (para compatibilidade)
            'income': totals['income_done'] + totals['income_pending'],
            'expense': totals['expense_done'] + totals['expense_pending'],
            'has_data': has_data,
        })

    return grid