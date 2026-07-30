from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from transactions.models import Category, Transaction
from wallets.models import Account


class TransactionValidationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='tester', password='password')
        self.category = Category.objects.create(user=self.user, name='Groceries', type=Category.types.EXPENSE)

    def test_transaction_requires_account_or_credit_card(self):
        transaction = Transaction(
            user=self.user,
            category=self.category,
            description='Lunch',
            amount='10.00',
            date='2026-01-01',
            type=Transaction.types.EXPENSE,
        )

        with self.assertRaises(ValidationError):
            transaction.full_clean()

    def test_installment_number_requires_total_installments(self):
        account = Account.objects.create(user=self.user, name='Checking', type='checking')
        transaction = Transaction(
            user=self.user,
            account=account,
            category=self.category,
            description='Lunch',
            amount='10.00',
            date='2026-01-01',
            type=Transaction.types.EXPENSE,
            installment_number=2,
        )

        with self.assertRaises(ValidationError):
            transaction.full_clean()

    def test_installment_number_cannot_exceed_total_installments(self):
        account = Account.objects.create(user=self.user, name='Checking', type='checking')
        transaction = Transaction(
            user=self.user,
            account=account,
            category=self.category,
            description='Lunch',
            amount='10.00',
            date='2026-01-01',
            type=Transaction.types.EXPENSE,
            installment_number=3,
            total_installments=2,
        )

        with self.assertRaises(ValidationError):
            transaction.full_clean()
