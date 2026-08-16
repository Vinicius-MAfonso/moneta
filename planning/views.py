from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from transactions.models import Category

from .models import Budget, Goal


@login_required(login_url='users_web:login')
def planning_list_view(request):
    from planning.services import get_budgets_with_progress
    
    raw_goals = Goal.objects.filter(user=request.user)

    goals = []
    for goal in raw_goals:
        pct = (goal.current_amount / goal.target_amount * 100) if goal.target_amount > 0 else 0
        goal.percentage = round(pct, 1)
        goal.bounded_pct = min(100, pct)
        goal.bounded_pct_str = str(round(goal.bounded_pct, 2))
        goals.append(goal)

    budgets = get_budgets_with_progress(request.user)

    context = {
        'budgets': budgets,
        'goals': goals,
    }
    return render(request, 'planning/index.html', context)


@login_required(login_url='users_web:login')
def budget_create_view(request):
    categories = Category.objects.filter(user=request.user, is_system=False)

    if request.method == 'POST':
        try:
            category_id = request.POST.get('category')
            amount = Decimal(request.POST.get('amount') or '0')
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date') or None

            from planning.services import create_budget
            create_budget(
                user=request.user,
                category_id=category_id,
                amount=amount,
                start_date=start_date,
                end_date=end_date,
            )
            if request.headers.get('HX-Request'):
                from django.contrib import messages
                messages.success(request, "Orçamento criado com sucesso!")
                from django.http import HttpResponse
                response = HttpResponse(status=204)
                response['HX-Redirect'] = reverse('planning_web:list')
                return response
            return redirect('planning_web:list')
        except Exception as e:
            if request.headers.get('HX-Request'):
                import json

                from django.http import HttpResponse
                response = HttpResponse(status=204)
                response['HX-Trigger'] = json.dumps({'show-toast': {'message': f'Erro: {e!s}', 'type': 'error'}})
                return response
            from django.contrib import messages
            messages.error(request, f"Erro: {e!s}")
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
        from planning.services import delete_budget
        delete_budget(budget)
        from django.contrib import messages
        messages.success(request, "Orçamento excluído com sucesso!")
        if request.headers.get('HX-Request'):
            from django.http import HttpResponse
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
            from wallets.models import Account
            account = Account.objects.get(id=account_id, user=request.user) if account_id else None

            from planning.services import create_goal
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
                from django.contrib import messages
                messages.success(request, "Objetivo criado com sucesso!")
                from django.http import HttpResponse
                response = HttpResponse(status=204)
                response['HX-Redirect'] = reverse('planning_web:list')
                return response
            return redirect('planning_web:list')
        except Exception as e:
            if request.headers.get('HX-Request'):
                import json

                from django.http import HttpResponse
                response = HttpResponse(status=204)
                response['HX-Trigger'] = json.dumps({'show-toast': {'message': f'Erro: {e!s}', 'type': 'error'}})
                return response
            from django.contrib import messages
            messages.error(request, f"Erro: {e!s}")
            return redirect('planning_web:list')

    from wallets.models import Account
    accounts = Account.objects.filter(user=request.user).exclude(type=Account.Types.CREDIT_CARD)
    return render(request, 'planning/partials/goal_form.html', {'accounts': accounts})


@login_required(login_url='users_web:login')
def goal_deposit_view(request, pk):
    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    if request.method == 'POST':
        try:
            amount = Decimal(request.POST.get('amount') or '0')
            if amount > 0:
                from planning.services import deposit_to_goal
                deposit_to_goal(goal, amount)
            if request.headers.get('HX-Request'):
                from django.contrib import messages
                messages.success(request, "Depósito realizado!")
                from django.http import HttpResponse
                response = HttpResponse(status=204)
                response['HX-Redirect'] = reverse('planning_web:list')
                return response
            return redirect('planning_web:list')
        except Exception as e:
            if request.headers.get('HX-Request'):
                import json

                from django.http import HttpResponse
                response = HttpResponse(status=204)
                response['HX-Trigger'] = json.dumps({'show-toast': {'message': f'Erro: {e!s}', 'type': 'error'}})
                return response
            from django.contrib import messages
            messages.error(request, f"Erro: {e!s}")
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
        from planning.services import delete_goal
        delete_goal(goal)
        from django.contrib import messages
        messages.success(request, "Objetivo excluído com sucesso!")
        if request.headers.get('HX-Request'):
            from django.http import HttpResponse
            response = HttpResponse(status=204)
            response['HX-Redirect'] = reverse('planning_web:list')
            return response
        return redirect('planning_web:list')
