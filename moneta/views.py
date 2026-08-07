from decimal import Decimal
from django.shortcuts import render
from django.db.models import Sum
from django.contrib.auth.decorators import login_required

from wallets.models import Account
from transactions.models import Transaction
from planning.models import Goal
from moneta.common import TransactionType, get_month_context, get_month_calendar_grid
from transactions.services import process_recurring_transactions


@login_required(login_url='users_web:login')
def dashboard_view(request):
    user = request.user
    accounts = Account.objects.filter(user=user, active=True)
    total_balance = accounts.aggregate(total=Sum('balance'))['total'] or Decimal('0.00')

    month_param = request.GET.get('month')
    month_ctx = get_month_context(month_param)

    # Process recurring transactions for user up to selected month end
    process_recurring_transactions(user, month_ctx['end_date'])

    monthly_income = Transaction.objects.filter(
        user=user,
        category__type=TransactionType.INCOME,
        date__range=(month_ctx['start_date'], month_ctx['end_date']),
        status=Transaction.Statuses.COMPLETED
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    monthly_expense = Transaction.objects.filter(
        user=user,
        category__type=TransactionType.EXPENSE,
        date__range=(month_ctx['start_date'], month_ctx['end_date']),
        status=Transaction.Statuses.COMPLETED
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    monthly_net_balance = monthly_income - monthly_expense

    recent_transactions = Transaction.objects.filter(
        user=user,
        date__range=(month_ctx['start_date'], month_ctx['end_date'])
    ).select_related('account', 'category').order_by('-date', '-created_at')[:6]

    goals = Goal.objects.filter(user=user)[:3]

    # Category Breakdown for Expenses
    expenses_qs = (
        Transaction.objects.filter(
            user=user,
            category__type=TransactionType.EXPENSE,
            date__range=(month_ctx['start_date'], month_ctx['end_date']),
            status=Transaction.Statuses.COMPLETED
        )
        .values('category__name', 'category__color')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    expenses_by_category = []
    for item in expenses_qs:
        pct = (item['total'] / monthly_expense * 100) if monthly_expense > 0 else 0
        expenses_by_category.append({
            'name': item['category__name'],
            'color': item['category__color'],
            'total': item['total'],
            'percentage': round(pct, 1),
        })

    # Category Breakdown for Incomes
    incomes_qs = (
        Transaction.objects.filter(
            user=user,
            category__type=TransactionType.INCOME,
            date__range=(month_ctx['start_date'], month_ctx['end_date']),
            status=Transaction.Statuses.COMPLETED
        )
        .values('category__name', 'category__color')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    incomes_by_category = []
    for item in incomes_qs:
        pct = (item['total'] / monthly_income * 100) if monthly_income > 0 else 0
        incomes_by_category.append({
            'name': item['category__name'],
            'color': item['category__color'],
            'total': item['total'],
            'percentage': round(pct, 1),
        })

    # Monthly Calendar Grid
    calendar_grid = get_month_calendar_grid(user, month_ctx['start_date'], month_ctx['end_date'])

    context = {
        'total_balance': total_balance,
        'monthly_income': monthly_income,
        'monthly_expense': monthly_expense,
        'monthly_net_balance': monthly_net_balance,
        'accounts': accounts,
        'recent_transactions': recent_transactions,
        'goals': goals,
        'month_info': month_ctx,
        'expenses_by_category': expenses_by_category,
        'incomes_by_category': incomes_by_category,
        'calendar_grid': calendar_grid,
    }
    return render(request, 'dashboard.html', context)
