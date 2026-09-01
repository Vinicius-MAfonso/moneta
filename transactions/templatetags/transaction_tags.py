from django import template

register = template.Library()


@register.filter(name='amount_sign')
def amount_sign(tx_type):
    """Returns '+' for income/receita, '-' for expense/despesa, or empty string."""
    if not tx_type:
        return ''
    normalized = str(tx_type).strip().lower()
    if normalized in ('receita', 'income'):
        return '+'
    if normalized in ('despesa', 'expense'):
        return '-'
    return ''


@register.filter(name='tx_color_class')
def tx_color_class(tx_type):
    """Returns Tailwind color class based on transaction or category type."""
    if not tx_type:
        return 'text-slate-900'
    normalized = str(tx_type).strip().lower()
    if normalized in ('receita', 'income'):
        return 'text-emerald-600'
    if normalized in ('despesa', 'expense'):
        return 'text-rose-600'
    return 'text-indigo-600'


@register.filter(name='hex_alpha')
def hex_alpha(color, opacity='20'):
    """Appends an opacity hex suffix to a 6-digit hex color (#RRGGBB -> #RRGGBB20)."""
    if not color:
        return color
    color_str = str(color).strip()
    if color_str.startswith('#') and len(color_str) == 7:
        return f"{color_str}{opacity}"
    return color_str

