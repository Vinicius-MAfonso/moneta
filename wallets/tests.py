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

    def test_calculate_expected_balance(self):
        from wallets.services import calculate_expected_balance
        account = Account.objects.create(
            user=self.user, name='Conta Esperada', type=Account.Types.CHECKING,
            balance=Decimal('100.00'), initial_balance=Decimal('100.00')
        )
        from moneta.common import TransactionType
        from transactions.models import Category, Transaction
        cat_income = Category.objects.create(user=self.user, name='Salário', type=TransactionType.INCOME)
        Transaction.objects.create(
            user=self.user, account=account, category=cat_income,
            description='Bonus Pendente', amount=Decimal('500.00'), date='2026-08-15',
            status=Transaction.Statuses.PENDING
        )
        expected = calculate_expected_balance(account)
        self.assertEqual(expected, Decimal('600.00'))

    def test_pay_credit_card_bill(self):
        from moneta.common import TransactionType
        from transactions.models import Category, Transaction
        from wallets.models import CreditCardBill, CreditCardDetails
        from wallets.services import (
            get_or_create_bill_for_transaction,
            pay_credit_card_bill,
        )

        cc_account = Account.objects.create(
            user=self.user, name='Cartão X', type=Account.Types.CREDIT_CARD, balance=Decimal('0.00'), initial_balance=Decimal('0.00')
        )
        CreditCardDetails.objects.create(account=cc_account, limit=Decimal('1000.00'), available_limit=Decimal('1000.00'), closing_day=10, due_day=20)
        
        checking_account = Account.objects.create(
            user=self.user, name='Corrente', type=Account.Types.CHECKING, balance=Decimal('2000.00'), initial_balance=Decimal('2000.00')
        )

        cat_expense = Category.objects.create(user=self.user, name='Compras', type=TransactionType.EXPENSE)
        
        tx = Transaction.objects.create(
            user=self.user, account=cc_account, category=cat_expense,
            description='TV', amount=Decimal('200.00'), date='2026-08-05',
            status=Transaction.Statuses.COMPLETED
        )
        import datetime
        bill = get_or_create_bill_for_transaction(cc_account, datetime.date(2026, 8, 5))
        tx.bill = bill
        tx.save()

        bill = pay_credit_card_bill(bill, checking_account.id)
        self.assertEqual(bill.status, CreditCardBill.Statuses.PAID)
        
        from wallets.services import recalculate_account_balance
        recalculate_account_balance(checking_account)
        self.assertEqual(checking_account.balance, Decimal('1800.00'))
