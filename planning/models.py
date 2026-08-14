import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db import transaction as db_transaction


class Budget(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='budgets', verbose_name='usuário')
    category = models.ForeignKey('transactions.Category', on_delete=models.CASCADE, related_name='budgets', verbose_name='categoria')
    amount = models.DecimalField(max_digits=20, decimal_places=2, validators=[MinValueValidator(0.01)], verbose_name='valor')
    start_date = models.DateField(verbose_name='data de início')
    end_date = models.DateField(verbose_name='data de término')
    is_warning_notified = models.BooleanField(default=False, verbose_name='notificado aviso')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='atualizado em')

    class Meta:
        verbose_name = 'orçamento'
        verbose_name_plural = 'orçamentos'
        ordering = ['-start_date']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F('start_date')),
                name='budget_end_date_after_start_date',
            ),
        ]

    def __str__(self):
        return f"{self.category.name} - {self.amount} ({self.start_date} to {self.end_date})"


class Goal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='goals', verbose_name='usuário')
    account = models.ForeignKey('wallets.Account', on_delete=models.CASCADE, related_name='goals', verbose_name='conta', null=True, blank=True)
    name = models.CharField(max_length=100, verbose_name='nome')
    target_amount = models.DecimalField(max_digits=20, decimal_places=2, validators=[MinValueValidator(0.01)], verbose_name='valor alvo')
    current_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0, validators=[MinValueValidator(0)], verbose_name='valor atual')
    start_date = models.DateField(verbose_name='data de início')
    end_date = models.DateField(verbose_name='data de término')
    is_near_target_notified = models.BooleanField(default=False, verbose_name='notificado quase atingindo')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='atualizado em')

    class Meta:
        verbose_name = 'objetivo'
        verbose_name_plural = 'objetivos'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F('start_date')),
                name='goal_end_date_after_start_date',
            ),
        ]

    def __str__(self):
        return f"{self.name} - {self.current_amount}/{self.target_amount} ({self.start_date} to {self.end_date})"

