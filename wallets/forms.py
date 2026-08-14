from django import forms

from .models import Account


class AccountForm(forms.ModelForm):
    balance = forms.DecimalField(max_digits=20, decimal_places=2, localize=True, required=False)
    limit = forms.DecimalField(max_digits=20, decimal_places=2, min_value=0, required=False, localize=True)
    closing_day = forms.IntegerField(min_value=1, max_value=31, required=False)
    due_day = forms.IntegerField(min_value=1, max_value=31, required=False)

    class Meta:
        model = Account
        fields = ['name', 'type', 'institution', 'balance', 'color', 'icon']

    def clean(self):
        cleaned_data = super().clean()
        account_type = cleaned_data.get('type')

        if account_type == Account.Types.CREDIT_CARD:
            from decimal import Decimal
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
