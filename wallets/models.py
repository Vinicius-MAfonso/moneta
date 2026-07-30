import uuid
from django.db import models
from django.conf import settings


class Account(models.Model):
    class Types(models.TextChoices):
        CHECKING = 'checking', 'Conta Corrente'
        SAVINGS = 'savings', 'Conta Poupança'
        INVESTMENT = 'investment', 'Investimento'
        CREDIT_CARD = 'credit_card', 'Cartão de Crédito'
        OTHER = 'other', 'Outro'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name='accounts', verbose_name='usuário')
    name = models.CharField(max_length=100, verbose_name='nome')
    type = models.CharField(max_length=50, choices=Types.choices, verbose_name='tipo')
    institution = models.CharField(max_length=100, blank=True, null=True, verbose_name='instituição')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name='saldo')
    color = models.CharField(max_length=7, default='#000000', verbose_name='cor')
    active = models.BooleanField(default=True, verbose_name='ativa')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='criada em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='atualizada em')

    class Meta:
        verbose_name = 'conta'
        verbose_name_plural = 'contas'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['user', 'name'], name='unique_account_name_per_user')
        ]

    def clean(self):
        super().clean()
        if self.balance < 0:
            raise ValidationError('Account balance cannot be negative.')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.type})"


class CreditCard(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name='credit_cards', verbose_name='usuário')
    name = models.CharField(max_length=100, verbose_name='nome')
    institution = models.CharField(max_length=100, blank=True, null=True, verbose_name='instituição')
    limit = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='limite')
    available_limit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name='limite disponível')
    closing_day = models.PositiveSmallIntegerField(verbose_name='dia de fechamento')
    due_day = models.PositiveSmallIntegerField(verbose_name='dia de vencimento')
    color = models.CharField(max_length=7, default='#000000', verbose_name='cor')
    active = models.BooleanField(default=True, verbose_name='ativa')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='criada em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='atualizada em')

    class Meta:
        verbose_name = 'cartão de crédito'
        verbose_name_plural = 'cartões de crédito'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['user', 'name'], name='unique_credit_card_name_per_user')
        ]

    def clean(self):
        super().clean()
        if self.limit < 0:
            raise ValidationError('Limite do cartão de crédito não pode ser negativo.')
        if self.available_limit < 0:
            raise ValidationError('Limite disponível do cartão de crédito não pode ser negativo.')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.institution})"
