import uuid
from django.db import models
from django.conf import settings



class Budget(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name='budgets', verbose_name='usuário')
    category = models.ForeignKey('transactions.Category', on_delete=models.RESTRICT, related_name='budgets', verbose_name='categoria')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='valor')
    start_date = models.DateField(verbose_name='data de início')
    end_date = models.DateField(verbose_name='data de término')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='atualizado em')

    class Meta:
        verbose_name = 'orçamento'
        verbose_name_plural = 'orçamentos'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.category.name} - {self.amount} ({self.start_date} to {self.end_date})"


class Goal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name='goals', verbose_name='usuário')
    name = models.CharField(max_length=100, verbose_name='nome')
    target_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='valor alvo')
    current_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='valor atual')
    start_date = models.DateField(verbose_name='data de início')
    end_date = models.DateField(verbose_name='data de término')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='atualizado em')

    class Meta:
        verbose_name = 'objetivo'
        verbose_name_plural = 'objetivos'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.current_amount}/{self.target_amount} ({self.start_date} to {self.end_date})"


class GoalTransaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    goal = models.ForeignKey('Goal', on_delete=models.RESTRICT, verbose_name='objetivo')
    transaction = models.ForeignKey('transactions.Transaction', on_delete=models.RESTRICT, verbose_name='transação')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='valor')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='atualizado em')

    class Meta:
        verbose_name = 'link ao objetivo'
        verbose_name_plural = 'links aos objetivos'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.goal.name} - {self.amount} ({self.transaction.description})"