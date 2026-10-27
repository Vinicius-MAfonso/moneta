import calendar
import json
from collections import defaultdict
from datetime import date
from decimal import Decimal

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


def get_month_calendar_grid(user, start_date, end_date, account=None):
    from django.db.models import Sum

    from transactions.models import Transaction

    qs = Transaction.objects.filter(
        user=user,
        date__range=(start_date, end_date),
    ).exclude(category__type=TransactionType.TRANSFER)

    if account:
        qs = qs.filter(account=account)

    daily_txs = (
        qs.values('date', 'category__type', 'status')
        .annotate(total=Sum('amount'))
    )

    daily_totals = defaultdict(lambda: {
        'income_done': Decimal('0.00'),
        'expense_done': Decimal('0.00'),
        'income_pending': Decimal('0.00'),
        'expense_pending': Decimal('0.00'),
    })

    for item in daily_txs:
        d_str = item['date'].strftime('%Y-%m-%d')
        c_type = item['category__type']
        is_done = (item['status'] == Transaction.Statuses.COMPLETED)

        if c_type == TransactionType.INCOME:
            if is_done:
                daily_totals[d_str]['income_done'] += item['total']
            else:
                daily_totals[d_str]['income_pending'] += item['total']
        elif c_type == TransactionType.EXPENSE:
            if is_done:
                daily_totals[d_str]['expense_done'] += item['total']
            else:
                daily_totals[d_str]['expense_pending'] += item['total']

    cal = calendar.Calendar(firstweekday=6)
    month_days = list(cal.itermonthdays4(start_date.year, start_date.month))

    grid = []
    today_date = timezone.localdate()
    for year, month, day, _ in month_days:
        day_date = date(year, month, day)
        d_str = day_date.strftime('%Y-%m-%d')
        is_current_month = (month == start_date.month)
        totals = daily_totals.get(d_str, {
            'income_done': Decimal('0.00'),
            'expense_done': Decimal('0.00'),
            'income_pending': Decimal('0.00'),
            'expense_pending': Decimal('0.00'),
        })

        has_data = any(v > 0 for v in totals.values())

        grid.append({
            'day': day,
            'date_str': d_str,
            'is_current_month': is_current_month,
            'is_today': (day_date == today_date),
            'income_done': totals['income_done'],
            'expense_done': totals['expense_done'],
            'income_pending': totals['income_pending'],
            'expense_pending': totals['expense_pending'],
            'income': totals['income_done'] + totals['income_pending'],
            'expense': totals['expense_done'] + totals['expense_pending'],
            'has_data': has_data,
        })

    return grid


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