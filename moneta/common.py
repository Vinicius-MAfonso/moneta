import json
from datetime import date

from dateutil.relativedelta import relativedelta
from django.core.validators import RegexValidator
from django.db import models
from django.http import HttpResponse
from django.utils import timezone

HEX_COLOR_VALIDATOR = RegexValidator(
    regex=r'^#[0-9A-Fa-f]{6}$',
    message='Insira uma cor hexadecimal válida no formato #RRGGBB.',
)


class TransactionType(models.TextChoices):
    INCOME = 'receita', 'Receita'
    EXPENSE = 'despesa', 'Despesa'
    TRANSFER = 'transferência', 'Transferência'


RECURRING_TRANSACTION_TYPE_CHOICES = [
    choice for choice in TransactionType.choices if choice[0] != TransactionType.TRANSFER
]


MONTH_NAMES_PT = [
    'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
]


def get_month_context(month_str=None):
    today = timezone.localdate()
    if not month_str:
        year = today.year
        month_num = today.month
    else:
        try:
            parts = month_str.split('-')
            year = int(parts[0])
            month_num = int(parts[1])
        except (ValueError, TypeError, IndexError):
            year = today.year
            month_num = today.month

    month_num = max(1, min(12, month_num))

    start_date = date(year, month_num, 1)
    end_date = start_date + relativedelta(day=31)
    prev_month = (start_date - relativedelta(months=1)).strftime('%Y-%m')
    next_month = (start_date + relativedelta(months=1)).strftime('%Y-%m')

    month_label = f"{MONTH_NAMES_PT[month_num - 1]} {year}"
    current_month_str = start_date.strftime('%Y-%m')

    return {
        'current_month_str': current_month_str,
        'month_label': month_label,
        'prev_month': prev_month,
        'next_month': next_month,
        'start_date': start_date,
        'end_date': end_date,
        'year': year,
        'month_num': month_num,
    }


FIELD_LABELS_PT = {
    'amount': 'Valor',
    'target_amount': 'Valor Meta',
    'current_amount': 'Valor Inicial',
    'new_balance': 'Novo Saldo',
    'description': 'Descrição',
    'name': 'Nome',
    'date': 'Data',
    'start_date': 'Data de Início',
    'end_date': 'Data de Término',
    'account': 'Conta',
    'category': 'Categoria',
}


def format_form_errors(form):
    """
    Retorna a primeira mensagem de erro limpa e amigável para exibição em toasts,
    removendo a sintaxe de asteriscos e nomes técnicos de campos do Django.
    """
    if not form or not form.errors:
        return "Preencha todos os campos obrigatórios corretamente."

    for field, errors in form.errors.items():
        if errors:
            err = str(errors[0]).replace('0.01', '0,01')
            if field in FIELD_LABELS_PT:
                return f"{FIELD_LABELS_PT[field]}: {err}"
            if field != '__all__':
                field_obj = form.fields.get(field) if hasattr(form, 'fields') else None
                field_label = field_obj.label if field_obj and field_obj.label else field
                return f"{field_label}: {err}" if field_label else err
            return err

    return "Verifique os dados informados no formulário."


def format_exception_message(exc):
    """Extrai mensagem amigável de ValidationError ou ValueError."""
    if hasattr(exc, 'message_dict'):
        return "; ".join(
            f"{FIELD_LABELS_PT.get(k, k)}: {', '.join(v)}" if k != '__all__' else ", ".join(v)
            for k, v in exc.message_dict.items()
        )
    if hasattr(exc, 'messages'):
        return "; ".join(exc.messages)
    return str(exc)


def hx_redirect(url):
    """Retorna HTTP 204 com header HX-Redirect para navegação via HTMX."""
    response = HttpResponse(status=204)
    response['HX-Redirect'] = url
    return response


def hx_toast(message, toast_type='error'):
    """Retorna HTTP 204 com header HX-Trigger para disparar um Toast no Alpine.js."""
    response = HttpResponse(status=204)
    response['HX-Trigger'] = json.dumps({'show-toast': {'message': message, 'type': toast_type}})
    return response