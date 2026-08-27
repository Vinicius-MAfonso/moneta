from decimal import Decimal

from django.db import models
from django.db.models import OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from moneta.common import TransactionType
from planning.models import Budget, Goal
from transactions.models import Transaction


def calculate_budget_progress(budget):
    transactions = Transaction.objects.filter(
        user=budget.user,
        date__gte=budget.start_date,
        date__lte=budget.end_date,
        status=Transaction.Statuses.COMPLETED,
        category__type=TransactionType.EXPENSE
    ).filter(
        models.Q(category=budget.category) | models.Q(category__parent=budget.category)
    )
    
    spent = transactions.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
    
    if budget.amount > 0:
        percentage = (spent / budget.amount) * Decimal('100.00')
    else:
        percentage = Decimal('100.00') if spent > 0 else Decimal('0.00')
        
    return {
        'budget': budget,
        'spent': spent,
        'remaining': max(Decimal('0.00'), budget.amount - spent),
        'percentage': min(percentage, Decimal('100.00')),
        'real_percentage': percentage,
        'is_over_budget': spent >= budget.amount,
        'is_warning': (spent / budget.amount) >= Decimal('0.8') if budget.amount > 0 else False
    }


def get_active_budgets(user, reference_date=None):
    if not reference_date:
        reference_date = timezone.now().date()
        
    budgets = Budget.objects.filter(
        user=user,
        start_date__lte=reference_date,
        end_date__gte=reference_date
    ).select_related('category')
    
    progress_list = []
    for b in budgets:
        progress_list.append(calculate_budget_progress(b))
        
    progress_list.sort(key=lambda x: x['real_percentage'], reverse=True)
    return progress_list


def get_budgets_with_progress(user):
    transactions_subquery = Transaction.objects.filter(
        user=user,
        date__gte=OuterRef('start_date'),
        date__lte=OuterRef('end_date'),
        status=Transaction.Statuses.COMPLETED,
        category__type=TransactionType.EXPENSE,
    ).filter(
        Q(category=OuterRef('category')) | Q(category__parent=OuterRef('category'))
    ).values('user').annotate(
        total_spent=Sum('amount')
    ).values('total_spent')

    budgets = Budget.objects.filter(user=user).select_related('category').annotate(
        spent_annotated=Coalesce(Subquery(transactions_subquery), Decimal('0.00'))
    ).order_by('-start_date')
    
    result = []
    for b in budgets:
        spent = b.spent_annotated
        pct = (spent / b.amount * Decimal('100.00')) if b.amount > 0 else (Decimal('100.00') if spent > 0 else Decimal('0.00'))
        
        b.spent = spent
        b.remaining = max(Decimal('0.00'), b.amount - spent)
        b.real_percentage = pct
        b.percentage = round(pct, 1)
        b.bounded_pct = min(pct, Decimal('100.00'))
        b.bounded_pct_str = str(round(b.bounded_pct, 2))
        result.append(b)
        
    return result


def create_budget(user, category_id, amount, start_date, end_date=None):
    if not end_date:
        raise ValueError("A data de término é obrigatória.")
        
    return Budget.objects.create(
        user=user,
        category_id=category_id,
        amount=amount,
        start_date=start_date,
        end_date=end_date
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
