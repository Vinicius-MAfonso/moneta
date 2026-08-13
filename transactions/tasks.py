from django.contrib.auth import get_user_model
from django.utils import timezone

from transactions.models import Transaction
from transactions.services import process_recurring_transactions
from users.services import send_push_notification

User = get_user_model()

def process_all_recurring_transactions():
    users = User.objects.all()
    for user in users:
        process_recurring_transactions(user)


def notify_due_transactions():
    today = timezone.now().date()
    
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
            
        send_push_notification(user, title, body, url='/dashboard/')
