from django.db.models.signals import post_save, post_init
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django_q.tasks import async_task
from django.db import transaction

from moneta.common import TransactionType
from transactions.models import Category

User = get_user_model()


@receiver(post_save, sender=User)
def create_default_categories(sender, instance, created, **kwargs):
    if created:
        default_categories = [
            ('Alimentação', TransactionType.EXPENSE, '#ef4444', '🍔', False),
            ('Moradia', TransactionType.EXPENSE, '#f59e0b', '🏠', False),
            ('Transporte', TransactionType.EXPENSE, '#3b82f6', '🚌', False),
            ('Lazer', TransactionType.EXPENSE, '#8b5cf6', '🎉', False),
            ('Saúde', TransactionType.EXPENSE, '#ec4899', '🏥', False),
            ('Educação', TransactionType.EXPENSE, '#06b6d4', '📚', False),
            ('Vestuário', TransactionType.EXPENSE, '#f97316', '👕', False),
            ('Assinaturas', TransactionType.EXPENSE, '#6366f1', '📱', False),
            ('Pet', TransactionType.EXPENSE, '#84cc16', '🐾', False),
            ('Viagem', TransactionType.EXPENSE, '#14b8a6', '✈️', False),
            ('Outras Despesas', TransactionType.EXPENSE, '#64748b', '📦', False),  # <-- Nome alterado
            ('Salário', TransactionType.INCOME, '#10b981', '💰', False),
            ('Freelance', TransactionType.INCOME, '#22c55e', '💻', False),
            ('Investimentos', TransactionType.INCOME, '#06b6d4', '📈', False),
            ('Outras Receitas', TransactionType.INCOME, '#64748b', '📦', False),    # <-- Nome alterado
            ('Transferência', TransactionType.TRANSFER, '#737373', '🔄', False),
            ('Reajuste de Saldo Positivo', TransactionType.INCOME, '#64748b', '⚖️', True),
            ('Reajuste de Saldo Negativo', TransactionType.EXPENSE, '#64748b', '⚖️', True),
        ]
        categories_to_create = [
            Category(user=instance, name=name, type=cat_type, color=color, icon=icon, is_system=is_system)
            for name, cat_type, color, icon, is_system in default_categories
        ]
        Category.objects.bulk_create(categories_to_create)



@receiver(post_init, sender=User)
def remember_user_state(sender, instance, **kwargs):
    instance._original_is_active = instance.is_active

@receiver(post_save, sender=User)
def track_user_activation(sender, instance, created, **kwargs):
    if created:
        return

    if hasattr(instance, '_original_is_active'):
        if not instance._original_is_active and instance.is_active:
            transaction.on_commit(lambda: async_task('users.emails.send_welcome_email', instance.pk))
            
    instance._original_is_active = instance.is_active
