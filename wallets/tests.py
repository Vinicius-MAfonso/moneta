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
        CreditCardDetails.objects.create(account=cc_account, limit=Decimal('1000.00'), closing_day=10, due_day=20)
        
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
            account=self.cc_account, limit=Decimal('5000.00'),
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

    def test_credit_card_available_and_used_limit_properties(self):
        from decimal import Decimal

        from moneta.common import TransactionType
        from transactions.models import Category, Transaction
        from wallets.services import recalculate_account_balance

        cc = self.cc_account.credit_card_details
        self.assertEqual(cc.available_limit, Decimal('5000.00'))
        self.assertEqual(cc.used_limit, Decimal('0.00'))
        self.assertEqual(cc.limit_usage_pct, Decimal('0.00'))

        cat_expense, _ = Category.objects.get_or_create(user=self.user, name='Lazer', defaults={'type': TransactionType.EXPENSE})
        Transaction.objects.create(
            user=self.user, account=self.cc_account, category=cat_expense,
            description='Restaurante', amount=Decimal('1500.00'), date='2026-08-10',
            status=Transaction.Statuses.COMPLETED
        )
        recalculate_account_balance(self.cc_account)
        cc.refresh_from_db()

        self.assertEqual(self.cc_account.balance, Decimal('-1500.00'))
        self.assertEqual(cc.available_limit, Decimal('3500.00'))
        self.assertEqual(cc.used_limit, Decimal('1500.00'))
        self.assertEqual(cc.limit_usage_pct, Decimal('30.00'))

    def test_credit_card_limit_recurring_vs_installments(self):
        from datetime import timedelta
        from decimal import Decimal

        from django.utils import timezone

        from moneta.common import TransactionType
        from transactions.models import Category, RecurringTransaction, Transaction
        from wallets.services import recalculate_account_balance

        cc = self.cc_account.credit_card_details
        self.assertEqual(cc.available_limit, Decimal('5000.00'))
        self.assertEqual(cc.used_limit, Decimal('0.00'))

        cat_expense, _ = Category.objects.get_or_create(user=self.user, name='Streaming', defaults={'type': TransactionType.EXPENSE})
        today = timezone.now().date()

        # 1. Add recurring subscription (e.g. Netflix 50.00) with 1 current charge and 5 future projections
        recurring = RecurringTransaction.objects.create(
            user=self.user, account=self.cc_account, category=cat_expense,
            description='Netflix', amount=Decimal('50.00'), frequency='monthly',
            start_date=today
        )

        # Current occurrence (today)
        Transaction.objects.create(
            user=self.user, account=self.cc_account, category=cat_expense,
            description='Netflix 1', amount=Decimal('50.00'), date=today,
            status=Transaction.Statuses.PENDING, recurring=recurring
        )

        # 5 Future occurrences
        for i in range(1, 6):
            future_date = today + timedelta(days=30 * i)
            Transaction.objects.create(
                user=self.user, account=self.cc_account, category=cat_expense,
                description=f'Netflix {i+1}', amount=Decimal('50.00'), date=future_date,
                status=Transaction.Statuses.PENDING, recurring=recurring
            )

        recalculate_account_balance(self.cc_account)
        cc.refresh_from_db()

        # Only the current occurrence (50.00) should consume the limit, NOT all 6 occurrences (300.00)
        self.assertEqual(cc.used_limit, Decimal('50.00'))
        self.assertEqual(cc.available_limit, Decimal('4950.00'))

        # 2. Add an installment purchase (e.g. Smartphone 3x 500.00 = 1500.00)
        # All installments (including future ones) MUST consume the limit upfront
        for i in range(3):
            inst_date = today + timedelta(days=30 * i)
            Transaction.objects.create(
                user=self.user, account=self.cc_account, category=cat_expense,
                description=f'Smartphone ({i+1}/3)', amount=Decimal('500.00'), date=inst_date,
                status=Transaction.Statuses.PENDING,
                installment_number=i + 1, total_installments=3
            )

        recalculate_account_balance(self.cc_account)
        cc.refresh_from_db()

        # Total used should now be 50.00 (subscription) + 1500.00 (installments) = 1550.00
        self.assertEqual(cc.used_limit, Decimal('1550.00'))
        self.assertEqual(cc.available_limit, Decimal('3450.00'))

    def test_reconcile_balances_management_command(self):
        from io import StringIO

        from django.core.management import call_command

        from wallets.models import Account

        # Introduce intentional drift on checking_account
        Account.objects.filter(id=self.checking_account.id).update(balance=Decimal('9999.00'))
        self.checking_account.refresh_from_db()
        self.assertEqual(self.checking_account.balance, Decimal('9999.00'))

        # Run command without --fix
        out = StringIO()
        call_command('reconcile_balances', stdout=out)
        output = out.getvalue()
        self.assertIn('[MISMATCH]', output)
        self.checking_account.refresh_from_db()
        self.assertEqual(self.checking_account.balance, Decimal('9999.00'))

        # Run command with --fix
        out_fix = StringIO()
        call_command('reconcile_balances', '--fix', stdout=out_fix)
        output_fix = out_fix.getvalue()
        self.assertIn('[FIXED]', output_fix)
        self.checking_account.refresh_from_db()
        self.assertEqual(self.checking_account.balance, Decimal('1000.00'))

    def test_get_credit_card_timeline_recurring_subscriptions(self):
        import datetime
        from decimal import Decimal

        from moneta.common import TransactionType
        from transactions.models import Category, RecurringTransaction, Transaction
        from wallets.services import get_credit_card_timeline

        cat_expense, _ = Category.objects.get_or_create(user=self.user, name='Serviços', defaults={'type': TransactionType.EXPENSE})
        start_date = datetime.date(2026, 8, 1)

        recurring = RecurringTransaction.objects.create(
            user=self.user,
            account=self.cc_account,
            category=cat_expense,
            description='Netflix',
            amount=Decimal('50.00'),
            frequency='monthly',
            start_date=datetime.date(2026, 8, 10),
            active=True
        )

        Transaction.objects.create(
            user=self.user, account=self.cc_account, category=cat_expense,
            description='Netflix (Recorrente)', amount=Decimal('50.00'), date=datetime.date(2026, 8, 10),
            status=Transaction.Statuses.PENDING, recurring=recurring
        )
        Transaction.objects.create(
            user=self.user, account=self.cc_account, category=cat_expense,
            description='Netflix (Recorrente)', amount=Decimal('50.00'), date=datetime.date(2026, 9, 10),
            status=Transaction.Statuses.PENDING, recurring=recurring
        )

        for i in range(3):
            tx_month = datetime.date(2026, 8 + i, 15)
            Transaction.objects.create(
                user=self.user, account=self.cc_account, category=cat_expense,
                description=f'Parcela ({i+1}/3)', amount=Decimal('100.00'), date=tx_month,
                status=Transaction.Statuses.PENDING, installment_number=i+1, total_installments=3
            )

        timeline = get_credit_card_timeline(self.user, start_date, months=12)
        self.assertEqual(len(timeline), 12)

        self.assertEqual(timeline[0]['total'], Decimal('150.00'))  # Ago/2026
        self.assertEqual(timeline[1]['total'], Decimal('150.00'))  # Set/2026
        self.assertEqual(timeline[2]['total'], Decimal('150.00'))  # Out/2026

        for m in timeline[3:]:
            self.assertEqual(m['total'], Decimal('50.00'))

