from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from wallets.models import Account, CreditCardDetails

User = get_user_model()


class WalletsWebTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.client.force_login(self.user)

    def test_account_web_crud(self):
        # List Accounts
        res = self.client.get('/wallets/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Contas & Cartões')

        # Create Checking Account
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

        # Confirm Delete view
        res = self.client.get(f'/wallets/{account.id}/confirm-delete/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Excluir Conta')

        # Delete Account
        res = self.client.post(f'/wallets/{account.id}/delete/')
        self.assertEqual(res.status_code, 302)
        self.assertFalse(Account.objects.filter(id=account.id).exists())
