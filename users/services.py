import json
import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction as db_transaction
from ofxparse import OfxParser
from pywebpush import WebPushException, webpush

from transactions.models import Category, Transaction


def parse_ofx_file(ofx_file):
    ofx = OfxParser.parse(ofx_file)
    transactions = []
    for account in ofx.accounts:
        for tx in account.statement.transactions:
            transactions.append({
                'id': str(uuid.uuid4()),
                'date': tx.date.strftime('%d/%m/%Y'),
                'date_iso': tx.date.strftime('%Y-%m-%d'),
                'payee': getattr(tx, 'payee', '') or getattr(tx, 'memo', '') or getattr(tx, 'name', '') or "Transação sem descrição",
                'amount': str(tx.amount),
                'type': 'despesa' if tx.amount < 0 else 'receita'
            })
    return transactions


def process_ofx_transactions(user, account, ofx_data, request_post):
    transactions_to_create = []
    
    with db_transaction.atomic():
        for tx in ofx_data:
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
