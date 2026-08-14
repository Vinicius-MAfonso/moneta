from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from wallets.models import Account


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
                from wallets.models import CreditCardDetails
                CreditCardDetails.objects.create(
                    account=account,
                    limit=cd['limit'],
                    available_limit=cd['limit'],
                    closing_day=cd['closing_day'],
                    due_day=cd['due_day'],
                )
            if request.headers.get('HX-Request'):
                messages.success(request, "Conta criada com sucesso!")
                response = HttpResponse(status=204)
                response['HX-Redirect'] = reverse('wallets_web:list')
                return response
            messages.success(request, "Conta criada com sucesso!")
            return redirect('wallets_web:list')
        else:
            error_msg = form.errors.as_text()
            if request.headers.get('HX-Request'):
                import json
                response = HttpResponse(status=204)
                response['HX-Trigger'] = json.dumps({'show-toast': {'message': f'Erro: {error_msg}', 'type': 'error'}})
                return response
            messages.error(request, f"Erro ao criar conta: {error_msg}")
            return redirect('wallets_web:list')

    return render(request, 'wallets/partials/account_form.html')


@login_required(login_url='users_web:login')
def account_update_view(request, pk):
    from django.contrib import messages

    from .forms import AccountForm

    account = get_object_or_404(Account, pk=pk, user=request.user)

    if request.method == 'POST':
        form = AccountForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            from wallets.services import update_account
            update_account(account, cd)

            if request.headers.get('HX-Request'):
                messages.success(request, "Conta atualizada com sucesso!")
                response = HttpResponse(status=204)
                response['HX-Redirect'] = reverse('wallets_web:list')
                return response
            messages.success(request, "Conta atualizada com sucesso!")
            return redirect('wallets_web:list')
        else:
            error_msg = form.errors.as_text()
            if request.headers.get('HX-Request'):
                import json
                response = HttpResponse(status=204)
                response['HX-Trigger'] = json.dumps({'show-toast': {'message': f'Erro: {error_msg}', 'type': 'error'}})
                return response
            context = {'account': account, 'form': form}
            return render(request, 'wallets/partials/account_form.html', context)

    context = {
        'account': account,
    }
    return render(request, 'wallets/partials/account_form.html', context)

@login_required(login_url='users_web:login')
def account_balance_adjustment_view(request, pk):
    from django.contrib import messages
    from django.utils import timezone

    from moneta.common import TransactionType
    from transactions.models import Category, Transaction
    from wallets.services import recalculate_account_balance

    account = get_object_or_404(Account, pk=pk, user=request.user)

    if request.method == 'POST':
        new_balance_str = request.POST.get('new_balance')
        adjustment_type = request.POST.get('adjustment_type')

        try:
            new_balance = Decimal(new_balance_str.replace(',', '.'))
        except Exception:
            messages.error(request, "Valor de saldo inválido.")
            return redirect('wallets_web:list')

        from wallets.services import adjust_account_balance
        success, result_type = adjust_account_balance(account, new_balance, adjustment_type, request.user)
        
        if success:
            if result_type == "initial":
                messages.success(request, f"Saldo inicial de '{account.name}' atualizado.")
            else:
                messages.success(request, f"Transação de reajuste criada em '{account.name}'.")
        else:
            if result_type == "no_change":
                messages.info(request, "O novo saldo é igual ao saldo atual.")
            else:
                messages.error(request, "Tipo de reajuste inválido.")

        if request.headers.get('HX-Request'):
            response = HttpResponse(status=204)
            response['HX-Redirect'] = reverse('wallets_web:list')
            return response
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
        messages.success(request, f"Conta '{account_name}' excluída com sucesso.")
        if request.headers.get('HX-Request'):
            response = HttpResponse(status=204)
            response['HX-Redirect'] = reverse('wallets_web:list')
            return response
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
    from decimal import Decimal

    from django.contrib import messages

    from wallets.models import Account, CreditCardBill
    from wallets.services import pay_credit_card_bill

    bill = get_object_or_404(CreditCardBill, pk=pk, account__user=request.user)

    if request.method == 'POST':
        payment_account_id = request.POST.get('payment_account')
        payment_amount = request.POST.get('payment_amount')
        try:
            payment_account = get_object_or_404(Account, pk=payment_account_id, user=request.user)
            amount_decimal = Decimal(str(payment_amount))

            if payment_account.type != Account.Types.CREDIT_CARD and payment_account.balance < amount_decimal:
                raise ValueError(
                    f"Saldo insuficiente na conta '{payment_account.name}'. "
                    f"Saldo disponível: R$ {payment_account.balance:.2f}."
                )

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
