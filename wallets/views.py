from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .models import Account, CreditCardDetails


@login_required(login_url='users_web:login')
def account_list_view(request):

    accounts_qs = Account.objects.filter(user=request.user).select_related('credit_card_details')
    from wallets.services import calculate_expected_balance
    
    accounts = []
    for account in accounts_qs:
        account.expected_balance = calculate_expected_balance(account)
        accounts.append(account)
        
    context = {
        'accounts': accounts,
    }
    return render(request, 'wallets/index.html', context)


@login_required(login_url='users_web:login')
def account_create_view(request):
    from django.contrib import messages

    from .forms import AccountForm
    if request.method == 'POST':
        form = AccountForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            account = Account.objects.create(
                user=request.user,
                name=cd['name'],
                type=cd['type'],
                institution=cd['institution'],
                balance=cd['balance'],
                initial_balance=cd['balance'],
                color=cd['color'],
            )

            if cd['type'] == Account.Types.CREDIT_CARD:
                CreditCardDetails.objects.create(
                    account=account,
                    limit=cd['limit'],
                    available_limit=cd['limit'],
                    closing_day=cd['closing_day'],
                    due_day=cd['due_day'],
                )
            messages.success(request, "Conta criada com sucesso!")
            return redirect('wallets_web:list')
        else:
            messages.error(request, f"Erro ao criar conta: {form.errors.as_text()}")
            return redirect('wallets_web:list')

    return render(request, 'wallets/partials/account_form.html')


@login_required(login_url='users_web:login')
def account_update_view(request, pk):
    from django.contrib import messages
    from wallets.models import Account, CreditCardDetails
    from .forms import AccountForm
    
    account = get_object_or_404(Account, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = AccountForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            account.name = cd['name']
            account.institution = cd['institution']
            account.color = cd['color']
            # We don't update type to avoid complex recalculations
            if 'balance' in cd:
                account.initial_balance = cd['balance']
                
            account.save()
            
            if account.type == Account.Types.CREDIT_CARD and hasattr(account, 'credit_card_details'):
                cc = account.credit_card_details
                
                # if limit increased, available limit should increase too
                diff = cd['limit'] - cc.limit
                cc.limit = cd['limit']
                cc.available_limit = max(Decimal('0.00'), cc.available_limit + diff)
                
                cc.closing_day = cd['closing_day']
                cc.due_day = cd['due_day']
                cc.save()
                
            from wallets.services import recalculate_account_balance
            recalculate_account_balance(account)
                
            messages.success(request, "Conta atualizada com sucesso!")
            if request.headers.get('HX-Request'):
                return HttpResponse()
            return redirect('wallets_web:list')
        else:
            context = {'account': account, 'form': form}
            return render(request, 'wallets/partials/account_form.html', context)
            
    context = {
        'account': account,
    }
    return render(request, 'wallets/partials/account_form.html', context)

@login_required(login_url='users_web:login')
def account_balance_adjustment_view(request, pk):
    from django.contrib import messages
    from wallets.services import recalculate_account_balance
    from transactions.models import Category, Transaction
    from moneta.common import TransactionType
    from django.utils import timezone
    
    account = get_object_or_404(Account, pk=pk, user=request.user)
    
    if request.method == 'POST':
        new_balance_str = request.POST.get('new_balance')
        adjustment_type = request.POST.get('adjustment_type')
        
        try:
            # Replace comma for point to parse decimal if needed
            new_balance = Decimal(new_balance_str.replace(',', '.'))
        except:
            messages.error(request, "Valor de saldo inválido.")
            return redirect('wallets_web:list')
            
        if adjustment_type == 'initial':
            account.initial_balance = new_balance
            account.save()
            recalculate_account_balance(account)
            
            messages.success(request, f"Saldo inicial de '{account.name}' atualizado.")
        
        elif adjustment_type == 'transaction':
            delta = new_balance - account.balance
            if delta != 0:
                tx_type = TransactionType.INCOME if delta > 0 else TransactionType.EXPENSE
                
                category_name = "Reajuste de Saldo Positivo" if delta > 0 else "Reajuste de Saldo Negativo"
                # Get or create category for adjustment
                category, _ = Category.objects.get_or_create(
                    user=request.user,
                    name=category_name,
                    defaults={
                        'type': tx_type,
                        'color': '#64748B', # Slate 500
                        'icon': '⚖️'
                    }
                )
                
                Transaction.objects.create(
                    user=request.user,
                    account=account,
                    category=category,
                    amount=abs(delta),
                    date=timezone.now().date(),
                    description="Reajuste de Saldo",
                    status=Transaction.Statuses.COMPLETED
                )
                
                recalculate_account_balance(account)
                messages.success(request, f"Transação de reajuste criada em '{account.name}'.")
            else:
                messages.info(request, "O novo saldo é igual ao saldo atual.")
                
        if request.headers.get('HX-Request'):
            return HttpResponse()
        return redirect('wallets_web:list')
        
    context = {'account': account}
    return render(request, 'wallets/partials/balance_adjustment_form.html', context)



@login_required(login_url='users_web:login')
def account_confirm_delete_view(request, pk):
    account = get_object_or_404(Account, pk=pk, user=request.user)
    context = {
        'title': 'Excluir Conta',
        'message': f"Tem certeza que deseja excluir a conta '{account.name}'? Isso vai excluir TODAS as transações relacionadas a essa conta.",
        'action_url': reverse('wallets_web:delete', args=[account.id]),
    }
    return render(request, 'partials/confirm_modal.html', context)


@login_required(login_url='users_web:login')
def account_delete_view(request, pk):
    from django.contrib import messages
    account = get_object_or_404(Account, pk=pk, user=request.user)
    if request.method == 'POST' or request.headers.get('HX-Request'):
        account_name = account.name
        account.delete()
        messages.success(request, f"Conta '{account_name}' e todas as suas transações foram excluídas.")
    return redirect('wallets_web:list')

@login_required(login_url='users_web:login')
def bill_detail_view(request, pk):
    from django.db.models import Sum

    from moneta.common import TransactionType
    from wallets.models import Account, CreditCardBill
    
    bill = get_object_or_404(CreditCardBill, pk=pk, account__user=request.user)
    transactions = bill.transactions.all().order_by('-date', '-created_at')
    
    expenses = transactions.filter(category__type=TransactionType.EXPENSE).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    incomes = transactions.filter(category__type=TransactionType.INCOME).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    transfers_in = transactions.filter(transfer_in__isnull=False).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    transfers_out = transactions.filter(transfer_out__isnull=False).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    total = expenses - incomes - transfers_in + transfers_out
    
    checking_accounts = Account.objects.filter(user=request.user).exclude(type=Account.Types.CREDIT_CARD)

    context = {
        'bill': bill,
        'transactions': transactions,
        'expenses': expenses,
        'incomes': incomes,
        'total': total,
        'checking_accounts': checking_accounts,
    }
    return render(request, 'wallets/bill_detail.html', context)


@login_required(login_url='users_web:login')
def pay_bill_view(request, pk):
    from django.contrib import messages

    from wallets.models import CreditCardBill
    from wallets.services import pay_credit_card_bill
    
    bill = get_object_or_404(CreditCardBill, pk=pk, account__user=request.user)
    
    if request.method == 'POST':
        payment_account_id = request.POST.get('payment_account')
        payment_amount = request.POST.get('payment_amount')
        try:
            pay_credit_card_bill(bill, payment_account_id, payment_amount)
            messages.success(request, f"Pagamento da fatura de {bill.period_date.strftime('%m/%Y')} registrado com sucesso!")
        except Exception as e:
            messages.error(request, f"Erro ao pagar fatura: {e!s}")
            
    return redirect('wallets_web:bill_detail', pk=bill.pk)


@login_required(login_url='users_web:login')
def bill_list_view(request, account_id):
    from wallets.models import Account
    account = get_object_or_404(Account, pk=account_id, user=request.user, type=Account.Types.CREDIT_CARD)
    bills = account.bills.all().order_by('-period_date')
    
    status_filter = request.GET.get('status')
    if status_filter in ['open', 'closed', 'paid']:
        bills = bills.filter(status=status_filter)
    
    context = {
        'account': account,
        'bills': bills,
        'status_filter': status_filter,
    }
    return render(request, 'wallets/bill_list.html', context)
