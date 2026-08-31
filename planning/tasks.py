from django.db import models
from django.utils import timezone

from planning.models import Budget
from planning.services import calculate_budgets_progress_bulk, get_month_range
from users.services import send_push_notification


def notify_budget_warnings():
    today = timezone.now().date()
    month_start, month_end = get_month_range(today)

    # 1. Reset warning notification flag for recurring monthly budgets in a new month
    Budget.objects.filter(
        is_recurring=True,
        is_warning_notified=True,
        updated_at__date__lt=month_start,
    ).update(is_warning_notified=False)

    # 2. Fetch all unnotified active budgets for the current period
    active_budgets = list(
        Budget.objects.filter(
            models.Q(is_warning_notified=False) & (
                models.Q(is_recurring=True, start_date__lte=month_end) |
                models.Q(is_recurring=False, start_date__lte=today, end_date__gte=today)
            )
        ).select_related('user', 'category')
    )

    if not active_budgets:
        return

    # 3. Calculate progress in bulk to eliminate N+1 queries
    progress_list = calculate_budgets_progress_bulk(active_budgets, reference_date=today)

    for progress in progress_list:
        if progress['is_warning']:
            budget = progress['budget']
            user = budget.user
            title = "Atenção ao Orçamento!"
            body = f"Você já consumiu {progress['percentage']:.0f}% do seu orçamento de {budget.category.name}."
            
            send_push_notification(user, title, body, url='/planning/')
            
            budget.is_warning_notified = True
            budget.save(update_fields=['is_warning_notified', 'updated_at'])
