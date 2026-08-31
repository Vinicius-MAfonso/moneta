from decimal import Decimal

from django.db import models


def recalculate_account_balance(account):
    from django.utils import timezone

    from moneta.common import TransactionType
    from transactions.models import Transaction, Transfer
    from wallets.models import Account

    status_filter = [Transaction.Statuses.COMPLETED]
    if account.type == Account.Types.CREDIT_CARD:
        status_filter.append(Transaction.Statuses.PENDING)

    txs_query = Transaction.objects.filter(
        account=account,
        status__in=status_filter,
    ).exclude(category__type=TransactionType.TRANSFER)

    transfers_out_query = Transfer.objects.filter(
        out_transaction__account=account,
        out_transaction__status__in=status_filter,
    )

    transfers_in_query = Transfer.objects.filter(
        in_transaction__account=account,
        in_transaction__status__in=status_filter,
    )

    if account.type == Account.Types.CREDIT_CARD:
        today = timezone.now().date()
        # Future projections/subscriptions (recurring or single transactions without installments)
        # should not consume the credit card limit upfront.
        # Only installments (installment_number is not null) consume the limit upfront across future months.
        future_exclusion = models.Q(
            status=Transaction.Statuses.PENDING,
            date__gt=today,
            installment_number__isnull=True
        )
        txs_query = txs_query.exclude(future_exclusion)

        future_transfer_out_exclusion = models.Q(
            out_transaction__status=Transaction.Statuses.PENDING,
            out_transaction__date__gt=today,
            out_transaction__installment_number__isnull=True
        )
        transfers_out_query = transfers_out_query.exclude(future_transfer_out_exclusion)

        future_transfer_in_exclusion = models.Q(
            in_transaction__status=Transaction.Statuses.PENDING,
            in_transaction__date__gt=today,
            in_transaction__installment_number__isnull=True
        )
        transfers_in_query = transfers_in_query.exclude(future_transfer_in_exclusion)

    incomes = txs_query.filter(category__type=TransactionType.INCOME).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
    expenses = txs_query.filter(category__type=TransactionType.EXPENSE).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    transfers_out = transfers_out_query.aggregate(total=models.Sum('out_transaction__amount'))['total'] or Decimal('0.00')
    transfers_in = transfers_in_query.aggregate(total=models.Sum('in_transaction__amount'))['total'] or Decimal('0.00')

    new_balance = account.initial_balance + incomes - expenses - transfers_out + transfers_in
    new_balance = Decimal(new_balance).quantize(Decimal('.01'))

    Account.objects.filter(id=account.id).update(balance=new_balance)
    account.refresh_from_db()
    return new_balance


def recalculate_all_user_balances(user):
    from wallets.models import Account
    for account in Account.objects.filter(user_id=user.id if hasattr(user, 'id') else user):
        recalculate_account_balance(account)


def calculate_expected_balance(account, end_date=None):
    from moneta.common import TransactionType
    from transactions.models import Transaction, Transfer

    pending_txs = Transaction.objects.filter(
        account=account,
        status=Transaction.Statuses.PENDING,
    ).exclude(category__type=TransactionType.TRANSFER)

    if end_date:
        pending_txs = pending_txs.filter(date__lte=end_date)

    incomes = pending_txs.filter(category__type=TransactionType.INCOME).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
    expenses = pending_txs.filter(category__type=TransactionType.EXPENSE).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    transfers_out_qs = Transfer.objects.filter(
        out_transaction__account=account,
        out_transaction__status=Transaction.Statuses.PENDING,
    )
    if end_date:
        transfers_out_qs = transfers_out_qs.filter(out_transaction__date__lte=end_date)
    transfers_out = transfers_out_qs.aggregate(total=models.Sum('out_transaction__amount'))['total'] or Decimal('0.00')

    transfers_in_qs = Transfer.objects.filter(
        in_transaction__account=account,
        in_transaction__status=Transaction.Statuses.PENDING,
    )
    if end_date:
        transfers_in_qs = transfers_in_qs.filter(in_transaction__date__lte=end_date)
    transfers_in = transfers_in_qs.aggregate(total=models.Sum('in_transaction__amount'))['total'] or Decimal('0.00')

    return account.balance + incomes - expenses - transfers_out + transfers_in


def get_expected_balances_bulk(accounts_qs, end_date=None):

    from django.db import models

    from moneta.common import TransactionType
    from transactions.models import Transaction, Transfer

    account_ids = [a.id for a in accounts_qs]
    if not account_ids:
        return {}
    
    pending_txs = Transaction.objects.filter(
        account_id__in=account_ids,
        status=Transaction.Statuses.PENDING
    ).exclude(category__type=TransactionType.TRANSFER)
    if end_date:
        pending_txs = pending_txs.filter(date__lte=end_date)
        
    stats = pending_txs.values('account_id', 'category__type').annotate(total=models.Sum('amount'))
    
    transfers_out_qs = Transfer.objects.filter(
        out_transaction__account_id__in=account_ids,
        out_transaction__status=Transaction.Statuses.PENDING
    )
    if end_date:
        transfers_out_qs = transfers_out_qs.filter(out_transaction__date__lte=end_date)
    transfers_out_stats = transfers_out_qs.values('out_transaction__account_id').annotate(total=models.Sum('out_transaction__amount'))

    transfers_in_qs = Transfer.objects.filter(
        in_transaction__account_id__in=account_ids,
        in_transaction__status=Transaction.Statuses.PENDING
    )
    if end_date:
        transfers_in_qs = transfers_in_qs.filter(in_transaction__date__lte=end_date)
    transfers_in_stats = transfers_in_qs.values('in_transaction__account_id').annotate(total=models.Sum('in_transaction__amount'))

    balances = {a.id: a.balance for a in accounts_qs}
    
    for s in stats:
        if s['category__type'] == TransactionType.INCOME:
            balances[s['account_id']] += s['total']
        elif s['category__type'] == TransactionType.EXPENSE:
            balances[s['account_id']] -= s['total']
            
    for s in transfers_out_stats:
        balances[s['out_transaction__account_id']] -= s['total']
        
    for s in transfers_in_stats:
        balances[s['in_transaction__account_id']] += s['total']

    return balances


def calculate_balance_at_date(user, target_date, account_id=None):
    from moneta.common import TransactionType
    from transactions.models import Transaction, Transfer
    from wallets.models import Account

    accounts = Account.objects.filter(user=user).exclude(type=Account.Types.CREDIT_CARD)
    if account_id:
        accounts = accounts.filter(id=account_id)
        
    initial_balance = accounts.aggregate(total=models.Sum('initial_balance'))['total'] or Decimal('0.00')

    txs = Transaction.objects.filter(
        account__in=accounts,
        date__lte=target_date
    ).exclude(category__type=TransactionType.TRANSFER)

    incomes = txs.filter(category__type=TransactionType.INCOME).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
    expenses = txs.filter(category__type=TransactionType.EXPENSE).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    transfers_out = Transfer.objects.filter(
        out_transaction__account__in=accounts,
        out_transaction__date__lte=target_date
    ).aggregate(total=models.Sum('out_transaction__amount'))['total'] or Decimal('0.00')

    transfers_in = Transfer.objects.filter(
        in_transaction__account__in=accounts,
        in_transaction__date__lte=target_date
    ).aggregate(total=models.Sum('in_transaction__amount'))['total'] or Decimal('0.00')

    return initial_balance + incomes - expenses - transfers_out + transfers_in


def calculate_balances_for_dates(user, dates, account_id=None):
    """
    Calculates account balance at the end of each specified date efficiently in batch.
    Returns a dict mapping {date: balance_decimal}.
    """
    if not dates:
        return {}

    import datetime

    from moneta.common import TransactionType
    from transactions.models import Transaction, Transfer
    from wallets.models import Account

    unique_dates = sorted(set(dates))
    min_date = unique_dates[0]
    max_date = unique_dates[-1]

    accounts = Account.objects.filter(user=user).exclude(type=Account.Types.CREDIT_CARD)
    if account_id:
        accounts = accounts.filter(id=account_id)

    initial_balance = accounts.aggregate(total=models.Sum('initial_balance'))['total'] or Decimal('0.00')

    prior_txs = Transaction.objects.filter(
        account__in=accounts,
        date__lt=min_date
    ).exclude(category__type=TransactionType.TRANSFER)

    prior_incomes = prior_txs.filter(category__type=TransactionType.INCOME).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
    prior_expenses = prior_txs.filter(category__type=TransactionType.EXPENSE).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    prior_tf_out = Transfer.objects.filter(
        out_transaction__account__in=accounts,
        out_transaction__date__lt=min_date
    ).aggregate(total=models.Sum('out_transaction__amount'))['total'] or Decimal('0.00')

    prior_tf_in = Transfer.objects.filter(
        in_transaction__account__in=accounts,
        in_transaction__date__lt=min_date
    ).aggregate(total=models.Sum('in_transaction__amount'))['total'] or Decimal('0.00')

    running_balance = initial_balance + prior_incomes - prior_expenses - prior_tf_out + prior_tf_in

    range_txs = Transaction.objects.filter(
        account__in=accounts,
        date__gte=min_date,
        date__lte=max_date
    ).exclude(category__type=TransactionType.TRANSFER)

    range_incomes_by_date = dict(
        range_txs.filter(category__type=TransactionType.INCOME)
        .values('date')
        .annotate(total=models.Sum('amount'))
        .values_list('date', 'total')
    )

    range_expenses_by_date = dict(
        range_txs.filter(category__type=TransactionType.EXPENSE)
        .values('date')
        .annotate(total=models.Sum('amount'))
        .values_list('date', 'total')
    )

    range_tf_out_by_date = dict(
        Transfer.objects.filter(
            out_transaction__account__in=accounts,
            out_transaction__date__gte=min_date,
            out_transaction__date__lte=max_date
        )
        .values('out_transaction__date')
        .annotate(total=models.Sum('out_transaction__amount'))
        .values_list('out_transaction__date', 'total')
    )

    range_tf_in_by_date = dict(
        Transfer.objects.filter(
            in_transaction__account__in=accounts,
            in_transaction__date__gte=min_date,
            in_transaction__date__lte=max_date
        )
        .values('in_transaction__date')
        .annotate(total=models.Sum('in_transaction__amount'))
        .values_list('in_transaction__date', 'total')
    )

    delta_day = datetime.timedelta(days=1)
    curr = min_date
    date_balances = {}
    target_set = set(unique_dates)

    while curr <= max_date:
        inc = range_incomes_by_date.get(curr, Decimal('0.00'))
        exp = range_expenses_by_date.get(curr, Decimal('0.00'))
        tout = range_tf_out_by_date.get(curr, Decimal('0.00'))
        tin = range_tf_in_by_date.get(curr, Decimal('0.00'))
        running_balance = running_balance + inc - exp - tout + tin
        if curr in target_set:
            date_balances[curr] = running_balance
        curr += delta_day

    return date_balances


def get_or_create_bill_for_transaction(account, transaction_date):
    import datetime

    from wallets.models import CreditCardBill

    if account.type != account.Types.CREDIT_CARD or not hasattr(account, 'credit_card_details'):
        return None

    cc = account.credit_card_details
    closing_day = cc.closing_day
    due_day = cc.due_day

    if transaction_date.day <= closing_day:
        cycle_month = transaction_date.month
        cycle_year = transaction_date.year
    else:
        cycle_month = transaction_date.month + 1
        cycle_year = transaction_date.year
        if cycle_month > 12:
            cycle_month = 1
            cycle_year += 1

    import calendar
    def get_valid_date(year, month, day):
        _, max_day = calendar.monthrange(year, month)
        return datetime.date(year, month, min(day, max_day))

    while True:
        closing_date = get_valid_date(cycle_year, cycle_month, closing_day)

        if due_day > closing_day:
            due_month = cycle_month
            due_year = cycle_year
        else:
            due_month = cycle_month + 1
            due_year = cycle_year
            if due_month > 12:
                due_month = 1
                due_year += 1

        due_date = get_valid_date(due_year, due_month, due_day)
        period_date = datetime.date(due_year, due_month, 1)

        bill, _created = CreditCardBill.objects.get_or_create(
            account=account,
            period_date=period_date,
            defaults={
                'closing_date': closing_date,
                'due_date': due_date,
                'status': CreditCardBill.Statuses.OPEN
            }
        )

        if bill.status == CreditCardBill.Statuses.OPEN:
            break

        cycle_month += 1
        if cycle_month > 12:
            cycle_month = 1
            cycle_year += 1

    return bill


def pay_credit_card_bill(bill, payment_account_id, payment_amount=None):
    from decimal import Decimal

    from django.db import transaction as db_transaction
    from django.utils import timezone

    from transactions.services import create_transfer
    from wallets.models import Account, CreditCardBill

    if bill.status == CreditCardBill.Statuses.PAID:
        raise ValueError("Esta fatura já está paga.")

    payment_account = Account.objects.get(id=payment_account_id)
    
    summary = get_bill_summary(bill)
    total_amount = summary['remaining_amount']
    
    amount_to_pay = Decimal(payment_amount) if payment_amount is not None else total_amount
    amount_to_pay = min(amount_to_pay, total_amount)

    if payment_account.type != Account.Types.CREDIT_CARD and payment_account.balance < amount_to_pay:
        bal_str = f"{payment_account.balance:.2f}".replace('.', ',')
        raise ValueError(
            f"Saldo insuficiente na conta '{payment_account.name}'. "
            f"Saldo disponível: R$ {bal_str}."
        )

    if amount_to_pay <= 0:
        if total_amount <= 0:
            bill.status = CreditCardBill.Statuses.PAID
            bill.save()
        else:
            raise ValueError("O valor do pagamento deve ser estritamente maior que zero.")
        return bill

    with db_transaction.atomic():
        bill = CreditCardBill.objects.select_for_update().get(id=bill.id)
        if bill.status == CreditCardBill.Statuses.PAID:
            raise ValueError("Esta fatura já está paga.")

        transfer = create_transfer(
            user=bill.account.user,
            out_account_id=payment_account_id,
            in_account_id=bill.account.id,
            description=f"Pagamento Fatura {bill.period_date.strftime('%m/%Y')}",
            amount=amount_to_pay,
            tx_date=timezone.now().date(),
            status='concluída'
        )

        in_tx = transfer.in_transaction
        in_tx.bill = bill
        in_tx.save()

        if amount_to_pay >= total_amount:
            bill.status = CreditCardBill.Statuses.PAID
            bill.save()
            
            from transactions.models import Transaction
            bill.transactions.filter(status=Transaction.Statuses.PENDING).update(status=Transaction.Statuses.COMPLETED)

    return bill

def reopen_credit_card_bill(bill):
    from django.db import transaction as db_transaction
    from django.utils import timezone

    from wallets.models import CreditCardBill

    with db_transaction.atomic():
        if bill.status != CreditCardBill.Statuses.PAID:
            raise ValueError("Apenas faturas pagas podem ser reabertas.")

        payment_txs = bill.transactions.filter(transfer_in__isnull=False)
        for tx in payment_txs:
            transfer = getattr(tx, 'transfer_in', None)
            if transfer:
                out_tx = transfer.out_transaction
                tx.delete()
                out_tx.delete()

        if timezone.now().date() > bill.closing_date:
            bill.status = CreditCardBill.Statuses.CLOSED
        else:
            bill.status = CreditCardBill.Statuses.OPEN
        bill.save()

        from transactions.models import Transaction
        bill.transactions.filter(status=Transaction.Statuses.COMPLETED).update(status=Transaction.Statuses.PENDING)

def adjust_account_balance(account, new_balance, adjustment_type, user):
    """
    Adjust the account balance either by updating the initial balance
    or by creating a compensatory transaction.
    """
    from django.utils import timezone

    from moneta.common import TransactionType
    from transactions.models import Category, Transaction

    if adjustment_type == 'initial':
        account.initial_balance = new_balance
        account.save(update_fields=['initial_balance'])
        recalculate_account_balance(account)
        return True, "initial"

    elif adjustment_type == 'transaction':
        delta = new_balance - account.balance
        if delta == 0:
            return False, "no_change"

        tx_type = TransactionType.INCOME if delta > 0 else TransactionType.EXPENSE
        category_name = "Reajuste de Saldo Positivo" if delta > 0 else "Reajuste de Saldo Negativo"
        category, _ = Category.objects.get_or_create(
            user=user,
            name=category_name,
            defaults={
                'type': tx_type,
                'color': '#64748B',
                'icon': '⚖️',
                'is_system': True,
            }
        )
        if not category.is_system:
            Category.objects.filter(pk=category.pk).update(is_system=True)

        Transaction.objects.create(
            user=user,
            account=account,
            category=category,
            amount=abs(delta),
            date=timezone.now().date(),
            description="Reajuste de Saldo",
            status=Transaction.Statuses.COMPLETED
        )

        recalculate_account_balance(account)
        return True, "transaction"
    
    return False, "invalid_type"


def update_account(account, validated_data):
    """
    Update account data including credit card specifics if applicable.
    """

    account.name = validated_data['name']
    account.institution = validated_data['institution']
    account.color = validated_data['color']
    if 'balance' in validated_data:
        account.initial_balance = validated_data['balance']

    account.save()

    if account.type == account.Types.CREDIT_CARD and hasattr(account, 'credit_card_details'):
        cc = account.credit_card_details
        cc.limit = validated_data['limit']
        old_closing = cc.closing_day
        old_due = cc.due_day

        cc.closing_day = validated_data['closing_day']
        cc.due_day = validated_data['due_day']
        cc.save()

        if old_closing != cc.closing_day or old_due != cc.due_day:
            import calendar
            import datetime

            from wallets.models import CreditCardBill
            
            open_bills = account.bills.filter(status=CreditCardBill.Statuses.OPEN)
            for bill in open_bills:
                due_month = bill.period_date.month
                due_year = bill.period_date.year
                
                _, max_day = calendar.monthrange(due_year, due_month)
                bill.due_date = datetime.date(due_year, due_month, min(cc.due_day, max_day))
                
                if cc.due_day > cc.closing_day:
                    cycle_month = due_month
                    cycle_year = due_year
                else:
                    cycle_month = due_month - 1
                    cycle_year = due_year
                    if cycle_month < 1:
                        cycle_month = 12
                        cycle_year -= 1
                
                _, max_day = calendar.monthrange(cycle_year, cycle_month)
                bill.closing_date = datetime.date(cycle_year, cycle_month, min(cc.closing_day, max_day))
                bill.save()

    recalculate_account_balance(account)
    return account


def get_bill_summary(bill):
    from decimal import Decimal

    from django.db.models import Sum

    from moneta.common import TransactionType
    
    expenses = bill.transactions.filter(category__type=TransactionType.EXPENSE).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    incomes = bill.transactions.filter(category__type=TransactionType.INCOME).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    transfers_out = bill.transactions.filter(transfer_out__isnull=False).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    paid_amount = bill.transactions.filter(transfer_in__isnull=False).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    total = expenses - incomes + transfers_out
    remaining_amount = total - paid_amount
    
    return {
        'expenses': expenses,
        'incomes': incomes,
        'transfers_out': transfers_out,
        'total': total,
        'paid_amount': paid_amount,
        'remaining_amount': remaining_amount
    }


def create_account(user, account_data):
    from django.db import transaction

    from wallets.models import Account, CreditCardDetails

    with transaction.atomic():
        account = Account.objects.create(
            user=user,
            name=account_data['name'],
            type=account_data['type'],
            institution=account_data.get('institution'),
            balance=account_data.get('balance', Decimal('0.00')),
            initial_balance=account_data.get('balance', Decimal('0.00')),
            color=account_data.get('color', '#000000'),
        )
        if account_data['type'] == Account.Types.CREDIT_CARD:
            CreditCardDetails.objects.create(
                account=account,
                limit=account_data.get('limit', Decimal('0.00')),
                closing_day=account_data.get('closing_day', 1),
                due_day=account_data.get('due_day', 10),
            )
        return account


def delete_account(account):
    from django.db import transaction
    with transaction.atomic():
        account.delete()


def get_credit_card_timeline(user, start_date, months=12):
    from datetime import timedelta

    from dateutil.relativedelta import relativedelta
    from django.db.models import Q, Sum
    from django.db.models.functions import TruncMonth

    from moneta.common import TransactionType
    from transactions.models import RecurringTransaction, Transaction
    from transactions.services import add_months, add_years
    from wallets.models import Account

    end_date = start_date + relativedelta(months=months)

    monthly_totals = Transaction.objects.filter(
        user=user,
        account__type=Account.Types.CREDIT_CARD,
        status=Transaction.Statuses.PENDING,
        date__gte=start_date,
        date__lt=end_date,
        category__type=TransactionType.EXPENSE
    ).annotate(
        month=TruncMonth('date')
    ).values('month').annotate(total=Sum('amount')).order_by('month')

    totals_dict = {}
    for item in monthly_totals:
        m = item['month']
        if hasattr(m, 'date'):
            m_date = m.date()
        elif isinstance(m, str):
            import datetime as dt
            m_date = dt.datetime.strptime(m[:10], '%Y-%m-%d').date()
        else:
            m_date = m
        totals_dict[m_date] = item['total']

    active_recurring = RecurringTransaction.objects.filter(
        user=user,
        active=True,
        account__active=True,
        account__type=Account.Types.CREDIT_CARD,
        category__type=TransactionType.EXPENSE
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=start_date)
    ).prefetch_related('ignored_date_entries')

    if active_recurring.exists():
        existing_recurring_dates = set(
            Transaction.objects.filter(
                recurring__in=active_recurring,
                date__gte=start_date,
                date__lt=end_date
            ).values_list('recurring_id', 'date')
        )

        for rec in active_recurring:
            ignored_dates_set = {entry.date for entry in rec.ignored_date_entries.all()}
            current_date = rec.start_date

            if current_date < start_date:
                if rec.frequency == RecurringTransaction.Frequencies.DAILY:
                    current_date = start_date
                elif rec.frequency == RecurringTransaction.Frequencies.WEEKLY:
                    weeks_diff = max(0, (start_date - current_date).days // 7)
                    current_date += timedelta(weeks=weeks_diff)
                    while current_date < start_date:
                        current_date += timedelta(weeks=1)
                elif rec.frequency == RecurringTransaction.Frequencies.MONTHLY:
                    months_diff = (start_date.year - current_date.year) * 12 + (start_date.month - current_date.month)
                    current_date = add_months(rec.start_date, months_diff)
                    if current_date < start_date:
                        current_date = add_months(current_date, 1)
                elif rec.frequency == RecurringTransaction.Frequencies.YEARLY:
                    years_diff = max(0, start_date.year - current_date.year)
                    current_date = add_years(rec.start_date, years_diff)
                    if current_date < start_date:
                        current_date = add_years(current_date, 1)

            loop_guard = 0
            while current_date < end_date and (rec.end_date is None or current_date <= rec.end_date) and loop_guard < 500:
                loop_guard += 1
                if current_date >= start_date and current_date not in ignored_dates_set and (rec.id, current_date) not in existing_recurring_dates:
                    month_key = current_date.replace(day=1)
                    totals_dict[month_key] = totals_dict.get(month_key, Decimal('0.00')) + rec.amount

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

    timeline = []
    months_pt = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    
    for i in range(months):
        month_date = start_date + relativedelta(months=i)
        total = totals_dict.get(month_date, Decimal('0.00'))
        month_name = months_pt[month_date.month - 1]
        
        timeline.append({
            'date': month_date,
            'label': f"{month_name}/{month_date.year}",
            'total': total
        })

    return timeline
