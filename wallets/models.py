import uuid
from django.db import models
from django.conf import settings

class Account(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name='accounts')
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=50)
    institution = models.CharField(max_length=100, blank=True, null=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    color = models.CharField(max_length=7, default='#000000')
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.type})"

class CreditCard(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name='credit_cards')
    name = models.CharField(max_length=100)
    institution = models.CharField(max_length=100, blank=True, null=True)
    limit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    available_limit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    closing_day = models.PositiveSmallIntegerField()
    due_day = models.PositiveSmallIntegerField()
    color = models.CharField(max_length=7, default='#000000')
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.institution})"
