import json
from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from pywebpush import WebPushException, webpush

from transactions.models import Transaction
from transactions.services import process_recurring_transactions

User = get_user_model()

def process_all_recurring_transactions():
    """
    Background task to process recurring transactions for all users.
    Should be scheduled to run daily at midnight.
    """
    users = User.objects.all()
    for user in users:
        process_recurring_transactions(user)


def notify_due_transactions():
    """
    Background task to send Web Push notifications for bills due today.
    """
    today = date.today()
    
    due_transactions = Transaction.objects.filter(
        date=today,
        status=Transaction.Statuses.PENDING
    ).select_related('user', 'category')
    
    user_transactions = {}
    for tx in due_transactions:
        if tx.user_id not in user_transactions:
            user_transactions[tx.user_id] = []
        user_transactions[tx.user_id].append(tx)
        
    for user_id, txs in user_transactions.items():
        user = User.objects.get(id=user_id)
        subscriptions = user.push_subscriptions.all()
        
        if not subscriptions.exists():
            continue
            
        count = len(txs)
        if count == 1:
            tx = txs[0]
            title = "Conta Vencendo Hoje!"
            body = f"{tx.description} no valor de R$ {tx.amount}."
        else:
            title = f"{count} Contas Vencendo Hoje!"
            body = f"Você tem {count} transações pendentes para hoje. Acesse o Moneta para conferir."
            
        payload = json.dumps({
            'title': title,
            'body': body,
            'url': '/dashboard/'
        })
        
        for sub in subscriptions:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {
                            "p256dh": sub.p256dh,
                            "auth": sub.auth
                        }
                    },
                    data=payload,
                    vapid_private_key=str(settings.VAPID_PRIVATE_KEY),
                    vapid_claims={
                        "sub": settings.VAPID_ADMIN_EMAIL
                    }
                )
            except WebPushException as ex:
                if ex.response and ex.response.status_code in [404, 410]:
                    sub.delete()
                print("Web Push Error:", repr(ex))
