from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from moneta.common import TransactionType
from transactions.models import Category

User = get_user_model()


@receiver(post_save, sender=User)
def create_default_categories(sender, instance, created, **kwargs):
    if created:
        default_categories = [
            ('Alimentação', TransactionType.EXPENSE, '#ef4444', '🍔'),
            ('Moradia', TransactionType.EXPENSE, '#f59e0b', '🏠'),
            ('Transporte', TransactionType.EXPENSE, '#3b82f6', '🚌'),
            ('Lazer', TransactionType.EXPENSE, '#8b5cf6', '🎉'),
            ('Salário', TransactionType.INCOME, '#10b981', '💰'),
            ('Investimentos', TransactionType.INCOME, '#06b6d4', '📈'),
            ('Transferência', TransactionType.TRANSFER, '#737373', '🔄'),
        ]
        categories_to_create = [
            Category(user=instance, name=name, type=cat_type, color=color, icon=icon)
            for name, cat_type, color, icon in default_categories
        ]
        Category.objects.bulk_create(categories_to_create)
