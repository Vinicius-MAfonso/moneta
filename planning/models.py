import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Budget(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='budgets', verbose_name='usuário')
    category = models.ForeignKey('transactions.Category', on_delete=models.CASCADE, related_name='budgets', verbose_name='categoria')
    amount = models.DecimalField(max_digits=20, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))], verbose_name='valor')
    is_recurring = models.BooleanField(default=True, verbose_name='recorrente mensal')
    start_date = models.DateField(default=timezone.now, verbose_name='data de início')
    end_date = models.DateField(null=True, blank=True, verbose_name='data de término')
    is_warning_notified = models.BooleanField(default=False, verbose_name='notificado aviso')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='atualizado em')

    class Meta:
        verbose_name = 'orçamento'
        verbose_name_plural = 'orçamentos'
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['user', 'is_recurring', 'start_date'], name='budget_user_rec_date_idx'),
            models.Index(fields=['is_warning_notified', 'is_recurring'], name='budget_warn_notif_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__isnull=True) | models.Q(end_date__gte=models.F('start_date')),
                name='budget_end_date_after_start_date',
            ),
            models.UniqueConstraint(
                fields=['user', 'category'],
                condition=models.Q(is_recurring=True),
                name='unique_recurring_budget_per_user_cat',
            ),
        ]

    def clean(self):
        super().clean()
        if not self.is_recurring:
            if not self.end_date:
                raise ValidationError({'end_date': 'A data de término é obrigatória para orçamentos pontuais.'})
            if self.start_date and self.end_date and self.start_date > self.end_date:
                raise ValidationError({'end_date': 'A data de término deve ser posterior ou igual à data de início.'})

        if self.user_id and self.category_id:
            if self.is_recurring:
                existing_rec = Budget.objects.filter(
                    user=self.user,
                    category=self.category,
                    is_recurring=True,
                ).exclude(pk=self.pk)
                if existing_rec.exists():
                    raise ValidationError('Já existe um orçamento mensal recorrente para esta categoria.')
            elif self.start_date and self.end_date:
                overlapping = Budget.objects.filter(
                    user=self.user,
                    category=self.category,
                    is_recurring=False,
                    start_date__lte=self.end_date,
                    end_date__gte=self.start_date,
                ).exclude(pk=self.pk)
                if overlapping.exists():
                    raise ValidationError('Já existe um orçamento cadastrado para esta categoria no período informado.')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        period = "Mensal" if self.is_recurring else f"{self.start_date} to {self.end_date}"
        return f"{self.category.name} - R$ {self.amount} ({period})"


class Goal(models.Model):
    """
    Financial Goals / Envelopes.
    
    Architecture Note:
    The `current_amount` field functions as a virtual envelope.
    When linked to a bank account (`Account`), the value of `current_amount`
    locks the account's available funds (calculated via `Account.free_balance`).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='goals', verbose_name='usuário')
    account = models.ForeignKey('wallets.Account', on_delete=models.SET_NULL, related_name='goals', verbose_name='conta', null=True, blank=True)
    name = models.CharField(max_length=100, verbose_name='nome')
    target_amount = models.DecimalField(max_digits=20, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))], verbose_name='valor alvo')
    current_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0.00'))], verbose_name='valor atual')
    start_date = models.DateField(verbose_name='data de início')
    end_date = models.DateField(verbose_name='data de término')
    is_near_target_notified = models.BooleanField(default=False, verbose_name='notificado quase atingindo')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='atualizado em')

    class Meta:
        verbose_name = 'objetivo'
        verbose_name_plural = 'objetivos'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at'], name='goal_user_created_idx'),
            models.Index(fields=['account'], name='goal_account_idx'),
            models.Index(fields=['is_near_target_notified'], name='goal_near_target_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F('start_date')),
                name='goal_end_date_after_start_date',
            ),
        ]

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.current_amount}/{self.target_amount} ({self.start_date} to {self.end_date})"

