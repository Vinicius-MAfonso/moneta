from datetime import date, timedelta
from decimal import Decimal
from django.core.mail import send_mail
from planning.models import Goal
from wallets.models import CreditCardBill

def check_and_send_alerts():
    """
    Verifica metas próximas e faturas vencendo amanhã para enviar notificações por e-mail.
    Criado para rodar diariamente via agendamento do Django-Q2.
    """
    today = date.today()
    tomorrow = today + timedelta(days=1)
    
    # 1. Verifica Faturas Vencendo Amanhã
    bills_due_tomorrow = CreditCardBill.objects.filter(
        status=CreditCardBill.Statuses.OPEN,
        due_date=tomorrow,
        is_due_tomorrow_notified=False
    ).select_related('account', 'account__user')
    
    for bill in bills_due_tomorrow:
        user = bill.account.user
        if user.email:
            subject = f"Alerta Moneta: Fatura do cartão {bill.account.name} vence amanhã!"
            message = (
                f"Olá {user.first_name or user.username},\n\n"
                f"A sua fatura do cartão {bill.account.name} vence amanhã ({bill.due_date.strftime('%d/%m/%Y')}).\n"
                f"Não se esqueça de pagar para evitar juros!\n\n"
                f"Equipe Moneta"
            )
            send_mail(
                subject,
                message,
                'naoresponda@moneta.com.br',
                [user.email],
                fail_silently=True,
            )
        # Marca como notificado mesmo se não tiver e-mail, para não tentarmos novamente
        bill.is_due_tomorrow_notified = True
        bill.save(update_fields=['is_due_tomorrow_notified'])
        
    # 2. Verifica Metas Próximas do Objetivo (90%+)
    # Queremos metas que ainda não chegaram em 100%, mas estão >= 90%.
    active_goals = Goal.objects.filter(is_near_target_notified=False).select_related('user')
    
    for goal in active_goals:
        if goal.target_amount > 0 and goal.current_amount >= (goal.target_amount * Decimal('0.9')) and goal.current_amount < goal.target_amount:
            user = goal.user
            if user.email:
                subject = f"Alerta Moneta: Sua meta '{goal.name}' está quase lá!"
                message = (
                    f"Olá {user.first_name or user.username},\n\n"
                    f"Parabéns! Você já atingiu {goal.current_amount} de {goal.target_amount} na sua meta '{goal.name}'.\n"
                    f"Falta muito pouco para você completar esse objetivo!\n\n"
                    f"Equipe Moneta"
                )
                send_mail(
                    subject,
                    message,
                    'naoresponda@moneta.com.br',
                    [user.email],
                    fail_silently=True,
                )
            goal.is_near_target_notified = True
            goal.save(update_fields=['is_near_target_notified'])
