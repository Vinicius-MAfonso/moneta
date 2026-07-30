import uuid
from django.db import models
from django.db import transaction as db_transaction
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator

from common.choices import TransactionType, RECURRING_TRANSACTION_TYPE_CHOICES


class Category(models.Model):
    types = TransactionType

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name='categories', null=True, blank=True, verbose_name='usuário')
    name = models.CharField(max_length=100, verbose_name='nome')
    type = models.CharField(max_length=15, choices=TransactionType.choices, verbose_name='tipo')
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
            models.UniqueConstraint(
                fields=['user', 'name'],
                condition=models.Q(user__isnull=False),
                name='unique_category_name_per_user',
            ),
            models.UniqueConstraint(
                fields=['name'],
                condition=models.Q(user__isnull=True),
                name='unique_default_category_name',
            ),
        ]

    def __str__(self):
        return self.name


class Tag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name='tags', verbose_name='usuário')
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
    types = TransactionType

    class statuses(models.TextChoices):
        PENDING = 'pendente', 'Pendente'
        COMPLETED = 'concluída', 'Concluída'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name='transactions', verbose_name='usuário')
    account = models.ForeignKey('wallets.Account', on_delete=models.RESTRICT, related_name='transactions', null=True, blank=True, verbose_name='conta')
    credit_card = models.ForeignKey('wallets.CreditCard', on_delete=models.RESTRICT, related_name='transactions', null=True, blank=True, verbose_name='cartão de crédito')
    category = models.ForeignKey('Category', on_delete=models.RESTRICT, related_name='transactions', verbose_name='categoria')
    tags = models.ManyToManyField('Tag', blank=True, related_name='transactions', verbose_name='tags')
    type = models.CharField(max_length=15, choices=TransactionType.choices, verbose_name='tipo')
    description = models.CharField(max_length=255, verbose_name='descrição')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)], verbose_name='valor')
    date = models.DateField(verbose_name='data')
    due_date = models.DateField(blank=True, null=True, verbose_name='data de vencimento')
    status = models.CharField(max_length=10, choices=statuses.choices, default='pendente', verbose_name='status')
    installment_number = models.PositiveIntegerField(blank=True, null=True, verbose_name='número da parcela')
    total_installments = models.PositiveIntegerField(blank=True, null=True, verbose_name='total de parcelas')
    recurring = models.ForeignKey('RecurringTransaction', on_delete=models.RESTRICT, blank=True, null=True, related_name='generated_transactions', verbose_name='recorrente')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='criada em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='atualizada em')

    class Meta:
        verbose_name = 'transação'
        verbose_name_plural = 'transações'
        ordering = ['-date', '-created_at']
        constraints = [
            models.CheckConstraint(
                check=models.Q(account__isnull=False) | models.Q(credit_card__isnull=False),
                name='transaction_requires_account_or_credit_card',
            ),
        ]
        indexes = [
            models.Index(fields=['user', '-date'], name='transaction_user_date_idx'),
        ]

    def clean(self):
        super().clean()
        if not self.account and not self.credit_card:
            raise ValidationError('A transação deve estar associada a uma conta ou a um cartão de crédito.')

        if self.category_id and self.type != self.category.type:
            raise ValidationError('O tipo da transação deve corresponder ao tipo da categoria.')

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
    transaction = models.OneToOneField('Transaction', on_delete=models.SET_NULL, blank=True, null=True, related_name='transfer', verbose_name='transação')
    from_account = models.ForeignKey('wallets.Account', on_delete=models.RESTRICT, related_name='transfers_out', verbose_name='conta de origem')
    to_account = models.ForeignKey('wallets.Account', on_delete=models.RESTRICT, related_name='transfers_in', verbose_name='conta de destino')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)], verbose_name='valor')
    date = models.DateField(verbose_name='data')
    description = models.CharField(max_length=255, blank=True, null=True, verbose_name='descrição')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='criada em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='atualizada em')

    class Meta:
        verbose_name = 'transferência'
        verbose_name_plural = 'transferências'
        ordering = ['-date', '-created_at']
        constraints = [
            models.CheckConstraint(
                check=~models.Q(from_account=models.F('to_account')),
                name='transfer_from_account_not_equal_to_account',
            ),
        ]

    def clean(self):
        super().clean()
        if self.from_account_id and self.to_account_id and self.from_account_id == self.to_account_id:
            raise ValidationError('A conta de origem e a conta de destino não podem ser a mesma.')

    def save(self, *args, **kwargs):
        self.full_clean()
        with db_transaction.atomic():
            super().save(*args, **kwargs)

            if not self.transaction:
                transfer_category, _ = Category.objects.get_or_create(
                    user=self.user,
                    name='Transferência',
                    defaults={'type': Category.types.TRANSFER},
                )
                transaction = Transaction.objects.create(
                    user=self.user,
                    account=self.from_account,
                    category=transfer_category,
                    description=self.description or f'Transferência de {self.from_account} para {self.to_account}',
                    amount=self.amount,
                    date=self.date,
                    type=Transaction.types.TRANSFER,
                    status=Transaction.statuses.COMPLETED,
                )
                self.transaction = transaction
                super().save(update_fields=['transaction'])

    def __str__(self):
        return f"Transferência de {self.from_account} para {self.to_account} - {self.amount}"


class RecurringTransaction(models.Model):
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
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)], verbose_name='valor')
    type = models.CharField(max_length=10, choices=RECURRING_TRANSACTION_TYPE_CHOICES, verbose_name='tipo')
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
        constraints = [
            models.CheckConstraint(
                check=models.Q(account__isnull=False) | models.Q(credit_card__isnull=False),
                name='recurringtransaction_requires_account_or_credit_card',
            ),
            models.CheckConstraint(
                check=models.Q(end_date__isnull=True) | models.Q(end_date__gte=models.F('start_date')),
                name='recurringtransaction_end_date_after_start_date',
            ),
        ]

    def clean(self):
        super().clean()
        if not self.account and not self.credit_card:
            raise ValidationError('Uma transação recorrente deve ser associada a uma conta ou a um cartão de crédito.')

        if self.category_id and self.type != self.category.type:
            raise ValidationError('O tipo da transação recorrente deve corresponder ao tipo da categoria.')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.description} - {self.amount} ({self.type})"