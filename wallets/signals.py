from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Account


@receiver(post_save, sender=Account)
@receiver(post_delete, sender=Account)
def trigger_balance_recalculation_on_account_change(sender, instance, **kwargs):
    if instance.user_id:
        pass
