from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.db import models
from django.contrib.auth.decorators import login_required

from .models import Budget, Goal
from transactions.models import Category


@login_required(login_url='users_web:login')
def planning_list_view(request):
    from planning.services import calculate_budget_progress
    
    raw_budgets = Budget.objects.filter(user=request.user).select_related('category').order_by('-start_date')
    raw_goals = Goal.objects.filter(user=request.user)

    goals = []
    for goal in raw_goals:
        pct = (goal.current_amount / goal.target_amount * 100) if goal.target_amount > 0 else 0
        goal.percentage = round(pct, 1)
        goal.bounded_pct = min(100, int(pct))
        goals.append(goal)

    budgets = []
    for budget in raw_budgets:
        prog = calculate_budget_progress(budget)
        budget.spent = prog['spent']
        budget.percentage = round(prog['real_percentage'], 1)
        budget.bounded_pct = prog['percentage']
        budget.remaining = prog['remaining']
        budgets.append(budget)

    context = {
        'budgets': budgets,
        'goals': goals,
    }
    return render(request, 'planning/index.html', context)


@login_required(login_url='users_web:login')
def budget_create_view(request):
    categories = Category.objects.filter(user=request.user)

    if request.method == 'POST':
        category_id = request.POST.get('category')
        amount = Decimal(request.POST.get('amount', '0'))
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')

        Budget.objects.create(
            user=request.user,
            category_id=category_id,
            amount=amount,
            start_date=start_date,
            end_date=end_date,
        )
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
    if request.method == 'POST' or request.headers.get('HX-Request'):
        budget.delete()
    return redirect('planning_web:list')


@login_required(login_url='users_web:login')
def goal_create_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        target_amount = Decimal(request.POST.get('target_amount', '0'))
        current_amount = Decimal(request.POST.get('current_amount', '0'))
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')

        Goal.objects.create(
            user=request.user,
            name=name,
            target_amount=target_amount,
            current_amount=current_amount,
            start_date=start_date,
            end_date=end_date,
        )
        return redirect('planning_web:list')

    return render(request, 'planning/partials/goal_form.html')


@login_required(login_url='users_web:login')
def goal_deposit_view(request, pk):
    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount', '0'))
        if amount > 0:
            Goal.objects.filter(pk=goal.pk).update(
                current_amount=models.F('current_amount') + amount
            )
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
    if request.method == 'POST' or request.headers.get('HX-Request'):
        goal.delete()
    return redirect('planning_web:list')
