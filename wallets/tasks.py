from wallets.services import recalculate_all_user_balances


def async_recalculate_user_balances(user):
    recalculate_all_user_balances(user)


def notify_due_credit_card_bills():
    from datetime import timedelta

    from django.utils import timezone

    from users.services import send_push_notification
    from wallets.models import CreditCardBill

    tomorrow = timezone.now().date() + timedelta(days=1)
    
    bills = CreditCardBill.objects.filter(
        status=CreditCardBill.Statuses.OPEN,
        due_date=tomorrow,
        is_due_tomorrow_notified=False
    ).select_related('account__user')

    for bill in bills:
        user = bill.account.user
        title = "Fatura Vencendo Amanhã!"
        body = f"A fatura do seu cartão {bill.account.name} vence amanhã. Acesse o Moneta para pagar."
        
        send_push_notification(user, title, body, url='/wallets/')
        
        bill.is_due_tomorrow_notified = True
        bill.save(update_fields=['is_due_tomorrow_notified', 'updated_at'])

def update_and_notify_closed_credit_card_bills():
    from django.utils import timezone
    from users.services import send_push_notification
    from wallets.models import CreditCardBill

    today = timezone.now().date()
    
    # 1. Altera faturas OPEN que já passaram da data de fechamento para CLOSED
    bills_to_close = CreditCardBill.objects.filter(
        status=CreditCardBill.Statuses.OPEN,
        closing_date__lt=today
    )
    for bill in bills_to_close:
        bill.status = CreditCardBill.Statuses.CLOSED
        bill.save(update_fields=['status', 'updated_at'])

    # 2. Notifica faturas CLOSED que não foram notificadas
    bills_to_notify = CreditCardBill.objects.filter(
        status=CreditCardBill.Statuses.CLOSED,
        is_closed_notified=False
    ).select_related('account__user')

    for bill in bills_to_notify:
        user = bill.account.user
        title = "Fatura Fechada!"
        body = f"A fatura do seu cartão {bill.account.name} fechou. O melhor dia para compras começou!"
        
        send_push_notification(user, title, body, url='/wallets/')
        
        bill.is_closed_notified = True
        bill.save(update_fields=['is_closed_notified', 'updated_at'])
