from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import Transaction, Category, Tag, RecurringTransaction
from wallets.models import Account
from moneta.common import TransactionType, get_month_context
from .services import create_transfer, create_regular_transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce


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
        qs = qs.filter(description__icontains=search)

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
    accounts = Account.objects.filter(user=request.user)
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
                    status=request.POST.get('status', 'concluída'),
                    tag_ids=[t.id for t in cd['tags']],
                    is_recurring=cd['is_recurring'],
                    frequency=cd['frequency'],
                    recurring_end_date=cd['recurring_end_date']
                )
                if request.headers.get('HX-Request'):
                    response = HttpResponse(status=204)
                    response['HX-Trigger'] = 'reload-transactions'
                    return response
                return redirect('transactions_web:list')
            else:
                messages.error(request, f"Erro na transferência: {form.errors.as_text()}")
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
                recurring_end_date=cd['recurring_end_date']
            )
            if request.headers.get('HX-Request'):
                response = HttpResponse(status=204)
                response['HX-Trigger'] = 'reload-transactions'
                return response
            return redirect('transactions_web:list')
        else:
            messages.error(request, f"Erro ao criar transação: {form.errors.as_text()}")
            return redirect('transactions_web:list')

    context = {
        'accounts': accounts,
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
    from django_q.tasks import async_task
    tx = get_object_or_404(Transaction, pk=pk, user=request.user)
    delete_mode = request.POST.get('delete_mode', 'single')
    
    if tx.recurring:
        if delete_mode == 'future':
            Transaction.objects.filter(recurring=tx.recurring, date__gte=tx.date).delete()
        elif delete_mode == 'all':
            Transaction.objects.filter(recurring=tx.recurring).delete()
        else:
            tx.delete()
    else:
        tx.delete()

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
    from .forms import CategoryForm
    from django.contrib import messages
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            cat = form.save(commit=False)
            cat.user = request.user
            cat.save()
            return redirect('transactions_web:category_list')
        else:
            messages.error(request, f"Erro ao criar categoria: {form.errors.as_text()}")
            return redirect('transactions_web:category_list')

    return render(request, 'categories/partials/category_form.html')


@login_required(login_url='users_web:login')
def category_confirm_delete_view(request, pk):
    cat = get_object_or_404(Category, pk=pk, user=request.user)
    context = {
        'title': 'Excluir Categoria',
        'message': f"Tem certeza que deseja excluir a categoria '{cat.name}'?",
        'action_url': reverse('transactions_web:category_delete', args=[cat.id]),
    }
    return render(request, 'partials/confirm_modal.html', context)


@login_required(login_url='users_web:login')
def category_delete_view(request, pk):
    cat = get_object_or_404(Category, pk=pk, user=request.user)
    if request.method == 'POST' or request.headers.get('HX-Request'):
        cat.delete()
    return redirect('transactions_web:category_list')


@login_required(login_url='users_web:login')
def tag_create_view(request):
    from .forms import TagForm
    from django.contrib import messages
    if request.method == 'POST':
        form = TagForm(request.POST)
        if form.is_valid():
            tag = form.save(commit=False)
            tag.user = request.user
            tag.save()
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
        tag.delete()
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

# Import Views
@login_required(login_url='users_web:login')
def import_upload_view(request):
    if request.method == 'POST':
        account_id = request.POST.get('account_id')
        file = request.FILES.get('file')
        if not file or not account_id:
            messages.error(request, 'Por favor, selecione uma conta e um arquivo.')
            return redirect('transactions_web:import_upload')
            
        from transactions.services import parse_statement_file
        try:
            transactions = parse_statement_file(file.read(), file.name)
            request.session['import_data'] = transactions
            request.session['import_account_id'] = account_id
            return redirect('transactions_web:import_preview')
        except Exception as e:
            messages.error(request, f'Erro ao ler o arquivo: {str(e)}')
            return redirect('transactions_web:import_upload')
            
    accounts = Account.objects.filter(user=request.user)
    return render(request, 'transactions/import_upload.html', {'accounts': accounts})

@login_required(login_url='users_web:login')
def import_preview_view(request):
    import_data = request.session.get('import_data')
    account_id = request.session.get('import_account_id')
    
    if not import_data or not account_id:
        return redirect('transactions_web:import_upload')
        
    account = get_object_or_404(Account, id=account_id, user=request.user)
    categories = Category.objects.filter(user=request.user)
    
    from transactions.services import guess_category
    
    for tx in import_data:
        if 'category_id' not in tx:
            tx['category_id'] = guess_category(tx['description'], request.user)
            
    # save back to session with guesses
    request.session['import_data'] = import_data
    
    context = {
        'account': account,
        'transactions': import_data,
        'categories': categories,
    }
    return render(request, 'transactions/import_preview.html', context)

@login_required(login_url='users_web:login')
def import_process_view(request):
    import_data = request.session.get('import_data')
    account_id = request.session.get('import_account_id')
    
    if not import_data or not account_id:
        return redirect('transactions_web:import_upload')
        
    account = get_object_or_404(Account, id=account_id, user=request.user)
    
    if request.method == 'POST':
        selected_ids = request.POST.getlist('selected_transactions')
        
        imported_count = 0
        from django.db import transaction as db_transaction
        
        with db_transaction.atomic():
            for tx in import_data:
                orig_id = str(tx.get('original_id'))
                if orig_id in selected_ids:
                    cat_id_str = request.POST.get(f"category_{orig_id}")
                    cat = None
                    if cat_id_str:
                        cat = Category.objects.filter(id=cat_id_str, user=request.user).first()
                    
                    if not cat:
                        cat, _ = Category.objects.get_or_create(
                            user=request.user,
                            name="Outros (Importado)",
                            defaults={"type": tx['type'], "color": "#9ca3af"}
                        )
                        
                    Transaction.objects.create(
                        user=request.user,
                        account=account,
                        category=cat,
                        description=tx['description'],
                        amount=Decimal(tx['amount']),
                        date=tx['date'],
                        status=Transaction.Statuses.COMPLETED
                    )
                    imported_count += 1
                    
        # Recalculate balance is now handled by signals

        
        # Clear session
        del request.session['import_data']
        del request.session['import_account_id']
        
        messages.success(request, f'{imported_count} transações importadas com sucesso!')
        return redirect('transactions_web:list')
        
    return redirect('transactions_web:import_preview')
