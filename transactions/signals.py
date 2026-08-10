from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django_q.tasks import async_task

from .models import Transaction


@receiver(post_save, sender=Transaction)
@receiver(post_delete, sender=Transaction)
def trigger_balance_recalculation(sender, instance, **kwargs):
    """
    Sempre que uma transação for salva, criada ou deletada, 
    recalculamos o saldo de todas as contas do usuário em background.
    """
    if instance.user_id:
        async_task('wallets.tasks.async_recalculate_user_balances', instance.user_id)
