from decimal import Decimal

from django import forms
from django.db.models import Q

from wallets.models import Account

from .models import Category, Tag, Transaction


class TransactionForm(forms.Form):
    account = forms.ModelChoiceField(queryset=Account.objects.none(), required=True)
    category = forms.ModelChoiceField(queryset=Category.objects.none(), required=True)
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
            self.fields['account'].queryset = Account.objects.filter(user=self.user, active=True)
            self.fields['category'].queryset = Category.objects.filter(Q(user=self.user) | Q(is_system=True))
            self.fields['tags'].queryset = Tag.objects.filter(user=self.user)

    def clean_description(self):
        desc = self.cleaned_data.get('description')
        return desc or 'Nova transação'


class TransferForm(forms.Form):
    out_account = forms.ModelChoiceField(queryset=Account.objects.none(), required=True)
    in_account = forms.ModelChoiceField(queryset=Account.objects.none(), required=True)
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
            self.fields['out_account'].queryset = Account.objects.filter(user=self.user, active=True)
            self.fields['in_account'].queryset = Account.objects.filter(user=self.user, active=True)
            self.fields['tags'].queryset = Tag.objects.filter(user=self.user)

    def clean_description(self):
        desc = self.cleaned_data.get('description')
        return desc or 'Transferência entre contas'

    def clean(self):
        cleaned_data = super().clean()
        out_account = cleaned_data.get('out_account')
        in_account = cleaned_data.get('in_account')
        if out_account and in_account and out_account == in_account:
            raise forms.ValidationError("As contas de origem e destino devem ser diferentes.")
        return cleaned_data


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'type', 'color', 'icon']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if not name:
            raise forms.ValidationError("O nome da categoria é obrigatório.")
        if self.user:
            qs = Category.objects.filter(user=self.user, name__iexact=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Você já possui uma categoria com este nome.")
        return name


class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ['name', 'color']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if not name:
            raise forms.ValidationError("O nome da tag é obrigatório.")
        if self.user:
            qs = Tag.objects.filter(user=self.user, name__iexact=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Você já possui uma tag com este nome.")
        return name

