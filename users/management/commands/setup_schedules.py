import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone
from django_q.models import Schedule
from django_q.tasks import schedule


class Command(BaseCommand):
    help = 'Configura os agendamentos automáticos do Django-Q.'

    def handle(self, *args, **kwargs):
        self.stdout.write('Configurando agendamentos do Django-Q...')

        tasks = [
            {'func': 'transactions.tasks.process_all_recurring_transactions', 'hour': 0, 'minute': 0},
            {'func': 'wallets.tasks.notify_due_credit_card_bills', 'hour': 9, 'minute': 0},
            {'func': 'planning.tasks.notify_budget_warnings', 'hour': 10, 'minute': 0},
            {'func': 'transactions.tasks.notify_due_transactions', 'hour': 11, 'minute': 0},
            {'func': 'moneta.tasks.check_and_send_alerts', 'hour': 12, 'minute': 0},
        ]

        now = timezone.now()

        for task in tasks:
            func_name = task['func']
            Schedule.objects.filter(func=func_name).delete()
            
            next_run = now.replace(hour=task['hour'], minute=task['minute'], second=0, microsecond=0)
            if next_run < now:
                next_run += datetime.timedelta(days=1)
                
            schedule(
                func_name,
                schedule_type=Schedule.DAILY,
                repeats=-1,
                next_run=next_run
            )
            self.stdout.write(self.style.SUCCESS(f'Sucesso: {func_name} agendado (Próxima execução: {next_run.strftime("%d/%m/%Y %H:%M")}).'))

        self.stdout.write(self.style.SUCCESS('Todos os agendamentos configurados com sucesso!'))
