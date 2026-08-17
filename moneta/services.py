from django.db.models import Sum


def get_category_breakdown(base_tx_qs, tx_type, start_date, end_date):
    qs = base_tx_qs.filter(
        category__type=tx_type,
        date__range=(start_date, end_date),
    ).values('category__name', 'category__color').annotate(total=Sum('amount')).order_by('-total')
    
    total_amount = sum(item['total'] for item in qs)
    
    return [
        {
            'name': item['category__name'],
            'color': item['category__color'],
            'total': item['total'],
            'percentage': round((item['total'] / total_amount * 100), 1) if total_amount > 0 else 0,
        }
        for item in qs
    ]


def get_report_data(user, start_date, end_date):
    import datetime
    from decimal import Decimal

    from moneta.common import TransactionType
    from transactions.models import Transaction
    
    transactions = Transaction.objects.filter(
        user=user,
        date__gte=start_date,
        date__lte=end_date,
    ).select_related('category', 'account')

    completed_or_cc_txs = transactions.exclude(category__type=TransactionType.TRANSFER)

    total_income = completed_or_cc_txs.filter(category__type=TransactionType.INCOME).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_expense = completed_or_cc_txs.filter(category__type=TransactionType.EXPENSE).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    net_savings = total_income - total_expense

    expenses_by_category = get_category_breakdown(completed_or_cc_txs, TransactionType.EXPENSE, start_date, end_date)

    delta_days = (end_date - start_date).days
    
    from django.db.models.functions import TruncDay, TruncMonth

    timeline_dict = {}

    if delta_days <= 60:
        daily_stats = completed_or_cc_txs.annotate(
            period=TruncDay('date')
        ).values('period', 'category__type').annotate(
            total=Sum('amount')
        ).order_by('period')
        
        for stat in daily_stats:
            p_key = stat['period'].strftime('%Y-%m-%d')
            if p_key not in timeline_dict:
                timeline_dict[p_key] = {'income': Decimal('0.00'), 'expense': Decimal('0.00')}
            if stat['category__type'] == TransactionType.INCOME:
                timeline_dict[p_key]['income'] += stat['total']
            elif stat['category__type'] == TransactionType.EXPENSE:
                timeline_dict[p_key]['expense'] += stat['total']
                
        timeline_labels = []
        timeline_incomes = []
        timeline_expenses = []
        
        current = start_date
        while current <= end_date:
            p_key = current.strftime('%Y-%m-%d')
            timeline_labels.append(current.strftime('%d/%m'))
            timeline_incomes.append(float(timeline_dict.get(p_key, {}).get('income', 0)))
            timeline_expenses.append(float(timeline_dict.get(p_key, {}).get('expense', 0)))
            current += datetime.timedelta(days=1)
            
    else:
        monthly_stats = completed_or_cc_txs.annotate(
            period=TruncMonth('date')
        ).values('period', 'category__type').annotate(
            total=Sum('amount')
        ).order_by('period')
        
        for stat in monthly_stats:
            p_key = stat['period'].strftime('%Y-%m-01')
            label = stat['period'].strftime('%m/%Y')
            if p_key not in timeline_dict:
                timeline_dict[p_key] = {'income': Decimal('0.00'), 'expense': Decimal('0.00'), 'label': label}
            if stat['category__type'] == TransactionType.INCOME:
                timeline_dict[p_key]['income'] += stat['total']
            elif stat['category__type'] == TransactionType.EXPENSE:
                timeline_dict[p_key]['expense'] += stat['total']
                
        timeline_labels = []
        timeline_incomes = []
        timeline_expenses = []
        
        for p_key in sorted(timeline_dict.keys()):
            timeline_labels.append(timeline_dict[p_key]['label'])
            timeline_incomes.append(float(timeline_dict[p_key]['income']))
            timeline_expenses.append(float(timeline_dict[p_key]['expense']))

    top_transactions = completed_or_cc_txs.filter(category__type=TransactionType.EXPENSE).order_by('-amount')[:10]

    return {
        'total_income': total_income,
        'total_expense': total_expense,
        'net_savings': net_savings,
        'expenses_by_category': expenses_by_category,
        'timeline_labels': timeline_labels,
        'timeline_incomes': timeline_incomes,
        'timeline_expenses': timeline_expenses,
        'top_transactions': top_transactions,
        'transactions_qs': transactions.order_by('-date', '-created_at'),
    }


def generate_csv_export(transactions):
    import csv

    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="relatorio_transacoes.csv"'

    writer = csv.writer(response)
    writer.writerow(['Data', 'Descrição', 'Categoria', 'Tipo', 'Conta', 'Status', 'Valor'])

    for tx in transactions:
        writer.writerow([
            tx.date.strftime('%d/%m/%Y'),
            tx.description,
            tx.category.name,
            tx.category.get_type_display(),
            tx.account.name,
            tx.get_status_display(),
            f"{tx.amount:.2f}".replace('.', ',')
        ])

    return response
