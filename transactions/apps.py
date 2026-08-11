from django.apps import AppConfig


class TransactionsConfig(AppConfig):
    name = 'transactions'
    verbose_name = 'Transações'

    def ready(self):
        try:
            from django_q.models import Schedule
            from django_q.tasks import schedule
            
            if not Schedule.objects.filter(func='transactions.tasks.process_all_recurring_transactions').exists():
                schedule('transactions.tasks.process_all_recurring_transactions', schedule_type=Schedule.DAILY, time='00:00')
                
            if not Schedule.objects.filter(func='transactions.tasks.notify_due_transactions').exists():
                schedule('transactions.tasks.notify_due_transactions', schedule_type=Schedule.DAILY, time='08:00')
        except Exception:
            pass
