from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required

from .models import Account, CreditCardDetails


@login_required(login_url='users_web:login')
def account_list_view(request):
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
