from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required

from .models import Investment
from wallets.models import Account


@login_required(login_url='users_web:login')
def investment_list_view(request):
    raw_investments = Investment.objects.filter(user=request.user).select_related('account')

    investments = []
    total_value = Decimal('0.00')

    for inv in raw_investments:
        total_position = inv.quantity * inv.current_price
        total_cost = inv.quantity * inv.average_price
        gain_loss = total_position - total_cost
        gain_loss_pct = ((inv.current_price - inv.average_price) / inv.average_price * 100) if inv.average_price > 0 else Decimal('0.00')

        inv.total_position = total_position
        inv.total_cost = total_cost
        inv.gain_loss = gain_loss
        inv.gain_loss_pct = round(gain_loss_pct, 2)

        total_value += total_position
        investments.append(inv)

    context = {
        'investments': investments,
        'total_value': total_value,
    }
    return render(request, 'investments/index.html', context)


@login_required(login_url='users_web:login')
def investment_create_view(request):
    accounts = Account.objects.filter(user=request.user)

    if request.method == 'POST':
        account_id = request.POST.get('account')
        name = request.POST.get('name')
        inv_type = request.POST.get('type')
        quantity = Decimal(request.POST.get('quantity', '0'))
        average_price = Decimal(request.POST.get('average_price', '0'))
        current_price = Decimal(request.POST.get('current_price', '0'))

        Investment.objects.create(
            user=request.user,
            account_id=account_id,
            name=name,
            type=inv_type,
            quantity=quantity,
            average_price=average_price,
            current_price=current_price,
        )
        return redirect('investments_web:list')

    return render(request, 'investments/partials/investment_form.html', {'accounts': accounts})


@login_required(login_url='users_web:login')
def investment_confirm_delete_view(request, pk):
    inv = get_object_or_404(Investment, pk=pk, user=request.user)
    context = {
        'title': 'Excluir Ativo',
        'message': f"Tem certeza que deseja excluir o ativo '{inv.name}' da sua carteira?",
        'action_url': reverse('investments_web:delete', args=[inv.id]),
    }
    return render(request, 'partials/confirm_modal.html', context)


@login_required(login_url='users_web:login')
def investment_delete_view(request, pk):
    inv = get_object_or_404(Investment, pk=pk, user=request.user)
    if request.method == 'POST' or request.headers.get('HX-Request'):
        inv.delete()
    return redirect('investments_web:list')
