from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model
from wallets.models import Account
from transactions.models import Category, Tag, Transaction, RecurringTransaction, Transfer
from moneta.common import TransactionType
from transactions.services import process_recurring_transactions

User = get_user_model()


class TransactionsWebTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='txuser', password='password123')
        self.client.force_login(self.user)
        self.account1 = Account.objects.create(user=self.user, name='Conta A', type=Account.Types.CHECKING)
        self.account2 = Account.objects.create(user=self.user, name='Conta B', type=Account.Types.SAVINGS)
        self.category = Category.objects.create(user=self.user, name='Alimentação', type=TransactionType.EXPENSE)
        self.tag = Tag.objects.create(user=self.user, name='Essencial', color='#FF0000')

    def test_category_and_tag_web_view(self):
        res = self.client.get('/transactions/categories/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Categorias & Tags')

    def test_transaction_web_crud(self):
        payload = {
            'account': str(self.account1.id),
            'category': str(self.category.id),
            'description': 'Almoço',
            'amount': '45.90',
            'date': '2026-08-07',
            'status': 'concluída'
        }
        res = self.client.post('/transactions/create/', data=payload)
        self.assertEqual(res.status_code, 302)

        tx = Transaction.objects.get(description='Almoço')
        self.assertEqual(tx.amount, Decimal('45.90'))

        res = self.client.get('/transactions/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Almoço')

        res = self.client.post(f'/transactions/{tx.id}/delete/')
        self.assertEqual(res.status_code, 302)
        self.assertFalse(Transaction.objects.filter(id=tx.id).exists())

    def test_transaction_create_recurring(self):
        payload = {
            'account': str(self.account1.id),
            'category': str(self.category.id),
            'description': 'Aluguel Mensal',
            'amount': '1500.00',
            'date': '2026-08-01',
            'status': 'concluída',
            'is_recurring': 'on',
            'frequency': 'monthly'
        }
        res = self.client.post('/transactions/create/', data=payload)
        self.assertEqual(res.status_code, 302)

        tx = Transaction.objects.get(description='Aluguel Mensal')
        self.assertIsNotNone(tx.recurring)
        self.assertEqual(tx.recurring.frequency, 'monthly')

    def test_transfer_web_create(self):
        payload = {
            'out_account': str(self.account1.id),
            'in_account': str(self.account2.id),
            'description': 'Transferência Poupança',
            'amount': '500.00',
            'date': '2026-08-07',
        }
        res = self.client.post('/transactions/transfers/create/', data=payload)
        self.assertEqual(res.status_code, 302)
        self.assertTrue(Transfer.objects.filter(user=self.user).exists())

    def test_transaction_web_filters(self):
        Transaction.objects.create(
            user=self.user,
            account=self.account1,
            category=self.category,
            description='Jantar',
            amount=Decimal('80.00'),
            date='2026-08-01',
            status='concluída'
        )
        res = self.client.get(f'/transactions/?account_id={self.account1.id}')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Jantar')

    def test_process_recurring_transactions(self):
        rec = RecurringTransaction.objects.create(
            user=self.user,
            account=self.account1,
            category=self.category,
            description='Assinatura Streaming',
            amount=Decimal('39.90'),
            frequency=RecurringTransaction.Frequencies.MONTHLY,
            start_date=date(2026, 6, 1),
            active=True
        )

        process_recurring_transactions(self.user, date(2026, 8, 31))

        txs = Transaction.objects.filter(recurring=rec).order_by('date')
        self.assertEqual(txs.count(), 3)
        self.assertEqual(txs[0].date, date(2026, 6, 1))
        self.assertEqual(txs[1].date, date(2026, 7, 1))
        self.assertEqual(txs[2].date, date(2026, 8, 1))

    def test_transaction_create_recurring_transfer(self):
        payload = {
            'tx_type': 'transferencia',
            'out_account': str(self.account1.id),
            'in_account': str(self.account2.id),
            'description': 'Reserva Mensal',
            'amount': '300.00',
            'date': '2026-08-01',
            'is_recurring': 'on',
            'frequency': 'monthly'
        }
        res = self.client.post('/transactions/create/', data=payload)
        self.assertEqual(res.status_code, 302)

        transfers = Transfer.objects.filter(user=self.user)
        self.assertTrue(transfers.exists())
        transfer = transfers.first()
        self.assertEqual(transfer.out_transaction.amount, Decimal('300.00'))
        self.assertIsNotNone(transfer.out_transaction.recurring)
        self.assertEqual(transfer.out_transaction.recurring.target_account, self.account2)
