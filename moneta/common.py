from django.db import models
 
 
class TransactionType(models.TextChoices):
    INCOME = 'receita', 'Receita'
    EXPENSE = 'despesa', 'Despesa'
    TRANSFER = 'transferência', 'Transferência'
 
 
RECURRING_TRANSACTION_TYPE_CHOICES = [
    choice for choice in TransactionType.choices if choice[0] != TransactionType.TRANSFER
]
 