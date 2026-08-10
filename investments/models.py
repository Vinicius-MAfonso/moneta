import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Investment(models.Model):
    class Types(models.TextChoices):
        STOCK = 'stock', 'Ação'
        BOND = 'bond', 'Título'
        REAL_ESTATE = 'real_estate', 'Imóvel'
        MUTUAL_FUND = 'mutual_fund', 'Fundo de Investimento'
        ETF = 'etf', 'ETF'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='investments', verbose_name='usuário')
    account = models.ForeignKey('wallets.Account', on_delete=models.CASCADE, related_name='investments', verbose_name='conta')
    name = models.CharField(max_length=100, verbose_name='nome')
    type = models.CharField(max_length=50, choices=Types.choices, verbose_name='tipo')
    quantity = models.DecimalField(max_digits=20, decimal_places=2, validators=[MinValueValidator(0)], verbose_name='quantidade')
    average_price = models.DecimalField(max_digits=20, decimal_places=2, validators=[MinValueValidator(0)], verbose_name='preço médio')
    current_price = models.DecimalField(max_digits=20, decimal_places=2, validators=[MinValueValidator(0)], verbose_name='preço atual')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='atualizado em')

    class Meta:
        verbose_name = 'investimento'
        verbose_name_plural = 'investimentos'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.get_type_display()} ({self.quantity} @ {self.average_price})"