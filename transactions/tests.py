from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from moneta.common import TransactionType
from transactions.models import (
    Category,
    RecurringTransaction,
    Tag,
    Transaction,
    Transfer,
)
from transactions.services import process_recurring_transactions
from wallets.models import Account

User = get_user_model()


class TransactionsWebTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='txuser', password='password123')
        self.client.force_login(self.user)
        self.account1 = Account.objects.create(user=self.user, name='Conta A', type=Account.Types.CHECKING)
        self.account2 = Account.objects.create(user=self.user, name='Conta B', type=Account.Types.OTHER)
        self.category, _ = Category.objects.get_or_create(user=self.user, name='Alimentação', defaults={'type': TransactionType.EXPENSE})
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

    def test_create_transfer_same_account(self):
        from django.core.exceptions import ValidationError

        from transactions.services import create_transfer
        with self.assertRaises(ValidationError):
            create_transfer(
                user=self.user,
                out_account_id=self.account1.id,
                in_account_id=self.account1.id,
                description='Mesma conta',
                amount=Decimal('100.00'),
                tx_date='2026-08-01',
                status='concluída'
            )


class TransactionServicesTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='svcuser', password='password123')
        self.account1 = Account.objects.create(user=self.user, name='Conta A', type=Account.Types.CHECKING)
        self.account2 = Account.objects.create(user=self.user, name='Conta B', type=Account.Types.OTHER)
        self.cc_account = Account.objects.create(user=self.user, name='Cartão', type=Account.Types.CREDIT_CARD)
        
        from wallets.models import CreditCardDetails
        CreditCardDetails.objects.create(account=self.cc_account, limit=Decimal('5000.00'), closing_day=10, due_day=15)
        
        self.cat_expense, _ = Category.objects.get_or_create(user=self.user, name='Despesa', defaults={'type': TransactionType.EXPENSE})
        self.cat_transfer, _ = Category.objects.get_or_create(user=self.user, name='Transferência', defaults={'type': TransactionType.TRANSFER})

    def test_create_regular_transaction_installments(self):
        from transactions.services import create_regular_transaction
        
        create_regular_transaction(
            user=self.user,
            account_id=self.cc_account.id,
            category_id=self.cat_expense.id,
            description='Compra Dividida',
            amount=Decimal('100.00'),
            tx_date=date(2026, 8, 15),
            status=Transaction.Statuses.COMPLETED,
            installments=3
        )
        
        txs = Transaction.objects.filter(description__startswith='Compra Dividida').order_by('installment_number')
        self.assertEqual(txs.count(), 3)
        self.assertEqual(txs[0].amount, Decimal('33.33'))
        self.assertEqual(txs[1].amount, Decimal('33.33'))
        self.assertEqual(txs[2].amount, Decimal('33.34')) # Sobra do dízima foi pra última!
        
        # O cartão deve ter atrelado à fatura
        self.assertIsNotNone(txs[0].bill)
        
        # A primeira conta vence esse mês e já está pendente ou concluída?
        # A lógica coloca a primeira como enviada no status e as seguintes como PENDING.
        self.assertEqual(txs[0].status, Transaction.Statuses.COMPLETED)
        self.assertEqual(txs[1].status, Transaction.Statuses.PENDING)
        self.assertEqual(txs[2].status, Transaction.Statuses.PENDING)

    def test_update_transaction_paid_bill(self):
        from django.core.exceptions import ValidationError
        
        from transactions.services import create_regular_transaction, update_transaction
        from wallets.models import CreditCardBill
        
        create_regular_transaction(
            user=self.user,
            account_id=self.cc_account.id,
            category_id=self.cat_expense.id,
            description='Compra',
            amount=Decimal('50.00'),
            tx_date=date(2026, 8, 15),
            status=Transaction.Statuses.COMPLETED
        )
        tx = Transaction.objects.get(description='Compra')
        
        # Simular pagamento da fatura
        bill = tx.bill
        bill.status = CreditCardBill.Statuses.PAID
        bill.save()
        
        with self.assertRaises(ValidationError) as e:
            update_transaction(tx, {
                'account': self.account1.id,
                'category': self.cat_expense.id,
                'description': 'Editado',
                'amount': Decimal('60.00'),
                'date': date(2026, 8, 15),
                'status': Transaction.Statuses.COMPLETED,
                'tags': []
            })
            
        self.assertEqual(str(e.exception.messages[0]), "Transações de faturas já pagas não podem ser alteradas.")

    def test_update_transaction_account_change(self):
        from transactions.services import create_regular_transaction, update_transaction
        
        create_regular_transaction(
            user=self.user,
            account_id=self.account1.id,
            category_id=self.cat_expense.id,
            description='Compra',
            amount=Decimal('50.00'),
            tx_date=date(2026, 8, 15),
            status=Transaction.Statuses.COMPLETED
        )
        tx = Transaction.objects.get(description='Compra')
        self.account1.refresh_from_db()
        self.assertEqual(self.account1.balance, Decimal('-50.00'))
        
        # Mudar para account2
        update_transaction(tx, {
            'account': self.account2.id,
            'category': self.cat_expense.id,
            'description': 'Compra Movida',
            'amount': Decimal('50.00'),
            'date': date(2026, 8, 15),
            'status': Transaction.Statuses.COMPLETED,
            'tags': []
        })
        
        self.account1.refresh_from_db()
        self.account2.refresh_from_db()
        self.assertEqual(self.account1.balance, Decimal('0.00'))
        self.assertEqual(self.account2.balance, Decimal('-50.00'))

    def test_process_recurring_transactions_idempotency(self):
        from transactions.services import process_recurring_transactions
        
        rec = RecurringTransaction.objects.create(
            user=self.user,
            account=self.account1,
            category=self.cat_expense,
            description='Netflix',
            amount=Decimal('40.00'),
            frequency=RecurringTransaction.Frequencies.MONTHLY,
            start_date=date(2026, 8, 1),
            active=True
        )
        rec.ignore_date(date(2026, 9, 1))
        
        # Rodar primeira vez
        process_recurring_transactions(self.user, target_end_date=date(2026, 10, 31))
        
        txs = Transaction.objects.filter(recurring=rec).order_by('date')
        # Deveria criar: 8/1, (9/1 é ignored), 10/1 -> total 2 transações
        self.assertEqual(txs.count(), 2)
        self.assertEqual(txs[0].date, date(2026, 8, 1))
        self.assertEqual(txs[1].date, date(2026, 10, 1))
        
        # Rodar segunda vez (motor é idempotente)
        process_recurring_transactions(self.user, target_end_date=date(2026, 10, 31))
        
        # A quantidade deve permanecer 2
        txs = Transaction.objects.filter(recurring=rec).order_by('date')
        self.assertEqual(txs.count(), 2)

    def test_update_transaction_add_recurrence(self):
        from transactions.services import create_regular_transaction, update_transaction
        
        create_regular_transaction(
            user=self.user,
            account_id=self.account1.id,
            category_id=self.cat_expense.id,
            description='Academia',
            amount=Decimal('100.00'),
            tx_date=date(2026, 8, 1),
            status=Transaction.Statuses.COMPLETED
        )
        tx = Transaction.objects.get(description='Academia')
        self.assertIsNone(tx.recurring)
        
        update_transaction(tx, {
            'account': self.account1.id,
            'category': self.cat_expense.id,
            'description': 'Academia',
            'amount': Decimal('100.00'),
            'date': date(2026, 8, 1),
            'status': Transaction.Statuses.COMPLETED,
            'tags': [],
            'is_recurring': True,
            'frequency': 'monthly',
            'recurring_end_date': None
        })
        
        tx.refresh_from_db()
        self.assertIsNotNone(tx.recurring)
        self.assertEqual(tx.recurring.frequency, 'monthly')

    def test_update_transaction_remove_recurrence(self):
        from transactions.services import (
            process_recurring_transactions,
            update_transaction,
        )
        
        rec = RecurringTransaction.objects.create(
            user=self.user,
            account=self.account1,
            category=self.cat_expense,
            description='Curso',
            amount=Decimal('50.00'),
            frequency=RecurringTransaction.Frequencies.MONTHLY,
            start_date=date(2026, 8, 1),
            active=True
        )
        process_recurring_transactions(self.user, target_end_date=date(2026, 10, 31))
        
        txs = Transaction.objects.filter(recurring=rec).order_by('date')
        self.assertEqual(txs.count(), 3)
        
        # Vamos destransformar a transação de Setembro
        tx_sept = txs.get(date=date(2026, 9, 1))
        
        update_transaction(tx_sept, {
            'account': self.account1.id,
            'category': self.cat_expense.id,
            'description': 'Curso (Avulso)',
            'amount': Decimal('50.00'),
            'date': date(2026, 9, 1),
            'status': Transaction.Statuses.PENDING,
            'tags': [],
            'is_recurring': False,
            'frequency': 'monthly',
            'recurring_end_date': None
        })
        
        tx_sept.refresh_from_db()
        self.assertIsNone(tx_sept.recurring)
        
        rec.refresh_from_db()
        self.assertFalse(rec.active)
        self.assertEqual(rec.end_date, date(2026, 9, 1))
        
        # A de Outubro (futura) deve ter sido deletada, a de Agosto (passada) deve continuar existindo atrelada à série
        self.assertTrue(Transaction.objects.filter(date=date(2026, 8, 1), recurring=rec).exists())
        self.assertFalse(Transaction.objects.filter(date=date(2026, 10, 1), recurring=rec).exists())


