from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags

from wallets.models import Account

User = get_user_model()


class UserLoginForm(AuthenticationForm):
    error_messages = {
        'invalid_login': 'Usuário ou senha incorretos.',
        'inactive': 'Sua conta ainda está em análise pelo administrador. Aguarde a aprovação.',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_pending_approval = False

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username is not None and password:
            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is None:
                user_obj = User.objects.filter(username=username).first()
                if user_obj and user_obj.check_password(password) and not user_obj.is_active:
                    self.is_pending_approval = True
                    raise ValidationError(self.error_messages['inactive'], code='inactive')
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class UserRegistrationForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=False, label='Nome')
    last_name = forms.CharField(max_length=150, required=False, label='Sobrenome')
    email = forms.EmailField(required=True, label='E-mail')
    password = forms.CharField(widget=forms.PasswordInput, required=True, label='Senha')
    password_confirm = forms.CharField(widget=forms.PasswordInput, required=True, label='Confirmar Senha')

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']

    def clean_username(self):
        username = strip_tags(self.cleaned_data.get('username') or '').strip()
        if not username:
            raise ValidationError('O nome de usuário é obrigatório.')
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError('Nome de usuário já em uso.')
        return username

    def clean_first_name(self):
        return strip_tags(self.cleaned_data.get('first_name') or '').strip()

    def clean_last_name(self):
        return strip_tags(self.cleaned_data.get('last_name') or '').strip()

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        if password and password_confirm and password != password_confirm:
            raise ValidationError('As senhas não coincidem.')

        if password:
            temp_user = User(
                username=cleaned_data.get('username') or '',
                first_name=cleaned_data.get('first_name') or '',
                last_name=cleaned_data.get('last_name') or '',
                email=cleaned_data.get('email') or '',
            )
            validate_password(password, user=temp_user)

        return cleaned_data

    def save(self, commit=True):
        return User.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password'],
            first_name=self.cleaned_data.get('first_name', ''),
            last_name=self.cleaned_data.get('last_name', ''),
            is_active=False,
        )


class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=False, label='Nome')
    last_name = forms.CharField(max_length=150, required=False, label='Sobrenome')
    email = forms.EmailField(required=False, label='E-mail')

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

    def clean_first_name(self):
        return strip_tags(self.cleaned_data.get('first_name') or '').strip()

    def clean_last_name(self):
        return strip_tags(self.cleaned_data.get('last_name') or '').strip()


class ImportReviewForm(forms.Form):
    account_id = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        required=True,
        label='Conta de destino',
        error_messages={'required': 'Selecione uma conta de destino.'},
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['account_id'].queryset = Account.objects.filter(
                user=self.user,
                type__in=[Account.Types.CHECKING, Account.Types.OTHER],
                active=True,
            )

