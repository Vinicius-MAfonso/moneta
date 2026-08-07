import calendar
from datetime import date, timedelta
from django.utils import timezone


def add_months(orig_date, months=1):
    new_year = orig_date.year + (orig_date.month + months - 1) // 12
    new_month = (orig_date.month + months - 1) % 12 + 1
    max_day = calendar.monthrange(new_year, new_month)[1]
    new_day = min(orig_date.day, max_day)
    return date(new_year, new_month, new_day)


def add_years(orig_date, years=1):
    try:
        return orig_date.replace(year=orig_date.year + years)
    except ValueError:
        return orig_date.replace(year=orig_date.year + years, day=28)


def process_recurring_transactions(user, target_end_date=None):
    """
    Automatically generates missing scheduled transaction instances for all active
    recurring transaction rules of the user up to target_end_date.
    """
    from transactions.models import Transaction, RecurringTransaction

    today = timezone.now().date()
    if not target_end_date:
        target_end_date = add_months(today, 2)

    active_recurring = RecurringTransaction.objects.filter(user=user, active=True)

    for rec in active_recurring:
        current_date = rec.start_date
        rec_end = rec.end_date if rec.end_date else target_end_date
        effective_limit = min(target_end_date, rec_end)

        # Safeguard iteration count to prevent infinite loop
        loop_guard = 0
        while current_date <= effective_limit and loop_guard < 500:
            loop_guard += 1
            exists = Transaction.objects.filter(recurring=rec, date=current_date).exists()
            if not exists:
                status = Transaction.Statuses.COMPLETED if current_date <= today else Transaction.Statuses.PENDING
                Transaction.objects.create(
                    user=user,
                    account=rec.account,
                    category=rec.category,
                    description=f"{rec.description} (Recorrente)",
                    amount=rec.amount,
                    date=current_date,
                    status=status,
                    recurring=rec,
                )

            # Advance date based on frequency
            if rec.frequency == RecurringTransaction.Frequencies.DAILY:
                current_date += timedelta(days=1)
            elif rec.frequency == RecurringTransaction.Frequencies.WEEKLY:
                current_date += timedelta(weeks=1)
            elif rec.frequency == RecurringTransaction.Frequencies.MONTHLY:
                current_date = add_months(current_date, 1)
            elif rec.frequency == RecurringTransaction.Frequencies.YEARLY:
                current_date = add_years(current_date, 1)
            else:
                break
