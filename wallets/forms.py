from django import forms
from .models import Account

class AccountForm(forms.ModelForm):
    # Additional fields for credit card details
    limit = forms.DecimalField(max_digits=20, decimal_places=2, min_value=0, required=False)
    closing_day = forms.IntegerField(min_value=1, max_value=31, required=False)
    due_day = forms.IntegerField(min_value=1, max_value=31, required=False)

    class Meta:
        model = Account
        fields = ['name', 'type', 'institution', 'balance', 'color']

    def clean(self):
        cleaned_data = super().clean()
        account_type = cleaned_data.get('type')

        if account_type == Account.Types.CREDIT_CARD:
            if cleaned_data.get('limit') is None:
                self.add_error('limit', 'O limite é obrigatório para contas de cartão de crédito.')
            if cleaned_data.get('closing_day') is None:
                self.add_error('closing_day', 'O dia de fechamento é obrigatório para contas de cartão de crédito.')
            if cleaned_data.get('due_day') is None:
                self.add_error('due_day', 'O dia de vencimento é obrigatório para contas de cartão de crédito.')
                
        return cleaned_data
