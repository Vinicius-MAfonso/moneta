from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from wallets.models import Account, CreditCard


class WalletValidationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='wallet_tester', password='password')

    def test_account_balance_cannot_be_negative(self):
        account = Account(user=self.user, name='Checking', type='checking', balance=-1)

        with self.assertRaises(ValidationError):
            account.full_clean()

    def test_credit_card_limits_cannot_be_negative(self):
        card = CreditCard(
            user=self.user,
            name='Visa',
            limit=-1,
            available_limit=-1,
            closing_day=10,
            due_day=20,
        )

        with self.assertRaises(ValidationError):
            card.full_clean()
