from django.apps import AppConfig


class TransactionsConfig(AppConfig):
    name = 'transactions'
    verbose_name = 'Transações'

    def ready(self):
        import transactions.signals  # noqa: F401
        from django.db.models.signals import post_migrate
        post_migrate.connect(_setup_schedules, sender=self)


def _setup_schedules(sender, **kwargs):
    """
    Cria os agendamentos do django-q apenas após as migrações.
    Executado via post_migrate para evitar o RuntimeWarning de acesso ao
    banco durante a inicialização do app (AppConfig.ready).
    """
    try:
        from django_q.models import Schedule
        from django_q.tasks import schedule

        if not Schedule.objects.filter(func='transactions.tasks.process_all_recurring_transactions').exists():
            schedule(
                'transactions.tasks.process_all_recurring_transactions',
                schedule_type=Schedule.DAILY,
                time='00:00',
            )

        if not Schedule.objects.filter(func='transactions.tasks.notify_due_transactions').exists():
            schedule(
                'transactions.tasks.notify_due_transactions',
                schedule_type=Schedule.DAILY,
                time='08:00',
            )
    except Exception:
        pass
