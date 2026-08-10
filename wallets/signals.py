from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django_q.tasks import async_task

from .models import Account


@receiver(post_save, sender=Account)
@receiver(post_delete, sender=Account)
def trigger_balance_recalculation_on_account_change(sender, instance, **kwargs):
    """
    Sempre que uma conta for salva (ex: alteração de saldo inicial) ou deletada, 
    recalculamos o saldo de todas as contas do usuário em background.
    """
    if instance.user_id:
        async_task('wallets.tasks.async_recalculate_user_balances', instance.user_id)
