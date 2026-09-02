import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import strip_tags
from django.utils.http import url_has_allowed_host_and_scheme

from transactions.models import Category
from wallets.models import Account

from .models import PushSubscription

logger = logging.getLogger(__name__)
User = get_user_model()


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.GET.get('next')
            redirect_to = 'dashboard'
            if next_url and url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                redirect_to = next_url
            return redirect(redirect_to)
        else:
            user_obj = User.objects.filter(username=username).first()
            if user_obj and user_obj.check_password(password) and not user_obj.is_active:
                messages.warning(request, 'Sua conta ainda está em análise pelo administrador. Aguarde a aprovação.')
            else:
                messages.error(request, 'Usuário ou senha incorretos.')

    return render(request, 'users/login.html')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = strip_tags(request.POST.get('username', '')).strip()
        first_name = strip_tags(request.POST.get('first_name', '')).strip()
        last_name = strip_tags(request.POST.get('last_name', '')).strip()
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')

        if password != password_confirm:
            messages.error(request, 'As senhas não coincidem.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'Nome de usuário já em uso.')
        else:
            try:
                from django.contrib.auth.password_validation import validate_password
                from django.core.exceptions import ValidationError
                validate_password(password)
            except ValidationError as e:
                messages.error(request, ' '.join(e.messages))
                return render(request, 'users/register.html')

            User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_active=False,
            )
            messages.success(request, 'Conta criada com sucesso! Aguarde a aprovação do administrador para acessar.')
            return redirect('users_web:login')

    return render(request, 'users/register.html')


def logout_view(request):
    logout(request)
    messages.info(request, 'Você saiu da sua conta.')
    return redirect('users_web:login')


@login_required(login_url='users_web:login')
def settings_view(request):
    if request.method == 'POST':
        user = request.user
        user.first_name = strip_tags(request.POST.get('first_name', user.first_name)).strip()
        user.last_name = strip_tags(request.POST.get('last_name', user.last_name)).strip()
        user.email = request.POST.get('email', user.email)
        user.save()
        messages.success(request, 'Perfil e preferências atualizados com sucesso!')
        return redirect('users_web:settings')

    context = {
        'vapid_public_key': settings.VAPID_PUBLIC_KEY
    }
    return render(request, 'users/settings.html', context)


@login_required(login_url='users_web:login')
def import_file_view(request):
    upload_file = request.FILES.get('file') or request.FILES.get('ofx_file')
    if request.method == 'POST' and upload_file:
        filename = upload_file.name.lower()
        try:
            from users.services import parse_csv_file, parse_ofx_file

            if filename.endswith('.ofx'):
                transactions = parse_ofx_file(upload_file)
            elif filename.endswith(('.csv', '.txt')):
                transactions = parse_csv_file(upload_file)
            else:
                # Try OFX first; fallback to CSV if it fails
                try:
                    transactions = parse_ofx_file(upload_file)
                except Exception:
                    transactions = parse_csv_file(upload_file)

            if not transactions:
                messages.warning(request, 'O arquivo foi lido, mas nenhuma transação válida foi encontrada.')
                return redirect('users_web:settings')

            request.session['import_transactions'] = transactions
            request.session['ofx_transactions'] = transactions  # Backward compatibility
            messages.info(request, f'Foram lidas {len(transactions)} transações do extrato. Revise os lançamentos abaixo.')
            return redirect('users_web:import_review')

        except Exception as e:
            messages.error(request, f'Erro ao processar arquivo: {e!s}')
            return redirect('users_web:settings')
    else:
        messages.warning(request, 'Nenhum arquivo de extrato (.OFX ou .CSV) foi enviado.')

    return redirect('users_web:settings')


# Alias for backward compatibility
import_ofx_view = import_file_view


@login_required(login_url='users_web:login')
def import_review_view(request):
    transactions = request.session.get('import_transactions') or request.session.get('ofx_transactions', [])

    if not transactions:
        messages.warning(request, 'Nenhuma transação na memória. Faça o upload do extrato novamente.')
        return redirect('users_web:settings')

    if request.method == 'POST':
        account_id = request.POST.get('account_id')
        if not account_id:
            messages.error(request, 'Selecione uma conta de destino.')
            return redirect('users_web:import_review')

        account = get_object_or_404(Account, id=account_id, user=request.user)

        try:
            from users.services import process_import_transactions
            saved_count = process_import_transactions(request.user, account, transactions, request.POST)
        except Exception as e:
            messages.error(request, f"Erro ao importar transações: {e!s}")
            return redirect('users_web:import_review')

        if 'import_transactions' in request.session:
            del request.session['import_transactions']
        if 'ofx_transactions' in request.session:
            del request.session['ofx_transactions']

        messages.success(request, f'{saved_count} transações importadas com sucesso!')
        return redirect('dashboard')

    from users.services import enrich_transactions_with_suggestions_and_duplicates
    transactions = enrich_transactions_with_suggestions_and_duplicates(request.user, transactions)
    # Update session with enriched transactions
    request.session['import_transactions'] = transactions

    # Support Checking and Other accounts (Savings/Investments)
    accounts = Account.objects.filter(
        user=request.user,
        type__in=[Account.Types.CHECKING, Account.Types.OTHER],
        active=True
    ).order_by('name')

    categories = Category.objects.filter(user=request.user, is_system=False).order_by('type', 'name')

    suggestions_count = sum(1 for t in transactions if t.get('suggested_category_id'))
    duplicates_count = sum(1 for t in transactions if t.get('is_duplicate'))

    from transactions.services import get_user_description_habits
    description_habits = get_user_description_habits(request.user)

    context = {
        'transactions': transactions,
        'accounts': accounts,
        'categories': categories,
        'total_count': len(transactions),
        'suggestions_count': suggestions_count,
        'duplicates_count': duplicates_count,
        'description_habits': description_habits,
    }
    return render(request, 'users/import_review.html', context)


@login_required
def save_push_subscription(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            endpoint = data.get('endpoint')
            keys = data.get('keys', {})
            p256dh = keys.get('p256dh')
            auth = keys.get('auth')

            if not endpoint or not p256dh or not auth:
                return JsonResponse({'status': 'error', 'message': 'Invalid subscription payload'}, status=400)

            PushSubscription.objects.update_or_create(
                user=request.user,
                endpoint=endpoint,
                defaults={
                    'p256dh': p256dh,
                    'auth': auth,
                }
            )

            return JsonResponse({'status': 'success', 'message': 'Subscription saved'})
        except Exception:
            logger.exception("Erro ao salvar assinatura push.")
            return JsonResponse({'status': 'error', 'message': 'Falha ao processar assinatura push.'}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)


@login_required
def delete_push_subscription(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            endpoint = data.get('endpoint')
            if endpoint:
                PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
            return JsonResponse({'status': 'success', 'message': 'Subscription deleted'})
        except Exception:
            logger.exception("Erro ao remover assinatura push.")
            return JsonResponse({'status': 'error', 'message': 'Falha ao remover assinatura push.'}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

