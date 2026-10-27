from datetime import timedelta

from dateutil.relativedelta import relativedelta
from django.utils import timezone
from django.utils.html import strip_tags


def add_months(orig_date, months=1):
    return orig_date + relativedelta(months=months)


def add_years(orig_date, years=1):
    return orig_date + relativedelta(years=years)


def process_recurring_transactions(user, target_end_date=None):
    from moneta.common import TransactionType
    from transactions.models import RecurringTransaction, Transaction, Transfer
    from wallets.models import Account
    from wallets.services import get_or_create_bill_for_transaction

    today = timezone.localdate()
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

        existing_dates = set(
            Transaction.objects.filter(
                recurring=rec,
                date__gte=rec.start_date,
                date__lte=effective_limit,
            ).values_list('date', flat=True)
        )

        new_regular_txs = []
        loop_guard = 0
        while current_date <= effective_limit and loop_guard < 500:
            loop_guard += 1
            if current_date not in existing_dates and current_date not in ignored_dates_set:
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

                    new_regular_txs.append(
                        Transaction(
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

        if new_regular_txs:
            Transaction.objects.bulk_create(new_regular_txs, ignore_conflicts=True)
            from wallets.services import recalculate_account_balance
            recalculate_account_balance(rec.account)


def create_transfer(user, out_account_id, in_account_id, description, amount, tx_date, status, tag_ids=None, is_recurring=False, frequency='monthly', recurring_end_date=None):
    description = strip_tags(description).strip() if description else description

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

    actual_out_id = out_account_id.id if hasattr(out_account_id, 'id') else out_account_id
    actual_in_id = in_account_id.id if hasattr(in_account_id, 'id') else in_account_id

    out_account = get_object_or_404(Account, id=actual_out_id, user=user)
    in_account = get_object_or_404(Account, id=actual_in_id, user=user)

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


def update_transfer(transfer, validated_data):
    if validated_data.get('description'):
        validated_data['description'] = strip_tags(validated_data['description']).strip()

    import re

    from django.core.exceptions import ValidationError
    from django.db import transaction as db_transaction
    from django.shortcuts import get_object_or_404

    from wallets.models import Account
    from wallets.services import recalculate_account_balance

    user = transfer.user
    out_account_raw = validated_data['out_account']
    in_account_raw = validated_data['in_account']
    out_account_id = out_account_raw.id if hasattr(out_account_raw, 'id') else out_account_raw
    in_account_id = in_account_raw.id if hasattr(in_account_raw, 'id') else in_account_raw

    out_account = get_object_or_404(Account, id=out_account_id, user=user)
    in_account = get_object_or_404(Account, id=in_account_id, user=user)
    if out_account.id == in_account.id:
        raise ValidationError("A conta de origem e a conta de destino não podem ser a mesma.")

    amount = validated_data['amount']
    tx_date = validated_data['date']
    description = (validated_data.get('description') or '').strip()
    clean_desc = re.sub(r'^Transferência (p/|de) [^:]+:\s*', '', description).strip() or 'Transferência entre contas'

    out_tx = transfer.out_transaction
    in_tx = transfer.in_transaction

    old_out_account = out_tx.account
    old_in_account = in_tx.account

    with db_transaction.atomic():
        out_tx.account = out_account
        out_tx.amount = amount
        out_tx.date = tx_date
        out_tx.description = f"Transferência p/ {in_account.name}: {clean_desc}"
        out_tx.save()

        in_tx.account = in_account
        in_tx.amount = amount
        in_tx.date = tx_date
        in_tx.description = f"Transferência de {out_account.name}: {clean_desc}"
        in_tx.save()

        if 'tags' in validated_data and validated_data['tags'] is not None:
            tag_objs = validated_data['tags']
            tag_ids = [t.id if hasattr(t, 'id') else t for t in tag_objs]
            out_tx.tags.set(tag_ids)
            in_tx.tags.set(tag_ids)

        transfer.save()

        accounts_to_recalc = {out_account, in_account, old_out_account, old_in_account}
        for acc in accounts_to_recalc:
            recalculate_account_balance(acc)

    return transfer


def create_regular_transaction(user, account_id, category_id, description, amount, tx_date, status, tag_ids=None, is_recurring=False, frequency='monthly', recurring_end_date=None, installments=1):
    description = strip_tags(description).strip() if description else description
    
    from decimal import Decimal
    
    from django.db import models
    from django.db import transaction as db_transaction
    from django.shortcuts import get_object_or_404
    from django_q.tasks import async_task

    from transactions.models import Category, RecurringTransaction, Transaction
    from wallets.models import Account
    from wallets.services import get_or_create_bill_for_transaction

    actual_account_id = account_id.id if hasattr(account_id, 'id') else account_id
    actual_category_id = category_id.id if hasattr(category_id, 'id') else category_id

    account = get_object_or_404(Account, id=actual_account_id, user=user)
    category = get_object_or_404(Category, models.Q(user=user) | models.Q(is_system=True), id=actual_category_id)
    
    if account.type != Account.Types.CREDIT_CARD:
        installments = 1

    clean_tag_ids = [t.id if hasattr(t, 'id') else t for t in tag_ids] if tag_ids else []

    with db_transaction.atomic():
        if installments > 1:
            base_amount = (amount / Decimal(installments)).quantize(Decimal('.01'))
            if base_amount < Decimal('0.01'):
                raise ValueError("O valor é muito pequeno para essa quantidade de parcelas.")
            remaining_amount = amount - (base_amount * (installments - 1))
            if remaining_amount < Decimal('0.01'):
                raise ValueError("O valor restante da última parcela seria inválido.")
            
            tx_instances = []
            today = timezone.localdate()
            for i in range(1, installments + 1):
                current_amount = base_amount if i < installments else remaining_amount
                current_date = add_months(tx_date, i - 1)
                
                bill = None
                if account.type == Account.Types.CREDIT_CARD:
                    bill = get_or_create_bill_for_transaction(account, current_date)
                    
                tx_instances.append(
                    Transaction(
                        user=user,
                        account=account,
                        category=category,
                        description=f"{description} ({i}/{installments})",
                        amount=current_amount,
                        date=current_date,
                        status=status if i == 1 and current_date <= today else Transaction.Statuses.PENDING,
                        bill=bill,
                        installment_number=i,
                        total_installments=installments,
                    )
                )

            created_txs = Transaction.objects.bulk_create(tx_instances)
            if clean_tag_ids and created_txs:
                TagThrough = Transaction.tags.through
                through_records = [
                    TagThrough(transaction_id=tx.id, tag_id=t_id)
                    for tx in created_txs
                    for t_id in clean_tag_ids
                ]
                TagThrough.objects.bulk_create(through_records, ignore_conflicts=True)
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
            if clean_tag_ids:
                tx.tags.set(clean_tag_ids)

            if is_recurring:
                db_transaction.on_commit(
                    lambda u=user: async_task('transactions.services.process_recurring_transactions', u)
                )
                
        from wallets.services import recalculate_account_balance
        recalculate_account_balance(account)


def update_transaction(transaction, validated_data):
    if validated_data.get('description'):
        validated_data['description'] = strip_tags(validated_data['description']).strip()
    if validated_data.get('notes'):
        validated_data['notes'] = strip_tags(validated_data['notes']).strip()

    from django.core.exceptions import ValidationError
    from django.db import models
    from django.db import transaction as db_transaction
    from django.shortcuts import get_object_or_404

    from transactions.models import Category
    from wallets.models import Account
    from wallets.services import (
        get_or_create_bill_for_transaction,
        recalculate_account_balance,
    )

    if transaction.bill and transaction.bill.status == 'paid':
        raise ValidationError("Transações de faturas já pagas não podem ser alteradas.")

    user = transaction.user
    raw_account = validated_data['account']
    raw_category = validated_data['category']
    new_account_id = raw_account.id if hasattr(raw_account, 'id') else raw_account
    new_category_id = raw_category.id if hasattr(raw_category, 'id') else raw_category

    new_account = get_object_or_404(Account, id=new_account_id, user=user)
    new_category = get_object_or_404(Category, models.Q(user=user) | models.Q(is_system=True), id=new_category_id)

    old_account_id = transaction.account_id
    old_date = transaction.date

    with db_transaction.atomic():
        transaction.account = new_account
        transaction.category = new_category
        transaction.description = validated_data['description']
        transaction.amount = validated_data['amount']
        transaction.date = validated_data['date']
        transaction.status = validated_data['status']
        
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
            edit_mode = validated_data.get('edit_mode', 'single')
            if edit_mode == 'future':
                recurring = transaction.recurring
                recurring.amount = transaction.amount
                recurring.description = transaction.description
                recurring.category = transaction.category
                recurring.account = transaction.account
                recurring.save(update_fields=['amount', 'description', 'category', 'account'])
                
                from transactions.models import Transaction
                Transaction.objects.filter(
                    recurring=recurring,
                    date__gt=transaction.date,
                    status=Transaction.Statuses.PENDING
                ).delete()
                
                trigger_async_process = True
            else:
                if old_date != transaction.date:
                    transaction.recurring.ignore_date(old_date)
                    trigger_async_process = True
            
        elif not was_recurring and is_recurring:
            from transactions.models import RecurringTransaction
            
            new_recurring = RecurringTransaction.objects.create(
                user=transaction.user,
                account=new_account,
                category=new_category,
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

        if 'tags' in validated_data and validated_data['tags'] is not None:
            tag_objs = validated_data['tags']
            tag_ids = [t.id if hasattr(t, 'id') else t for t in tag_objs]
            transaction.tags.set(tag_ids)

        if trigger_async_process:
            from django_q.tasks import async_task
            db_transaction.on_commit(
                lambda u=transaction.user: async_task('transactions.services.process_recurring_transactions', u)
            )

        recalculate_account_balance(transaction.account)
        if old_account_id != transaction.account_id:
            old_account = Account.objects.get(id=old_account_id, user=user)
            recalculate_account_balance(old_account)

    return transaction


def delete_transaction(user, transaction_id, delete_mode='single'):
    from datetime import timedelta

    from django.core.exceptions import ValidationError
    from django.db import transaction as db_transaction
    from django.shortcuts import get_object_or_404

    from transactions.models import Transaction
    from wallets.services import recalculate_account_balance

    with db_transaction.atomic():
        tx = get_object_or_404(Transaction.objects.select_for_update(), pk=transaction_id, user=user)

        if tx.bill and tx.bill.status == 'paid':
            raise ValidationError("Transações de faturas já pagas não podem ser excluídas.")

        tx_to_delete_extra = None
        if hasattr(tx, 'transfer_out'):
            tx_to_delete_extra = tx.transfer_out.in_transaction
        elif hasattr(tx, 'transfer_in'):
            tx_to_delete_extra = tx.transfer_in.out_transaction

        accounts_to_recalc = {tx.account}
        if tx_to_delete_extra:
            accounts_to_recalc.add(tx_to_delete_extra.account)

        if tx.recurring:
            if delete_mode == 'future':
                Transaction.objects.filter(recurring=tx.recurring, date__gte=tx.date).delete()
                tx.recurring.end_date = tx.date - timedelta(days=1)
                tx.recurring.save(update_fields=['end_date'])
            elif delete_mode == 'all':
                Transaction.objects.filter(recurring=tx.recurring).delete()
                tx.recurring.active = False
                tx.recurring.save(update_fields=['active'])
            else:
                tx.recurring.ignore_date(tx.date)
                tx.delete()
                if tx_to_delete_extra:
                    tx_to_delete_extra.delete()
        else:
            tx.delete()
            if tx_to_delete_extra:
                tx_to_delete_extra.delete()

        for acc in accounts_to_recalc:
            recalculate_account_balance(acc)


def delete_category(user, category_id, action='delete', fallback_category_id=None):
    from django.core.exceptions import ValidationError
    from django.db import models
    from django.db import transaction as db_transaction
    from django.shortcuts import get_object_or_404

    from transactions.models import Category

    with db_transaction.atomic():
        cat = get_object_or_404(Category, pk=category_id, user=user)

        if cat.transactions.exists():
            if cat.transactions.filter(bill__status='paid').exists():
                raise ValidationError("Não é possível excluir esta categoria pois ela possui transações vinculadas a faturas pagas.")

            if action == 'move':
                if not fallback_category_id:
                    raise ValidationError("Selecione uma categoria de destino válida.")
                fallback_category = get_object_or_404(Category, models.Q(user=user) | models.Q(is_system=True), id=fallback_category_id)
                if fallback_category.id == cat.id:
                    raise ValidationError("A categoria de destino deve ser diferente da categoria atual.")
                cat.transactions.all().update(category=fallback_category)
            elif action == 'delete_all':
                tx_list = list(cat.transactions.all().values_list('id', flat=True))
                for tx_id in tx_list:
                    delete_transaction(user=user, transaction_id=tx_id, delete_mode='single')
            else:
                raise ValidationError("Ação de exclusão inválida.")

        cat.delete()


def get_user_description_habits(user, limit=50):
    """
    Returns a dictionary of user transaction habits indexed by cleaned description.
    E.g.: {'iFood': {'type': 'expense', 'category_id': '...', 'account_id': '...', 'tag_ids': [...]}}
    """
    import re

    from moneta.common import TransactionType
    from transactions.models import Transaction

    recent_txs = (
        Transaction.objects.filter(user=user, account__active=True)
        .exclude(category__type=TransactionType.TRANSFER)
        .select_related('category', 'account')
        .prefetch_related('tags')
        .order_by('-created_at')[:60]
    )

    habits = {}
    for tx in recent_txs:
        raw_desc = (tx.description or '').strip()
        if not raw_desc:
            continue

        desc = re.sub(r'\s*\(\d+/\d+\)', '', raw_desc)
        desc = re.sub(r'\s*\(Recorrente\)', '', desc, flags=re.IGNORECASE)
        desc = desc.strip()
        if not desc:
            continue

        # Ignore automatic balance adjustments
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


def get_filtered_transactions_context(user, query_params):
    from collections import defaultdict
    from decimal import Decimal

    from django.db.models import Q, Sum
    from django.db.models.functions import Coalesce

    from moneta.common import TransactionType, get_month_context
    from transactions.models import Category, Transaction
    from wallets.models import Account
    from wallets.services import calculate_balances_for_dates

    qs = Transaction.objects.filter(user=user)

    month_param = query_params.get('month')
    month_ctx = get_month_context(month_param)

    tx_type = query_params.get('type')
    account_id = query_params.get('account_id')
    category_id = query_params.get('category_id')
    status = query_params.get('status')
    search = query_params.get('search')
    start_date = query_params.get('start_date')
    end_date = query_params.get('end_date')

    if tx_type:
        qs = qs.filter(category__type=tx_type)
    if account_id:
        qs = qs.filter(account_id=account_id)
    if category_id:
        qs = qs.filter(category_id=category_id)
    if status:
        qs = qs.filter(status=status)
    if search:
        qs = qs.filter(
            Q(description__icontains=search) |
            Q(tags__name__icontains=search) |
            Q(category__name__icontains=search) |
            Q(account__name__icontains=search)
        ).distinct()

    if start_date or end_date:
        if start_date:
            qs = qs.filter(date__gte=start_date)
        if end_date:
            qs = qs.filter(date__lte=end_date)
    else:
        qs = qs.filter(date__range=(month_ctx['start_date'], month_ctx['end_date']))

    if not account_id:
        qs = qs.exclude(transfer_in__isnull=False, account__type=Account.Types.CREDIT_CARD)

    transactions = qs.select_related(
        'account', 'category', 'bill__account', 'transfer_out__in_transaction__bill__account'
    )
    totals = qs.aggregate(
        income=Coalesce(Sum('amount', filter=Q(category__type=TransactionType.INCOME)), Decimal('0.00')),
        expense=Coalesce(Sum('amount', filter=Q(category__type=TransactionType.EXPENSE)), Decimal('0.00')),
    )
    month_net_balance = totals['income'] - totals['expense']

    tx_dict = defaultdict(list)
    for tx in transactions:
        tx_dict[tx.date].append(tx)

    date_balances = calculate_balances_for_dates(user, list(tx_dict.keys()), account_id)
    tx_by_date = [
        {
            'date': tx_date,
            'list': tx_list,
            'balance': date_balances.get(tx_date, Decimal('0.00')),
        }
        for tx_date, tx_list in tx_dict.items()
    ]

    query_params_prev = query_params.copy()
    query_params_prev['month'] = month_ctx['prev_month']
    query_params_next = query_params.copy()
    query_params_next['month'] = month_ctx['next_month']

    return {
        'transactions': transactions,
        'tx_by_date': tx_by_date,
        'accounts': Account.objects.filter(user=user),
        'categories': Category.objects.filter(user=user, is_system=False),
        'month_info': month_ctx,
        'prev_month_url': query_params_prev.urlencode(),
        'next_month_url': query_params_next.urlencode(),
        'month_net_balance': month_net_balance,
    }


def get_transaction_form_context(user, transaction=None, transfer=None):
    import re

    from transactions.models import Category, Tag
    from wallets.models import Account

    accounts = list(Account.objects.filter(user=user, active=True).select_related('credit_card_details'))
    transfer_accounts = [a for a in accounts if a.type != Account.Types.CREDIT_CARD]
    categories = list(Category.objects.filter(user=user, is_system=False))
    tags = list(Tag.objects.filter(user=user))

    if transfer is not None:
        raw_desc = transfer.out_transaction.description or ''
        clean_desc = re.sub(r'^Transferência (p/|de) [^:]+:\s*', '', raw_desc).strip()
        rec = transfer.out_transaction.recurring

        initial_tx_data = {
            'txType': 'transferencia',
            'selectedAccountType': transfer.out_transaction.account.type,
            'originalAccountId': str(transfer.out_transaction.account.id),
            'selectedAccountId': str(transfer.out_transaction.account.id),
            'outAccount': str(transfer.out_transaction.account.id),
            'inAccount': str(transfer.in_transaction.account.id),
            'originalAmount': float(transfer.out_transaction.amount),
            'amount': float(transfer.out_transaction.amount),
            'selectedAccountLimit': 0,
            'categories': [],
            'isRecurring': rec is not None,
            'frequency': rec.frequency if rec else 'monthly',
            'recurringEndDate': str(rec.end_date) if rec and rec.end_date else '',
            'selectedCategoryId': str(transaction.category.id) if transaction and transaction.category else '',
            'selectedTagIds': [str(t.id) for t in transfer.out_transaction.tags.all()],
            'status': transfer.out_transaction.status,
            'descriptionHabits': {},
        }
        return {
            'transaction': transaction,
            'transfer': transfer,
            'clean_description': clean_desc,
            'accounts': accounts,
            'transfer_accounts': transfer_accounts,
            'categories': categories,
            'tags': tags,
            'initial_tx_data': initial_tx_data,
            'description_habits': {},
        }

    serialized_categories = [
        {'id': str(c.id), 'name': f"{c.icon + ' ' if c.icon else ''}{c.name}", 'type': c.type}
        for c in categories
    ]

    if transaction is not None:
        rec = transaction.recurring
        initial_tx_data = {
            'txType': transaction.category.type,
            'originalAccountId': str(transaction.account.id),
            'selectedAccountId': str(transaction.account.id),
            'originalAmount': float(transaction.amount),
            'selectedAccountLimit': (
                float(transaction.account.credit_card_details.available_limit)
                if transaction.account.type == Account.Types.CREDIT_CARD
                else 0
            ),
            'categories': serialized_categories,
            'isRecurring': rec is not None,
            'frequency': rec.frequency if rec else 'monthly',
            'recurringEndDate': str(rec.end_date) if rec and rec.end_date else '',
            'selectedCategoryId': str(transaction.category.id) if transaction.category else '',
            'selectedTagIds': [str(t.id) for t in transaction.tags.all()],
            'status': transaction.status,
            'descriptionHabits': {},
        }
        return {
            'transaction': transaction,
            'accounts': accounts,
            'categories': categories,
            'tags': tags,
            'initial_tx_data': initial_tx_data,
        }

    description_habits = get_user_description_habits(user)
    initial_tx_data = {
        'txType': 'despesa',
        'selectedAccountType': accounts[0].type if accounts else '',
        'originalAccountId': '',
        'selectedAccountId': str(accounts[0].id) if accounts else '',
        'originalAmount': 0,
        'selectedAccountLimit': (
            float(accounts[0].credit_card_details.available_limit)
            if accounts and accounts[0].type == Account.Types.CREDIT_CARD
            else 0
        ),
        'categories': serialized_categories,
        'isRecurring': False,
        'frequency': 'monthly',
        'recurringEndDate': '',
        'selectedCategoryId': '',
        'selectedTagIds': [],
        'status': 'concluída',
        'descriptionHabits': description_habits,
    }
    return {
        'accounts': accounts,
        'transfer_accounts': transfer_accounts,
        'categories': categories,
        'tags': tags,
        'initial_tx_data': initial_tx_data,
        'description_habits': description_habits,
    }



