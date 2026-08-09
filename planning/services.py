from decimal import Decimal
from django.db import models
from django.utils import timezone

def calculate_budget_progress(budget):
    from transactions.models import Transaction
    from moneta.common import TransactionType
    
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
    from planning.models import Budget
    if not reference_date:
        reference_date = timezone.now().date()
        
    budgets = Budget.objects.filter(
        user=user,
        start_date__lte=reference_date,
        end_date__gte=reference_date
    )
    
    progress_list = []
    for b in budgets:
        progress_list.append(calculate_budget_progress(b))
        
    progress_list.sort(key=lambda x: x['real_percentage'], reverse=True)
    return progress_list
