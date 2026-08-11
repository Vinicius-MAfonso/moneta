from wallets.services import recalculate_all_user_balances


def async_recalculate_user_balances(user):
    """
    Background task to recalculate a user's balances asynchronously.
    """
    recalculate_all_user_balances(user)


def notify_due_credit_card_bills():
    """
    Background task to notify users about credit card bills due tomorrow.
    """
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
