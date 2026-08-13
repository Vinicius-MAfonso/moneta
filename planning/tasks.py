from django.utils import timezone

from planning.models import Budget
from planning.services import calculate_budget_progress
from users.services import send_push_notification


def notify_budget_warnings():
    today = timezone.now().date()
    
    active_budgets = Budget.objects.filter(
        start_date__lte=today,
        end_date__gte=today,
        is_warning_notified=False
    ).select_related('user', 'category')
    
    for budget in active_budgets:
        progress = calculate_budget_progress(budget)
        
        if progress['is_warning']:
            user = budget.user
            title = "Atenção ao Orçamento!"
            body = f"Você já consumiu {progress['percentage']:.0f}% do seu orçamento de {budget.category.name}."
            
            send_push_notification(user, title, body, url='/planning/')
            
            budget.is_warning_notified = True
            budget.save(update_fields=['is_warning_notified', 'updated_at'])
