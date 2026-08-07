from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from wallets.models import Account
from transactions.models import Category, Tag, Transaction, RecurringTransaction, Transfer
from moneta.common import TransactionType

User = get_user_model()


class TransactionsAPITestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='txuser', password='password123')
        self.client.force_login(self.user)
        self.account1 = Account.objects.create(user=self.user, name='Conta A', type=Account.Types.CHECKING)
        self.account2 = Account.objects.create(user=self.user, name='Conta B', type=Account.Types.SAVINGS)
        self.category = Category.objects.create(user=self.user, name='Alimentação', type=TransactionType.EXPENSE)
        self.tag = Tag.objects.create(user=self.user, name='Essencial', color='#FF0000')

    def test_category_and_tag_crud(self):
        # Category
        res = self.client.get('/api/transactions/categories')
        self.assertEqual(res.status_code, 200)

        # Tag
        res = self.client.get('/api/transactions/tags')
        self.assertEqual(res.status_code, 200)

    def test_transaction_crud(self):
        payload = {
            'account': str(self.account1.id),
            'category': str(self.category.id),
            'tags': [str(self.tag.id)],
            'description': 'Almoço',
            'amount': '45.90',
            'date': '2026-08-07',
            'status': 'concluída'
        }
        res = self.client.post('/api/transactions/transactions', data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 201)
        tx_id = res.json()['id']

        res = self.client.get('/api/transactions/transactions')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 1)

        res = self.client.delete(f'/api/transactions/transactions/{tx_id}')
        self.assertEqual(res.status_code, 204)

    def test_transfer(self):
        payload = {
            'out_account_id': str(self.account1.id),
            'in_account_id': str(self.account2.id),
            'description': 'Transferência Poupança',
            'amount': '500.00',
            'date': '2026-08-07',
            'status': 'concluída'
        }
        res = self.client.post('/api/transactions/transfers', data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 201)
        transfer_id = res.json()['id']

        res = self.client.get('/api/transactions/transfers')
        self.assertEqual(res.status_code, 200)

        res = self.client.delete(f'/api/transactions/transfers/{transfer_id}')
        self.assertEqual(res.status_code, 204)

    def test_transaction_filters(self):
        tx1 = Transaction.objects.create(
            user=self.user,
            account=self.account1,
            category=self.category,
            description='Jantar',
            amount=Decimal('80.00'),
            date='2026-08-01',
            status='concluída'
        )
        tx2 = Transaction.objects.create(
            user=self.user,
            account=self.account2,
            category=self.category,
            description='Gasolina',
            amount=Decimal('150.00'),
            date='2026-08-05',
            status='pendente'
        )
        # Filter by account
        res = self.client.get(f'/api/transactions/transactions?account_id={self.account1.id}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 1)
        self.assertEqual(res.json()[0]['id'], str(tx1.id))

        # Filter by status
        res = self.client.get('/api/transactions/transactions?status=pendente')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 1)
        self.assertEqual(res.json()[0]['id'], str(tx2.id))

        # Filter by date range
        res = self.client.get('/api/transactions/transactions?start_date=2026-08-02&end_date=2026-08-06')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 1)
        self.assertEqual(res.json()[0]['id'], str(tx2.id))

