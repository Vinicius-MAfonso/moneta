from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required

from .models import Investment
from wallets.models import Account


@login_required(login_url='users_web:login')
def investment_list_view(request):
    investments = Investment.objects.filter(user=request.user).select_related('account')
    total_value = sum((inv.quantity * inv.current_price for inv in investments), Decimal('0.00'))

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
def investment_delete_view(request, pk):
    inv = get_object_or_404(Investment, pk=pk, user=request.user)
    inv.delete()
    return redirect('investments_web:list')
