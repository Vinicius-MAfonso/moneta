import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from moneta.common import TransactionType

class Category(models.Model):
    Types = TransactionType

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
            models.UniqueConstraint(fields=['user', 'name'], condition=models.Q(user__isnull=False), name='unique_category_name_per_user'),
            models.UniqueConstraint(fields=['name'], condition=models.Q(user__isnull=True), name='unique_default_category_name'),
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
    class Statuses(models.TextChoices):
        PENDING = 'pendente', 'Pendente'
        COMPLETED = 'concluída', 'Concluída'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name='transactions', verbose_name='usuário')
    
    account = models.ForeignKey('wallets.Account', on_delete=models.RESTRICT, related_name='transactions', verbose_name='conta')
    category = models.ForeignKey('Category', on_delete=models.RESTRICT, related_name='transactions', verbose_name='categoria')
    tags = models.ManyToManyField('Tag', blank=True, null=True, related_name='transactions', verbose_name='tags')
    
    description = models.CharField(max_length=255, verbose_name='descrição')
    amount = models.DecimalField(max_digits=20, decimal_places=2, validators=[MinValueValidator(0.01)], verbose_name='valor')
    date = models.DateField(verbose_name='data')
    due_date = models.DateField(blank=True, null=True, verbose_name='data de vencimento')
    status = models.CharField(max_length=10, choices=Statuses.choices, default='pendente', verbose_name='status')
    installment_number = models.PositiveIntegerField(blank=True, null=True, verbose_name='número da parcela')
    total_installments = models.PositiveIntegerField(blank=True, null=True, verbose_name='total de parcelas')
    recurring = models.ForeignKey('RecurringTransaction', on_delete=models.RESTRICT, blank=True, null=True, related_name='generated_transactions', verbose_name='recorrente')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='criada em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='atualizada em')

    class Meta:
        verbose_name = 'transação'
        verbose_name_plural = 'transações'
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['user', '-date'], name='transaction_user_date_idx'),
        ]

    @property
    def type(self):
        return self.category.type

    def clean(self):
        super().clean()
        
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
        return f"{self.description} - {self.amount} ({self.category.get_type_display()})"


class Transfer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name='transfers', verbose_name='usuário')
    
    out_transaction = models.OneToOneField('Transaction', on_delete=models.CASCADE, related_name='transfer_out', verbose_name='transação de saída')
    in_transaction = models.OneToOneField('Transaction', on_delete=models.CASCADE, related_name='transfer_in', verbose_name='transação de entrada')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='criada em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='atualizada em')

    class Meta:
        verbose_name = 'transferência'
        verbose_name_plural = 'transferências'
        ordering = ['-created_at']

    def clean(self):
        super().clean()
        if self.out_transaction_id and self.in_transaction_id:
            if self.out_transaction.account_id == self.in_transaction.account_id:
                raise ValidationError('A conta de origem e a conta de destino não podem ser a mesma.')
            if self.out_transaction.amount != self.in_transaction.amount:
                raise ValidationError('Os valores de saída e entrada devem ser idênticos.')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Transferência: {self.out_transaction.account.name} -> {self.in_transaction.account.name}"


class RecurringTransaction(models.Model):
    class Frequencies(models.TextChoices):
        DAILY = 'daily', 'Diariamente'
        WEEKLY = 'weekly', 'Semanalmente'
        MONTHLY = 'monthly', 'Mensalmente'
        YEARLY = 'yearly', 'Anualmente'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name='recurring_transactions', verbose_name='usuário')
    category = models.ForeignKey('Category', on_delete=models.RESTRICT, related_name='recurring_transactions', verbose_name='categoria')
    account = models.ForeignKey('wallets.Account', on_delete=models.RESTRICT, related_name='recurring_transactions', verbose_name='conta')
    description = models.CharField(max_length=255, verbose_name='descrição')
    amount = models.DecimalField(max_digits=20, decimal_places=2, validators=[MinValueValidator(0.01)], verbose_name='valor')
    frequency = models.CharField(max_length=10, choices=Frequencies.choices, verbose_name='frequência')
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
                condition=models.Q(end_date__isnull=True) | models.Q(end_date__gte=models.F('start_date')),
                name='recurringtransaction_end_date_after_start_date',
            ),
        ]

    @property
    def type(self):
        return self.category.type

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.description} - {self.amount} ({self.category.get_type_display()})"