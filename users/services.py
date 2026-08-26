import csv
import io
import json
import re
import unicodedata
import uuid
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction as db_transaction
from ofxparse import OfxParser
from pywebpush import WebPushException, webpush

from transactions.models import Category, Transaction
from transactions.services import get_user_description_habits


def _decode_file(uploaded_file):
    """
    Decodifica o arquivo tentando utf-8-sig (BOM), utf-8, latin-1 e cp1252.
    """
    if hasattr(uploaded_file, 'read'):
        content = uploaded_file.read()
        if hasattr(uploaded_file, 'seek'):
            uploaded_file.seek(0)
    elif isinstance(uploaded_file, bytes):
        content = uploaded_file
    else:
        return str(uploaded_file)

    for encoding in ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']:
        try:
            return content.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return content.decode('utf-8', errors='ignore')


def _clean_amount(val_str, is_debit=None):
    """
    Normaliza e converte strings monetárias brasileiras ou internacionais em Decimal.
    Retorna (raw_amount: Decimal com sinal, tx_type: 'despesa' | 'receita').
    """
    if not val_str:
        return Decimal('0.00'), 'despesa'

    s = str(val_str).strip()

    # Identifica sufixos de débito/crédito (ex: "150,00 D" ou "200,00 C")
    trailing_d = False
    trailing_c = False
    if re.search(r'[dD]\s*$', s):
        trailing_d = True
        s = re.sub(r'[dD]\s*$', '', s).strip()
    elif re.search(r'[cC]\s*$', s):
        trailing_c = True
        s = re.sub(r'[cC]\s*$', '', s).strip()

    # Formatos com parênteses negativos ex: "(150.00)"
    is_negative = False
    if s.startswith('(') and s.endswith(')'):
        is_negative = True
        s = s[1:-1].strip()

    if s.startswith('-'):
        is_negative = True
        s = s[1:].strip()
    elif s.startswith('+'):
        s = s[1:].strip()

    # Remove símbolos de moeda (R$, $, etc.)
    s = re.sub(r'[^\d.,]', '', s)
    if not s:
        return Decimal('0.00'), 'despesa'

    # Detecção de separador decimal vs milhar
    if ',' in s and '.' in s:
        last_comma = s.rfind(',')
        last_dot = s.rfind('.')
        if last_comma > last_dot:
            # Padrão brasileiro: 1.234,56
            s = s.replace('.', '').replace(',', '.')
        else:
            # Padrão internacional: 1,234.56
            s = s.replace(',', '')
    elif ',' in s:
        s = s.replace(',', '.')

    try:
        amount_val = Decimal(s).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except Exception:
        amount_val = Decimal('0.00')

    if is_debit is True or trailing_d or is_negative:
        tx_type = 'despesa'
        raw_amount = -abs(amount_val)
    elif is_debit is False or trailing_c:
        tx_type = 'receita'
        raw_amount = abs(amount_val)
    else:
        if amount_val < 0:
            tx_type = 'despesa'
            raw_amount = amount_val
        else:
            tx_type = 'receita'
            raw_amount = amount_val

    return raw_amount, tx_type


def _parse_date(date_str):
    """
    Tenta converter diferentes formatos de data para ('DD/MM/YYYY', 'YYYY-MM-DD').
    """
    if not date_str:
        return None, None

    s = str(date_str).strip().split(' ')[0].split('T')[0]
    formats = [
        '%d/%m/%Y',
        '%Y-%m-%d',
        '%d-%m-%Y',
        '%d/%m/%y',
        '%Y/%m/%d',
        '%d.%m.%Y',
        '%Y.%m.%d',
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt).date()
            return dt.strftime('%d/%m/%Y'), dt.strftime('%Y-%m-%d')
        except ValueError:
            continue
    return None, None


def _normalize_text(text):
    if not text:
        return ''
    nfkd = unicodedata.normalize('NFKD', str(text))
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def parse_csv_file(csv_file):
    """
    Parser semi-inteligente para extratos bancários em CSV.
    Detecta automaticamente delimitadores (, ; \t), cabeçalhos de bancos (Nubank, Inter, Itaú, BB, etc.)
    ou infere as colunas por análise de tipo de dados.
    """
    raw_text = _decode_file(csv_file)
    if not raw_text or not raw_text.strip():
        return []

    lines = [line for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return []

    # Detecta delimitador (, ; ou \t)
    sample = '\n'.join(lines[:10])
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
        delimiter = dialect.delimiter
    except Exception:
        # Fallback por contagem
        first_line = lines[0]
        counts = {',': first_line.count(','), ';': first_line.count(';'), '\t': first_line.count('\t')}
        delimiter = max(counts, key=counts.get) if max(counts.values()) > 0 else ','

    reader = csv.reader(io.StringIO(raw_text), delimiter=delimiter)
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        return []

    DATE_KEYS = {'data', 'date', 'dt', 'dia', 'dt_lancamento', 'data_lancamento', 'dt lancamento', 'data do lancamento'}
    PRIMARY_DESC_KEYS = {'descricao', 'descrição', 'historico', 'histórico', 'memo', 'payee', 'estabelecimento', 'lancamento', 'lançamento', 'detalhes', 'nome', 'titulo', 'título'}
    FALLBACK_DESC_KEYS = {'identificador', 'documento', 'numero_documento'}
    AMOUNT_KEYS = {'valor', 'amount', 'montante', 'total', 'valor (r$)', 'valor_liquido', 'valor r$'}
    DEBIT_KEYS = {'debito', 'débito', 'saida', 'saída', 'debit'}
    CREDIT_KEYS = {'credito', 'crédito', 'entrada', 'credit'}

    header_row_index = -1
    date_col = -1
    desc_col = -1
    amount_col = -1
    debit_col = -1
    credit_col = -1

    # Procura linha de cabeçalho nas primeiras 5 linhas
    for i, row in enumerate(rows[:5]):
        norm_row = [_normalize_text(c) for c in row]
        d_col = next((idx for idx, c in enumerate(norm_row) if any(k == c or c.startswith(k) for k in DATE_KEYS)), -1)
        dsc_col = next((idx for idx, c in enumerate(norm_row) if any(k == c or c.startswith(k) for k in PRIMARY_DESC_KEYS)), -1)
        if dsc_col == -1:
            dsc_col = next((idx for idx, c in enumerate(norm_row) if any(k == c or c.startswith(k) for k in FALLBACK_DESC_KEYS)), -1)

        amt_col = next((idx for idx, c in enumerate(norm_row) if any(k == c or c.startswith(k) for k in AMOUNT_KEYS)), -1)
        deb_col = next((idx for idx, c in enumerate(norm_row) if any(k == c or c.startswith(k) for k in DEBIT_KEYS)), -1)
        cred_col = next((idx for idx, c in enumerate(norm_row) if any(k == c or c.startswith(k) for k in CREDIT_KEYS)), -1)

        if d_col != -1 and (dsc_col != -1 or amt_col != -1 or deb_col != -1):
            header_row_index = i
            date_col = d_col
            desc_col = dsc_col
            amount_col = amt_col
            debit_col = deb_col
            credit_col = cred_col
            break

    # Se não encontrou cabeçalho explícito, tenta inferir pelas colunas dos dados
    data_rows = rows[header_row_index + 1:] if header_row_index != -1 else rows

    if (date_col == -1 or (amount_col == -1 and debit_col == -1)) and data_rows:
        sample_row = data_rows[0]
        for idx, cell in enumerate(sample_row):
            d_fmt, _ = _parse_date(cell)
            if d_fmt and date_col == -1:
                date_col = idx
            elif amount_col == -1:
                # Testa se parece número
                cleaned = re.sub(r'[^\d.,\-+]', '', cell)
                if cleaned and any(ch.isdigit() for ch in cleaned):
                    amount_col = idx
            elif desc_col == -1:
                desc_col = idx

    # Fallback padrão
    if date_col == -1:
        date_col = 0
    if desc_col == -1:
        desc_col = 1 if len(data_rows[0]) > 1 else 0
    if amount_col == -1 and debit_col == -1:
        amount_col = 2 if len(data_rows[0]) > 2 else 1

    transactions = []
    for row in data_rows:
        if not row or len(row) <= max(date_col, desc_col, amount_col if amount_col != -1 else 0):
            continue

        raw_date = row[date_col].strip() if date_col < len(row) else ''
        date_br, date_iso = _parse_date(raw_date)
        if not date_br:
            continue

        raw_desc = row[desc_col].strip() if desc_col != -1 and desc_col < len(row) else 'Transação sem descrição'
        if not raw_desc:
            raw_desc = 'Transação sem descrição'

        if amount_col != -1 and amount_col < len(row):
            raw_amount_str = row[amount_col].strip()
            raw_val, tx_type = _clean_amount(raw_amount_str)
        elif debit_col != -1 and credit_col != -1:
            raw_deb = row[debit_col].strip() if debit_col < len(row) else ''
            raw_cred = row[credit_col].strip() if credit_col < len(row) else ''
            if raw_deb and raw_deb != '0' and raw_deb != '0,00':
                raw_val, tx_type = _clean_amount(raw_deb, is_debit=True)
            elif raw_cred and raw_cred != '0' and raw_cred != '0,00':
                raw_val, tx_type = _clean_amount(raw_cred, is_debit=False)
            else:
                continue
        else:
            continue

        if raw_val == Decimal('0.00'):
            continue

        transactions.append({
            'id': str(uuid.uuid4()),
            'date': date_br,
            'date_iso': date_iso,
            'payee': raw_desc,
            'amount': str(abs(raw_val)),
            'type': tx_type,
            'raw_amount': str(raw_val)
        })

    return transactions


def parse_ofx_file(ofx_file):
    """
    Parser para arquivos de extrato bancário no formato OFX.
    """
    ofx = OfxParser.parse(ofx_file)
    transactions = []
    for account in ofx.accounts:
        for tx in account.statement.transactions:
            raw_amount = Decimal(str(tx.amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            tx_type = 'despesa' if raw_amount < 0 else 'receita'
            transactions.append({
                'id': str(uuid.uuid4()),
                'date': tx.date.strftime('%d/%m/%Y'),
                'date_iso': tx.date.strftime('%Y-%m-%d'),
                'payee': getattr(tx, 'payee', '') or getattr(tx, 'memo', '') or getattr(tx, 'name', '') or "Transação sem descrição",
                'amount': str(abs(raw_amount)),
                'type': tx_type,
                'raw_amount': str(raw_amount)
            })
    return transactions


def enrich_transactions_with_suggestions_and_duplicates(user, transactions):
    """
    Analisa a lista de transações importadas:
    1. Sugere categorias com base no histórico de hábitos do usuário (get_user_description_habits).
    2. Detecta possíveis duplicatas comparando data (+/- 1 dia) e valor exato no banco de dados.
    """
    if not transactions:
        return transactions

    habits = get_user_description_habits(user, limit=100)
    categories_by_id = {str(c.id): c for c in Category.objects.filter(user=user)}

    # Obtém intervalo de datas para buscar transações existentes
    dates_iso = [t['date_iso'] for t in transactions if t.get('date_iso')]
    if dates_iso:
        min_date_obj = datetime.strptime(min(dates_iso), '%Y-%m-%d').date() - timedelta(days=2)
        max_date_obj = datetime.strptime(max(dates_iso), '%Y-%m-%d').date() + timedelta(days=2)
        existing_txs = list(
            Transaction.objects.filter(
                user=user,
                date__gte=min_date_obj,
                date__lte=max_date_obj
            ).values('id', 'date', 'amount', 'description')
        )
    else:
        existing_txs = []

    # Prefixos bancários comuns a serem desconsiderados na busca por similaridade
    NOISE_REGEX = re.compile(r'^(pix\s+enviado|pix\s+recebido|compra\s+no\s+cartao|compra\s+cartao|pagto\s+eletronico|pagamento\s+eletronico|ted\s+recebida|doc\s+recebido|transferencia\s+pix|deb\s+auto|pagamento\s+fatura|recarga\s+celular)\s*[:\-]?\s*', re.IGNORECASE)

    for tx in transactions:
        payee = tx.get('payee', '').strip()
        cleaned_payee = NOISE_REGEX.sub('', payee).strip()
        tx_type = tx.get('type', 'despesa')

        # 1. Sugestão de Categoria
        matched_habit = None
        # Match direto
        if payee in habits:
            matched_habit = habits[payee]
        elif cleaned_payee and cleaned_payee in habits:
            matched_habit = habits[cleaned_payee]
        else:
            # Match insensível a maiúsculas / substring / tokens
            payee_lower = (cleaned_payee or payee).lower()
            payee_tokens = {w for w in re.findall(r'\b\w+\b', payee_lower) if len(w) >= 3}
            for habit_name, habit_data in habits.items():
                habit_lower = habit_name.lower()
                habit_tokens = {w for w in re.findall(r'\b\w+\b', habit_lower) if len(w) >= 3}
                if (
                    habit_lower == payee_lower
                    or (len(habit_lower) >= 4 and habit_lower in payee_lower)
                    or (len(payee_lower) >= 4 and payee_lower in habit_lower)
                    or (payee_tokens & habit_tokens)
                ):
                    matched_habit = habit_data
                    break

        if matched_habit and matched_habit.get('category_id'):
            cat_id = matched_habit['category_id']
            if cat_id in categories_by_id:
                cat_obj = categories_by_id[cat_id]
                # Valida se o tipo da categoria é compatível
                if cat_obj.type == tx_type:
                    tx['suggested_category_id'] = cat_id
                    tx['suggested_category_name'] = cat_obj.name
                    tx['suggested_category_icon'] = cat_obj.icon or ''

        # 2. Detecção de Duplicata (Estratégia B - Transparência com aviso)
        tx_amount = Decimal(str(tx.get('amount', '0.00')))
        tx_date_str = tx.get('date_iso')
        if tx_date_str:
            tx_date_obj = datetime.strptime(tx_date_str, '%Y-%m-%d').date()
            is_dup = False
            dup_reason = ''

            for ext in existing_txs:
                ext_date = ext['date']
                ext_amount = Decimal(str(ext['amount']))
                if ext_amount == tx_amount and abs((ext_date - tx_date_obj).days) <= 1:
                    is_dup = True
                    dup_reason = f"Já existe: {ext['description']} (R$ {ext_amount}) em {ext_date.strftime('%d/%m/%Y')}"
                    break

            tx['is_duplicate'] = is_dup
            tx['duplicate_reason'] = dup_reason
        else:
            tx['is_duplicate'] = False
            tx['duplicate_reason'] = ''

    return transactions


def process_import_transactions(user, account, transactions_data, request_post):
    """
    Processa e salva as transações aprovadas na tela de revisão de importação.
    Recalcula o saldo da conta destino atomicamente.
    """
    transactions_to_create = []

    with db_transaction.atomic():
        for tx in transactions_data:
            cat_id = request_post.get(f"category_{tx['id']}")
            if cat_id and cat_id != 'ignore':
                category = Category.objects.filter(id=cat_id, user=user).first()
                if not category:
                    raise ValueError(f"Categoria selecionada inválida para a transação '{tx['payee']}'.")

                raw_amount = Decimal(str(abs(float(tx['amount'])))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                custom_description = request_post.get(f"description_{tx['id']}", tx['payee']).strip() or tx['payee']

                transactions_to_create.append(
                    Transaction(
                        user=user,
                        account=account,
                        category=category,
                        amount=raw_amount,
                        date=tx['date_iso'],
                        description=custom_description[:255],
                        status=Transaction.Statuses.COMPLETED
                    )
                )

        if transactions_to_create:
            Transaction.objects.bulk_create(transactions_to_create)

            from wallets.services import recalculate_account_balance
            recalculate_account_balance(account)

    return len(transactions_to_create)


# Alias para retrocompatibilidade
process_ofx_transactions = process_import_transactions


def send_push_notification(user, title, body, url='/dashboard/'):
    subscriptions = user.push_subscriptions.all()
    if not subscriptions.exists():
        return

    payload = json.dumps({
        'title': title,
        'body': body,
        'url': url
    })

    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh,
                        "auth": sub.auth
                    }
                },
                data=payload,
                vapid_private_key=str(settings.VAPID_PRIVATE_KEY),
                vapid_claims={
                    "sub": f"mailto:{settings.VAPID_ADMIN_EMAIL.replace('mailto:', '')}"
                }
            )
        except WebPushException as ex:
            if ex.response is not None and ex.response.status_code in [404, 410]:
                sub.delete()
            print("Web Push Error:", repr(ex))
