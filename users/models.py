import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    photo_url = models.URLField(blank=True, null=True, verbose_name='URL da foto')
    currency = models.CharField(max_length=3, default='BRL', verbose_name='moeda')
    timezone = models.CharField(max_length=50, default='America/Sao_Paulo', verbose_name='fuso horário')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='criada em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='atualizada em')

    class Meta:
        verbose_name = 'usuário'
        verbose_name_plural = 'usuários'

    def __str__(self):
        return self.username


class PushSubscription(models.Model):
    user = models.ForeignKey(User, related_name='push_subscriptions', on_delete=models.CASCADE)
    endpoint = models.URLField(max_length=500)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'inscrição push'
        verbose_name_plural = 'inscrições push'
        unique_together = ('user', 'endpoint')

    def __str__(self):
        return f"Push para {self.user.username}"