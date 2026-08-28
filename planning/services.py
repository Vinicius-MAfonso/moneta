import calendar
from datetime import date
from decimal import Decimal

from django.db import models
from django.utils import timezone

from moneta.common import TransactionType
from planning.models import Budget, Goal
from transactions.models import Transaction


def get_month_range(ref_date=None):
    if not ref_date:
        ref_date = timezone.now().date()
    elif isinstance(ref_date, str):
        if len(ref_date) == 7:  # 'YYYY-MM'
            parts = ref_date.split('-')
            ref_date = date(int(parts[0]), int(parts[1]), 1)
        else:
            parts = ref_date.split('-')
            ref_date = date(int(parts[0]), int(parts[1]), int(parts[2]))

    year = ref_date.year
    month = ref_date.month
    _, last_day = calendar.monthrange(year, month)
    return date(year, month, 1), date(year, month, last_day)


def calculate_budget_progress(budget, reference_date=None, start_date=None, end_date=None):
    if start_date and end_date:
        p_start = start_date
        p_end = end_date
    elif budget.is_recurring:
        p_start, p_end = get_month_range(reference_date)
    else:
        p_start = budget.start_date
        p_end = budget.end_date

    tx_filters = {
        'user': budget.user,
        'status': Transaction.Statuses.COMPLETED,
        'category__type': TransactionType.EXPENSE,
    }
    if p_start:
        tx_filters['date__gte'] = p_start
    if p_end:
        tx_filters['date__lte'] = p_end

    transactions = Transaction.objects.filter(**tx_filters).filter(
        models.Q(category=budget.category) | models.Q(category__parent=budget.category)
    )

    spent = transactions.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    if budget.amount > 0:
        percentage = (spent / budget.amount) * Decimal('100.00')
    else:
        percentage = Decimal('100.00') if spent > 0 else Decimal('0.00')

    bounded_pct = min(percentage, Decimal('100.00'))

    return {
        'budget': budget,
        'spent': spent,
        'remaining': max(Decimal('0.00'), budget.amount - spent),
        'percentage': round(percentage, 1),
        'real_percentage': percentage,
        'bounded_pct': bounded_pct,
        'bounded_pct_str': str(round(bounded_pct, 2)),
        'is_over_budget': spent >= budget.amount,
        'is_warning': (spent / budget.amount) >= Decimal('0.8') if budget.amount > 0 else False,
        'period_start': p_start,
        'period_end': p_end,
    }


def get_active_budgets(user, reference_date=None):
    if not reference_date:
        reference_date = timezone.now().date()
    elif isinstance(reference_date, str):
        if len(reference_date) == 7:
            p = reference_date.split('-')
            reference_date = date(int(p[0]), int(p[1]), 1)
        else:
            p = reference_date.split('-')
            reference_date = date(int(p[0]), int(p[1]), int(p[2]))

    month_start, month_end = get_month_range(reference_date)

    budgets = Budget.objects.filter(
        models.Q(user=user) & (
            models.Q(is_recurring=True, start_date__lte=month_end) |
            models.Q(is_recurring=False, start_date__lte=month_end, end_date__gte=month_start)
        )
    ).select_related('category')

    progress_list = []
    for b in budgets:
        progress_list.append(calculate_budget_progress(b, reference_date=reference_date))

    progress_list.sort(key=lambda x: x['real_percentage'], reverse=True)
    return progress_list


def get_budgets_with_progress(user, reference_date=None):
    if not reference_date:
        reference_date = timezone.now().date()

    budgets = Budget.objects.filter(user=user).select_related('category').order_by('-is_recurring', '-created_at')

    result = []
    for b in budgets:
        prog = calculate_budget_progress(b, reference_date=reference_date)
        b.spent = prog['spent']
        b.remaining = prog['remaining']
        b.real_percentage = prog['real_percentage']
        b.percentage = prog['percentage']
        b.bounded_pct = prog['bounded_pct']
        b.bounded_pct_str = prog['bounded_pct_str']
        b.is_over_budget = prog['is_over_budget']
        b.is_warning = prog['is_warning']
        result.append(b)

    return result


def create_budget(user, category_id, amount, is_recurring=True, start_date=None, end_date=None):
    if start_date is None:
        start_date = timezone.now().date()

    if not is_recurring and not end_date:
        raise ValueError("A data de término é obrigatória para orçamentos pontuais.")

    return Budget.objects.create(
        user=user,
        category_id=category_id,
        amount=amount,
        is_recurring=is_recurring,
        start_date=start_date,
        end_date=end_date if not is_recurring else None,
    )


def delete_budget(budget):
    budget.delete()


def create_goal(user, name, target_amount, current_amount, start_date, end_date=None, account=None):
    if not end_date:
        raise ValueError("A data de término é obrigatória.")
        
    return Goal.objects.create(
        user=user,
        account=account,
        name=name,
        target_amount=target_amount,
        current_amount=current_amount,
        start_date=start_date,
        end_date=end_date,
    )


def delete_goal(goal):
    goal.delete()


def deposit_to_goal(goal, amount):
    """
    Deposit the given amount to the specified goal.
    """
    if amount <= 0:
        return False
        
    if goal.account and amount > goal.account.free_balance:
        bal_str = f"{goal.account.free_balance:.2f}".replace('.', ',')
        raise ValueError(f"Saldo livre insuficiente na conta '{goal.account.name}'. Saldo disponível: R$ {bal_str}.")
        
    goal.__class__.objects.filter(pk=goal.pk).update(
        current_amount=models.F('current_amount') + amount
    )
    return True
