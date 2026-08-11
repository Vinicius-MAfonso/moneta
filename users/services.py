import json

from django.conf import settings
from pywebpush import WebPushException, webpush


def send_push_notification(user, title, body, url='/dashboard/'):
    """
    Sends a Web Push notification to all active subscriptions of a user.
    """
    subscriptions = user.push_subscriptions.all()
    if not subscriptions.exists():
        return
        
    payload = json.dumps({
        'title': title,
        'body': body,
        'url': url
    })
    
    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh,
                        "auth": sub.auth
                    }
                },
                data=payload,
                vapid_private_key=str(settings.VAPID_PRIVATE_KEY),
                vapid_claims={
                    "sub": settings.VAPID_ADMIN_EMAIL
                }
            )
        except WebPushException as ex:
            if ex.response is not None and ex.response.status_code in [404, 410]:
                sub.delete()
            print("Web Push Error:", repr(ex))
