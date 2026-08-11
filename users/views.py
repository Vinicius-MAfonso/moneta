from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, get_object_or_404
import uuid

from moneta.common import TransactionType
from transactions.models import Category, Transaction
from wallets.models import Account
from ofxparse import OfxParser

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
            next_url = request.GET.get('next') or 'dashboard'
            return redirect(next_url)
        else:
            # Check if user exists but is inactive
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
        username = request.POST.get('username')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        currency = request.POST.get('currency', 'BRL')

        if password != password_confirm:
            messages.error(request, 'As senhas não coincidem.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'Nome de usuário já em uso.')
        else:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                currency=currency,
                is_active=False,  # Requer aprovação do admin
            )
            # Cria as categorias padrão para o novo usuário
            default_categories = [
                ('Alimentação', TransactionType.EXPENSE, '#ef4444'),
                ('Moradia', TransactionType.EXPENSE, '#f59e0b'),
                ('Transporte', TransactionType.EXPENSE, '#3b82f6'),
                ('Lazer', TransactionType.EXPENSE, '#8b5cf6'),
                ('Salário', TransactionType.INCOME, '#10b981'),
                ('Investimentos', TransactionType.INCOME, '#06b6d4'),
                ('Transferência', TransactionType.TRANSFER, '#737373'),
            ]
            for name, cat_type, color in default_categories:
                Category.objects.create(user=user, name=name, type=cat_type, color=color)

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
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.currency = request.POST.get('currency', user.currency)
        user.timezone = request.POST.get('timezone', user.timezone)



        user.save()
        messages.success(request, 'Perfil e preferências atualizados com sucesso!')
        return redirect('users_web:settings')

    return render(request, 'users/settings.html')


@login_required(login_url='users_web:login')
def import_ofx_view(request):
    if request.method == 'POST' and request.FILES.get('ofx_file'):
        ofx_file = request.FILES['ofx_file']
        try:
            ofx = OfxParser.parse(ofx_file)
            transactions = []
            for account in ofx.accounts:
                for tx in account.statement.transactions:
                    transactions.append({
                        'id': str(uuid.uuid4()),
                        'date': tx.date.strftime('%d/%m/%Y'),
                        'date_iso': tx.date.strftime('%Y-%m-%d'),
                        'payee': tx.payee,
                        'amount': str(tx.amount),
                        'type': 'despesa' if tx.amount < 0 else 'receita'
                    })
            
            request.session['ofx_transactions'] = transactions
            messages.info(request, f'Foram lidas {len(transactions)} transações. Revise-as abaixo.')
            return redirect('users_web:import_review')
            
        except Exception as e:
            messages.error(request, f'Erro ao ler arquivo OFX: {str(e)}')
            return redirect('users_web:settings')
            
    return redirect('users_web:settings')


@login_required(login_url='users_web:login')
def import_review_view(request):
    transactions = request.session.get('ofx_transactions', [])
    
    if not transactions:
        messages.warning(request, 'Nenhuma transação na memória. Faça o upload novamente.')
        return redirect('users_web:settings')

    if request.method == 'POST':
        account_id = request.POST.get('account_id')
        if not account_id:
            messages.error(request, 'Selecione uma conta de destino.')
            return redirect('users_web:import_review')
            
        account = get_object_or_404(Account, id=account_id, user=request.user)
        saved_count = 0
        
        for tx in transactions:
            cat_id = request.POST.get(f"category_{tx['id']}")
            if cat_id and cat_id != 'ignore':
                category = get_object_or_404(Category, id=cat_id, user=request.user)
                Transaction.objects.create(
                    user=request.user,
                    account=account,
                    category=category,
                    amount=abs(float(tx['amount'])),
                    date=tx['date_iso'],
                    description=tx['payee'][:255],
                    status=Transaction.Statuses.COMPLETED
                )
                saved_count += 1
                
        # Clear session
        if 'ofx_transactions' in request.session:
            del request.session['ofx_transactions']
            
        messages.success(request, f'{saved_count} transações importadas com sucesso!')
        return redirect('dashboard')

    accounts = Account.objects.filter(user=request.user)
    categories = Category.objects.filter(user=request.user).order_by('type', 'name')
    
    context = {
        'transactions': transactions,
        'accounts': accounts,
        'categories': categories,
    }
    return render(request, 'users/import_review.html', context)
