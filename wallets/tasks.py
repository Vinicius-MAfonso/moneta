from wallets.services import recalculate_all_user_balances

def async_recalculate_user_balances(user):
    """
    Background task to recalculate a user's balances asynchronously.
    """
    recalculate_all_user_balances(user)
