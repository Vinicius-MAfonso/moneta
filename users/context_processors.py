from django.utils import timezone


def notifications(request):
    if request.user.is_authenticated:
        from users.models import Notification
        from users.services import run_user_daily_checks

        today_str = str(timezone.localdate())
        if hasattr(request, 'session') and request.session.get('last_daily_check') != today_str:
            run_user_daily_checks(request.user)
            request.session['last_daily_check'] = today_str

        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return {'unread_notifications_count': count}
    return {'unread_notifications_count': 0}
