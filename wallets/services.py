from decimal import Decimal

from django.db import models


def recalculate_account_balance(account):
    """
    Calculates the real current balance of an account based on:
    initial_balance + sum(completed receitas) - sum(completed despesas) - sum(transfers out) + sum(transfers in)
    """
    from moneta.common import TransactionType
    from transactions.models import Transaction, Transfer
    from wallets.models import Account

    # 1. Transações concluídas normais (não-transferências)
    completed_txs = Transaction.objects.filter(
        account=account,
        status=Transaction.Statuses.COMPLETED,
    ).exclude(category__type=TransactionType.TRANSFER)

    incomes = completed_txs.filter(category__type=TransactionType.INCOME).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
    expenses = completed_txs.filter(category__type=TransactionType.EXPENSE).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    # 2. Transferências de saída concluídas
    transfers_out = Transfer.objects.filter(
        out_transaction__account=account,
        out_transaction__status=Transaction.Statuses.COMPLETED,
    ).aggregate(total=models.Sum('out_transaction__amount'))['total'] or Decimal('0.00')

    # 3. Transferências de entrada concluídas
    transfers_in = Transfer.objects.filter(
        in_transaction__account=account,
        in_transaction__status=Transaction.Statuses.COMPLETED,
    ).aggregate(total=models.Sum('in_transaction__amount'))['total'] or Decimal('0.00')

    new_balance = account.initial_balance + incomes - expenses - transfers_out + transfers_in

    # Atualiza o limite disponível caso seja Cartão de Crédito
    if account.type == Account.Types.CREDIT_CARD and hasattr(account, 'credit_card_details'):
        cc = account.credit_card_details
        cc.available_limit = max(Decimal('0.00'), cc.limit - expenses + incomes)
        cc.save()

    Account.objects.filter(id=account.id).update(balance=new_balance)
    account.refresh_from_db()
    return new_balance


def recalculate_all_user_balances(user):
    from wallets.models import Account
    for account in Account.objects.filter(user_id=user.id if hasattr(user, 'id') else user):
        recalculate_account_balance(account)


def calculate_expected_balance(account, end_date=None):
    """
    Calculates the expected balance by adding pending transactions to the current balance.
    """
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



def get_or_create_bill_for_transaction(account, transaction_date):
    import datetime

    from wallets.models import CreditCardBill
    
    if account.type != account.Types.CREDIT_CARD or not hasattr(account, 'credit_card_details'):
        return None
        
    cc = account.credit_card_details
    closing_day = cc.closing_day
    due_day = cc.due_day
    
    # Determina a data de fechamento para a fatura na qual esta transação se enquadra
    if transaction_date.day <= closing_day:
        cycle_month = transaction_date.month
        cycle_year = transaction_date.year
    else:
        cycle_month = transaction_date.month + 1
        cycle_year = transaction_date.year
        if cycle_month > 12:
            cycle_month = 1
            cycle_year += 1
            
    closing_date = datetime.date(cycle_year, cycle_month, closing_day)
    
    if due_day > closing_day:
        due_month = cycle_month
        due_year = cycle_year
    else:
        due_month = cycle_month + 1
        due_year = cycle_year
        if due_month > 12:
            due_month = 1
            due_year += 1
            
    due_date = datetime.date(due_year, due_month, due_day)
    period_date = datetime.date(due_year, due_month, 1)
    
    bill, created = CreditCardBill.objects.get_or_create(
        account=account,
        period_date=period_date,
        defaults={
            'closing_date': closing_date,
            'due_date': due_date,
            'status': CreditCardBill.Statuses.OPEN
        }
    )
    return bill


def pay_credit_card_bill(bill, payment_account_id):
    from django.db import transaction as db_transaction

    from moneta.common import TransactionType
    from transactions.services import create_transfer
    from wallets.models import CreditCardBill
    
    if bill.status == CreditCardBill.Statuses.PAID:
        raise ValueError("Esta fatura já está paga.")
        
    expenses = bill.transactions.filter(category__type=TransactionType.EXPENSE).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
    incomes = bill.transactions.filter(category__type=TransactionType.INCOME).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
    
    total_amount = expenses - incomes
    if total_amount <= 0:
        bill.status = CreditCardBill.Statuses.PAID
        bill.save()
        return bill
        
    with db_transaction.atomic():
        import datetime
        create_transfer(
            user=bill.account.user,
            out_account_id=payment_account_id,
            in_account_id=bill.account.id,
            description=f"Pagamento Fatura {bill.period_date.strftime('%m/%Y')}",
            amount=total_amount,
            tx_date=datetime.date.today(),
            status='concluída'
        )
        
        bill.status = CreditCardBill.Statuses.PAID
        bill.save()
        
    return bill
