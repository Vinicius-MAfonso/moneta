from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    photo_url = models.URLField(blank=True, null=True)
    currency = models.CharField(max_length=3, default='BRL')
    timezone = models.CharField(max_length=50, default='America/Sao_Paulo')
    