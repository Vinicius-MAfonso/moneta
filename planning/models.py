import uuid
from django.db import models
from django.db import transaction as db_transaction
from django.conf import settings
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError

class Budget(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name='budgets', verbose_name='usuário')
    category = models.ForeignKey('transactions.Category', on_delete=models.RESTRICT, related_name='budgets', verbose_name='categoria')
    amount = models.DecimalField(max_digits=20, decimal_places=2, validators=[MinValueValidator(0.01)], verbose_name='valor')
    start_date = models.DateField(verbose_name='data de início')
    end_date = models.DateField(verbose_name='data de término')
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
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name='goals', verbose_name='usuário')
    name = models.CharField(max_length=100, verbose_name='nome')
    target_amount = models.DecimalField(max_digits=20, decimal_places=2, validators=[MinValueValidator(0.01)], verbose_name='valor alvo')
    current_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0, validators=[MinValueValidator(0)], verbose_name='valor atual')
    start_date = models.DateField(verbose_name='data de início')
    end_date = models.DateField(verbose_name='data de término')
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


class GoalTransaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    goal = models.ForeignKey('Goal', on_delete=models.RESTRICT, related_name='goal_transactions', verbose_name='objetivo')
    transaction = models.ForeignKey('transactions.Transaction', on_delete=models.RESTRICT, related_name='goal_transactions', verbose_name='transação')
    amount = models.DecimalField(max_digits=20, decimal_places=2, validators=[MinValueValidator(0.01)], verbose_name='valor')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='atualizado em')

    class Meta:
        verbose_name = 'link ao objetivo'
        verbose_name_plural = 'links aos objetivos'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['goal', 'transaction'], name='unique_goal_transaction_link'),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_amount = self.amount

    def clean(self):
        super().clean()
        
        existing_allocations = self.transaction.goal_transactions.exclude(pk=self.pk).aggregate(
            total=models.Sum('amount')
        )['total'] or 0
        
        if existing_allocations + self.amount > self.transaction.amount:
            raise ValidationError('O valor alocado aos objetivos não pode exceder o valor total da transação.')

    def save(self, *args, **kwargs):
        self.full_clean()
        
        is_new = self._state.adding
        delta = self.amount if is_new else (self.amount - self._original_amount)

        with db_transaction.atomic():
            super().save(*args, **kwargs)
            if delta:
                Goal.objects.filter(pk=self.goal_id).update(
                    current_amount=models.F('current_amount') + delta
                )
        self._original_amount = self.amount

    def delete(self, *args, **kwargs):
        with db_transaction.atomic():
            Goal.objects.filter(pk=self.goal_id).update(
                current_amount=models.F('current_amount') - self.amount
            )
            return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.goal.name} - {self.amount} ({self.transaction.description})"