from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from wallets.models import Account

User = get_user_model()


class WalletsWebTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.client.force_login(self.user)

    def test_account_web_crud(self):
        # Lista de Contas
        res = self.client.get('/wallets/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Contas & Cartões')

        # Criação de Conta Corrente
        payload = {
            'name': 'Conta Principal',
            'type': Account.Types.CHECKING,
            'institution': 'Banco X',
            'balance': '1500.50',
            'color': '#123456',
        }
        res = self.client.post('/wallets/create/', data=payload)
        self.assertEqual(res.status_code, 302)

        account = Account.objects.get(name='Conta Principal')
        self.assertEqual(account.user, self.user)
        self.assertEqual(account.balance, Decimal('1500.50'))

        # View de Confirmação de Exclusão
        res = self.client.get(f'/wallets/{account.id}/confirm-delete/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Excluir Conta')

        # Excluir Conta
        res = self.client.post(f'/wallets/{account.id}/delete/')
        self.assertEqual(res.status_code, 302)
        self.assertFalse(Account.objects.filter(id=account.id).exists())

    def test_account_balance_recalculation(self):
        from moneta.common import TransactionType
        from transactions.models import Category, Transaction
        from wallets.services import recalculate_account_balance

        account = Account.objects.create(
            user=self.user,
            name='Conta Corrente Teste',
            type=Account.Types.CHECKING,
            balance=Decimal('1000.00'),
            initial_balance=Decimal('1000.00')
        )

        cat_income = Category.objects.create(user=self.user, name='Salário', type=TransactionType.INCOME)
        cat_expense = Category.objects.create(user=self.user, name='Aluguel', type=TransactionType.EXPENSE)

        # Receita Concluída: +500
        Transaction.objects.create(
            user=self.user, account=account, category=cat_income,
            description='Bonus', amount=Decimal('500.00'), date='2026-08-01',
            status=Transaction.Statuses.COMPLETED
        )
        # Despesa Concluída: -200
        Transaction.objects.create(
            user=self.user, account=account, category=cat_expense,
            description='Mercado', amount=Decimal('200.00'), date='2026-08-02',
            status=Transaction.Statuses.COMPLETED
        )

        new_bal = recalculate_account_balance(account)
        # 1000 + 500 - 200 = 1300
        self.assertEqual(new_bal, Decimal('1300.00'))
