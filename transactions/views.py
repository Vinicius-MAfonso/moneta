import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import models
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from moneta.common import (
    TransactionType,
    format_exception_message,
    format_form_errors,
    hx_redirect,
    hx_toast,
)
from wallets.models import Account

from .forms import (
    CategoryForm,
    TagForm,
    TransactionForm,
    TransactionPayForm,
    TransferForm,
)
from .models import Category, Tag, Transaction, Transfer
from .services import (
    create_regular_transaction,
    create_transfer,
    delete_category,
    delete_transaction,
    get_filtered_transactions_context,
    get_transaction_form_context,
    update_transaction,
    update_transfer,
)


def _hx_reload_and_toast(message, toast_type='success'):
    response = HttpResponse(status=204)
    response['HX-Trigger'] = json.dumps({
        'reload-transactions': '',
        'show-toast': {'message': message, 'type': toast_type},
    })
    return response


@login_required
def transaction_list_view(request):
    context = get_filtered_transactions_context(request.user, request.GET)
    if request.headers.get('HX-Request'):
        return render(request, 'transactions/partials/transaction_list.html', context)
    return render(request, 'transactions/index.html', context)


@login_required
def transaction_create_view(request):
    if request.method == 'POST':
        tx_type = request.POST.get('tx_type', 'despesa')

        if tx_type == 'transferencia':
            form = TransferForm(request.POST, user=request.user)
            if form.is_valid():
                cd = form.cleaned_data
                try:
                    create_transfer(
                        user=request.user,
                        out_account_id=cd['out_account'].id if hasattr(cd['out_account'], 'id') else cd['out_account'],
                        in_account_id=cd['in_account'].id if hasattr(cd['in_account'], 'id') else cd['in_account'],
                        description=cd['description'],
                        amount=cd['amount'],
                        tx_date=cd['date'],
                        status=cd.get('status', 'concluída'),
                        tag_ids=[t.id for t in cd['tags']] if cd.get('tags') else None,
                        is_recurring=cd['is_recurring'],
                        frequency=cd['frequency'],
                        recurring_end_date=cd['recurring_end_date'],
                    )
                except ValidationError as e:
                    error_msg = format_exception_message(e)
                    if request.headers.get('HX-Request'):
                        return hx_toast(error_msg)
                    messages.error(request, f"Erro na transferência: {error_msg}")
                    return redirect('transactions_web:list')

                if request.headers.get('HX-Request'):
                    return _hx_reload_and_toast('Transferência criada com sucesso!')
                messages.success(request, "Transferência criada com sucesso!")
                return redirect('transactions_web:list')
            else:
                error_msg = format_form_errors(form)
                if request.headers.get('HX-Request'):
                    return hx_toast(error_msg)
                messages.error(request, f"Erro na transferência: {error_msg}")
                return redirect('transactions_web:list')

        form = TransactionForm(request.POST, user=request.user)
        if form.is_valid():
            cd = form.cleaned_data
            try:
                create_regular_transaction(
                    user=request.user,
                    account_id=cd['account'].id if hasattr(cd['account'], 'id') else cd['account'],
                    category_id=cd['category'].id if hasattr(cd['category'], 'id') else cd['category'],
                    description=cd['description'],
                    amount=cd['amount'],
                    tx_date=cd['date'],
                    status=cd['status'],
                    tag_ids=[t.id for t in cd['tags']] if cd.get('tags') else None,
                    is_recurring=cd['is_recurring'],
                    frequency=cd['frequency'],
                    recurring_end_date=cd['recurring_end_date'],
                    installments=cd.get('installments') or 1,
                )
            except (ValueError, ValidationError) as e:
                error_msg = format_exception_message(e)
                if request.headers.get('HX-Request'):
                    return hx_toast(error_msg)
                messages.error(request, f"Erro ao criar transação: {error_msg}")
                return redirect('transactions_web:list')

            if request.headers.get('HX-Request'):
                return _hx_reload_and_toast('Transação criada com sucesso!')
            messages.success(request, "Transação criada com sucesso!")
            return redirect('transactions_web:list')
        else:
            error_msg = format_form_errors(form)
            if request.headers.get('HX-Request'):
                return hx_toast(error_msg)
            messages.error(request, f"Erro ao criar transação: {error_msg}")

    context = get_transaction_form_context(request.user)
    return render(request, 'transactions/partials/transaction_form.html', context)


@login_required
def transaction_update_view(request, pk):
    transaction = get_object_or_404(
        Transaction.objects.select_related(
            'category',
            'account__credit_card_details',
            'recurring',
            'bill',
            'transfer_out__in_transaction__account',
            'transfer_out__out_transaction__account',
            'transfer_in__in_transaction__account',
            'transfer_in__out_transaction__account',
        ).prefetch_related('tags'),
        pk=pk,
        user=request.user,
    )

    transfer = getattr(transaction, 'transfer_out', None) or getattr(transaction, 'transfer_in', None)
    if not transfer and transaction.category and transaction.category.type == TransactionType.TRANSFER:
        transfer = Transfer.objects.filter(
            models.Q(out_transaction=transaction) | models.Q(in_transaction=transaction)
        ).first()

    if transfer:
        if request.method == 'POST':
            form = TransferForm(request.POST, user=request.user)
            if form.is_valid():
                try:
                    update_transfer(transfer, form.cleaned_data)
                except ValidationError as e:
                    error_msg = format_exception_message(e)
                    if request.headers.get('HX-Request'):
                        return hx_toast(error_msg)
                    messages.error(request, error_msg)
                    return redirect('transactions_web:list')

                if request.headers.get('HX-Request'):
                    return _hx_reload_and_toast('Transferência atualizada com sucesso!')
                messages.success(request, "Transferência atualizada com sucesso!")
                return redirect('transactions_web:list')
            else:
                error_msg = format_form_errors(form)
                if request.headers.get('HX-Request'):
                    return hx_toast(error_msg)
                messages.error(request, error_msg)
                return redirect('transactions_web:list')

        context = get_transaction_form_context(request.user, transaction=transaction, transfer=transfer)
        return render(request, 'transactions/partials/transaction_form.html', context)

    if request.method == 'POST':
        form = TransactionForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                update_transaction(transaction, form.cleaned_data)
            except ValidationError as e:
                error_msg = format_exception_message(e)
                if request.headers.get('HX-Request'):
                    return hx_toast(error_msg)
                messages.error(request, error_msg)
                return redirect('transactions_web:list')

            if request.headers.get('HX-Request'):
                return _hx_reload_and_toast('Transação atualizada com sucesso!')
            messages.success(request, "Transação atualizada com sucesso!")
            return redirect('transactions_web:list')
        else:
            error_msg = format_form_errors(form)
            if request.headers.get('HX-Request'):
                return hx_toast(error_msg)
            messages.error(request, error_msg)
            return redirect('transactions_web:list')

    context = get_transaction_form_context(request.user, transaction=transaction)
    return render(request, 'transactions/partials/transaction_form.html', context)


@login_required
def transaction_confirm_delete_view(request, pk):
    tx = get_object_or_404(Transaction, pk=pk, user=request.user)

    if tx.bill and tx.bill.status == 'paid':
        msg = "Transações de faturas já pagas não podem ser excluídas."
        if request.headers.get('HX-Request'):
            return hx_toast(msg)
        messages.error(request, msg)
        return redirect('transactions_web:list')

    amount_str = f"{tx.amount:.2f}".replace('.', ',')
    context = {
        'title': 'Excluir Transação',
        'message': f"Tem certeza que deseja excluir a transação '{tx.description}' no valor de R$ {amount_str}?",
        'action_url': reverse('transactions_web:delete', args=[tx.id]),
    }

    if tx.recurring:
        context['options'] = [
            {'value': 'single', 'label': 'Excluir somente esta'},
            {'value': 'future', 'label': 'Excluir esta e as futuras'},
            {'value': 'all', 'label': 'Excluir toda a série'},
        ]

    return render(request, 'partials/confirm_modal.html', context)


@login_required
@require_POST
def transaction_delete_view(request, pk):
    delete_mode = request.POST.get('delete_mode', 'single')
    try:
        delete_transaction(user=request.user, transaction_id=pk, delete_mode=delete_mode)
    except ValidationError as e:
        error_msg = format_exception_message(e)
        if request.headers.get('HX-Request'):
            return hx_toast(error_msg)
        messages.error(request, error_msg)
        return redirect('transactions_web:list')

    if request.headers.get('HX-Request'):
        return _hx_reload_and_toast('Transação excluída com sucesso.')

    messages.success(request, "Transação excluída com sucesso.")
    referer = request.META.get('HTTP_REFERER')
    if referer and url_has_allowed_host_and_scheme(
        url=referer,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(referer)
    return redirect('transactions_web:list')


@login_required
def category_list_view(request):
    context = {
        'categories': Category.objects.filter(user=request.user, is_system=False),
        'tags': Tag.objects.filter(user=request.user),
    }
    return render(request, 'categories/index.html', context)


@login_required
def category_create_view(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST, user=request.user)
        if form.is_valid():
            cat = form.save(commit=False)
            cat.user = request.user
            cat.save()
            messages.success(request, "Categoria criada com sucesso!")
            if request.headers.get('HX-Request'):
                return hx_redirect(reverse('transactions_web:category_list'))
            return redirect('transactions_web:category_list')
        else:
            error_msg = format_form_errors(form)
            if request.headers.get('HX-Request'):
                return hx_toast(error_msg)
            messages.error(request, f"Erro ao criar categoria: {error_msg}")
            return redirect('transactions_web:category_list')

    return render(request, 'categories/partials/category_form.html')


@login_required
def category_confirm_delete_view(request, pk):
    cat = get_object_or_404(Category, pk=pk, user=request.user)

    if cat.transactions.exists():
        fallback_categories = Category.objects.filter(user=request.user, type=cat.type, is_system=False).exclude(id=cat.id)
        context = {
            'category': cat,
            'transactions_count': cat.transactions.count(),
            'fallback_categories': fallback_categories,
        }
        return render(request, 'categories/partials/category_delete_with_transactions.html', context)

    context = {
        'title': 'Excluir Categoria',
        'message': f"Tem certeza que deseja excluir a categoria '{cat.name}'?",
        'action_url': reverse('transactions_web:category_delete', args=[cat.id]),
    }
    return render(request, 'partials/confirm_modal.html', context)


@login_required
@require_POST
def category_delete_view(request, pk):
    delete_action = request.POST.get('delete_action', 'delete')
    fallback_category_id = request.POST.get('fallback_category_id')

    try:
        delete_category(
            user=request.user,
            category_id=pk,
            action=delete_action,
            fallback_category_id=fallback_category_id,
        )
    except ValidationError as e:
        error_msg = format_exception_message(e)
        if request.headers.get('HX-Request'):
            return hx_toast(error_msg)
        messages.error(request, error_msg)
        return redirect('transactions_web:category_list')

    messages.success(request, "Categoria excluída com sucesso.")
    if request.headers.get('HX-Request'):
        return hx_redirect(reverse('transactions_web:category_list'))
    return redirect('transactions_web:category_list')


@login_required
def tag_create_view(request):
    if request.method == 'POST':
        form = TagForm(request.POST, user=request.user)
        if form.is_valid():
            tag = form.save(commit=False)
            tag.user = request.user
            tag.save()
            messages.success(request, "Tag criada com sucesso!")
            if request.headers.get('HX-Request'):
                return hx_redirect(reverse('transactions_web:category_list'))
            return redirect('transactions_web:category_list')
        else:
            error_msg = format_form_errors(form)
            if request.headers.get('HX-Request'):
                return hx_toast(error_msg)
            messages.error(request, f"Erro ao criar tag: {error_msg}")
            return redirect('transactions_web:category_list')

    return render(request, 'categories/partials/tag_form.html')


@login_required
def tag_confirm_delete_view(request, pk):
    tag = get_object_or_404(Tag, pk=pk, user=request.user)
    context = {
        'title': 'Excluir Tag',
        'message': f"Tem certeza que deseja excluir a tag '{tag.name}'?",
        'action_url': reverse('transactions_web:tag_delete', args=[tag.id]),
    }
    return render(request, 'partials/confirm_modal.html', context)


@login_required
@require_POST
def tag_delete_view(request, pk):
    tag = get_object_or_404(Tag, pk=pk, user=request.user)
    tag_name = tag.name
    tag.delete()
    messages.success(request, f"Tag '{tag_name}' excluída com sucesso.")
    if request.headers.get('HX-Request'):
        return hx_redirect(reverse('transactions_web:category_list'))
    return redirect('transactions_web:category_list')


@login_required
def transaction_pay_view(request, pk):
    tx = get_object_or_404(Transaction.objects.select_related('category', 'account'), pk=pk, user=request.user)

    if tx.status == Transaction.Statuses.COMPLETED:
        msg = "Esta transação já está efetivada."
        if request.headers.get('HX-Request'):
            return hx_toast(msg)
        messages.error(request, msg)
        return redirect('transactions_web:list')

    accounts = list(Account.objects.filter(user=request.user, active=True))

    if request.method == 'POST':
        form = TransactionPayForm(request.POST, user=request.user)
        if not form.is_valid():
            error_msg = format_form_errors(form)
            if request.headers.get('HX-Request'):
                return hx_toast(error_msg)
            messages.error(request, f"Erro ao efetivar: {error_msg}")
            return redirect('transactions_web:list')

        cd = form.cleaned_data
        validated_data = {
            'account': cd['account'].id,
            'category': str(tx.category.id),
            'description': tx.description,
            'amount': cd['amount'],
            'date': cd['date'],
            'status': Transaction.Statuses.COMPLETED,
            'tags': [t.id for t in tx.tags.all()],
            'is_recurring': tx.recurring is not None,
            'frequency': tx.recurring.frequency if tx.recurring else 'monthly',
            'recurring_end_date': tx.recurring.end_date if tx.recurring else None,
        }

        try:
            update_transaction(tx, validated_data)
            if request.headers.get('HX-Request'):
                return _hx_reload_and_toast('Transação efetivada com sucesso!')
            messages.success(request, "Transação efetivada com sucesso!")
            return redirect('transactions_web:list')
        except (ValueError, ValidationError) as e:
            error_msg = format_exception_message(e)
            if request.headers.get('HX-Request'):
                return hx_toast(error_msg)
            messages.error(request, f"Erro ao efetivar: {error_msg}")
            return redirect('transactions_web:list')

    context = {
        'transaction': tx,
        'accounts': accounts,
    }
    return render(request, 'transactions/partials/pay_modal.html', context)

