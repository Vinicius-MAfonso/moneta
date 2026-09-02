from django.conf import settings
from django.db import models



class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='notifications', on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    message = models.TextField()
    url = models.CharField(max_length=255, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'notificação'
        verbose_name_plural = 'notificações'
        ordering = ['-created_at']

    def __str__(self):
        return f"Notificação: {self.title} - {self.user.username}"
