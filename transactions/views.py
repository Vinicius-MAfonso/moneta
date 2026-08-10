from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from moneta.common import TransactionType, get_month_context
from wallets.models import Account

from .models import Category, RecurringTransaction, Tag, Transaction
from .services import create_regular_transaction, create_transfer


@login_required(login_url='users_web:login')
def transaction_list_view(request):
    qs = Transaction.objects.filter(user=request.user)
    
    # Query Filters
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
        from django.db.models import Q
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

    transactions = qs.select_related('account', 'category').prefetch_related('tags').order_by('-date', '-created_at')

    # Net balance calculation for selected period
    month_income = transactions.filter(category__type=TransactionType.INCOME).aggregate(total=Coalesce(Sum('amount'), Decimal('0.00')))['total']
    month_expense = transactions.filter(category__type=TransactionType.EXPENSE).aggregate(total=Coalesce(Sum('amount'), Decimal('0.00')))['total']
    month_net_balance = month_income - month_expense

    context = {
        'transactions': transactions,
        'accounts': Account.objects.filter(user=request.user),
        'categories': Category.objects.filter(user=request.user),
        'month_info': month_ctx,
        'month_net_balance': month_net_balance,
    }

    if request.headers.get('HX-Request'):
        return render(request, 'transactions/partials/transaction_list.html', context)
    
    return render(request, 'transactions/index.html', context)


@login_required(login_url='users_web:login')
def transaction_create_view(request):
    accounts = Account.objects.filter(user=request.user, active=True)
    transfer_accounts = accounts.exclude(type='credit_card')
    categories = Category.objects.filter(user=request.user)
    tags = Tag.objects.filter(user=request.user)

    from .forms import TransactionForm, TransferForm

    if request.method == 'POST':
        tx_type = request.POST.get('tx_type', 'despesa')

        if tx_type == 'transferencia':
            form = TransferForm(request.POST, user=request.user)
            if form.is_valid():
                cd = form.cleaned_data
                create_transfer(
                    user=request.user,
                    out_account_id=cd['out_account'],
                    in_account_id=cd['in_account'],
                    description=cd['description'],
                    amount=cd['amount'],
                    tx_date=cd['date'],
                    status=cd.get('status', 'concluída'),
                    tag_ids=[t.id for t in cd['tags']],
                    is_recurring=cd['is_recurring'],
                    frequency=cd['frequency'],
                    recurring_end_date=cd['recurring_end_date']
                )
                if request.headers.get('HX-Request'):
                    import json
                    response = HttpResponse(status=204)
                    response['HX-Trigger'] = json.dumps({
                        'reload-transactions': '',
                        'show-toast': {'message': 'Transferência criada com sucesso!', 'type': 'success'}
                    })
                    return response
                messages.success(request, "Transferência criada com sucesso!")
                return redirect('transactions_web:list')
            else:
                error_msg = form.errors.as_text()
                if request.headers.get('HX-Request'):
                    import json
                    response = HttpResponse(status=204)
                    response['HX-Trigger'] = json.dumps({
                        'show-toast': {'message': f'Erro: {error_msg}', 'type': 'error'}
                    })
                    return response
                messages.error(request, f"Erro na transferência: {error_msg}")
                return redirect('transactions_web:list')

        # Normal Despesa or Receita
        form = TransactionForm(request.POST, user=request.user)
        if form.is_valid():
            cd = form.cleaned_data
            create_regular_transaction(
                user=request.user,
                account_id=cd['account'],
                category_id=cd['category'],
                description=cd['description'],
                amount=cd['amount'],
                tx_date=cd['date'],
                status=cd['status'],
                tag_ids=[t.id for t in cd['tags']],
                is_recurring=cd['is_recurring'],
                frequency=cd['frequency'],
                recurring_end_date=cd['recurring_end_date'],
                installments=cd.get('installments') or 1
            )
            if request.headers.get('HX-Request'):
                import json
                response = HttpResponse(status=204)
                response['HX-Trigger'] = json.dumps({
                    'reload-transactions': '',
                    'show-toast': {'message': 'Transação criada com sucesso!', 'type': 'success'}
                })
                return response
            messages.success(request, "Transação criada com sucesso!")
            return redirect('transactions_web:list')
        else:
            error_msg = form.errors.as_text()
            if request.headers.get('HX-Request'):
                import json
                response = HttpResponse(status=204)
                response['HX-Trigger'] = json.dumps({
                    'show-toast': {'message': f'Erro: {error_msg}', 'type': 'error'}
                })
                return response
            messages.error(request, f"Erro ao criar transação: {error_msg}")
            return redirect('transactions_web:list')

    context = {
        'accounts': accounts,
        'transfer_accounts': transfer_accounts,
        'categories': categories,
        'tags': tags,
    }
    return render(request, 'transactions/partials/transaction_form.html', context)


@login_required(login_url='users_web:login')
def transaction_confirm_delete_view(request, pk):
    tx = get_object_or_404(Transaction, pk=pk, user=request.user)
    context = {
        'title': 'Excluir Transação',
        'message': f"Tem certeza que deseja excluir a transação '{tx.description}' no valor de R$ {tx.amount}?",
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
def transaction_delete_view(request, pk):
    tx = get_object_or_404(Transaction, pk=pk, user=request.user)
    delete_mode = request.POST.get('delete_mode', 'single')
    
    tx_to_delete_extra = None
    if hasattr(tx, 'transfer_out'):
        tx_to_delete_extra = tx.transfer_out.in_transaction
    elif hasattr(tx, 'transfer_in'):
        tx_to_delete_extra = tx.transfer_in.out_transaction
        
    if tx.recurring:
        import datetime
        if delete_mode == 'future':
            Transaction.objects.filter(recurring=tx.recurring, date__gte=tx.date).delete()
            tx.recurring.end_date = tx.date - datetime.timedelta(days=1)
            tx.recurring.save(update_fields=['end_date'])
        elif delete_mode == 'all':
            Transaction.objects.filter(recurring=tx.recurring).delete()
            tx.recurring.active = False
            tx.recurring.save(update_fields=['active'])
        else:
            date_str = str(tx.date)
            if date_str not in tx.recurring.ignored_dates:
                tx.recurring.ignored_dates.append(date_str)
                tx.recurring.save(update_fields=['ignored_dates'])
            tx.delete()
            if tx_to_delete_extra:
                tx_to_delete_extra.delete()
    else:
        tx.delete()
        if tx_to_delete_extra:
            tx_to_delete_extra.delete()
        
    messages.success(request, "Transação excluída com sucesso.")

    if request.headers.get('HX-Request'):
        return HttpResponse("")
    return redirect('transactions_web:list')


# Categories & Tags Views
@login_required(login_url='users_web:login')
def category_list_view(request):
    categories = Category.objects.filter(user=request.user)
    tags = Tag.objects.filter(user=request.user)

    context = {
        'categories': categories,
        'tags': tags,
    }
    return render(request, 'categories/index.html', context)


@login_required(login_url='users_web:login')
def category_create_view(request):
    from django.contrib import messages

    from .forms import CategoryForm
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            cat = form.save(commit=False)
            cat.user = request.user
            cat.save()
            messages.success(request, "Categoria criada com sucesso!")
            return redirect('transactions_web:category_list')
        else:
            messages.error(request, f"Erro ao criar categoria: {form.errors.as_text()}")
            return redirect('transactions_web:category_list')

    return render(request, 'categories/partials/category_form.html')


@login_required(login_url='users_web:login')
def category_confirm_delete_view(request, pk):
    from django.http import HttpResponse
    cat = get_object_or_404(Category, pk=pk, user=request.user)
    
    if cat.transactions.exists():
        from django.contrib import messages
        messages.error(request, f"Não é possível excluir a categoria '{cat.name}' pois existem transações atreladas a ela.")
        response = HttpResponse("")
        response['HX-Redirect'] = reverse('transactions_web:category_list')
        return response

    context = {
        'title': 'Excluir Categoria',
        'message': f"Tem certeza que deseja excluir a categoria '{cat.name}'?",
        'action_url': reverse('transactions_web:category_delete', args=[cat.id]),
    }
    return render(request, 'partials/confirm_modal.html', context)


@login_required(login_url='users_web:login')
def category_delete_view(request, pk):
    from django.contrib import messages
    cat = get_object_or_404(Category, pk=pk, user=request.user)
    
    if cat.transactions.exists():
        messages.error(request, "Não é possível excluir esta categoria.")
        return redirect('transactions_web:category_list')

    if request.method == 'POST' or request.headers.get('HX-Request'):
        cat_name = cat.name
        cat.delete()
        messages.success(request, f"Categoria '{cat_name}' excluída com sucesso.")
    return redirect('transactions_web:category_list')


@login_required(login_url='users_web:login')
def tag_create_view(request):
    from django.contrib import messages

    from .forms import TagForm
    if request.method == 'POST':
        form = TagForm(request.POST)
        if form.is_valid():
            tag = form.save(commit=False)
            tag.user = request.user
            tag.save()
            messages.success(request, "Tag criada com sucesso!")
            return redirect('transactions_web:category_list')
        else:
            messages.error(request, f"Erro ao criar tag: {form.errors.as_text()}")
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
def tag_delete_view(request, pk):
    tag = get_object_or_404(Tag, pk=pk, user=request.user)
    if request.method == 'POST' or request.headers.get('HX-Request'):
        tag_name = tag.name
        tag.delete()
        from django.contrib import messages
        messages.success(request, f"Tag '{tag_name}' excluída com sucesso.")
    return redirect('transactions_web:category_list')


# Recurring Transactions Views
@login_required(login_url='users_web:login')
def recurring_list_view(request):
    recurring = RecurringTransaction.objects.filter(user=request.user).select_related('account', 'category')

    context = {
        'recurring_transactions': recurring,
    }
    return render(request, 'recurring/index.html', context)


from django.db import transaction as db_transaction


@login_required(login_url='users_web:login')
def recurring_create_view(request):
    accounts = Account.objects.filter(user=request.user)
    categories = Category.objects.filter(user=request.user)

    if request.method == 'POST':
        category_id = request.POST.get('category')
        account_id = request.POST.get('account')
        description = request.POST.get('description')
        amount = Decimal(request.POST.get('amount', '0'))
        frequency = request.POST.get('frequency', 'monthly')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date') or None

        with db_transaction.atomic():
            recurring = RecurringTransaction.objects.create(
                user=request.user,
                category_id=category_id,
                account_id=account_id,
                description=description,
                amount=amount,
                frequency=frequency,
                start_date=start_date,
                end_date=end_date,
                active=True,
            )

            # Seed initial transaction for start date
            Transaction.objects.create(
                user=request.user,
                account_id=account_id,
                category_id=category_id,
                description=f"{description} (Recorrente)",
                amount=amount,
                date=start_date,
                status=Transaction.Statuses.COMPLETED,
                recurring=recurring,
            )

        from django.contrib import messages
        messages.success(request, "Transação recorrente criada com sucesso!")
        return redirect('transactions_web:recurring_list')

    context = {
        'accounts': accounts,
        'categories': categories,
    }
    return render(request, 'recurring/partials/recurring_form.html', context)


@login_required(login_url='users_web:login')
def recurring_confirm_delete_view(request, pk):
    item = get_object_or_404(RecurringTransaction, pk=pk, user=request.user)
    context = {
        'title': 'Excluir Transação Recorrente',
        'message': f"Deseja excluir a regra de recorrência '{item.description}'?",
        'action_url': reverse('transactions_web:recurring_delete', args=[item.id]),
        'options': [
            {
                'value': 'keep_history',
                'label': 'Manter transações já registradas (excluir apenas ocorrências futuras)'
            },
            {
                'value': 'delete_all',
                'label': 'Excluir a regra e TODAS as transações geradas por ela'
            }
        ]
    }
    return render(request, 'partials/confirm_modal.html', context)


@login_required(login_url='users_web:login')
def recurring_delete_view(request, pk):
    item = get_object_or_404(RecurringTransaction, pk=pk, user=request.user)
    if request.method == 'POST':
        delete_mode = request.POST.get('delete_mode', 'keep_history')
        with db_transaction.atomic():
            if delete_mode == 'delete_all':
                item.generated_transactions.all().delete()
            else:
                item.generated_transactions.update(recurring=None)
            item.delete()
    return redirect('transactions_web:recurring_list')


# Transfer View
@login_required(login_url='users_web:login')
def transfer_create_view(request):
    from transactions.services import create_transfer
    accounts = Account.objects.filter(user=request.user)

    if request.method == 'POST':
        out_account_id = request.POST.get('out_account')
        in_account_id = request.POST.get('in_account')
        description = request.POST.get('description', 'Transferência entre contas')
        amount = Decimal(request.POST.get('amount', '0'))
        date = request.POST.get('date')
        status = Transaction.Statuses.COMPLETED

        create_transfer(
            user=request.user,
            out_account_id=out_account_id,
            in_account_id=in_account_id,
            description=description,
            amount=amount,
            tx_date=date,
            status=status
        )

        return redirect('transactions_web:list')

    return render(request, 'transactions/partials/transfer_form.html', {'accounts': accounts})
