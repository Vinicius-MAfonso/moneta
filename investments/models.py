import uuid
from django.db import models
from django.conf import settings

class Investment(models.Model):
    class types(models.TextChoices):
        STOCK = 'stock', 'Stock'
        BOND = 'bond', 'Bond'
        REAL_ESTATE = 'real_estate', 'Real Estate'
        MUTUAL_FUND = 'mutual_fund', 'Mutual Fund'
        ETF = 'etf', 'ETF'
        
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name='investments')
    account = models.ForeignKey('wallets.Account', on_delete=models.RESTRICT, related_name='investments')
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=50, choices=types.choices)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    average_price = models.DecimalField(max_digits=10, decimal_places=2)
    current_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.type} ({self.quantity} @ {self.average_price})"