import datetime

from django.contrib import messages
from django.utils import timezone

from planning.services import get_active_budgets
from wallets.models import CreditCardBill


class DailyNotificationsMiddleware:
    """
    Middleware that runs once per day per user (tracked via session)
    and flashes toasts (Django messages) about upcoming bills and budgets near limit.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if hasattr(request, 'user') and request.user.is_authenticated:
            today_str = timezone.now().date().isoformat()
            last_alert = request.session.get('last_alert_date')

            if last_alert != today_str:
                self._generate_daily_alerts(request)
                request.session['last_alert_date'] = today_str
                
        return self.get_response(request)
        
    def _generate_daily_alerts(self, request):
        today = timezone.now().date()
        
        # 1. Verifica faturas vencendo nos próximos 5 dias
        upcoming_bills = CreditCardBill.objects.filter(
            account__user=request.user,
            status__in=[CreditCardBill.Statuses.OPEN, CreditCardBill.Statuses.CLOSED],
            due_date__lte=today + datetime.timedelta(days=5),
            due_date__gte=today
        )
        
        for bill in upcoming_bills:
            days_left = (bill.due_date - today).days
            if days_left == 0:
                msg = f"A fatura do seu cartão {bill.account.name} vence HOJE!"
                messages.warning(request, msg)
            elif days_left == 1:
                msg = f"A fatura do seu cartão {bill.account.name} vence amanhã!"
                messages.warning(request, msg)
            else:
                msg = f"A fatura do seu cartão {bill.account.name} vence em {days_left} dias."
                messages.info(request, msg)
                
        # 2. Verifica orçamentos ativos com mais de 80% de uso
        active_budgets = get_active_budgets(request.user, today)
        for b_info in active_budgets:
            if b_info['is_over_budget']:
                msg = f"Alerta de Orçamento: Você estourou a meta de {b_info['budget'].category.name}!"
                messages.error(request, msg)
            elif b_info['is_warning']:
                perc = int(b_info['percentage'])
                msg = f"Aviso de Orçamento: Você já usou {perc}% da sua meta de {b_info['budget'].category.name}."
                messages.warning(request, msg)
