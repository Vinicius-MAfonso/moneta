import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Account(models.Model):
    class Types(models.TextChoices):
        CHECKING = 'checking', 'Conta Corrente'
        SAVINGS = 'savings', 'Conta Poupança'
        INVESTMENT = 'investment', 'Investimento'
        CREDIT_CARD = 'credit_card', 'Cartão de Crédito'
        OTHER = 'other', 'Outro'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='accounts', verbose_name='usuário')
    name = models.CharField(max_length=100, verbose_name='nome')
    type = models.CharField(max_length=50, choices=Types.choices, verbose_name='tipo')
    institution = models.CharField(max_length=100, blank=True, null=True, verbose_name='instituição')
    balance = models.DecimalField(max_digits=20, decimal_places=2, default=0.00, verbose_name='saldo')
    initial_balance = models.DecimalField(max_digits=20, decimal_places=2, default=0.00, verbose_name='saldo inicial')
    color = models.CharField(max_length=7, default='#000000', verbose_name='cor')
    icon = models.CharField(max_length=5, blank=True, null=True, verbose_name='ícone')
    active = models.BooleanField(default=True, verbose_name='ativa')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='criada em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='atualizada em')

    class Meta:
        verbose_name = 'conta'
        verbose_name_plural = 'contas'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['user', 'name'], name='unique_account_name_per_user'),
            models.CheckConstraint(
                check=models.Q(type='credit_card') | models.Q(balance__gte=0),
                name='prevent_negative_balance_on_checking_accounts'
            )
        ]

    def clean(self):
        super().clean()
        if self.type != self.Types.CREDIT_CARD and self.balance < 0:
            raise ValidationError('O saldo da conta não pode ser negativo.')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"


class CreditCardDetails(models.Model):
    account = models.OneToOneField(Account, on_delete=models.CASCADE, primary_key=True, related_name='credit_card_details', verbose_name='conta')
    limit = models.DecimalField(max_digits=20, decimal_places=2, default=0, verbose_name='limite')
    available_limit = models.DecimalField(max_digits=20, decimal_places=2, default=0.00, verbose_name='limite disponível')
    closing_day = models.PositiveSmallIntegerField(verbose_name='dia de fechamento')
    due_day = models.PositiveSmallIntegerField(verbose_name='dia de vencimento')

    class Meta:
        verbose_name = 'detalhes do cartão de crédito'
        verbose_name_plural = 'detalhes dos cartões de crédito'

    @property
    def used_limit(self):
        return max(Decimal('0.00'), self.limit - self.available_limit)

    @property
    def limit_usage_pct(self):
        if self.limit > 0:
            return round((self.used_limit / self.limit) * 100, 2)
        return Decimal('0.00')

    @property
    def limit_usage_pct_str(self):
        return str(self.limit_usage_pct)

    def clean(self):
        super().clean()
        if self.limit < 0:
            raise ValidationError('O limite do cartão de crédito não pode ser negativo.')
        if self.available_limit < 0:
            raise ValidationError('O limite disponível do cartão de crédito não pode ser negativo.')
        if self.account.type != Account.Types.CREDIT_CARD:
            raise ValidationError('Os detalhes do cartão de crédito só podem ser associados a uma conta do tipo Cartão de Crédito.')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Detalhes de {self.account.name}"


class CreditCardBill(models.Model):
    class Statuses(models.TextChoices):
        OPEN = 'open', 'Aberta'
        CLOSED = 'closed', 'Fechada'
        PAID = 'paid', 'Paga'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='bills', verbose_name='conta')
    period_date = models.DateField(verbose_name='mês/ano da fatura')
    closing_date = models.DateField(verbose_name='data de fechamento')
    due_date = models.DateField(verbose_name='data de vencimento')
    status = models.CharField(max_length=10, choices=Statuses.choices, default='open', verbose_name='status')
    is_due_tomorrow_notified = models.BooleanField(default=False, verbose_name='notificado vencimento amanha')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='criada em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='atualizada em')

    class Meta:
        verbose_name = 'fatura'
        verbose_name_plural = 'faturas'
        ordering = ['-period_date']
        constraints = [
            models.UniqueConstraint(fields=['account', 'period_date'], name='unique_bill_per_month')
        ]

    def clean(self):
        super().clean()
        if self.account.type != Account.Types.CREDIT_CARD:
            raise ValidationError('Faturas só podem ser associadas a contas do tipo Cartão de Crédito.')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Fatura {self.period_date.strftime('%m/%Y')} - {self.account.name}"