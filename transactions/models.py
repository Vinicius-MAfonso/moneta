import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

class Category(models.Model):
    class types(models.TextChoices):
        INCOME = 'income', 'Income'
        EXPENSE = 'expense', 'Expense'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name='categories', null=True, blank=True)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=10, choices=types.choices)
    icon = models.CharField(max_length=100, blank=True, null=True)
    color = models.CharField(max_length=7, default='#000000')
    parent = models.ForeignKey('self', on_delete=models.RESTRICT, blank=True, null=True, related_name='subcategories')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
class Tag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT)
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default='#000000')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Transaction(models.Model):
    class types(models.TextChoices):
        INCOME = 'income', 'Income'
        EXPENSE = 'expense', 'Expense'

    class statuses(models.TextChoices):
        PENDING = 'pending', 'Pending'
        COMPLETED = 'completed', 'Completed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name='transactions')
    account = models.ForeignKey('wallets.Account', on_delete=models.RESTRICT, related_name='transactions', null=True, blank=True)
    credit_card = models.ForeignKey('wallets.CreditCard', on_delete=models.RESTRICT, related_name='transactions', null=True, blank=True)
    category = models.ForeignKey('Category', on_delete=models.RESTRICT, related_name='transactions')
    tags = models.ManyToManyField('Tag', blank=True, related_name='transactions')
    type = models.CharField(max_length=10, choices=types.choices)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    due_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=statuses.choices, default='pending')
    installment_number = models.PositiveIntegerField(blank=True, null=True)
    total_installments = models.PositiveIntegerField(blank=True, null=True)
    recurring = models.ForeignKey('RecurringTransaction', on_delete=models.RESTRICT, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if not self.account and not self.credit_card:
            raise ValidationError('A transação precisa estar associada a uma conta ou a um cartão de crédito.')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.description} - {self.amount} ({self.type})"

class Transfer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name='transfers')
    from_account = models.ForeignKey('wallets.Account', on_delete=models.RESTRICT, related_name='transfers_out')
    to_account = models.ForeignKey('wallets.Account', on_delete=models.RESTRICT, related_name='transfers_in')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    description = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Transfer from {self.from_account} to {self.to_account} - {self.amount}"

class RecurringTransaction(models.Model):
    class types(models.TextChoices):
        INCOME = 'income', 'Income'
        EXPENSE = 'expense', 'Expense'

    class frequencies(models.TextChoices):
        DAILY = 'daily', 'Daily'
        WEEKLY = 'weekly', 'Weekly'
        MONTHLY = 'monthly', 'Monthly'
        YEARLY = 'yearly', 'Yearly'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name='recurring_transactions')
    category = models.ForeignKey('Category', on_delete=models.RESTRICT, related_name='recurring_transactions')
    account = models.ForeignKey('wallets.Account', on_delete=models.RESTRICT, related_name='recurring_transactions', blank=True, null=True)
    credit_card = models.ForeignKey('wallets.CreditCard', on_delete=models.RESTRICT, related_name='recurring_transactions', blank=True, null=True)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    type = models.CharField(max_length=10, choices=types.choices)
    frequency = models.CharField(max_length=10, choices=frequencies.choices)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if not self.account and not self.credit_card:
            raise ValidationError('Uma recorrência precisa estar associada a uma conta ou a um cartão de crédito.')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.description} - {self.amount} ({self.type})"
