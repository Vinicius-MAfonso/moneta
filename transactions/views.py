import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from moneta.common import TransactionType, format_form_errors, get_month_context
from wallets.models import Account

from .models import Category, Tag, Transaction
from .services import (
    create_regular_transaction,
    create_transfer,
    delete_category,
    delete_transaction,
    update_transaction,
    update_transfer,
)


@login_required(login_url='users_web:login')
def transaction_list_view(request):
    qs = Transaction.objects.filter(user=request.user)

    month_param = request.GET.get('month')
    month_ctx = get_month_context(month_param)

    tx_type = request.GET.get('type')
    account_id = request.GET.get('account_id')
    category_id = request.GET.get('category_id')
    status = request.GET.get('status')
    search = request.GET.get('search')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

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
    month_income = totals['income']
    month_expense = totals['expense']
    month_net_balance = month_income - month_expense

    from collections import defaultdict

    from wallets.services import calculate_balances_for_dates
    tx_dict = defaultdict(list)
    for tx in transactions:
        tx_dict[tx.date].append(tx)
        
    date_balances = calculate_balances_for_dates(request.user, list(tx_dict.keys()), account_id)
    tx_by_date = []
    for date, tx_list in tx_dict.items():
        tx_by_date.append({
            'date': date,
            'list': tx_list,
            'balance': date_balances.get(date, Decimal('0.00'))
        })
    query_params_prev = request.GET.copy()
    query_params_prev['month'] = month_ctx['prev_month']
    query_params_next = request.GET.copy()
    query_params_next['month'] = month_ctx['next_month']

    context = {
        'transactions': transactions,
        'tx_by_date': tx_by_date,
        'accounts': Account.objects.filter(user=request.user),
        'categories': Category.objects.filter(user=request.user, is_system=False),
        'month_info': month_ctx,
        'prev_month_url': query_params_prev.urlencode(),
        'next_month_url': query_params_next.urlencode(),
        'month_net_balance': month_net_balance,
    }

    if request.headers.get('HX-Request'):
        return render(request, 'transactions/partials/transaction_list.html', context)

    return render(request, 'transactions/index.html', context)


@login_required(login_url='users_web:login')
def transaction_create_view(request):
    accounts = list(Account.objects.filter(user=request.user, active=True).select_related('credit_card_details'))
    transfer_accounts = [a for a in accounts if a.type != 'credit_card']
    categories = list(Category.objects.filter(user=request.user, is_system=False))
    tags = list(Tag.objects.filter(user=request.user))

    from .forms import TransactionForm, TransferForm

    if request.method == 'POST':
        tx_type = request.POST.get('tx_type', 'despesa')

        if tx_type == 'transferencia':
            form = TransferForm(request.POST, user=request.user)
            if form.is_valid():
                cd = form.cleaned_data
                try:
                    create_transfer(
                        user=request.user,
                        out_account_id=cd['out_account'].id if hasattr(cd['out_account'], 'id') else cd['out_account'],
                        in_account_id=cd['in_account'].id if hasattr(cd['in_account'], 'id') else cd['in_account'],
                        description=cd['description'],
                        amount=cd['amount'],
                        tx_date=cd['date'],
                        status=cd.get('status', 'concluída'),
                        tag_ids=[t.id for t in cd['tags']] if cd.get('tags') else None,
                        is_recurring=cd['is_recurring'],
                        frequency=cd['frequency'],
                        recurring_end_date=cd['recurring_end_date']
                    )
                except ValidationError as e:
                    error_msg = e.messages[0] if hasattr(e, 'messages') else str(e)
                    if request.headers.get('HX-Request'):
                        response = HttpResponse(status=204)
                        response['HX-Trigger'] = json.dumps({
                            'show-toast': {'message': f'{error_msg}', 'type': 'error'}
                        })
                        return response
                    messages.error(request, f"Erro na transferência: {error_msg}")
                    return redirect('transactions_web:list')
                if request.headers.get('HX-Request'):
                    response = HttpResponse(status=204)
                    response['HX-Trigger'] = json.dumps({
                        'reload-transactions': '',
                        'show-toast': {'message': 'Transferência criada com sucesso!', 'type': 'success'}
                    })
                    return response
                messages.success(request, "Transferência criada com sucesso!")
                return redirect('transactions_web:list')
            else:
                error_msg = format_form_errors(form)
                if request.headers.get('HX-Request'):
                    response = HttpResponse(status=204)
                    response['HX-Trigger'] = json.dumps({
                        'show-toast': {'message': f'{error_msg}', 'type': 'error'}
                    })
                    return response
                messages.error(request, f"Erro na transferência: {error_msg}")
                return redirect('transactions_web:list')

        form = TransactionForm(request.POST, user=request.user)
        if form.is_valid():
            cd = form.cleaned_data
            try:
                create_regular_transaction(
                    user=request.user,
                    account_id=cd['account'].id if hasattr(cd['account'], 'id') else cd['account'],
                    category_id=cd['category'].id if hasattr(cd['category'], 'id') else cd['category'],
                    description=cd['description'],
                    amount=cd['amount'],
                    tx_date=cd['date'],
                    status=cd['status'],
                    tag_ids=[t.id for t in cd['tags']] if cd.get('tags') else None,
                    is_recurring=cd['is_recurring'],
                    frequency=cd['frequency'],
                    recurring_end_date=cd['recurring_end_date'],
                    installments=cd.get('installments') or 1
                )
            except (ValueError, ValidationError) as e:
                error_msg = e.messages[0] if hasattr(e, 'messages') else str(e)
                if request.headers.get('HX-Request'):
                    response = HttpResponse(status=204)
                    response['HX-Trigger'] = json.dumps({
                        'show-toast': {'message': f'{error_msg}', 'type': 'error'}
                    })
                    return response
                messages.error(request, f"Erro ao criar transação: {error_msg}")
                return redirect('transactions_web:list')
            if request.headers.get('HX-Request'):
                response = HttpResponse(status=204)
                response['HX-Trigger'] = json.dumps({
                    'reload-transactions': '',
                    'show-toast': {'message': 'Transação criada com sucesso!', 'type': 'success'}
                })
                return response
            messages.success(request, "Transação criada com sucesso!")
            return redirect('transactions_web:list')
        else:
            error_msg = format_form_errors(form)
            if request.headers.get('HX-Request'):
                response = HttpResponse(status=204)
                response['HX-Trigger'] = json.dumps({
                    'show-toast': {'message': f'{error_msg}', 'type': 'error'}
                })
                return response
            messages.error(request, f"Erro ao criar transação: {error_msg}")

    from .services import get_user_description_habits
    description_habits = get_user_description_habits(request.user)

    initial_tx_data = {
        'txType': 'despesa',
        'selectedAccountType': accounts[0].type if accounts else '',
        'originalAccountId': '',
        'selectedAccountId': str(accounts[0].id) if accounts else '',
        'originalAmount': 0,
        'selectedAccountLimit': float(accounts[0].credit_card_details.available_limit) if accounts and accounts[0].type == 'credit_card' else 0,
        'categories': [{'id': str(c.id), 'name': f"{c.icon + ' ' if c.icon else ''}{c.name}", 'type': c.type} for c in categories],
        'isRecurring': False,
        'frequency': 'monthly',
        'recurringEndDate': '',
        'selectedCategoryId': '',
        'selectedTagIds': [],
        'status': 'concluída',
        'descriptionHabits': description_habits,
    }

    context = {
        'accounts': accounts,
        'transfer_accounts': transfer_accounts,
        'categories': categories,
        'tags': tags,
        'initial_tx_data': initial_tx_data,
        'description_habits': description_habits,
    }
    return render(request, 'transactions/partials/transaction_form.html', context)


@login_required(login_url='users_web:login')
def transaction_update_view(request, pk):
    from django.db import models

    transaction = get_object_or_404(
        Transaction.objects.select_related(
            'category',
            'account__credit_card_details',
            'recurring',
            'bill',
            'transfer_out__in_transaction__account',
            'transfer_out__out_transaction__account',
            'transfer_in__in_transaction__account',
            'transfer_in__out_transaction__account',
        ).prefetch_related('tags'),
        pk=pk,
        user=request.user
    )

    accounts = list(Account.objects.filter(user=request.user, active=True).select_related('credit_card_details'))
    categories = list(Category.objects.filter(user=request.user, is_system=False))
    tags = list(Tag.objects.filter(user=request.user))
    transfer_accounts = [a for a in accounts if a.type != 'credit_card']

    transfer = getattr(transaction, 'transfer_out', None) or getattr(transaction, 'transfer_in', None)
    if not transfer and transaction.category and transaction.category.type == TransactionType.TRANSFER:
        from transactions.models import Transfer
        transfer = Transfer.objects.filter(models.Q(out_transaction=transaction) | models.Q(in_transaction=transaction)).first()

    if transfer:
        if request.method == 'POST':
            from .forms import TransferForm
            form = TransferForm(request.POST, user=request.user)
            if form.is_valid():
                cd = form.cleaned_data
                from django.core.exceptions import ValidationError
                from .services import update_transfer
                try:
                    update_transfer(transfer, cd)
                except ValidationError as e:
                    error_msg = e.messages[0] if hasattr(e, 'messages') else str(e)
                    if request.headers.get('HX-Request'):
                        response = HttpResponse(status=204)
                        response['HX-Trigger'] = json.dumps({
                            'show-toast': {'message': f'{error_msg}', 'type': 'error'}
                        })
                        return response
                    messages.error(request, f"{error_msg}")
                    return redirect('transactions_web:list')
                if request.headers.get('HX-Request'):
                    response = HttpResponse(status=204)
                    response['HX-Trigger'] = json.dumps({
                        'reload-transactions': '',
                        'show-toast': {'message': 'Transferência atualizada com sucesso!', 'type': 'success'}
                    })
                    return response
                messages.success(request, "Transferência atualizada com sucesso!")
                return redirect('transactions_web:list')
            else:
                error_msg = format_form_errors(form)
                if request.headers.get('HX-Request'):
                    response = HttpResponse(status=204)
                    response['HX-Trigger'] = json.dumps({
                        'show-toast': {'message': f'{error_msg}', 'type': 'error'}
                    })
                    return response
                messages.error(request, f"{error_msg}")
                return redirect('transactions_web:list')

        raw_desc = transfer.out_transaction.description or ''
        clean_desc = re.sub(r'^Transferência (p/|de) [^:]+:\s*', '', raw_desc).strip()

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
            'isRecurring': transfer.out_transaction.recurring is not None,
            'frequency': transfer.out_transaction.recurring.frequency if transfer.out_transaction.recurring else 'monthly',
            'recurringEndDate': str(transfer.out_transaction.recurring.end_date) if transfer.out_transaction.recurring and transfer.out_transaction.recurring.end_date else '',
            'selectedCategoryId': str(transaction.category.id) if transaction.category else '',
            'selectedTagIds': [str(t.id) for t in transfer.out_transaction.tags.all()],
            'status': transfer.out_transaction.status,
            'descriptionHabits': {},
        }

        context = {
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
        return render(request, 'transactions/partials/transaction_form.html', context)

    if request.method == 'POST':
        from .forms import TransactionForm
        form = TransactionForm(request.POST, user=request.user)
        if form.is_valid():
            cd = form.cleaned_data

            from django.core.exceptions import ValidationError

            from transactions.services import update_transaction
            try:
                update_transaction(transaction, cd)
            except ValidationError as e:
                error_msg = e.messages[0] if hasattr(e, 'messages') else str(e)
                if request.headers.get('HX-Request'):
                    response = HttpResponse(status=204)
                    response['HX-Trigger'] = json.dumps({
                        'show-toast': {'message': f'{error_msg}', 'type': 'error'}
                    })
                    return response
                messages.error(request, f"{error_msg}")
                return redirect('transactions_web:list')

            if request.headers.get('HX-Request'):
                response = HttpResponse(status=204)
                response['HX-Trigger'] = json.dumps({
                    'reload-transactions': '',
                    'show-toast': {'message': 'Transação atualizada com sucesso!', 'type': 'success'}
                })
                return response
            messages.success(request, "Transação atualizada com sucesso!")
            return redirect('transactions_web:list')
        else:
            error_msg = format_form_errors(form)
            if request.headers.get('HX-Request'):
                response = HttpResponse(status=204)
                response['HX-Trigger'] = json.dumps({
                    'show-toast': {'message': f'{error_msg}', 'type': 'error'}
                })
                return response
            messages.error(request, f"{error_msg}")
            return redirect('transactions_web:list')

    initial_tx_data = {
        'txType': transaction.category.type,
        'originalAccountId': str(transaction.account.id),
        'selectedAccountId': str(transaction.account.id),
        'originalAmount': float(transaction.amount),
        'selectedAccountLimit': float(transaction.account.credit_card_details.available_limit) if transaction.account.type == 'credit_card' else 0,
        'categories': [{'id': str(c.id), 'name': f"{c.icon + ' ' if c.icon else ''}{c.name}", 'type': c.type} for c in categories],
        'isRecurring': transaction.recurring is not None,
        'frequency': transaction.recurring.frequency if transaction.recurring else 'monthly',
        'recurringEndDate': str(transaction.recurring.end_date) if transaction.recurring and transaction.recurring.end_date else '',
        'selectedCategoryId': str(transaction.category.id) if transaction.category else '',
        'selectedTagIds': [str(t.id) for t in transaction.tags.all()],
        'status': transaction.status,
        'descriptionHabits': {},
    }

    context = {
        'transaction': transaction,
        'accounts': accounts,
        'categories': categories,
        'tags': tags,
        'initial_tx_data': initial_tx_data,
    }
    return render(request, 'transactions/partials/transaction_form.html', context)


@login_required(login_url='users_web:login')
def transaction_confirm_delete_view(request, pk):
    tx = get_object_or_404(Transaction, pk=pk, user=request.user)

    if tx.bill and tx.bill.status == 'paid':
        if request.headers.get('HX-Request'):
            response = HttpResponse(status=204)
            response['HX-Trigger'] = json.dumps({
                'show-toast': {'message': 'Transações de faturas já pagas não podem ser excluídas.', 'type': 'error'}
            })
            return response
        messages.error(request, "Transações de faturas já pagas não podem ser excluídas.")
        return redirect('transactions_web:list')

    amount_str = f"{tx.amount:.2f}".replace('.', ',')
    context = {
        'title': 'Excluir Transação',
        'message': f"Tem certeza que deseja excluir a transação '{tx.description}' no valor de R$ {amount_str}?",
        'action_url': reverse('transactions_web:delete', args=[tx.id]),
    }

    if tx.recurring:
        context['options'] = [
            {'value': 'single', 'label': 'Excluir somente esta'},
            {'value': 'future', 'label': 'Excluir esta e as futuras'},
            {'value': 'all', 'label': 'Excluir toda a série'},
        ]

    return render(request, 'partials/confirm_modal.html', context)


@login_required(login_url='users_web:login')
@require_POST
def transaction_delete_view(request, pk):
    delete_mode = request.POST.get('delete_mode', 'single')
    try:
        delete_transaction(user=request.user, transaction_id=pk, delete_mode=delete_mode)
    except ValidationError as e:
        error_msg = e.messages[0] if hasattr(e, 'messages') else str(e)
        if request.headers.get('HX-Request'):
            response = HttpResponse(status=204)
            response['HX-Trigger'] = json.dumps({
                'show-toast': {'message': error_msg, 'type': 'error'}
            })
            return response
        messages.error(request, error_msg)
        return redirect('transactions_web:list')

    messages.success(request, "Transação excluída com sucesso.")

    if request.headers.get('HX-Request'):
        response = HttpResponse(status=204)
        response['HX-Trigger'] = json.dumps({
            'reload-transactions': '',
            'show-toast': {'message': 'Transação excluída com sucesso.', 'type': 'success'}
        })
        return response
    referer = request.META.get('HTTP_REFERER')
    if referer and url_has_allowed_host_and_scheme(
        url=referer,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(referer)
    return redirect('transactions_web:list')


@login_required(login_url='users_web:login')
def category_list_view(request):
    categories = Category.objects.filter(user=request.user, is_system=False)
    tags = Tag.objects.filter(user=request.user)

    context = {
        'categories': categories,
        'tags': tags,
    }
    return render(request, 'categories/index.html', context)


@login_required(login_url='users_web:login')
def category_create_view(request):
    from .forms import CategoryForm
    if request.method == 'POST':
        form = CategoryForm(request.POST, user=request.user)
        if form.is_valid():
            cat = form.save(commit=False)
            cat.user = request.user
            cat.save()
            if request.headers.get('HX-Request'):
                messages.success(request, "Categoria criada com sucesso!")
                response = HttpResponse(status=204)
                response['HX-Redirect'] = reverse('transactions_web:category_list')
                return response
            messages.success(request, "Categoria criada com sucesso!")
            return redirect('transactions_web:category_list')
        else:
            error_msg = format_form_errors(form)
            if request.headers.get('HX-Request'):
                response = HttpResponse(status=204)
                response['HX-Trigger'] = json.dumps({'show-toast': {'message': f'{error_msg}', 'type': 'error'}})
                return response
            messages.error(request, f"Erro ao criar categoria: {error_msg}")
            return redirect('transactions_web:category_list')

    return render(request, 'categories/partials/category_form.html')


@login_required(login_url='users_web:login')
def category_confirm_delete_view(request, pk):
    cat = get_object_or_404(Category, pk=pk, user=request.user)

    if cat.transactions.exists():
        fallback_categories = Category.objects.filter(user=request.user, type=cat.type, is_system=False).exclude(id=cat.id)
        context = {
            'category': cat,
            'transactions_count': cat.transactions.count(),
            'fallback_categories': fallback_categories,
        }
        return render(request, 'categories/partials/category_delete_with_transactions.html', context)

    context = {
        'title': 'Excluir Categoria',
        'message': f"Tem certeza que deseja excluir a categoria '{cat.name}'?",
        'action_url': reverse('transactions_web:category_delete', args=[cat.id]),
    }
    return render(request, 'partials/confirm_modal.html', context)


@login_required(login_url='users_web:login')
@require_POST
def category_delete_view(request, pk):
    delete_action = request.POST.get('delete_action', 'delete')
    fallback_category_id = request.POST.get('fallback_category_id')

    try:
        delete_category(
            user=request.user,
            category_id=pk,
            action=delete_action,
            fallback_category_id=fallback_category_id
        )
    except ValidationError as e:
        error_msg = e.messages[0] if hasattr(e, 'messages') else str(e)
        if request.headers.get('HX-Request'):
            response = HttpResponse(status=204)
            response['HX-Trigger'] = json.dumps({'show-toast': {'message': error_msg, 'type': 'error'}})
            return response
        messages.error(request, error_msg)
        return redirect('transactions_web:category_list')

    messages.success(request, "Categoria excluída com sucesso.")
    if request.headers.get('HX-Request'):
        response = HttpResponse(status=204)
        response['HX-Redirect'] = reverse('transactions_web:category_list')
        return response
    return redirect('transactions_web:category_list')


@login_required(login_url='users_web:login')
def tag_create_view(request):
    from .forms import TagForm
    if request.method == 'POST':
        form = TagForm(request.POST, user=request.user)
        if form.is_valid():
            tag = form.save(commit=False)
            tag.user = request.user
            tag.save()
            if request.headers.get('HX-Request'):
                messages.success(request, "Tag criada com sucesso!")
                response = HttpResponse(status=204)
                response['HX-Redirect'] = reverse('transactions_web:category_list')
                return response
            messages.success(request, "Tag criada com sucesso!")
            return redirect('transactions_web:category_list')
        else:
            error_msg = format_form_errors(form)
            if request.headers.get('HX-Request'):
                response = HttpResponse(status=204)
                response['HX-Trigger'] = json.dumps({'show-toast': {'message': f'{error_msg}', 'type': 'error'}})
                return response
            messages.error(request, f"Erro ao criar tag: {error_msg}")
            return redirect('transactions_web:category_list')

    return render(request, 'categories/partials/tag_form.html')


@login_required(login_url='users_web:login')
def tag_confirm_delete_view(request, pk):
    tag = get_object_or_404(Tag, pk=pk, user=request.user)
    context = {
        'title': 'Excluir Tag',
        'message': f"Tem certeza que deseja excluir a tag '{tag.name}'?",
        'action_url': reverse('transactions_web:tag_delete', args=[tag.id]),
    }
    return render(request, 'partials/confirm_modal.html', context)


@login_required(login_url='users_web:login')
@require_POST
def tag_delete_view(request, pk):
    tag = get_object_or_404(Tag, pk=pk, user=request.user)
    tag_name = tag.name
    tag.delete()
    messages.success(request, f"Tag '{tag_name}' excluída com sucesso.")
    if request.headers.get('HX-Request'):
        response = HttpResponse(status=204)
        response['HX-Redirect'] = reverse('transactions_web:category_list')
        return response
    return redirect('transactions_web:category_list')


@login_required(login_url='users_web:login')
def transfer_create_view(request):
    from .forms import TransferForm
    accounts = Account.objects.filter(user=request.user, active=True)

    if request.method == 'POST':
        form = TransferForm(request.POST, user=request.user)
        if form.is_valid():
            cd = form.cleaned_data
            try:
                create_transfer(
                    user=request.user,
                    out_account_id=cd['out_account'].id if hasattr(cd['out_account'], 'id') else cd['out_account'],
                    in_account_id=cd['in_account'].id if hasattr(cd['in_account'], 'id') else cd['in_account'],
                    description=cd['description'],
                    amount=cd['amount'],
                    tx_date=cd['date'],
                    status=cd.get('status', Transaction.Statuses.COMPLETED),
                    tag_ids=[t.id for t in cd.get('tags', [])] if cd.get('tags') else None,
                    is_recurring=cd.get('is_recurring', False),
                    frequency=cd.get('frequency', 'monthly'),
                    recurring_end_date=cd.get('recurring_end_date')
                )
                if request.headers.get('HX-Request'):
                    response = HttpResponse(status=204)
                    response['HX-Trigger'] = json.dumps({
                        'reload-transactions': '',
                        'show-toast': {'message': 'Transferência criada com sucesso!', 'type': 'success'}
                    })
                    return response
                messages.success(request, "Transferência criada com sucesso!")
                return redirect('transactions_web:list')
            except ValidationError as e:
                error_msg = e.messages[0] if hasattr(e, 'messages') else str(e)
                if request.headers.get('HX-Request'):
                    response = HttpResponse(status=204)
                    response['HX-Trigger'] = json.dumps({'show-toast': {'message': error_msg, 'type': 'error'}})
                    return response
                messages.error(request, f"Erro na transferência: {error_msg}")
                return redirect('transactions_web:list')
        else:
            error_msg = format_form_errors(form)
            if request.headers.get('HX-Request'):
                response = HttpResponse(status=204)
                response['HX-Trigger'] = json.dumps({'show-toast': {'message': error_msg, 'type': 'error'}})
                return response
            messages.error(request, f"Erro na transferência: {error_msg}")
            return redirect('transactions_web:list')

    return render(request, 'transactions/partials/transfer_form.html', {'accounts': accounts})


@login_required(login_url='users_web:login')
def transaction_pay_view(request, pk):
    tx = get_object_or_404(Transaction.objects.select_related('category', 'account'), pk=pk, user=request.user)
    
    if tx.status == Transaction.Statuses.COMPLETED:
        if request.headers.get('HX-Request'):
            response = HttpResponse(status=204)
            response['HX-Trigger'] = json.dumps({
                'show-toast': {'message': 'Esta transação já está efetivada.', 'type': 'error'}
            })
            return response
        messages.error(request, "Esta transação já está efetivada.")
        return redirect('transactions_web:list')

    accounts = list(Account.objects.filter(user=request.user, active=True))

    if request.method == 'POST':
        amount_str = request.POST.get('amount', '')
        date_str = request.POST.get('date', '')
        account_id = request.POST.get('account')

        try:
            import datetime
            amount = Decimal(amount_str.replace(',', '.'))
            date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            
            validated_data = {
                'account': account_id,
                'category': str(tx.category.id),
                'description': tx.description,
                'amount': amount,
                'date': date_obj,
                'status': Transaction.Statuses.COMPLETED,
                'tags': [t.id for t in tx.tags.all()],
                'is_recurring': tx.recurring is not None,
                'frequency': tx.recurring.frequency if tx.recurring else 'monthly',
                'recurring_end_date': tx.recurring.end_date if tx.recurring else None,
            }
            
            update_transaction(tx, validated_data)
            
            if request.headers.get('HX-Request'):
                response = HttpResponse(status=204)
                response['HX-Trigger'] = json.dumps({
                    'reload-transactions': '',
                    'show-toast': {'message': 'Transação efetivada com sucesso!', 'type': 'success'}
                })
                return response
            messages.success(request, "Transação efetivada com sucesso!")
            return redirect('transactions_web:list')
            
        except (ValueError, ValidationError) as e:
            error_msg = e.messages[0] if hasattr(e, 'messages') else str(e)
            if request.headers.get('HX-Request'):
                response = HttpResponse(status=204)
                response['HX-Trigger'] = json.dumps({
                    'show-toast': {'message': error_msg, 'type': 'error'}
                })
                return response
            messages.error(request, f"Erro ao efetivar: {error_msg}")
            return redirect('transactions_web:list')

    context = {
        'transaction': tx,
        'accounts': accounts,
    }
    return render(request, 'transactions/partials/pay_modal.html', context)

