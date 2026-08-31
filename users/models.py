from django.conf import settings


class PushSubscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='push_subscriptions', on_delete=models.CASCADE)
    endpoint = models.URLField(max_length=500)
    auth = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

        verbose_name = 'inscrição push'
        verbose_name_plural = 'inscrições push'
        constraints = [
            models.UniqueConstraint(fields=['user', 'endpoint'], name='unique_push_subscription_per_user'),
        ]

    def __str__(self):
        return f"Push para {self.user.username}"