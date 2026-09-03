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

def notify_goal_progress():
    from django.utils import timezone
    from users.services import send_push_notification
    from planning.models import Goal

    today = timezone.now().date()

    # Busca caixinhas que ainda estão no prazo (ativas)
    active_goals = Goal.objects.filter(
        end_date__gte=today
    ).select_related('user')

    for goal in active_goals:
        if goal.target_amount <= 0:
            continue
            
        percentage = (goal.current_amount / goal.target_amount) * 100

        # Verifica meta atingida (100%)
        if percentage >= 100 and not goal.is_completed_notified:
            title = "Parabéns, Meta Atingida! 🏆"
            body = f"Você alcançou 100% da sua meta '{goal.name}'!"
            send_push_notification(goal.user, title, body, url='/planning/')
            
            goal.is_completed_notified = True
            # Se atingiu 100% tão rápido que nem passou pelo 90%, marca os dois
            goal.is_near_target_notified = True 
            goal.save(update_fields=['is_completed_notified', 'is_near_target_notified', 'updated_at'])
            
        # Verifica quase atingida (>= 90% e < 100%)
        elif 90 <= percentage < 100 and not goal.is_near_target_notified:
            title = "Falta pouco! 🎯"
            body = f"Sua caixinha '{goal.name}' já atingiu {percentage:.0f}% da meta!"
            send_push_notification(goal.user, title, body, url='/planning/')
            
            goal.is_near_target_notified = True
            goal.save(update_fields=['is_near_target_notified', 'updated_at'])
