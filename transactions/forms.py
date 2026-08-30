from decimal import Decimal

from django import forms

from .models import Category, Tag, Transaction


class TransactionForm(forms.Form):
    account = forms.UUIDField(required=True)
    category = forms.UUIDField(required=True)
    description = forms.CharField(max_length=255, required=False)
    amount = forms.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal('0.01'), required=True, localize=True)
    date = forms.DateField(required=True)
    status = forms.ChoiceField(choices=Transaction.Statuses.choices, required=False, initial=Transaction.Statuses.COMPLETED)
    tags = forms.ModelMultipleChoiceField(queryset=Tag.objects.none(), required=False)

    installments = forms.IntegerField(min_value=1, required=False, initial=1)

    is_recurring = forms.BooleanField(required=False)
    frequency = forms.ChoiceField(choices=[('daily', 'Diária'), ('weekly', 'Semanal'), ('monthly', 'Mensal'), ('yearly', 'Anual')], required=False)
    recurring_end_date = forms.DateField(required=False)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['tags'].queryset = Tag.objects.filter(user=self.user)

    def clean_description(self):
        desc = self.cleaned_data.get('description')
        return desc or 'Nova transação'

class TransferForm(forms.Form):
    out_account = forms.UUIDField(required=True)
    in_account = forms.UUIDField(required=True)
    description = forms.CharField(max_length=255, required=False)
    amount = forms.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal('0.01'), required=True)
    date = forms.DateField(required=True)
    tags = forms.ModelMultipleChoiceField(queryset=Tag.objects.none(), required=False)

    is_recurring = forms.BooleanField(required=False)
    frequency = forms.ChoiceField(choices=[('daily', 'Diária'), ('weekly', 'Semanal'), ('monthly', 'Mensal'), ('yearly', 'Anual')], required=False)
    recurring_end_date = forms.DateField(required=False)
    status = forms.ChoiceField(choices=Transaction.Statuses.choices, required=False, initial=Transaction.Statuses.COMPLETED)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['tags'].queryset = Tag.objects.filter(user=self.user)

    def clean_description(self):
        desc = self.cleaned_data.get('description')
        return desc or 'Transferência entre contas'

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('out_account') == cleaned_data.get('in_account'):
            raise forms.ValidationError("As contas de origem e destino devem ser diferentes.")
        return cleaned_data

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'type', 'color', 'icon']

class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ['name', 'color']
