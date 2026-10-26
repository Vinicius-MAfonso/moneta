from decimal import Decimal

from django import forms
from django.utils.html import strip_tags

from .models import Account


class AccountForm(forms.ModelForm):
    balance = forms.DecimalField(max_digits=20, decimal_places=2, localize=True, required=False)
    limit = forms.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal('0.00'), required=False, localize=True)
    closing_day = forms.IntegerField(min_value=1, max_value=31, required=False)
    due_day = forms.IntegerField(min_value=1, max_value=31, required=False)

    class Meta:
        model = Account
        fields = ['name', 'type', 'institution', 'balance', 'color', 'icon']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.account_id = kwargs.pop('account_id', None)
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = strip_tags(self.cleaned_data.get('name') or '').strip()
        if not name:
            raise forms.ValidationError('O nome da conta é obrigatório.')
        if self.user:
            qs = Account.objects.filter(user=self.user, name__iexact=name)
            exclude_id = self.account_id or self.instance.pk
            if exclude_id:
                qs = qs.exclude(pk=exclude_id)
            if qs.exists():
                raise forms.ValidationError('Você já possui uma conta com este nome.')
        return name

    def clean_institution(self):
        inst = self.cleaned_data.get('institution')
        if inst:
            return strip_tags(inst).strip()
        return inst

    def clean(self):
        cleaned_data = super().clean()
        account_type = cleaned_data.get('type')

        if account_type == Account.Types.CREDIT_CARD:
            cleaned_data['balance'] = Decimal('0.00')
            if cleaned_data.get('limit') is None:
                self.add_error('limit', 'O limite é obrigatório para contas de cartão de crédito.')
            if cleaned_data.get('closing_day') is None:
                self.add_error('closing_day', 'O dia de fechamento é obrigatório para contas de cartão de crédito.')
            if cleaned_data.get('due_day') is None:
                self.add_error('due_day', 'O dia de vencimento é obrigatório para contas de cartão de crédito.')
        else:
            if cleaned_data.get('balance') is None:
                self.add_error('balance', 'O saldo inicial é obrigatório.')

        return cleaned_data


class BalanceAdjustmentForm(forms.Form):
    new_balance = forms.DecimalField(
        max_digits=20,
        decimal_places=2,
        localize=True,
        required=True,
        label='Novo Saldo',
    )
    adjustment_type = forms.ChoiceField(
        choices=[('transaction', 'Criar Transação'), ('initial', 'Alterar Saldo Inicial')],
        required=True,
        label='Forma de Reajuste',
    )


class PayBillForm(forms.Form):
    payment_account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        required=True,
        label='Conta de Pagamento',
    )
    payment_amount = forms.DecimalField(
        max_digits=20,
        decimal_places=2,
        min_value=Decimal('0.01'),
        localize=True,
        required=False,
        label='Valor do Pagamento',
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['payment_account'].queryset = Account.objects.filter(
                user=self.user,
            ).exclude(type=Account.Types.CREDIT_CARD)
