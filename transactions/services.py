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
    Automatically generates missing scheduled transaction or transfer instances for all active
    recurring rules of the user up to target_end_date.
    """
    from transactions.models import Transaction, Transfer, RecurringTransaction
    from moneta.common import TransactionType
    from wallets.models import Account
    from wallets.services import get_or_create_bill_for_transaction

    today = timezone.now().date()
    if not target_end_date:
        target_end_date = add_months(today, 2)

    active_recurring = RecurringTransaction.objects.filter(user=user, active=True).select_related('account', 'target_account', 'category')

    for rec in active_recurring:
        current_date = rec.start_date
        rec_end = rec.end_date if rec.end_date else target_end_date
        effective_limit = min(target_end_date, rec_end)

        loop_guard = 0
        while current_date <= effective_limit and loop_guard < 500:
            loop_guard += 1
            exists = Transaction.objects.filter(recurring=rec, date=current_date).exists()
            if not exists:
                status = Transaction.Statuses.COMPLETED if current_date <= today else Transaction.Statuses.PENDING

                if rec.category.type == TransactionType.TRANSFER and rec.target_account:
                    out_tx = Transaction.objects.create(
                        user=user,
                        account=rec.account,
                        category=rec.category,
                        description=f"Transferência p/ {rec.target_account.name}: {rec.description} (Recorrente)",
                        amount=rec.amount,
                        date=current_date,
                        status=status,
                        recurring=rec,
                    )
                    in_tx = Transaction.objects.create(
                        user=user,
                        account=rec.target_account,
                        category=rec.category,
                        description=f"Transferência de {rec.account.name}: {rec.description} (Recorrente)",
                        amount=rec.amount,
                        date=current_date,
                        status=status,
                        recurring=rec,
                    )
                    Transfer.objects.create(
                        user=user,
                        out_transaction=out_tx,
                        in_transaction=in_tx,
                    )
                else:
                    bill = None
                    if rec.account.type == Account.Types.CREDIT_CARD:
                        bill = get_or_create_bill_for_transaction(rec.account, current_date)

                    Transaction.objects.create(
                        user=user,
                        account=rec.account,
                        category=rec.category,
                        description=f"{rec.description} (Recorrente)",
                        amount=rec.amount,
                        date=current_date,
                        status=status,
                        recurring=rec,
                        bill=bill,
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


def create_transfer(user, out_account_id, in_account_id, description, amount, tx_date, status, tag_ids=None, is_recurring=False, frequency='monthly', recurring_end_date=None):
    from django.db import transaction as db_transaction
    from django.shortcuts import get_object_or_404
    from wallets.models import Account
    from transactions.models import Category, Transaction, Transfer, RecurringTransaction
    from django_q.tasks import async_task
    from moneta.common import TransactionType

    out_account = get_object_or_404(Account, id=out_account_id, user=user)
    in_account = get_object_or_404(Account, id=in_account_id, user=user)

    category, _ = Category.objects.get_or_create(
        user=user,
        name="Transferência",
        defaults={"type": TransactionType.TRANSFER, "color": "#737373"}
    )

    with db_transaction.atomic():
        recurring_obj = None
        if is_recurring:
            recurring_obj = RecurringTransaction.objects.create(
                user=user,
                account=out_account,
                target_account=in_account,
                category=category,
                description=description,
                amount=amount,
                frequency=frequency,
                start_date=tx_date,
                end_date=recurring_end_date,
                active=True,
            )

        out_tx = Transaction.objects.create(
            user=user,
            account=out_account,
            category=category,
            description=f"Transferência p/ {in_account.name}: {description}",
            amount=amount,
            date=tx_date,
            status=Transaction.Statuses.COMPLETED,
            recurring=recurring_obj,
        )
        in_tx = Transaction.objects.create(
            user=user,
            account=in_account,
            category=category,
            description=f"Transferência de {out_account.name}: {description}",
            amount=amount,
            date=tx_date,
            status=Transaction.Statuses.COMPLETED,
            recurring=recurring_obj,
        )
        if tag_ids:
            out_tx.tags.set(tag_ids)
            in_tx.tags.set(tag_ids)

        Transfer.objects.create(
            user=user,
            out_transaction=out_tx,
            in_transaction=in_tx,
        )

        if is_recurring:
            async_task('transactions.services.process_recurring_transactions', user)

        async_task('wallets.tasks.async_recalculate_user_balances', user)


def create_regular_transaction(user, account_id, category_id, description, amount, tx_date, status, tag_ids=None, is_recurring=False, frequency='monthly', recurring_end_date=None):
    from django.db import transaction as db_transaction
    from django.shortcuts import get_object_or_404
    from transactions.models import Category, Transaction, RecurringTransaction
    from wallets.models import Account
    from wallets.services import get_or_create_bill_for_transaction
    from django_q.tasks import async_task

    account = get_object_or_404(Account, id=account_id, user=user)
    category = get_object_or_404(Category, id=category_id, user=user)

    with db_transaction.atomic():
        recurring_obj = None
        if is_recurring:
            recurring_obj = RecurringTransaction.objects.create(
                user=user,
                account=account,
                category=category,
                description=description,
                amount=amount,
                frequency=frequency,
                start_date=tx_date,
                end_date=recurring_end_date,
                active=True,
            )

        bill = None
        if account.type == Account.Types.CREDIT_CARD:
            bill = get_or_create_bill_for_transaction(account, tx_date)

        tx = Transaction.objects.create(
            user=user,
            account=account,
            category=category,
            description=description,
            amount=amount,
            date=tx_date,
            status=status,
            recurring=recurring_obj,
            bill=bill,
        )
        if tag_ids:
            tx.tags.set(tag_ids)

        if is_recurring:
            async_task('transactions.services.process_recurring_transactions', user)

        async_task('wallets.tasks.async_recalculate_user_balances', user)
