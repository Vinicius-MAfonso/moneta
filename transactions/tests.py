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

        res = self.client.get('/transactions/?month=2026-08')
        self.assertContains(res, 'Almoço')

        res = self.client.post(f'/transactions/{tx.id}/delete/')
        self.assertEqual(res.status_code, 302)
        self.assertFalse(Transaction.objects.filter(id=tx.id).exists())

    def test_transaction_delete_redirect_safe_referer(self):
        tx = Transaction.objects.create(
            user=self.user,
            account=self.account1,
            category=self.category,
            description='Café',
            amount=Decimal('10.00'),
            date='2026-09-01',
            status='concluída'
        )
        res = self.client.post(
            f'/transactions/{tx.id}/delete/',
            HTTP_REFERER='http://testserver/wallets/'
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res['Location'], 'http://testserver/wallets/')
        self.assertFalse(Transaction.objects.filter(id=tx.id).exists())

    def test_transaction_delete_redirect_unsafe_referer(self):
        tx = Transaction.objects.create(
            user=self.user,
            account=self.account1,
            category=self.category,
            description='Cinema',
            amount=Decimal('50.00'),
            date='2026-09-01',
            status='concluída'
        )
        res = self.client.post(
            f'/transactions/{tx.id}/delete/',
            HTTP_REFERER='https://evil.com/phishing-attack'
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res['Location'], '/transactions/')
        self.assertFalse(Transaction.objects.filter(id=tx.id).exists())

    def test_transaction_one_cent_validation(self):
        payload = {
            'account': str(self.account1.id),
            'category': str(self.category.id),
            'description': 'Bala 1 Centavo',
            'amount': '0.01',
            'date': '2026-08-07',
            'status': 'concluída'
        }
        res = self.client.post('/transactions/create/', data=payload)
        self.assertEqual(res.status_code, 302)

        tx = Transaction.objects.get(description='Bala 1 Centavo')
        self.assertEqual(tx.amount, Decimal('0.01'))

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
        res = self.client.get(f'/transactions/?account_id={self.account1.id}&month=2026-08')
        self.assertEqual(res.status_code, 200)

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
        self.assertEqual(txs[2].amount, Decimal('33.34'))  # Remainder of division goes to the last installment!
        
        # Credit card transaction should be linked to the bill
        self.assertIsNotNone(txs[0].bill)
        
        # First installment inherits submitted status; subsequent installments are PENDING
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
        
        # Simulate bill payment
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
        
        # Change to account2
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
        
        # First run
        process_recurring_transactions(self.user, target_end_date=date(2026, 10, 31))
        
        txs = Transaction.objects.filter(recurring=rec).order_by('date')
        # Should create: 8/1, (9/1 is ignored), 10/1 -> total 2 transactions
        self.assertEqual(txs.count(), 2)
        self.assertEqual(txs[0].date, date(2026, 8, 1))
        self.assertEqual(txs[1].date, date(2026, 10, 1))
        
        # Second run (engine is idempotent)
        process_recurring_transactions(self.user, target_end_date=date(2026, 10, 31))
        
        # Count must remain 2
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
        
        # Unmark September transaction as recurring
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
        
        # October (future) occurrence should be deleted; August (past) occurrence should remain linked to series
        self.assertTrue(Transaction.objects.filter(date=date(2026, 8, 1), recurring=rec).exists())
        self.assertFalse(Transaction.objects.filter(date=date(2026, 10, 1), recurring=rec).exists())

    def test_get_user_description_habits(self):
        from transactions.services import get_user_description_habits

        tag_delivery = Tag.objects.create(user=self.user, name='Delivery', color='#FF5500')
        tx = Transaction.objects.create(
            user=self.user,
            account=self.account1,
            category=self.cat_expense,
            description='iFood Lanche',
            amount=Decimal('42.00'),
            date=date(2026, 8, 15),
            status=Transaction.Statuses.COMPLETED,
        )
        tx.tags.add(tag_delivery)

        habits = get_user_description_habits(self.user)
        self.assertIn('iFood Lanche', habits)
        habit = habits['iFood Lanche']
        self.assertEqual(habit['type'], TransactionType.EXPENSE)
        self.assertEqual(habit['category_id'], str(self.cat_expense.id))
        self.assertEqual(habit['account_id'], str(self.account1.id))
        self.assertIn(str(tag_delivery.id), habit['tag_ids'])

    def test_transaction_create_view_contains_description_habits(self):
        self.client.force_login(self.user)
        Transaction.objects.create(
            user=self.user,
            account=self.account1,
            category=self.cat_expense,
            description='Uber Viagem (1/2)',
            amount=Decimal('25.50'),
            date=date(2026, 8, 20),
            status=Transaction.Statuses.COMPLETED,
        )

        res = self.client.get('/transactions/create/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('description_habits', res.context)
        # Suffix (1/2) is cleanly stripped to 'Uber Viagem'
        self.assertIn('Uber Viagem', res.context['description_habits'])
        self.assertContains(res, 'Uber Viagem')
        self.assertContains(res, 'Preenchimento automático')

    def test_delete_endpoints_require_post(self):
        self.client.force_login(self.user)
        tx = Transaction.objects.create(
            user=self.user,
            account=self.account1,
            category=self.cat_expense,
            description='Test Delete Verb',
            amount=Decimal('10.00'),
            date=date(2026, 8, 1),
            status=Transaction.Statuses.COMPLETED,
        )
        # GET request to delete endpoint must be rejected with 405 Method Not Allowed
        res = self.client.get(f'/transactions/{tx.id}/delete/')
        self.assertEqual(res.status_code, 405)
        self.assertTrue(Transaction.objects.filter(id=tx.id).exists())

        # POST request should succeed
        res = self.client.post(f'/transactions/{tx.id}/delete/')
        self.assertEqual(res.status_code, 302)
        self.assertFalse(Transaction.objects.filter(id=tx.id).exists())

    def test_system_category_support_in_transaction(self):
        self.client.force_login(self.user)
        system_cat = Category.objects.create(
            user=None,
            name='Salário Sistema',
            type=TransactionType.INCOME,
            is_system=True,
        )
        payload = {
            'account': str(self.account1.id),
            'category': str(system_cat.id),
            'description': 'Salário Mensal',
            'amount': '5000.00',
            'date': '2026-08-05',
            'status': 'concluída',
        }
        res = self.client.post('/transactions/create/', data=payload)
        self.assertEqual(res.status_code, 302)
        tx = Transaction.objects.get(description='Salário Mensal')
        self.assertEqual(tx.category, system_cat)

    def test_category_and_tag_duplicate_form_validation(self):
        from transactions.forms import CategoryForm, TagForm

        Tag.objects.create(user=self.user, name='Essencial', color='#000000')

        # Duplicate category name for same user ('Despesa' was created in setUp)
        cat_form = CategoryForm(
            data={'name': 'Despesa', 'type': 'despesa', 'color': '#000000'},
            user=self.user
        )
        self.assertFalse(cat_form.is_valid())
        self.assertIn('name', cat_form.errors)

        # Duplicate tag name for same user
        tag_form = TagForm(
            data={'name': 'Essencial', 'color': '#000000'},
            user=self.user
        )
        self.assertFalse(tag_form.is_valid())
        self.assertIn('name', tag_form.errors)

    def test_idor_protection_in_update_transaction(self):
        other_user = User.objects.create_user(username='other_user', password='password123')
        other_account = Account.objects.create(user=other_user, name='Conta Outro', type=Account.Types.CHECKING)

        tx = Transaction.objects.create(
            user=self.user,
            account=self.account1,
            category=self.cat_expense,
            description='Minha Transação',
            amount=Decimal('50.00'),
            date=date(2026, 8, 1),
            status=Transaction.Statuses.COMPLETED,
        )

        from django.http import Http404

        from transactions.services import update_transaction

        # Attempting to assign other_user's account must raise 404
        with self.assertRaises(Http404):
            update_transaction(tx, {
                'account': other_account.id,
                'category': self.cat_expense.id,
                'description': 'Tentativa IDOR',
                'amount': Decimal('50.00'),
                'date': date(2026, 8, 1),
                'status': Transaction.Statuses.COMPLETED,
            })

    def test_delete_transaction_service_and_recalc(self):
        from transactions.services import delete_transaction

        tx = Transaction.objects.create(
            user=self.user,
            account=self.account1,
            category=self.cat_expense,
            description='Transação Service Test',
            amount=Decimal('100.00'),
            date=date(2026, 8, 1),
            status=Transaction.Statuses.COMPLETED,
        )
        delete_transaction(user=self.user, transaction_id=tx.id, delete_mode='single')
        self.assertFalse(Transaction.objects.filter(id=tx.id).exists())


class TransactionTemplateTagsTestCase(TestCase):
    def test_amount_sign_filter(self):
        from transactions.templatetags.transaction_tags import amount_sign

        self.assertEqual(amount_sign('receita'), '+')
        self.assertEqual(amount_sign('income'), '+')
        self.assertEqual(amount_sign('despesa'), '-')
        self.assertEqual(amount_sign('expense'), '-')
        self.assertEqual(amount_sign('transferência'), '')
        self.assertEqual(amount_sign(''), '')
        self.assertEqual(amount_sign(None), '')

    def test_tx_color_class_filter(self):
        from transactions.templatetags.transaction_tags import tx_color_class

        self.assertEqual(tx_color_class('receita'), 'text-emerald-600')
        self.assertEqual(tx_color_class('income'), 'text-emerald-600')
        self.assertEqual(tx_color_class('despesa'), 'text-rose-600')
        self.assertEqual(tx_color_class('expense'), 'text-rose-600')
        self.assertEqual(tx_color_class('transferência'), 'text-indigo-600')
        self.assertEqual(tx_color_class(''), 'text-slate-900')

    def test_hex_alpha_filter(self):
        from transactions.templatetags.transaction_tags import hex_alpha

        self.assertEqual(hex_alpha('#6366f1', '20'), '#6366f120')
        self.assertEqual(hex_alpha('#6366f1', '50'), '#6366f150')
        self.assertEqual(hex_alpha('#FFF', '20'), '#FFF')
        self.assertEqual(hex_alpha('', '20'), '')
        self.assertEqual(hex_alpha(None), None)


