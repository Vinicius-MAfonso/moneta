from collections import defaultdict

from django.contrib.auth import get_user_model
from django.utils import timezone

from transactions.models import Transaction
from transactions.services import process_recurring_transactions
from users.services import send_push_notification

User = get_user_model()


def process_all_recurring_transactions():
    for user in User.objects.all().iterator(chunk_size=100):
        process_recurring_transactions(user)


def notify_due_transactions():
    today = timezone.now().date()
    
    due_transactions = (
        Transaction.objects.filter(
            date=today,
            status=Transaction.Statuses.PENDING
        )
        .select_related('user', 'category')
        
    )
    
    user_map = {}
    user_transactions = defaultdict(list)
    for tx in due_transactions:
        user_map[tx.user_id] = tx.user
        user_transactions[tx.user_id].append(tx)
        
    for user_id, txs in user_transactions.items():
        user = user_map[user_id]
            
        count = len(txs)
        if count == 1:
            tx = txs[0]
            title = "Conta Vencendo Hoje!"
            body = f"{tx.description} no valor de R$ {tx.amount}."
        else:
            title = f"{count} Contas Vencendo Hoje!"
            body = f"Você tem {count} transações pendentes para hoje. Acesse o Moneta para conferir."
            
        send_push_notification(user, title, body, url='/dashboard/')

