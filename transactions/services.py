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
    from moneta.common import TransactionType
    from transactions.models import RecurringTransaction, Transaction, Transfer
    from wallets.models import Account
    from wallets.services import get_or_create_bill_for_transaction

    today = timezone.now().date()
    if not target_end_date:
        target_end_date = add_months(today, 2)

    active_recurring = RecurringTransaction.objects.filter(user=user, active=True).select_related(
        'account', 'target_account', 'category'
    ).prefetch_related('ignored_date_entries')

    for rec in active_recurring:
        ignored_dates_set = {entry.date for entry in rec.ignored_date_entries.all()}
        current_date = rec.start_date
        rec_end = rec.end_date if rec.end_date else target_end_date
        effective_limit = min(target_end_date, rec_end)

        loop_guard = 0
        while current_date <= effective_limit and loop_guard < 500:
            loop_guard += 1
            exists = Transaction.objects.filter(recurring=rec, date=current_date).exists()
            if not exists and current_date not in ignored_dates_set:
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
    from django_q.tasks import async_task

    from moneta.common import TransactionType
    from transactions.models import (
        Category,
        RecurringTransaction,
        Transaction,
        Transfer,
    )
    from wallets.models import Account

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

        transfer = Transfer.objects.create(
            user=user,
            out_transaction=out_tx,
            in_transaction=in_tx,
        )

        if is_recurring:
            db_transaction.on_commit(
                lambda: async_task('transactions.services.process_recurring_transactions', user)
            )

        from wallets.services import recalculate_account_balance
        recalculate_account_balance(out_account)
        recalculate_account_balance(in_account)

        return transfer


def create_regular_transaction(user, account_id, category_id, description, amount, tx_date, status, tag_ids=None, is_recurring=False, frequency='monthly', recurring_end_date=None, installments=1):
    from decimal import Decimal
    
    from django.db import transaction as db_transaction
    from django.shortcuts import get_object_or_404
    from django_q.tasks import async_task

    from transactions.models import Category, RecurringTransaction, Transaction
    from wallets.models import Account
    from wallets.services import get_or_create_bill_for_transaction

    account = get_object_or_404(Account, id=account_id, user=user)
    category = get_object_or_404(Category, id=category_id, user=user)
    
    if account.type != Account.Types.CREDIT_CARD:
        installments = 1

    with db_transaction.atomic():
        if installments > 1:
            base_amount = (amount / Decimal(installments)).quantize(Decimal('.01'))
            if base_amount < Decimal('0.01'):
                raise ValueError("O valor é muito pequeno para essa quantidade de parcelas.")
            remaining_amount = amount - (base_amount * (installments - 1))
            if remaining_amount < Decimal('0.01'):
                raise ValueError("O valor restante da última parcela seria inválido.")
            
            for i in range(1, installments + 1):
                current_amount = base_amount if i < installments else remaining_amount
                current_date = add_months(tx_date, i - 1)
                
                bill = None
                if account.type == Account.Types.CREDIT_CARD:
                    bill = get_or_create_bill_for_transaction(account, current_date)
                    
                tx = Transaction.objects.create(
                    user=user,
                    account=account,
                    category=category,
                    description=f"{description} ({i}/{installments})",
                    amount=current_amount,
                    date=current_date,
                    status=status if i == 1 and current_date <= timezone.now().date() else Transaction.Statuses.PENDING,
                    bill=bill,
                    installment_number=i,
                    total_installments=installments
                )
                if tag_ids:
                    tx.tags.set(tag_ids)
        else:
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
                db_transaction.on_commit(
                    lambda u=user: async_task('transactions.services.process_recurring_transactions', u)
                )
                
        from wallets.services import recalculate_account_balance
        recalculate_account_balance(account)

def update_transaction(transaction, validated_data):
    from django.core.exceptions import ValidationError

    from wallets.models import Account
    from wallets.services import (
        get_or_create_bill_for_transaction,
        recalculate_account_balance,
    )

    if transaction.bill and transaction.bill.status == 'paid':
        raise ValidationError("Transações de faturas já pagas não podem ser alteradas.")

    old_account_id = transaction.account_id
    old_date = transaction.date

    transaction.account_id = validated_data['account']
    transaction.category_id = validated_data['category']
    transaction.description = validated_data['description']
    transaction.amount = validated_data['amount']
    transaction.date = validated_data['date']
    transaction.status = validated_data['status']
    
    new_account = Account.objects.get(id=transaction.account_id)
    if new_account.type == Account.Types.CREDIT_CARD:
        new_bill = get_or_create_bill_for_transaction(new_account, transaction.date)
        transaction.bill = new_bill
    else:
        transaction.bill = None

    is_recurring = validated_data.get('is_recurring', False)
    frequency = validated_data.get('frequency', 'monthly')
    recurring_end_date = validated_data.get('recurring_end_date')

    was_recurring = transaction.recurring is not None
    trigger_async_process = False

    if was_recurring and not is_recurring:
        from transactions.models import Transaction
        old_recurring = transaction.recurring
        Transaction.objects.filter(recurring=old_recurring, date__gt=transaction.date).delete()
        old_recurring.active = False
        old_recurring.end_date = transaction.date
        old_recurring.save(update_fields=['active', 'end_date'])
        
        transaction.recurring = None
        
    elif was_recurring and is_recurring:
        if old_date != transaction.date:
            transaction.recurring.ignore_date(old_date)
            trigger_async_process = True
        
    elif not was_recurring and is_recurring:
        from django_q.tasks import async_task

        from transactions.models import Category, RecurringTransaction
        
        category = Category.objects.get(id=transaction.category_id)
        
        new_recurring = RecurringTransaction.objects.create(
            user=transaction.user,
            account=new_account,
            category=category,
            description=transaction.description,
            amount=transaction.amount,
            frequency=frequency,
            start_date=transaction.date,
            end_date=recurring_end_date,
            active=True
        )
        transaction.recurring = new_recurring
        trigger_async_process = True

    transaction.save()

    transaction.tags.set(validated_data['tags'])

    if trigger_async_process:
        from django.db import transaction as db_transaction
        from django_q.tasks import async_task
        db_transaction.on_commit(
            lambda u=transaction.user: async_task('transactions.services.process_recurring_transactions', u)
        )

    recalculate_account_balance(transaction.account)
    if old_account_id != transaction.account_id:
        old_account = Account.objects.get(id=old_account_id)
        recalculate_account_balance(old_account)

    return transaction


def get_user_description_habits(user, limit=50):
    """
    Retorna um dicionário com os hábitos de transação do usuário por descrição limpa.
    Ex: {'iFood': {'type': 'despesa', 'category_id': '...', 'account_id': '...', 'tag_ids': [...]}}
    """
    import re

    from moneta.common import TransactionType
    from transactions.models import Transaction

    recent_txs = (
        Transaction.objects.filter(user=user)
        .exclude(category__type=TransactionType.TRANSFER)
        .select_related('category', 'account')
        .prefetch_related('tags')
        .order_by('-created_at')[:300]
    )

    habits = {}
    for tx in recent_txs:
        raw_desc = (tx.description or '').strip()
        if not raw_desc:
            continue

        # Limpa sufixos de parcelas como (1/3), (2/12) e (Recorrente)
        desc = re.sub(r'\s*\(\d+/\d+\)', '', raw_desc)
        desc = re.sub(r'\s*\(Recorrente\)', '', desc, flags=re.IGNORECASE)
        desc = desc.strip()
        if not desc:
            continue

        # Ignora reajustes automáticos de saldo
        if desc.lower().startswith('reajuste de saldo'):
            continue

        desc_lower = desc.lower()
        if any(k.lower() == desc_lower for k in habits):
            continue

        if not tx.account or not tx.account.active or not tx.category:
            continue

        habits[desc] = {
            'type': tx.category.type,
            'category_id': str(tx.category_id),
            'account_id': str(tx.account_id),
            'tag_ids': [str(t.id) for t in tx.tags.all()],
        }
        if len(habits) >= limit:
            break

    return habits


