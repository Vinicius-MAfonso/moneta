import logging

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from moneta.common import format_form_errors

from .forms import (
    ImportReviewForm,
    UserLoginForm,
    UserProfileForm,
    UserRegistrationForm,
)
from .models import Notification
from .services import (
    get_import_review_context,
    parse_statement_file,
    process_import_transactions,
)

logger = logging.getLogger(__name__)


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            next_url = request.GET.get('next')
            redirect_to = 'dashboard'
            if next_url and url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                redirect_to = next_url
            return redirect(redirect_to)
        if form.is_pending_approval:
            messages.warning(request, form.error_messages['inactive'])
        else:
            messages.error(request, form.error_messages['invalid_login'])

    return render(request, 'users/login.html')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Conta criada com sucesso! Aguarde a aprovação do administrador para acessar.')
            return redirect('users_web:login')
        messages.error(request, format_form_errors(form))

    return render(request, 'users/register.html')


def logout_view(request):
    logout(request)
    messages.info(request, 'Você saiu da sua conta.')
    return redirect('users_web:login')


@login_required
def settings_view(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Perfil e preferências atualizados com sucesso!')
        else:
            messages.error(request, format_form_errors(form))
        return redirect('users_web:settings')

    return render(request, 'users/settings.html', {})


@login_required
def import_file_view(request):
    upload_file = request.FILES.get('file')
    if request.method == 'POST' and upload_file:
        try:
            transactions = parse_statement_file(upload_file)
            if not transactions:
                messages.warning(request, 'O arquivo foi lido, mas nenhuma transação válida foi encontrada.')
                return redirect('users_web:settings')

            request.session['import_transactions'] = transactions
            messages.info(request, f'Foram lidas {len(transactions)} transações do extrato. Revise os lançamentos abaixo.')
            return redirect('users_web:import_review')
        except Exception as e:
            messages.error(request, f'Erro ao processar arquivo: {e!s}')
            return redirect('users_web:settings')

    messages.warning(request, 'Nenhum arquivo de extrato (.OFX ou .CSV) foi enviado.')
    return redirect('users_web:settings')


@login_required
def import_review_view(request):
    transactions = request.session.get('import_transactions', [])

    if not transactions:
        messages.warning(request, 'Nenhuma transação na memória. Faça o upload do extrato novamente.')
        return redirect('users_web:settings')

    if request.method == 'POST':
        form = ImportReviewForm(request.POST, user=request.user)
        if not form.is_valid():
            messages.error(request, format_form_errors(form))
            return redirect('users_web:import_review')

        account = form.cleaned_data['account_id']

        try:
            saved_count = process_import_transactions(request.user, account, transactions, request.POST)
        except Exception as e:
            messages.error(request, f"Erro ao importar transações: {e!s}")
            return redirect('users_web:import_review')

        request.session.pop('import_transactions', None)
        messages.success(request, f'{saved_count} transações importadas com sucesso!')
        return redirect('dashboard')

    context = get_import_review_context(request.user, transactions)
    request.session['import_transactions'] = context['transactions']
    return render(request, 'users/import_review.html', context)


@login_required
def notifications_list(request):
    notifications = Notification.objects.filter(user=request.user)[:10]
    unread_notifications_count = Notification.objects.filter(user=request.user, is_read=False).count()
    return render(request, 'users/partials/notification_list.html', {
        'notifications': notifications,
        'unread_notifications_count': unread_notifications_count,
    })


@login_required
@require_POST
def notifications_mark_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)

    if request.headers.get('HX-Request'):
        notifications = Notification.objects.filter(user=request.user)[:10]
        return render(request, 'users/partials/notification_list.html', {
            'notifications': notifications,
            'unread_notifications_count': 0,
        })
    return redirect('dashboard')


@login_required
@require_POST
def notifications_clear(request):
    Notification.objects.filter(user=request.user).delete()

    if request.headers.get('HX-Request'):
        return render(request, 'users/partials/notification_list.html', {
            'notifications': [],
            'unread_notifications_count': 0,
        })
    return redirect('dashboard')
