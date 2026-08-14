from decimal import Decimal

from django.db import models


def recalculate_account_balance(account):
    from moneta.common import TransactionType
    from transactions.models import Transaction, Transfer
    from wallets.models import Account

    status_filter = [Transaction.Statuses.COMPLETED]
    if account.type == Account.Types.CREDIT_CARD:
        status_filter.append(Transaction.Statuses.PENDING)

    completed_txs = Transaction.objects.filter(
        account=account,
        status__in=status_filter,
    ).exclude(category__type=TransactionType.TRANSFER)

    incomes = completed_txs.filter(category__type=TransactionType.INCOME).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
    expenses = completed_txs.filter(category__type=TransactionType.EXPENSE).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    transfers_out = Transfer.objects.filter(
        out_transaction__account=account,
        out_transaction__status__in=status_filter,
    ).aggregate(total=models.Sum('out_transaction__amount'))['total'] or Decimal('0.00')

    transfers_in = Transfer.objects.filter(
        in_transaction__account=account,
        in_transaction__status__in=status_filter,
    ).aggregate(total=models.Sum('in_transaction__amount'))['total'] or Decimal('0.00')

    new_balance = account.initial_balance + incomes - expenses - transfers_out + transfers_in

    if account.type == Account.Types.CREDIT_CARD and hasattr(account, 'credit_card_details'):
        cc = account.credit_card_details
        cc.available_limit = max(Decimal('0.00'), cc.limit + new_balance)
        cc.save()

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

    from django.db import models
    from django.db import transaction as db_transaction
    from django.utils import timezone

    from moneta.common import TransactionType
    from transactions.services import create_transfer
    from wallets.models import CreditCardBill

    if bill.status == CreditCardBill.Statuses.PAID:
        raise ValueError("Esta fatura já está paga.")

    expenses = bill.transactions.filter(category__type=TransactionType.EXPENSE).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
    incomes = bill.transactions.filter(category__type=TransactionType.INCOME).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
    transfers_in = bill.transactions.filter(transfer_in__isnull=False).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
    transfers_out = bill.transactions.filter(transfer_out__isnull=False).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    total_amount = expenses - incomes - transfers_in + transfers_out
    amount_to_pay = Decimal(payment_amount) if payment_amount is not None else total_amount
    amount_to_pay = min(amount_to_pay, total_amount)

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
            
            # Marcar todas as transações da fatura como concluídas
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
    from decimal import Decimal

    account.name = validated_data['name']
    account.institution = validated_data['institution']
    account.color = validated_data['color']
    if 'balance' in validated_data:
        account.initial_balance = validated_data['balance']

    account.save()

    if account.type == account.Types.CREDIT_CARD and hasattr(account, 'credit_card_details'):
        cc = account.credit_card_details
        diff = validated_data['limit'] - cc.limit
        cc.limit = validated_data['limit']
        cc.available_limit = max(Decimal('0.00'), cc.available_limit + diff)
        cc.closing_day = validated_data['closing_day']
        cc.due_day = validated_data['due_day']
        cc.save()

    recalculate_account_balance(account)
    return account
