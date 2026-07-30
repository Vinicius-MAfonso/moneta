import uuid

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone as django_timezone


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    photo_url = models.URLField(blank=True, null=True, verbose_name='URL da foto')
    currency = models.CharField(max_length=3, default='BRL', verbose_name='moeda')
    timezone = models.CharField(max_length=50, default='America/Sao_Paulo', verbose_name='fuso horário')
    created_at = models.DateTimeField(default=django_timezone.now, editable=False, verbose_name='criada em')
    updated_at = models.DateTimeField(default=django_timezone.now, editable=False, verbose_name='atualizada em')

    class Meta:
        verbose_name = 'usuário'
        verbose_name_plural = 'usuários'

    def save(self, *args, **kwargs):
        if not self.created_at:
            self.created_at = django_timezone.now()
        self.updated_at = django_timezone.now()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.username