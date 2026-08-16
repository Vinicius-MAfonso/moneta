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
        res = self.client.get('/wallets/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Contas & Cartões')

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

        res = self.client.get(f'/wallets/{account.id}/confirm-delete/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Excluir Conta')

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

        cat_income, _ = Category.objects.get_or_create(user=self.user, name='Salário', defaults={'type': TransactionType.INCOME})
        cat_expense, _ = Category.objects.get_or_create(user=self.user, name='Aluguel', defaults={'type': TransactionType.EXPENSE})

        Transaction.objects.create(
            user=self.user, account=account, category=cat_income,
            description='Bonus', amount=Decimal('500.00'), date='2026-08-01',
            status=Transaction.Statuses.COMPLETED
        )
        Transaction.objects.create(
            user=self.user, account=account, category=cat_expense,
            description='Mercado', amount=Decimal('200.00'), date='2026-08-02',
            status=Transaction.Statuses.COMPLETED
        )

        new_bal = recalculate_account_balance(account)
        self.assertEqual(new_bal, Decimal('1300.00'))

    def test_calculate_expected_balance(self):
        from wallets.services import calculate_expected_balance
        account = Account.objects.create(
            user=self.user, name='Conta Esperada', type=Account.Types.CHECKING,
            balance=Decimal('100.00'), initial_balance=Decimal('100.00')
        )
        from moneta.common import TransactionType
        from transactions.models import Category, Transaction
        cat_income, _ = Category.objects.get_or_create(user=self.user, name='Salário', defaults={'type': TransactionType.INCOME})
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

        cat_expense, _ = Category.objects.get_or_create(user=self.user, name='Compras', defaults={'type': TransactionType.EXPENSE})
        
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


class WalletsServicesTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='wallet_svc', password='password123')
        
        from wallets.models import Account, CreditCardDetails
        self.cc_account = Account.objects.create(
            user=self.user, name='Cartão Black', type=Account.Types.CREDIT_CARD,
            balance=Decimal('0.00'), initial_balance=Decimal('0.00')
        )
        CreditCardDetails.objects.create(
            account=self.cc_account, limit=Decimal('5000.00'), available_limit=Decimal('5000.00'),
            closing_day=10, due_day=20
        )
        
        self.checking_account = Account.objects.create(
            user=self.user, name='Corrente', type=Account.Types.CHECKING,
            balance=Decimal('1000.00'), initial_balance=Decimal('1000.00')
        )

    def test_smart_forwarding_get_or_create_bill(self):
        import datetime

        from wallets.models import CreditCardBill
        from wallets.services import get_or_create_bill_for_transaction
        
        # Cria a primeira fatura e a fecha
        bill1 = get_or_create_bill_for_transaction(self.cc_account, datetime.date(2026, 8, 5))
        self.assertEqual(bill1.status, CreditCardBill.Statuses.OPEN)
        self.assertEqual(bill1.due_date, datetime.date(2026, 8, 20))
        
        bill1.status = CreditCardBill.Statuses.PAID
        bill1.save()
        
        # Tenta lançar despesa retroativa no mesmo período
        bill2 = get_or_create_bill_for_transaction(self.cc_account, datetime.date(2026, 8, 5))
        
        # O sistema deve pular a fatura PAID e criar/retornar a próxima OPEN (vencimento em setembro)
        self.assertEqual(bill2.status, CreditCardBill.Statuses.OPEN)
        self.assertEqual(bill2.due_date, datetime.date(2026, 9, 20))
        self.assertNotEqual(bill1.id, bill2.id)

    def test_reopen_credit_card_bill(self):
        import datetime

        from moneta.common import TransactionType
        from transactions.models import Category, Transaction
        from wallets.models import CreditCardBill
        from wallets.services import (
            get_or_create_bill_for_transaction,
            pay_credit_card_bill,
            reopen_credit_card_bill,
        )

        cat_expense, _ = Category.objects.get_or_create(user=self.user, name='Compras', defaults={'type': TransactionType.EXPENSE})
        
        tx = Transaction.objects.create(
            user=self.user, account=self.cc_account, category=cat_expense,
            description='Celular', amount=Decimal('500.00'), date='2026-08-01',
            status=Transaction.Statuses.COMPLETED
        )
        bill = get_or_create_bill_for_transaction(self.cc_account, datetime.date(2026, 8, 1))
        tx.bill = bill
        tx.save()
        
        # Pagar a fatura
        bill = pay_credit_card_bill(bill, self.checking_account.id)
        self.assertEqual(bill.status, CreditCardBill.Statuses.PAID)
        self.assertFalse(hasattr(tx, 'transfer_in'))
        
        # Pagar faturas cria uma transação de transferência atrelada aos payment_txs
        # A própria pay_credit_card_bill vincula o in_tx na fatura.
        payment_txs = bill.transactions.filter(transfer_in__isnull=False)
        self.assertEqual(payment_txs.count(), 1)
        
        # Recalcular saldos simulando fluxo real
        from wallets.services import recalculate_account_balance
        recalculate_account_balance(self.checking_account)
        self.assertEqual(self.checking_account.balance, Decimal('500.00')) # 1000 - 500
        
        # Chamar estorno
        reopen_credit_card_bill(bill)
        
        bill.refresh_from_db()
        self.assertIn(bill.status, [CreditCardBill.Statuses.OPEN, CreditCardBill.Statuses.CLOSED])
        
        # A transferência de pagamento foi deletada?
        payment_txs_after = bill.transactions.filter(transfer_in__isnull=False)
        self.assertEqual(payment_txs_after.count(), 0)
        
        # A conta corrente recuperou o dinheiro?
        recalculate_account_balance(self.checking_account)
        self.assertEqual(self.checking_account.balance, Decimal('1000.00'))

    def test_adjust_account_balance_transaction(self):
        from transactions.models import Transaction
        from wallets.services import adjust_account_balance
        
        success, adjust_type = adjust_account_balance(
            self.checking_account, 
            Decimal('1200.00'), 
            'transaction', 
            self.user
        )
        self.assertTrue(success)
        self.assertEqual(adjust_type, 'transaction')
        
        self.checking_account.refresh_from_db()
        self.assertEqual(self.checking_account.balance, Decimal('1200.00'))
        
        # Checar se a transação compensatória foi criada
        sys_tx = Transaction.objects.filter(account=self.checking_account, category__is_system=True).first()
        self.assertIsNotNone(sys_tx)
        self.assertEqual(sys_tx.amount, Decimal('200.00'))
        self.assertEqual(sys_tx.description, 'Reajuste de Saldo')
