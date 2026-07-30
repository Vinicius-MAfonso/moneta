import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


class Category(models.Model):
    class types(models.TextChoices):
        INCOME = 'receita', 'Receita'
        EXPENSE = 'despesa', 'Despesa'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name='categories', null=True, blank=True, verbose_name='usuário')
    name = models.CharField(max_length=100, verbose_name='nome')
    type = models.CharField(max_length=10, choices=types.choices, verbose_name='tipo')
    icon = models.CharField(max_length=100, blank=True, null=True, verbose_name='ícone')
    color = models.CharField(max_length=7, default='#000000', verbose_name='cor')
    parent = models.ForeignKey('self', on_delete=models.RESTRICT, blank=True, null=True, related_name='subcategories', verbose_name='categoria pai')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='criada em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='atualizada em')

    class Meta:
        verbose_name = 'categoria'
        verbose_name_plural = 'categorias'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['user', 'name'], name='unique_category_name_per_user')
        ]

    def __str__(self):
        return self.name


class Tag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, verbose_name='usuário')
    name = models.CharField(max_length=100, verbose_name='nome')
    color = models.CharField(max_length=7, default='#000000', verbose_name='cor')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='criada em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='atualizada em')

    class Meta:
        verbose_name = 'tag'
        verbose_name_plural = 'tags'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['user', 'name'], name='unique_tag_name_per_user')
        ]

    def __str__(self):
        return self.name


class Transaction(models.Model):
    class types(models.TextChoices):
        INCOME = 'receita', 'Receita'
        EXPENSE = 'despesa', 'Despesa'

    class statuses(models.TextChoices):
        PENDING = 'pendente', 'Pendente'
        COMPLETED = 'concluída', 'Concluída'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name='transactions', verbose_name='usuário')
    account = models.ForeignKey('wallets.Account', on_delete=models.RESTRICT, related_name='transactions', null=True, blank=True, verbose_name='conta')
    credit_card = models.ForeignKey('wallets.CreditCard', on_delete=models.RESTRICT, related_name='transactions', null=True, blank=True, verbose_name='cartão de crédito')
    category = models.ForeignKey('Category', on_delete=models.RESTRICT, related_name='transactions', verbose_name='categoria')
    tags = models.ManyToManyField('Tag', blank=True, related_name='transactions', verbose_name='tags')
    type = models.CharField(max_length=10, choices=types.choices, verbose_name='tipo')
    description = models.CharField(max_length=255, verbose_name='descrição')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='valor')
    date = models.DateField(verbose_name='data')
    due_date = models.DateField(blank=True, null=True, verbose_name='data de vencimento')
    status = models.CharField(max_length=10, choices=statuses.choices, default='pendente', verbose_name='status')
    installment_number = models.PositiveIntegerField(blank=True, null=True, verbose_name='número da parcela')
    total_installments = models.PositiveIntegerField(blank=True, null=True, verbose_name='total de parcelas')
    recurring = models.ForeignKey('RecurringTransaction', on_delete=models.RESTRICT, blank=True, null=True, verbose_name='recorrente')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='criada em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='atualizada em')

    class Meta:
        verbose_name = 'transação'
        verbose_name_plural = 'transações'
        ordering = ['-date', '-created_at']

    def clean(self):
        super().clean()
        if not self.account and not self.credit_card:
            raise ValidationError('A transação deve estar associada a uma conta ou a um cartão de crédito.')

        if self.installment_number is not None and self.total_installments is None:
            raise ValidationError('O número total de parcelas é obrigatório quando o número da parcela é fornecido.')

        if self.installment_number is not None and self.total_installments is not None:
            if self.installment_number < 1:
                raise ValidationError('O número da parcela deve ser maior que zero.')
            if self.total_installments < 1:
                raise ValidationError('O total de parcelas deve ser maior que zero.')
            if self.installment_number > self.total_installments:
                raise ValidationError('O número da parcela não pode ser maior que o total de parcelas.')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.description} - {self.amount} ({self.type})"


class Transfer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name='transfers', verbose_name='usuário')
    from_account = models.ForeignKey('wallets.Account', on_delete=models.RESTRICT, related_name='transfers_out', verbose_name='conta de origem')
    to_account = models.ForeignKey('wallets.Account', on_delete=models.RESTRICT, related_name='transfers_in', verbose_name='conta de destino')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='valor')
    date = models.DateField(verbose_name='data')
    description = models.CharField(max_length=255, blank=True, null=True, verbose_name='descrição')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='criada em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='atualizada em')

    class Meta:
        verbose_name = 'transferência'
        verbose_name_plural = 'transferências'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"Transferência de {self.from_account} para {self.to_account} - {self.amount}"


class RecurringTransaction(models.Model):
    class types(models.TextChoices):
        INCOME = 'receita', 'Receita'
        EXPENSE = 'despesa', 'Despesa'

    class frequencies(models.TextChoices):
        DAILY = 'daily', 'Daily'
        WEEKLY = 'weekly', 'Weekly'
        MONTHLY = 'monthly', 'Monthly'
        YEARLY = 'yearly', 'Yearly'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name='recurring_transactions', verbose_name='usuário')
    category = models.ForeignKey('Category', on_delete=models.RESTRICT, related_name='recurring_transactions', verbose_name='categoria')
    account = models.ForeignKey('wallets.Account', on_delete=models.RESTRICT, related_name='recurring_transactions', blank=True, null=True, verbose_name='conta')
    credit_card = models.ForeignKey('wallets.CreditCard', on_delete=models.RESTRICT, related_name='recurring_transactions', blank=True, null=True, verbose_name='cartão de crédito')
    description = models.CharField(max_length=255, verbose_name='descrição')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='valor')
    type = models.CharField(max_length=10, choices=types.choices, verbose_name='tipo')
    frequency = models.CharField(max_length=10, choices=frequencies.choices, verbose_name='frequência')
    start_date = models.DateField(verbose_name='data de início')
    end_date = models.DateField(blank=True, null=True, verbose_name='data de término')
    active = models.BooleanField(default=True, verbose_name='ativa')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='criada em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='atualizada em')

    class Meta:
        verbose_name = 'transação recorrente'
        verbose_name_plural = 'transações recorrentes'
        ordering = ['-created_at']

    def clean(self):
        super().clean()
        if not self.account and not self.credit_card:
            raise ValidationError('Uma transação recorrente deve ser associada a uma conta ou a um cartão de crédito.')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.description} - {self.amount} ({self.type})"
