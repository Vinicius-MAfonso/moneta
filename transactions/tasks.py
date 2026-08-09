from django.contrib.auth import get_user_model
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
