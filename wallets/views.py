from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required

from .models import Account, CreditCardDetails


@login_required(login_url='users_web:login')
def account_list_view(request):
    # TODO: move to background task or call only on account updates
    # recalculate_all_user_balances(request.user)
    accounts = Account.objects.filter(user=request.user).select_related('credit_card_details')
    context = {
        'accounts': accounts,
    }
    return render(request, 'wallets/index.html', context)


@login_required(login_url='users_web:login')
def account_create_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        account_type = request.POST.get('type')
        institution = request.POST.get('institution')
        balance = Decimal(request.POST.get('balance', '0'))
        color = request.POST.get('color', '#6366f1')

        account = Account.objects.create(
            user=request.user,
            name=name,
            type=account_type,
            institution=institution,
            balance=balance,
            initial_balance=balance,
            color=color,
        )

        if account_type == Account.Types.CREDIT_CARD:
            limit = Decimal(request.POST.get('limit', '0'))
            closing_day = int(request.POST.get('closing_day', '1'))
            due_day = int(request.POST.get('due_day', '10'))
            CreditCardDetails.objects.create(
                account=account,
                limit=limit,
                available_limit=limit,
                closing_day=closing_day,
                due_day=due_day,
            )

        return redirect('wallets_web:list')

    return render(request, 'wallets/partials/account_form.html')


@login_required(login_url='users_web:login')
def account_confirm_delete_view(request, pk):
    account = get_object_or_404(Account, pk=pk, user=request.user)
    context = {
        'title': 'Excluir Conta',
        'message': f"Tem certeza que deseja excluir a conta '{account.name}'? Todas as transações associadas a esta conta também serão afetadas.",
        'action_url': reverse('wallets_web:delete', args=[account.id]),
    }
    return render(request, 'partials/confirm_modal.html', context)


@login_required(login_url='users_web:login')
def account_delete_view(request, pk):
    account = get_object_or_404(Account, pk=pk, user=request.user)
    if request.method == 'POST' or request.headers.get('HX-Request'):
        account.delete()
    return redirect('wallets_web:list')


@login_required(login_url='users_web:login')
def bill_detail_view(request, pk):
    from wallets.models import CreditCardBill, Account
    from moneta.common import TransactionType
    from django.db.models import Sum
    
    bill = get_object_or_404(CreditCardBill, pk=pk, account__user=request.user)
    transactions = bill.transactions.all().order_by('-date', '-created_at')
    
    expenses = transactions.filter(category__type=TransactionType.EXPENSE).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    incomes = transactions.filter(category__type=TransactionType.INCOME).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total = expenses - incomes
    
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
    from wallets.models import CreditCardBill
    from wallets.services import pay_credit_card_bill
    from django.contrib import messages
    
    bill = get_object_or_404(CreditCardBill, pk=pk, account__user=request.user)
    
    if request.method == 'POST':
        payment_account_id = request.POST.get('payment_account')
        try:
            pay_credit_card_bill(bill, payment_account_id)
            messages.success(request, f"Fatura de {bill.period_date.strftime('%m/%Y')} paga com sucesso!")
        except Exception as e:
            messages.error(request, f"Erro ao pagar fatura: {str(e)}")
            
    return redirect('wallets_web:bill_detail', pk=bill.pk)


@login_required(login_url='users_web:login')
def bill_list_view(request, account_id):
    from wallets.models import Account
    account = get_object_or_404(Account, pk=account_id, user=request.user, type=Account.Types.CREDIT_CARD)
    bills = account.bills.all().order_by('-period_date')
    
    context = {
        'account': account,
        'bills': bills,
    }
    return render(request, 'wallets/bill_list.html', context)
