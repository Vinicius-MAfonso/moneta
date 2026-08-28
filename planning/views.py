import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from moneta.common import TransactionType, get_month_context
from transactions.models import Category
from wallets.models import Account

from .models import Budget, Goal
from .services import (
    create_budget,
    create_goal,
    delete_budget,
    delete_goal,
    deposit_to_goal,
    get_budgets_with_progress,
)


@login_required(login_url='users_web:login')
def planning_list_view(request):
    month_param = request.GET.get('month')
    month_ctx = get_month_context(month_param)

    raw_goals = Goal.objects.filter(user=request.user)

    goals = []
    for goal in raw_goals:
        pct = (goal.current_amount / goal.target_amount * 100) if goal.target_amount > 0 else 0
        goal.percentage = round(pct, 1)
        goal.bounded_pct = min(100, pct)
        goal.bounded_pct_str = str(round(goal.bounded_pct, 2))
        goals.append(goal)

    budgets = get_budgets_with_progress(request.user, reference_date=month_ctx['start_date'])

    context = {
        'budgets': budgets,
        'goals': goals,
        'month_ctx': month_ctx,
    }
    return render(request, 'planning/index.html', context)


@login_required(login_url='users_web:login')
def budget_create_view(request):
    categories = Category.objects.filter(user=request.user, is_system=False, type=TransactionType.EXPENSE)

    if request.method == 'POST':
        try:
            category_id = request.POST.get('category')
            amount = Decimal(request.POST.get('amount') or '0')
            is_recurring_raw = request.POST.get('is_recurring')
            is_recurring = is_recurring_raw in ['true', 'on', '1', True] or is_recurring_raw is None
            start_date = request.POST.get('start_date') or None
            end_date = request.POST.get('end_date') or None

            create_budget(
                user=request.user,
                category_id=category_id,
                amount=amount,
                is_recurring=is_recurring,
                start_date=start_date,
                end_date=end_date,
            )
            if request.headers.get('HX-Request'):
                messages.success(request, "Orçamento criado com sucesso!")
                response = HttpResponse(status=204)
                response['HX-Redirect'] = reverse('planning_web:list')
                return response
            return redirect('planning_web:list')
        except Exception as e:
            if request.headers.get('HX-Request'):
                response = HttpResponse(status=204)
                response['HX-Trigger'] = json.dumps({'show-toast': {'message': f'{e!s}', 'type': 'error'}})
                return response
            messages.error(request, f"{e!s}")
            return redirect('planning_web:list')

    return render(request, 'planning/partials/budget_form.html', {'categories': categories})


@login_required(login_url='users_web:login')
def budget_confirm_delete_view(request, pk):
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    context = {
        'title': 'Excluir Orçamento',
        'message': f"Tem certeza que deseja excluir o orçamento para a categoria '{budget.category.name}'?",
        'action_url': reverse('planning_web:budget_delete', args=[budget.id]),
    }
    return render(request, 'partials/confirm_modal.html', context)


@login_required(login_url='users_web:login')
def budget_delete_view(request, pk):
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    if request.method in ['POST', 'DELETE']:
        delete_budget(budget)
        messages.success(request, "Orçamento excluído com sucesso!")
        if request.headers.get('HX-Request'):
            response = HttpResponse(status=204)
            response['HX-Redirect'] = reverse('planning_web:list')
            return response
        return redirect('planning_web:list')


@login_required(login_url='users_web:login')
def goal_create_view(request):
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            target_amount = Decimal(request.POST.get('target_amount') or '0')
            current_amount = Decimal(request.POST.get('current_amount') or '0')
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date') or None
            account_id = request.POST.get('account')
            account = Account.objects.get(id=account_id, user=request.user) if account_id else None

            create_goal(
                user=request.user,
                account=account,
                name=name,
                target_amount=target_amount,
                current_amount=current_amount,
                start_date=start_date,
                end_date=end_date,
            )
            if request.headers.get('HX-Request'):
                messages.success(request, "Objetivo criado com sucesso!")
                response = HttpResponse(status=204)
                response['HX-Redirect'] = reverse('planning_web:list')
                return response
            return redirect('planning_web:list')
        except Exception as e:
            if request.headers.get('HX-Request'):
                response = HttpResponse(status=204)
                response['HX-Trigger'] = json.dumps({'show-toast': {'message': f'{e!s}', 'type': 'error'}})
                return response
            messages.error(request, f"{e!s}")
            return redirect('planning_web:list')

    accounts = Account.objects.filter(user=request.user).exclude(type=Account.Types.CREDIT_CARD)
    return render(request, 'planning/partials/goal_form.html', {'accounts': accounts})


@login_required(login_url='users_web:login')
def goal_deposit_view(request, pk):
    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    if request.method == 'POST':
        try:
            amount = Decimal(request.POST.get('amount') or '0')
            if amount > 0:
                deposit_to_goal(goal, amount)
            if request.headers.get('HX-Request'):
                messages.success(request, "Depósito realizado!")
                response = HttpResponse(status=204)
                response['HX-Redirect'] = reverse('planning_web:list')
                return response
            return redirect('planning_web:list')
        except Exception as e:
            if request.headers.get('HX-Request'):
                response = HttpResponse(status=204)
                response['HX-Trigger'] = json.dumps({'show-toast': {'message': f'{e!s}', 'type': 'error'}})
                return response
            messages.error(request, f"{e!s}")
            return redirect('planning_web:list')

    return render(request, 'planning/partials/goal_deposit_form.html', {'goal': goal})


@login_required(login_url='users_web:login')
def goal_confirm_delete_view(request, pk):
    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    context = {
        'title': 'Excluir Objetivo',
        'message': f"Tem certeza que deseja excluir o objetivo '{goal.name}'?",
        'action_url': reverse('planning_web:goal_delete', args=[goal.id]),
    }
    return render(request, 'partials/confirm_modal.html', context)


@login_required(login_url='users_web:login')
def goal_delete_view(request, pk):
    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    if request.method in ['POST', 'DELETE']:
        delete_goal(goal)
        messages.success(request, "Objetivo excluído com sucesso!")
        if request.headers.get('HX-Request'):
            response = HttpResponse(status=204)
            response['HX-Redirect'] = reverse('planning_web:list')
            return response
        return redirect('planning_web:list')

