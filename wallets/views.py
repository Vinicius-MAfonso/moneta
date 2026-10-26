from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from moneta.common import (
    format_exception_message,
    format_form_errors,
    hx_redirect,
    hx_toast,
)

from .forms import AccountForm, BalanceAdjustmentForm, PayBillForm
from .models import Account, CreditCardBill
from .services import (
    adjust_account_balance,
    create_account,
    delete_account,
    get_bill_detail_context,
    get_credit_card_dashboard_context,
    pay_credit_card_bill,
    reopen_credit_card_bill,
    update_account,
)


@login_required
def account_list_view(request):
    accounts = (
        Account.objects.filter(user=request.user)
        .select_related('credit_card_details')
        .prefetch_related('goals')
    )
    return render(request, 'wallets/index.html', {'accounts': accounts})


@login_required
def account_create_view(request):
    if request.method == 'POST':
        form = AccountForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                create_account(request.user, form.cleaned_data)
            except (ValueError, ValidationError) as e:
                error_msg = format_exception_message(e)
                if request.headers.get('HX-Request'):
                    return hx_toast(error_msg)
                messages.error(request, f"Erro ao criar conta: {error_msg}")
                return redirect('wallets_web:list')

            messages.success(request, "Conta criada com sucesso!")
            if request.headers.get('HX-Request'):
                return hx_redirect(reverse('wallets_web:list'))
            return redirect('wallets_web:list')
        else:
            error_msg = format_form_errors(form)
            if request.headers.get('HX-Request'):
                return hx_toast(error_msg)
            messages.error(request, f"Erro ao criar conta: {error_msg}")
            return redirect('wallets_web:list')

    return render(request, 'wallets/partials/account_form.html')


@login_required
def account_update_view(request, pk):
    account = get_object_or_404(Account.objects.select_related('credit_card_details'), pk=pk, user=request.user)

    if request.method == 'POST':
        form = AccountForm(request.POST, user=request.user, account_id=account.id)
        if form.is_valid():
            try:
                update_account(account, form.cleaned_data)
            except (ValueError, ValidationError) as e:
                error_msg = format_exception_message(e)
                if request.headers.get('HX-Request'):
                    return hx_toast(error_msg)
                messages.error(request, f"Erro ao atualizar conta: {error_msg}")
                return redirect('wallets_web:list')

            messages.success(request, "Conta atualizada com sucesso!")
            if request.headers.get('HX-Request'):
                return hx_redirect(reverse('wallets_web:list'))
            return redirect('wallets_web:list')
        else:
            error_msg = format_form_errors(form)
            if request.headers.get('HX-Request'):
                return hx_toast(error_msg)
            messages.error(request, f"Erro ao atualizar conta: {error_msg}")
            return redirect('wallets_web:list')

    return render(request, 'wallets/partials/account_form.html', {'account': account})


@login_required
def account_balance_adjustment_view(request, pk):
    account = get_object_or_404(Account.objects.select_related('credit_card_details'), pk=pk, user=request.user)

    if request.method == 'POST':
        form = BalanceAdjustmentForm(request.POST)
        if not form.is_valid():
            error_msg = format_form_errors(form)
            if request.headers.get('HX-Request'):
                return hx_toast(error_msg)
            messages.error(request, "Valor de saldo inválido.")
            return redirect('wallets_web:list')

        cd = form.cleaned_data
        try:
            success, result_type = adjust_account_balance(
                account, cd['new_balance'], cd['adjustment_type'], request.user
            )
        except (ValueError, ValidationError) as e:
            error_msg = format_exception_message(e)
            if request.headers.get('HX-Request'):
                return hx_toast(error_msg)
            messages.error(request, error_msg)
            return redirect('wallets_web:list')

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
            return hx_redirect(reverse('wallets_web:list'))
        return redirect('wallets_web:list')

    return render(request, 'wallets/partials/balance_adjustment_form.html', {'account': account})


@login_required
def account_confirm_delete_view(request, pk):
    account = get_object_or_404(Account, pk=pk, user=request.user)
    context = {
        'title': 'Excluir Conta',
        'message': f"Tem certeza que deseja excluir a conta '{account.name}'? Isso vai excluir TODAS as transações relacionadas a essa conta.",
        'action_url': reverse('wallets_web:delete', args=[account.id]),
    }
    return render(request, 'partials/confirm_modal.html', context)


@login_required
@require_http_methods(["POST", "DELETE"])
def account_delete_view(request, pk):
    account = get_object_or_404(Account, pk=pk, user=request.user)
    account_name = account.name
    delete_account(account)
    messages.success(request, f"Conta '{account_name}' excluída com sucesso.")
    if request.headers.get('HX-Request'):
        return hx_redirect(reverse('wallets_web:list'))
    return redirect('wallets_web:list')


@login_required
def bill_detail_view(request, pk):
    bill = get_object_or_404(CreditCardBill, pk=pk, account__user=request.user)
    context = get_bill_detail_context(request.user, bill)
    return render(request, 'wallets/bill_detail.html', context)


@login_required
@require_POST
def pay_bill_view(request, pk):
    bill = get_object_or_404(CreditCardBill, pk=pk, account__user=request.user)
    form = PayBillForm(request.POST, user=request.user)
    if not form.is_valid():
        messages.error(request, f"Erro ao pagar fatura: {format_form_errors(form)}")
        return redirect('wallets_web:bill_detail', pk=bill.pk)

    cd = form.cleaned_data
    try:
        pay_credit_card_bill(bill, cd['payment_account'].id, cd.get('payment_amount'))
        messages.success(request, f"Pagamento da fatura de {bill.period_date.strftime('%m/%Y')} registrado com sucesso!")
    except (ValueError, ValidationError) as e:
        messages.error(request, f"Erro ao pagar fatura: {format_exception_message(e)}")

    return redirect('wallets_web:bill_detail', pk=bill.pk)


@login_required
@require_POST
def reopen_bill_view(request, pk):
    bill = get_object_or_404(CreditCardBill, pk=pk, account__user=request.user)
    try:
        reopen_credit_card_bill(bill)
        messages.success(request, f"O pagamento da fatura de {bill.period_date.strftime('%m/%Y')} foi cancelado e a fatura reaberta.")
        if request.headers.get('HX-Request'):
            return hx_redirect(reverse('wallets_web:bill_detail', args=[bill.pk]))
    except (ValueError, ValidationError) as e:
        error_msg = f"Erro ao reabrir fatura: {format_exception_message(e)}"
        if request.headers.get('HX-Request'):
            return hx_toast(error_msg)
        messages.error(request, error_msg)

    return redirect('wallets_web:bill_detail', pk=bill.pk)


@login_required
def confirm_reopen_bill_view(request, pk):
    bill = get_object_or_404(CreditCardBill, pk=pk, account__user=request.user)
    context = {
        'title': 'Reabrir Fatura',
        'message': "Tem certeza que deseja cancelar o pagamento e reabrir esta fatura? O valor será devolvido para a conta de origem.",
        'action_url': reverse('wallets_web:reopen_bill', args=[bill.id]),
        'confirm_btn_text': 'Reabrir Fatura',
        'confirm_btn_class': 'px-5 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs transition shadow-lg shadow-rose-600/25',
    }
    return render(request, 'partials/confirm_modal.html', context)


@login_required
def bill_list_view(request, account_id):
    account = get_object_or_404(Account, pk=account_id, user=request.user, type=Account.Types.CREDIT_CARD)
    bills = account.bills.all().order_by('period_date')

    status_filter = request.GET.get('status')
    if status_filter in CreditCardBill.Statuses.values:
        bills = bills.filter(status=status_filter)

    context = {
        'account': account,
        'bills': bills,
        'status_filter': status_filter,
    }
    return render(request, 'wallets/bill_list.html', context)


@login_required
def credit_card_dashboard_view(request):
    context = get_credit_card_dashboard_context(request.user)
    return render(request, 'wallets/credit_card_dashboard.html', context)
