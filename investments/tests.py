from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from wallets.models import Account
from investments.models import Investment

User = get_user_model()


class InvestmentsAPITestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='investor', password='password123')
        self.client.force_login(self.user)
        self.account = Account.objects.create(user=self.user, name='Corretora Y', type=Account.Types.INVESTMENT)

    def test_investment_crud(self):
        payload = {
            'account': str(self.account.id),
            'name': 'PETR4',
            'type': Investment.Types.STOCK,
            'quantity': '100.00',
            'average_price': '30.50',
            'current_price': '35.00'
        }
        res = self.client.post('/api/investments/investments', data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 201)
        inv_id = res.json()['id']
        self.assertEqual(res.json()['name'], 'PETR4')

        res = self.client.get('/api/investments/investments')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 1)

        res = self.client.get(f'/api/investments/investments/{inv_id}')
        self.assertEqual(res.status_code, 200)

        update_payload = {**payload, 'current_price': '38.50'}
        res = self.client.put(f'/api/investments/investments/{inv_id}', data=update_payload, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['current_price'], '38.50')

        res = self.client.delete(f'/api/investments/investments/{inv_id}')
        self.assertEqual(res.status_code, 204)
        self.assertEqual(Investment.objects.filter(id=inv_id).count(), 0)
