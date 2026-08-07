from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import get_user_model, authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.files.storage import FileSystemStorage
from django.conf import settings

from transactions.models import Category
from moneta.common import TransactionType

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
            )
            # Create default categories for new user
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

            login(request, user)
            messages.success(request, 'Conta criada com sucesso! Bem-vindo ao Moneta.')
            return redirect('dashboard')

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

        # Profile photo file upload handling
        if 'profile_photo' in request.FILES:
            photo_file = request.FILES['profile_photo']
            fs = FileSystemStorage(location=settings.MEDIA_ROOT / 'profile_photos', base_url='/media/profile_photos/')
            filename = fs.save(f"user_{user.id}_{photo_file.name}", photo_file)
            user.photo_url = fs.url(filename)
        elif request.POST.get('photo_url'):
            user.photo_url = request.POST.get('photo_url')

        user.save()
        messages.success(request, 'Perfil e preferências atualizados com sucesso!')
        return redirect('users_web:settings')

    return render(request, 'users/settings.html')
