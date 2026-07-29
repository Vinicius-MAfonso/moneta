import uuid
from django.db import models

class Investment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='investments')
    account = models.ForeignKey('wallets.Account', on_delete=models.CASCADE, related_name='investments')
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=50, choices=[('stock', 'Stock'), ('bond', 'Bond'), ('real_estate', 'Real Estate'), ('mutual_fund', 'Mutual Fund'), ('etf', 'ETF')])
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    average_price = models.DecimalField(max_digits=10, decimal_places=2)
    current_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.type} ({self.quantity} @ {self.average_price})"