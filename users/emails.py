from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.contrib.auth import get_user_model

def send_welcome_email(user_id):
    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return False

    context = {
        'user_name': user.first_name or user.username,
        'login_url': f"{settings.SITE_URL.rstrip('/')}/users/login/"
    }

    subject_template = 'users/emails/welcome_subject.txt'
    text_template = 'users/emails/welcome_body.txt'
    html_template = 'users/emails/welcome_body_html.html'

    subject = render_to_string(subject_template, context).strip()
    text_content = render_to_string(text_template, context)
    html_content = render_to_string(html_template, context)

    from_email = settings.DEFAULT_FROM_EMAIL
    to_email = user.email

    if not to_email:
        return False

    msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
    msg.attach_alternative(html_content, "text/html")
    msg.send()

    return True
