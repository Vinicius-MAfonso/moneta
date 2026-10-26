from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from wallets.services import recalculate_account_balance

from .models import Transaction


@receiver(post_save, sender=Transaction)
@receiver(post_delete, sender=Transaction)
def trigger_balance_recalculation(sender, instance, **kwargs):
    if instance.account_id:
        recalculate_account_balance(instance.account)
