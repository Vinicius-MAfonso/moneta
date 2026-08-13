from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from planning.models import Goal
from wallets.models import CreditCardBill


def check_and_send_alerts():
    today = date.today()
    tomorrow = today + timedelta(days=1)
    
    bills_due_tomorrow = CreditCardBill.objects.filter(
        status=CreditCardBill.Statuses.OPEN,
        due_date=tomorrow,
        is_due_tomorrow_notified=False
    ).select_related('account', 'account__user')
    
    for bill in bills_due_tomorrow:
        user = bill.account.user
        if user.email:
            context = {
                'user_name': user.first_name or user.username,
                'account_name': bill.account.name,
                'due_date': bill.due_date.strftime('%d/%m/%Y'),
                'login_url': f"{settings.SITE_URL.rstrip('/')}/users/login/"
            }
            subject = f"Alerta Moneta: Fatura do cartão {bill.account.name} vence amanhã!"
            text_content = render_to_string('moneta/emails/bill_due_body.txt', context)
            html_content = render_to_string('moneta/emails/bill_due_body_html.html', context)
            
            msg = EmailMultiAlternatives(
                subject,
                text_content,
                settings.DEFAULT_FROM_EMAIL,
                [user.email]
            )
            msg.attach_alternative(html_content, "text/html")
            try:
                msg.send(fail_silently=True)
            except Exception:
                pass
        bill.is_due_tomorrow_notified = True
        bill.save(update_fields=['is_due_tomorrow_notified'])
        
    active_goals = Goal.objects.filter(is_near_target_notified=False).select_related('user')
    
    for goal in active_goals:
        if goal.target_amount > 0 and goal.current_amount >= (goal.target_amount * Decimal('0.9')) and goal.current_amount < goal.target_amount:
            user = goal.user
            if user.email:
                context = {
                    'user_name': user.first_name or user.username,
                    'goal_name': goal.name,
                    'current_amount': f"{goal.current_amount:.2f}".replace('.', ','),
                    'target_amount': f"{goal.target_amount:.2f}".replace('.', ','),
                    'login_url': f"{settings.SITE_URL.rstrip('/')}/users/login/"
                }
                subject = f"Alerta Moneta: Sua meta '{goal.name}' está quase lá!"
                text_content = render_to_string('moneta/emails/goal_near_body.txt', context)
                html_content = render_to_string('moneta/emails/goal_near_body_html.html', context)
                
                msg = EmailMultiAlternatives(
                    subject,
                    text_content,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email]
                )
                msg.attach_alternative(html_content, "text/html")
                try:
                    msg.send(fail_silently=True)
                except Exception:
                    pass
            goal.is_near_target_notified = True
            goal.save(update_fields=['is_near_target_notified'])
