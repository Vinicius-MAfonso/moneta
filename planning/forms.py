from decimal import Decimal

from django import forms

from moneta.common import TransactionType
from transactions.models import Category
from wallets.models import Account


class BudgetForm(forms.Form):
    category = forms.ModelChoiceField(
        queryset=Category.objects.none(),
        required=True,
        label='Categoria',
        error_messages={'invalid_choice': 'Categoria inválida ou não encontrada.'},
    )
    amount = forms.DecimalField(
        max_digits=20,
        decimal_places=2,
        min_value=Decimal('0.01'),
        required=True,
        localize=True,
        label='Valor',
    )
    is_recurring = forms.BooleanField(required=False, label='Recorrente mensal')
    start_date = forms.DateField(required=False, label='Data de Início')
    end_date = forms.DateField(required=False, label='Data de Término')

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['category'].queryset = Category.objects.filter(
                user=self.user,
                is_system=False,
                type=TransactionType.EXPENSE,
            )

    def clean(self):
        cleaned_data = super().clean()
        is_recurring = cleaned_data.get('is_recurring', False)
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        # If caller omitted both is_recurring and end_date, default to recurring monthly
        if 'is_recurring' not in self.data and not end_date:
            is_recurring = True
            cleaned_data['is_recurring'] = True

        if not is_recurring:
            if not end_date:
                self.add_error('end_date', 'A data de término é obrigatória para orçamentos pontuais.')
            elif start_date and start_date > end_date:
                self.add_error('end_date', 'A data de término deve ser posterior ou igual à data de início.')

        return cleaned_data


class GoalForm(forms.Form):
    name = forms.CharField(max_length=100, required=True, label='Nome')
    account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        required=False,
        label='Conta',
        error_messages={'invalid_choice': 'Conta inválida para este usuário.'},
    )
    target_amount = forms.DecimalField(
        max_digits=20,
        decimal_places=2,
        min_value=Decimal('0.01'),
        required=True,
        localize=True,
        label='Valor Meta',
    )
    current_amount = forms.DecimalField(
        max_digits=20,
        decimal_places=2,
        min_value=Decimal('0.00'),
        required=False,
        localize=True,
        label='Valor Inicial',
    )
    start_date = forms.DateField(required=True, label='Data de Início')
    end_date = forms.DateField(required=True, label='Data de Término')

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['account'].queryset = Account.objects.filter(
                user=self.user,
                active=True,
            ).exclude(type=Account.Types.CREDIT_CARD)

    def clean_current_amount(self):
        val = self.cleaned_data.get('current_amount')
        return val if val is not None else Decimal('0.00')

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if start_date and end_date and start_date > end_date:
            self.add_error('end_date', 'A data de término deve ser posterior ou igual à data de início.')
        return cleaned_data


class GoalDepositForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=20,
        decimal_places=2,
        min_value=Decimal('0.01'),
        required=True,
        localize=True,
        label='Valor do Depósito',
    )

