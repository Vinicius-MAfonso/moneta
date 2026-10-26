import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from moneta.common import (
    TransactionType,
    format_exception_message,
    format_form_errors,
    hx_redirect,
    hx_toast,
)
from transactions.models import Category
from wallets.models import Account

from .forms import BudgetForm, GoalDepositForm, GoalForm
from .models import Budget, Goal
from .services import (
    create_budget,
    create_goal,
    delete_budget,
    delete_goal,
    deposit_to_goal,
    get_budgets_with_progress,
    get_goals_with_progress,
)

logger = logging.getLogger(__name__)


@login_required
def planning_list_view(request):
    context = {
        'budgets': get_budgets_with_progress(request.user),
        'goals': get_goals_with_progress(request.user),
    }
    return render(request, 'planning/index.html', context)


@login_required
def budget_create_view(request):
    categories = Category.objects.filter(user=request.user, is_system=False, type=TransactionType.EXPENSE)

    if request.method == 'POST':
        form = BudgetForm(request.POST, user=request.user)
        if form.is_valid():
            cd = form.cleaned_data
            try:
                create_budget(
                    user=request.user,
                    category_id=cd['category'].id,
                    amount=cd['amount'],
                    is_recurring=cd['is_recurring'],
                    start_date=cd.get('start_date'),
                    end_date=cd.get('end_date'),
                )
                messages.success(request, "Orçamento criado com sucesso!")
                if request.headers.get('HX-Request'):
                    return hx_redirect(reverse('planning_web:list'))
                return redirect('planning_web:list')
            except (ValidationError, ValueError) as e:
                msg = format_exception_message(e)
                if request.headers.get('HX-Request'):
                    return hx_toast(msg)
                messages.error(request, msg)
                return redirect('planning_web:list')
            except Exception:
                logger.exception("Erro inesperado ao criar orçamento: ")
                msg = "Erro inesperado ao criar orçamento."
                if request.headers.get('HX-Request'):
                    return hx_toast(msg)
                messages.error(request, msg)
                return redirect('planning_web:list')
        else:
            msg = format_form_errors(form)
            if request.headers.get('HX-Request'):
                return hx_toast(msg)
            messages.error(request, msg)
            return redirect('planning_web:list')

    return render(request, 'planning/partials/budget_form.html', {'categories': categories})


@login_required
def budget_confirm_delete_view(request, pk):
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    context = {
        'title': 'Excluir Orçamento',
        'message': f"Tem certeza que deseja excluir o orçamento para a categoria '{budget.category.name}'?",
        'action_url': reverse('planning_web:budget_delete', args=[budget.id]),
    }
    return render(request, 'partials/confirm_modal.html', context)


@login_required
@require_http_methods(["POST", "DELETE"])
def budget_delete_view(request, pk):
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    delete_budget(budget)
    messages.success(request, "Orçamento excluído com sucesso!")
    if request.headers.get('HX-Request'):
        return hx_redirect(reverse('planning_web:list'))
    return redirect('planning_web:list')


@login_required
def goal_create_view(request):
    if request.method == 'POST':
        form = GoalForm(request.POST, user=request.user)
        if form.is_valid():
            cd = form.cleaned_data
            try:
                create_goal(
                    user=request.user,
                    account=cd.get('account'),
                    name=cd['name'],
                    target_amount=cd['target_amount'],
                    current_amount=cd['current_amount'],
                    start_date=cd['start_date'],
                    end_date=cd['end_date'],
                )
                messages.success(request, "Objetivo criado com sucesso!")
                if request.headers.get('HX-Request'):
                    return hx_redirect(reverse('planning_web:list'))
                return redirect('planning_web:list')
            except (ValidationError, ValueError) as e:
                msg = format_exception_message(e)
                if request.headers.get('HX-Request'):
                    return hx_toast(msg)
                messages.error(request, msg)
                return redirect('planning_web:list')
            except Exception:
                logger.exception("Erro inesperado ao criar objetivo: ")
                msg = "Erro inesperado ao criar objetivo."
                if request.headers.get('HX-Request'):
                    return hx_toast(msg)
                messages.error(request, msg)
                return redirect('planning_web:list')
        else:
            msg = format_form_errors(form)
            if request.headers.get('HX-Request'):
                return hx_toast(msg)
            messages.error(request, msg)
            return redirect('planning_web:list')

    accounts = (
        Account.objects.filter(user=request.user, active=True)
        .exclude(type=Account.Types.CREDIT_CARD)
        .prefetch_related('goals')
    )
    return render(request, 'planning/partials/goal_form.html', {'accounts': accounts})


@login_required
def goal_deposit_view(request, pk):
    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    if request.method == 'POST':
        form = GoalDepositForm(request.POST)
        if form.is_valid():
            try:
                deposit_to_goal(goal, form.cleaned_data['amount'])
                messages.success(request, "Depósito realizado com sucesso!")
                if request.headers.get('HX-Request'):
                    return hx_redirect(reverse('planning_web:list'))
                return redirect('planning_web:list')
            except (ValidationError, ValueError) as e:
                msg = format_exception_message(e)
                if request.headers.get('HX-Request'):
                    return hx_toast(msg)
                messages.error(request, msg)
                return redirect('planning_web:list')
            except Exception:
                logger.exception("Erro inesperado ao depositar no objetivo: ")
                msg = "Erro inesperado ao realizar depósito."
                if request.headers.get('HX-Request'):
                    return hx_toast(msg)
                messages.error(request, msg)
                return redirect('planning_web:list')
        else:
            msg = format_form_errors(form)
            if request.headers.get('HX-Request'):
                return hx_toast(msg)
            messages.error(request, msg)
            return redirect('planning_web:list')

    return render(request, 'planning/partials/goal_deposit_form.html', {'goal': goal})


@login_required
def goal_confirm_delete_view(request, pk):
    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    context = {
        'title': 'Excluir Objetivo',
        'message': f"Tem certeza que deseja excluir o objetivo '{goal.name}'?",
        'action_url': reverse('planning_web:goal_delete', args=[goal.id]),
    }
    return render(request, 'partials/confirm_modal.html', context)


@login_required
@require_http_methods(["POST", "DELETE"])
def goal_delete_view(request, pk):
    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    delete_goal(goal)
    messages.success(request, "Objetivo excluído com sucesso!")
    if request.headers.get('HX-Request'):
        return hx_redirect(reverse('planning_web:list'))
    return redirect('planning_web:list')


