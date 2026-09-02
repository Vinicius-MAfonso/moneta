import calendar
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction as db_transaction
from django.utils import timezone
from django.utils.html import strip_tags

from moneta.common import TransactionType
from planning.models import Budget, Goal
from transactions.models import Category, Transaction
from wallets.models import Account


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


def calculate_budgets_progress_bulk(budgets, reference_date=None):
    """
    Calculates progress for a list of budgets in a single database query.
    """
    if not budgets:
        return []

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
    user = budgets[0].user if budgets else None
    if not user:
        return []

    category_ids = {b.category_id for b in budgets}
    start_dates = []
    end_dates = []
    budget_periods = {}

    for b in budgets:
        if b.is_recurring:
            p_start, p_end = month_start, month_end
        else:
            p_start, p_end = b.start_date, b.end_date
        budget_periods[b.id] = (p_start, p_end)
        if p_start:
            start_dates.append(p_start)
        if p_end:
            end_dates.append(p_end)

    min_start = min(start_dates) if start_dates else None
    max_end = max(end_dates) if end_dates else None

    tx_filters = {
        'user': user,
        'status': Transaction.Statuses.COMPLETED,
        'category__type': TransactionType.EXPENSE,
    }
    if min_start:
        tx_filters['date__gte'] = min_start
    if max_end:
        tx_filters['date__lte'] = max_end

    raw_txs = list(
        Transaction.objects.filter(**tx_filters)
        .filter(
            models.Q(category_id__in=category_ids) |
            models.Q(category__parent_id__in=category_ids)
        )
        .values('category_id', 'category__parent_id', 'date', 'amount')
    )

    progress_list = []
    for b in budgets:
        p_start, p_end = budget_periods[b.id]
        cat_id = b.category_id

        spent = Decimal('0.00')
        for tx in raw_txs:
            if tx['category_id'] == cat_id or tx['category__parent_id'] == cat_id:
                tx_date = tx['date']
                if (p_start is None or tx_date >= p_start) and (p_end is None or tx_date <= p_end):
                    spent += tx['amount']

        if b.amount > 0:
            percentage = (spent / b.amount) * Decimal('100.00')
        else:
            percentage = Decimal('100.00') if spent > 0 else Decimal('0.00')

        bounded_pct = min(percentage, Decimal('100.00'))

        progress_list.append({
            'budget': b,
            'spent': spent,
            'remaining': max(Decimal('0.00'), b.amount - spent),
            'overspent': max(Decimal('0.00'), spent - b.amount),
            'percentage': round(percentage, 1),
            'real_percentage': percentage,
            'bounded_pct': bounded_pct,
            'bounded_pct_str': str(round(bounded_pct, 2)),
            'is_over_budget': spent >= b.amount,
            'is_warning': (spent / b.amount) >= Decimal('0.8') if b.amount > 0 else False,
            'period_start': p_start,
            'period_end': p_end,
        })

    return progress_list


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
        user=user,
        category__type=TransactionType.EXPENSE,
    ).filter(
        models.Q(is_recurring=True) |
        (models.Q(is_recurring=False) & models.Q(start_date__lte=month_end) & models.Q(end_date__gte=month_start))
    ).select_related('category')

    return calculate_budgets_progress_bulk(budgets, reference_date=reference_date)


def get_budgets_with_progress(user, reference_date=None):
    if not reference_date:
        reference_date = timezone.now().date()

    budgets = list(
        Budget.objects.filter(user=user)
        .select_related('category')
        .order_by('-is_recurring', '-created_at')
    )

    progress_list = calculate_budgets_progress_bulk(budgets, reference_date=reference_date)

    result = []
    for prog in progress_list:
        b = prog['budget']
        b.spent = prog['spent']
        b.remaining = prog['remaining']
        b.overspent = prog['overspent']
        b.real_percentage = prog['real_percentage']
        b.percentage = prog['percentage']
        b.bounded_pct = prog['bounded_pct']
        b.bounded_pct_str = prog['bounded_pct_str']
        b.is_over_budget = prog['is_over_budget']
        b.is_warning = prog['is_warning']
        result.append(b)

    return result

def create_budget(user, category_id, amount, is_recurring=True, start_date=None, end_date=None):
    category = Category.objects.filter(id=category_id, user=user).first()
    if not category:
        raise ValidationError("Categoria inválida ou não encontrada.")

    if start_date is None:
        start_date = timezone.now().date()

    if not is_recurring and not end_date:
        raise ValidationError("A data de término é obrigatória para orçamentos pontuais.")

    return Budget.objects.create(
        user=user,
        category=category,
        amount=amount,
        is_recurring=is_recurring,
        start_date=start_date,
        end_date=end_date if not is_recurring else None,
    )


def delete_budget(budget):
    budget.delete()


def create_goal(user, name, target_amount, current_amount, start_date, end_date=None, account=None):
    name = strip_tags(name).strip() if name else name

    if not end_date:
        raise ValidationError("A data de término é obrigatória.")
        
    if account and account.user_id != user.id:
        raise ValidationError("Conta inválida para este usuário.")

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
    Deposit the given amount to the specified goal using row-level locking and atomic transaction.
    """
    if amount <= 0:
        raise ValueError("O valor do depósito deve ser maior que zero.")

    with db_transaction.atomic():
        locked_goal = Goal.objects.select_for_update().get(pk=goal.pk)
        if locked_goal.account_id:
            account = Account.objects.select_for_update().get(pk=locked_goal.account_id)
            if amount > account.free_balance:
                bal_str = f"{account.free_balance:.2f}".replace('.', ',')
                raise ValueError(f"Saldo livre insuficiente na conta '{account.name}'. Saldo disponível: R$ {bal_str}.")

        Goal.objects.filter(pk=locked_goal.pk).update(
            current_amount=models.F('current_amount') + amount
        )
    return True
