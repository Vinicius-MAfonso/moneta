from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from wallets.models import Account, CreditCardDetails

User = get_user_model()


class WalletsAPITestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.client.force_login(self.user)

    def test_account_crud(self):
        # Create Account
        payload = {
            'name': 'Conta Principal',
            'type': Account.Types.CHECKING,
            'institution': 'Banco X',
            'balance': '1500.50',
            'color': '#123456',
            'active': True
        }
        res = self.client.post('/api/wallets/accounts', data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 201)
        account_id = res.json()['id']
        self.assertEqual(res.json()['name'], 'Conta Principal')

        # List Accounts
        res = self.client.get('/api/wallets/accounts')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 1)

        # Get Account
        res = self.client.get(f'/api/wallets/accounts/{account_id}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['id'], account_id)

        # Update Account
        update_payload = {**payload, 'name': 'Conta Atualizada'}
        res = self.client.put(f'/api/wallets/accounts/{account_id}', data=update_payload, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['name'], 'Conta Atualizada')

        # Delete Account
        res = self.client.delete(f'/api/wallets/accounts/{account_id}')
        self.assertEqual(res.status_code, 204)
        self.assertEqual(Account.objects.filter(id=account_id).count(), 0)

    def test_credit_card_details(self):
        account = Account.objects.create(
            user=self.user,
            name='Cartão Nubank',
            type=Account.Types.CREDIT_CARD,
            balance=Decimal('0.00')
        )
        cc_payload = {
            'limit': '5000.00',
            'available_limit': '4500.00',
            'closing_day': 5,
            'due_day': 12
        }
        # Create credit card details
        res = self.client.post(f'/api/wallets/accounts/{account.id}/credit-card', data=cc_payload, content_type='application/json')
        self.assertEqual(res.status_code, 201)

        # Get credit card details
        res = self.client.get(f'/api/wallets/accounts/{account.id}/credit-card')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['closing_day'], 5)

        # Delete credit card details
        res = self.client.delete(f'/api/wallets/accounts/{account.id}/credit-card')
        self.assertEqual(res.status_code, 204)
        self.assertEqual(CreditCardDetails.objects.filter(account=account).count(), 0)
